"""
Integration test for pipelines.digest - hits Postgres, yfinance, and Redis.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from stock_news.pipelines.digest import run_digest_pipeline
from stock_news.storage import redis_client
from stock_news.storage.models import (
    BenchmarkReturn,
    Company,
    DigestResult,
    PriceAnomaly,
    StockPrice,
)

pytestmark = pytest.mark.requires_env("REDIS_URL")

COMPANY_A_CIK = "9999999999"
COMPANY_B_CIK = "8888888888"
COMPANY_C_CIK = "7777777777"
COMPANY_A_TICKER = "AAA"
COMPANY_B_TICKER = "BBB"
COMPANY_C_TICKER = "CCC"

TEST_DATE = dt.date.today()


@pytest.fixture
def session(db_session):
    db_session.add_all(
        [
            Company(
                cik=COMPANY_A_CIK,
                ticker=COMPANY_A_TICKER,
                name="Company A",
                industry_segment="test",
            ),
            Company(
                cik=COMPANY_B_CIK,
                ticker=COMPANY_B_TICKER,
                name="Company B",
                industry_segment="test",
            ),
            Company(
                cik=COMPANY_C_CIK,
                ticker=COMPANY_C_TICKER,
                name="Company C",
                industry_segment="test",
            ),
        ]
    )
    db_session.add_all(
        [
            StockPrice(
                cik=COMPANY_A_CIK,
                date=TEST_DATE - dt.timedelta(days=1),
                open=100,
                high=100,
                low=100,
                close=100,
                volume=1000,
            ),
            StockPrice(
                cik=COMPANY_A_CIK,
                date=TEST_DATE,
                open=110,
                high=110,
                low=110,
                close=110,
                volume=1000,
            ),
            StockPrice(
                cik=COMPANY_B_CIK,
                date=TEST_DATE - dt.timedelta(days=1),
                open=100,
                high=100,
                low=100,
                close=100,
                volume=1000,
            ),
            StockPrice(
                cik=COMPANY_B_CIK,
                date=TEST_DATE,
                open=102,
                high=102,
                low=102,
                close=102,
                volume=1000,
            ),
            StockPrice(
                cik=COMPANY_C_CIK,
                date=TEST_DATE - dt.timedelta(days=1),
                open=100,
                high=100,
                low=100,
                close=100,
                volume=1000,
            ),
            StockPrice(
                cik=COMPANY_C_CIK,
                date=TEST_DATE,
                open=104,
                high=104,
                low=104,
                close=104,
                volume=1000,
            ),
        ]
    )
    db_session.add(
        PriceAnomaly(
            cik=COMPANY_A_CIK,
            date=TEST_DATE,
            return_pct=0.5,
            z_score=3.2,
            z_score_cross_sectional=None,
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
        select(DigestResult).where(DigestResult.cik == COMPANY_A_CIK)
    ).all()
    assert len(stored) == 1
    assert stored[0].return_pct is not None

    benchmarks = session.scalars(select(BenchmarkReturn)).all()
    assert {b.ticker for b in benchmarks} == {"SOXX", "SMH", "SPY"}

    cached = redis_client.read_digest(TEST_DATE)
    assert cached is not None
    assert any(c["cik"] == COMPANY_A_CIK for c in cached["companies"])
    redis_client._client().delete(redis_client._digest_key(TEST_DATE))

    anomaly = session.scalar(
        select(PriceAnomaly).where(
            PriceAnomaly.cik == COMPANY_A_CIK,
            PriceAnomaly.date == TEST_DATE,
        )
    )

    assert anomaly is not None
    assert anomaly.z_score_cross_sectional is not None
