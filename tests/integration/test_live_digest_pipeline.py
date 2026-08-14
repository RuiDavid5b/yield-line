"""
Integration test for pipelines.digest - hits Postgres, yfinance, and Redis.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from stock_news.pipelines.digest import run_digest_pipeline
from stock_news.storage import redis_client
from stock_news.storage.models import BenchmarkReturn, Company, DigestResult, StockPrice

pytestmark = pytest.mark.requires_env("REDIS_URL")

TEST_CIK = "0000320193"
TEST_TICKER = "AAPL"
TEST_DATE = dt.date.today()


@pytest.fixture
def session(db_session):
    db_session.add(
        Company(
            cik=TEST_CIK, ticker=TEST_TICKER, name="Apple Inc.", industry_segment="test"
        )
    )
    db_session.add(
        StockPrice(
            cik=TEST_CIK,
            date=TEST_DATE,
            open=100,
            high=101,
            low=99,
            close=100.5,
            volume=1000,
        )
    )
    db_session.add(
        StockPrice(
            cik=TEST_CIK,
            date=TEST_DATE - dt.timedelta(days=1),
            open=99,
            high=100,
            low=98,
            close=100.0,
            volume=1000,
        )
    )
    db_session.flush()
    yield db_session


def test_run_digest_pipeline_end_to_end(session):
    result = run_digest_pipeline(session, date=TEST_DATE)

    assert result.error is None
    assert result.digest_rows_upserted == result.companies_seen
    assert result.benchmark_rows_upserted == 3
    assert result.redis_written is True

    stored = session.scalars(
        select(DigestResult).where(DigestResult.cik == TEST_CIK)
    ).all()
    assert len(stored) == 1
    assert stored[0].return_pct is not None

    benchmarks = session.scalars(select(BenchmarkReturn)).all()
    assert {b.ticker for b in benchmarks} == {"SOXX", "SMH", "SPY"}

    cached = redis_client.read_digest(TEST_DATE)
    assert cached is not None
    assert any(c["cik"] == TEST_CIK for c in cached["companies"])
    redis_client._client().delete(redis_client._digest_key(TEST_DATE))
