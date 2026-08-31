"""
Integration tests for pipelines.prices.
Hits the yfinance API and postgres database.

Skipped if DATABASE_URL isn't set.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from stock_news.pipelines.stock_prices import run_price_pipeline
from stock_news.storage.models import Company, PriceAnomaly, StockPrice

TEST_CIK = "0000320193"
TEST_TICKER = "AAPL"


@pytest.fixture
def session(db_session):
    db_session.add(
        Company(
            cik=TEST_CIK, ticker=TEST_TICKER, name="Apple Inc.", industry_segment="test"
        )
    )
    db_session.flush()
    yield db_session


def test_run_price_pipeline_fetches_and_persists_real_prices(session):
    result = run_price_pipeline(
        cik=TEST_CIK, ticker=TEST_TICKER, session=session, period="5d"
    )

    assert result.error is None
    assert result.rows_fetched > 0
    assert result.rows_upserted == result.rows_fetched

    stored = session.scalars(select(StockPrice).where(StockPrice.cik == TEST_CIK)).all()
    assert len(stored) == result.rows_fetched


def test_run_price_pipeline_persists_detected_anomalies(session, monkeypatch):
    base_date = dt.date.today() - dt.timedelta(days=20)
    stable_closes = [150.0 * (1.001**i) for i in range(15)]
    for i, close in enumerate(stable_closes):
        session.add(
            StockPrice(
                cik=TEST_CIK,
                date=base_date + dt.timedelta(days=i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
            )
        )
    session.flush()

    result = run_price_pipeline(
        cik=TEST_CIK,
        ticker=TEST_TICKER,
        session=session,
        period="5d",
        anomaly_min_periods=10,
    )

    assert result.error is None
    stored = session.scalars(
        select(PriceAnomaly).where(PriceAnomaly.cik == TEST_CIK)
    ).all()
    assert len(stored) == len(result.anomalies)
    if result.anomalies:
        assert stored[0].z_score is not None
