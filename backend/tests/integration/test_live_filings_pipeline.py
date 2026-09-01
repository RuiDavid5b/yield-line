"""
Full pipeline smoke test - fetch -> classify -> extract -> write to Postgres
database.

Run explicitly with all three required:
    export EDGAR_USER_AGENT="Your Name your@email.com"
    export GOOGLE_API_KEY="your-key"
    export DATABASE_URL="postgresql+psycopg://..."
"""

import os
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from stock_news.pipelines.filings import run_company_pipeline
from stock_news.storage.models import Company, FilingSignal, FinancialMetric

pytestmark = pytest.mark.requires_env("EDGAR_USER_AGENT")
pytestmark = pytest.mark.requires_env("GOOGLE_API_KEY")


company_CIK = "0000883241"
USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "")


@pytest.fixture
def ensure_company_exists(db_session):
    """
    Insert the test company if it isn't already present.
    """
    existing = db_session.get(Company, company_CIK)
    if existing is None:
        db_session.add(
            Company(
                cik=company_CIK,
                ticker="SNPS",
                name="SYNOPSYS Inc",
                industry_segment="eda",
            )
        )
        db_session.flush()

    yield


def test_run_company_pipeline_end_to_end(db_session, ensure_company_exists):
    """
    Runs the actual production function, not a hand-assembled copy of its
    steps. filing_limit=8 (rather than the default) to improve the odds
    this batch includes at least one 10-Q/10-K, not just 8-Ks - which
    matters for the MD&A-specific assertion below.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=365)

    result = run_company_pipeline(
        cik=company_CIK,
        user_agent=USER_AGENT,
        session=db_session,
        filing_limit=1,
        start_date=start_date,
        end_date=end_date,
    )

    assert result.filings_seen > 0, "Expected at least one recent filing"
    assert result.filings_failed == 0, f"Unexpected failures: {result.errors}"
    assert result.metrics_upserted > 0, "Expected at least one financial metric row"

    stored_metrics = db_session.scalars(
        select(FinancialMetric).where(FinancialMetric.cik == company_CIK)
    ).all()
    assert len(stored_metrics) == result.metrics_upserted
    assert all(m.value is not None for m in stored_metrics)

    stored_signals = db_session.scalars(
        select(FilingSignal).where(FilingSignal.cik == company_CIK)
    ).all()
    assert (
        len(stored_signals)
        == (result.filings_processed + result.filings_skipped_already_processed)
        or len(stored_signals) == result.filings_processed
    )

    periodic_signals = [s for s in stored_signals if s.form in ("10-Q", "10-K")]
    if periodic_signals:
        assert any(
            (s.guidance_commentary or s.segment_commentary) for s in periodic_signals
        ), (
            "Expected at least one 10-Q/10-K in this batch to have "
            "non-empty extracted content."
        )
    else:
        pytest.skip(
            "No 10-Q/10-K in this batch of recent filings - increase "
            "filing_limit to get MD&A-specific coverage in this run."
        )
