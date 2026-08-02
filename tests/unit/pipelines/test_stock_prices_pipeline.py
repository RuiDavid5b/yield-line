"""
Tests for pipelines.prices.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from stock_news.pipelines.stock_prices import run_price_pipeline
from stock_news.storage.db import get_session_factory
from stock_news.storage.models import Company, StockPrice


def _fake_history(
    closes: list[float], start: dt.date = dt.date(2025, 1, 1)
) -> pd.DataFrame:
    dates = [start + dt.timedelta(days=i) for i in range(len(closes))]
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(dates),
            "Open": closes,
            "High": [c * 1.01 for c in closes],
            "Low": [c * 0.99 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        }
    )


class TestRunPricePipelineUnit:
    @patch("stock_news.pipelines.stock_prices.get_stock_price_history")
    @patch("stock_news.pipelines.stock_prices.upsert_stock_prices")
    @patch("stock_news.pipelines.stock_prices.fetch_prices")
    def test_happy_path_upserts_and_flags_no_anomaly_on_flat_history(
        self, mock_fetch, mock_upsert, mock_get_history
    ):
        history = _fake_history([100.0] * 15)
        mock_fetch.return_value = history
        mock_get_history.return_value = [
            {
                "cik": "0000320193",
                "date": row["Date"].date(),
                "open": row["Open"],
                "high": row["High"],
                "low": row["Low"],
                "close": row["Close"],
                "volume": row["Volume"],
            }
            for _, row in history.iterrows()
        ]

        result = run_price_pipeline(
            cik="0000320193", ticker="AAPL", session=MagicMock()
        )

        assert result.error is None
        assert result.rows_fetched == 15
        assert result.rows_upserted == 15
        assert result.anomalies == []
        mock_upsert.assert_called_once()

    @patch("stock_news.pipelines.stock_prices.fetch_prices")
    def test_empty_history_short_circuits(self, mock_fetch):
        mock_fetch.return_value = pd.DataFrame()

        result = run_price_pipeline(
            cik="0000320193", ticker="AAPL", session=MagicMock()
        )

        assert result.rows_fetched == 0
        assert result.rows_upserted == 0
        assert result.error is None

    @patch("stock_news.pipelines.stock_prices.fetch_prices")
    def test_fetch_failure_captured_on_result_not_raised(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("rate limited")

        result = run_price_pipeline(
            cik="0000320193", ticker="AAPL", session=MagicMock()
        )

        assert result.error is not None
        assert "rate limited" in result.error
        assert result.rows_fetched == 0

    @patch("stock_news.pipelines.stock_prices.get_stock_price_history")
    @patch("stock_news.pipelines.stock_prices.upsert_stock_prices")
    @patch("stock_news.pipelines.stock_prices.fetch_prices")
    def test_upsert_failure_captured_and_skips_anomaly_detection(
        self, mock_fetch, mock_upsert, mock_get_history
    ):
        mock_fetch.return_value = _fake_history([100.0, 101.0])
        mock_upsert.side_effect = RuntimeError("db unavailable")

        result = run_price_pipeline(
            cik="0000320193", ticker="AAPL", session=MagicMock()
        )

        assert result.error is not None
        assert "db unavailable" in result.error
        assert result.rows_upserted == 0
        mock_get_history.assert_not_called()

    @patch("stock_news.pipelines.stock_prices.get_stock_price_history")
    @patch("stock_news.pipelines.stock_prices.upsert_stock_prices")
    @patch("stock_news.pipelines.stock_prices.fetch_prices")
    def test_anomaly_detected_flows_through_to_result(
        self, mock_fetch, mock_upsert, mock_get_history
    ):
        daily_multipliers = [1.002, 0.999, 1.001, 0.998, 1.003] * 3
        closes = [100.0]
        for m in daily_multipliers:
            closes.append(closes[-1] * m)
        closes.append(closes[-1] * 1.30)  # sharp spike on the last day

        history = _fake_history(closes)
        mock_fetch.return_value = history
        mock_get_history.return_value = [
            {
                "cik": "0000320193",
                "date": row["Date"].date(),
                "open": row["Open"],
                "high": row["High"],
                "low": row["Low"],
                "close": row["Close"],
                "volume": row["Volume"],
            }
            for _, row in history.iterrows()
        ]

        result = run_price_pipeline(
            cik="0000320193",
            ticker="AAPL",
            session=MagicMock(),
            anomaly_window=10,
            anomaly_min_periods=5,
            z_threshold=2.5,
        )

        assert len(result.anomalies) == 1
        assert result.anomalies[0]["date"] == history.iloc[-1]["Date"].date()


@pytest.mark.integration
class TestRunPricePipelineIntegration:
    """
    Hits the real yfinance API and the real configured Postgres DB.
    Cleans up its own rows afterward.
    """

    TEST_CIK = "0000320193"
    TEST_TICKER = "AAPL"

    @pytest.fixture(autouse=True)
    def _ensure_company_exists(self):
        session_factory = get_session_factory()
        with session_factory() as session:
            existing = session.get(Company, self.TEST_CIK)
            if existing is None:
                session.add(
                    Company(
                        cik=self.TEST_CIK,
                        ticker=self.TEST_TICKER,
                        name="Apple Inc.",
                        subarea="fabless",
                    )
                )
                session.commit()
        yield
        with session_factory() as session:
            session.query(StockPrice).filter(StockPrice.cik == self.TEST_CIK).delete()
            session.commit()

    def test_fetches_real_prices_and_persists_them(self):
        session_factory = get_session_factory()
        with session_factory() as session:
            result = run_price_pipeline(
                cik=self.TEST_CIK,
                ticker=self.TEST_TICKER,
                session=session,
                period="5d",
            )

        assert result.error is None
        assert result.rows_fetched > 0
        assert result.rows_upserted == result.rows_fetched

        with session_factory() as session:
            stored = (
                session.query(StockPrice).filter(StockPrice.cik == self.TEST_CIK).all()
            )
        assert len(stored) == result.rows_fetched
