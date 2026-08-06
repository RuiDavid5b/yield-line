"""
Integration tests for pipelines.prices.
Hits the yfinance API and postgres database.

Skipped if DATABASE_URL isn't set.
"""

import pytest
from sqlalchemy import select

from stock_news.pipelines.stock_prices import run_price_pipeline
from stock_news.storage.models import Company, StockPrice

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
