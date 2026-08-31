"""
Tests for pipelines.prices.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pandas as pd

from stock_news.pipelines.stock_prices import run_price_pipeline


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
        assert result.error is not None
        assert "empty history" in result.error

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
    def test_start_and_end_date_passed_through_to_fetch(
        self, mock_fetch, mock_upsert, mock_get_history
    ):
        mock_fetch.return_value = _fake_history([100.0] * 15)
        mock_get_history.return_value = []

        run_price_pipeline(
            cik="0000320193",
            ticker="AAPL",
            session=MagicMock(),
            start_date=dt.date(2020, 1, 1),
            end_date=dt.date(2025, 1, 1),
        )

        mock_fetch.assert_called_once_with(
            "AAPL",
            period="5d",
            interval="1d",
            start_date=dt.date(2020, 1, 1),
            end_date=dt.date(2025, 1, 1),
        )

    @patch("stock_news.pipelines.stock_prices.get_stock_price_history")
    @patch("stock_news.pipelines.stock_prices.upsert_stock_prices")
    @patch("stock_news.pipelines.stock_prices.fetch_prices")
    def test_no_date_range_omits_start_end_and_uses_period(
        self, mock_fetch, mock_upsert, mock_get_history
    ):
        mock_fetch.return_value = _fake_history([100.0] * 15)
        mock_get_history.return_value = []

        run_price_pipeline(cik="0000320193", ticker="AAPL", session=MagicMock())

        mock_fetch.assert_called_once_with(
            "AAPL",
            period="5d",
            interval="1d",
            start_date=None,
            end_date=None,
        )

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
        closes.append(closes[-1] * 1.30)

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
