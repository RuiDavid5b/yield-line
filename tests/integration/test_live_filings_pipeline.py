"""
Full pipeline smoke test - fetch -> classify -> extract -> write to Postgres
database.

Run explicitly with all three required:
    export EDGAR_USER_AGENT="Your Name your@email.com"
    export GROQ_API_KEY="your-key"
    export DATABASE_URL="postgresql+psycopg://..."
    pytest tests/test_live_pipeline.py -m live -v
"""

import os

import pytest
from sqlalchemy import select

from stock_news.pipelines.filings import run_company_pipeline
from stock_news.storage.db import get_session_factory
from stock_news.storage.models import Company, FilingSignal, FinancialMetric

pytestmark = pytest.mark.skipif(
    not (
        os.environ.get("EDGAR_USER_AGENT")
        and os.environ.get("GROQ_API_KEY")
        and os.environ.get("DATABASE_URL")
    ),
    reason=(
        "Requires EDGAR_USER_AGENT, GROQ_API_KEY, and DATABASE_URL all set - "
        "skipping full pipeline smoke test"
    ),
)

# A real company, used deliberately (not a synthetic CIK) - this test's
# entire point is confirming the chain works against real data.
company_CIK = "0000883241"
USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "")


@pytest.fixture
def session():
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session


@pytest.fixture
def ensure_company_exists(session):
    """
    Insert the test company if it isn't already present (e.g. from your
    seed graph load), and remember whether this test created it - only
    clean up the company row if this test was the one that added it, so
    a pre-existing company from your real graph is never deleted.
    """
    existing = session.get(Company, company_CIK)
    created_here = existing is None

    if created_here:
        session.add(
            Company(
                cik=company_CIK,
                ticker="SNPS",
                name="SYNOPSYS Inc",
                subarea="eda",
            )
        )
        session.commit()

    yield

    session.execute(
        FinancialMetric.__table__.delete().where(FinancialMetric.cik == company_CIK)
    )
    session.execute(
        FilingSignal.__table__.delete().where(FilingSignal.cik == company_CIK)
    )
    if created_here:
        session.execute(Company.__table__.delete().where(Company.cik == company_CIK))
    session.commit()


def test_run_company_pipeline_end_to_end(session, ensure_company_exists):
    """
    Runs the actual production function, not a hand-assembled copy of its
    steps. filing_limit=8 (rather than the default) to improve the odds
    this batch includes at least one 10-Q/10-K, not just 8-Ks - which
    matters for the MD&A-specific assertion below.
    """
    result = run_company_pipeline(
        cik=company_CIK,
        user_agent=USER_AGENT,
        session=session,
        filing_limit=8,
    )

    assert result.filings_seen > 0, "Expected at least one recent filing"
    assert result.filings_failed == 0, f"Unexpected failures: {result.errors}"
    assert result.metrics_upserted > 0, "Expected at least one financial metric row"

    stored_metrics = session.scalars(
        select(FinancialMetric).where(FinancialMetric.cik == company_CIK)
    ).all()
    assert len(stored_metrics) == result.metrics_upserted
    assert all(m.value is not None for m in stored_metrics)

    stored_signals = session.scalars(
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
