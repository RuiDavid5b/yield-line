"""
Integration tests for storage.loader, hits a real Postgres database, not
mocked.

Skipped if DATABASE_URL isn't set.
"""

import datetime as dt
import os

import pytest
from sqlalchemy import select

from stock_news.processing.signals import ExtractedFilingSignal
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import (
    upsert_filing_signal,
    upsert_financial_metrics,
)
from stock_news.storage.models import Company, FilingSignal, FinancialMetric

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - skipping writer integration tests",
)

TEST_CIK = "9999999999"


@pytest.fixture
def session():
    session_factory = get_session_factory()
    with session_factory() as session:
        session.execute(Company.__table__.delete().where(Company.cik == TEST_CIK))
        session.add(
            Company(cik=TEST_CIK, ticker="TEST", name="Test Co", subarea="test")
        )
        session.commit()

        yield session

        session.execute(
            FinancialMetric.__table__.delete().where(FinancialMetric.cik == TEST_CIK)
        )
        session.execute(
            FilingSignal.__table__.delete().where(FilingSignal.cik == TEST_CIK)
        )
        session.execute(Company.__table__.delete().where(Company.cik == TEST_CIK))
        session.commit()


def _metric_row(**overrides):
    row = {
        "cik": TEST_CIK,
        "tag": "revenue",
        "period_start": dt.date(2026, 2, 1),
        "period_end": dt.date(2026, 4, 30),
        "period_type": "quarterly",
        "value": 100.0,
        "form": "10-Q",
        "accession_number": "0001-01",
        "filed_date": dt.date(2026, 5, 15),
    }
    row.update(overrides)
    return row


def test_upsert_financial_metrics_inserts_new_rows(session):
    upsert_financial_metrics(session, [_metric_row()])

    rows = session.scalars(
        select(FinancialMetric).where(FinancialMetric.cik == TEST_CIK)
    ).all()

    assert len(rows) == 1
    assert rows[0].value == 100.0


def test_upsert_financial_metrics_updates_on_conflict_not_duplicate(session):
    upsert_financial_metrics(session, [_metric_row(value=100.0)])
    upsert_financial_metrics(session, [_metric_row(value=105.0)])

    rows = session.scalars(
        select(FinancialMetric).where(FinancialMetric.cik == TEST_CIK)
    ).all()

    assert len(rows) == 1  # no duplicate row
    assert rows[0].value == 105.0  # value updated


def test_upsert_financial_metrics_empty_list_is_noop(session):
    upsert_financial_metrics(session, [])  # should not raise

    rows = session.scalars(
        select(FinancialMetric).where(FinancialMetric.cik == TEST_CIK)
    ).all()
    assert rows == []


def test_upsert_filing_signal_stores_extracted_content(session):
    extracted = ExtractedFilingSignal(
        guidance_commentary="Revenue expected to grow next quarter.",
        mentioned_customers=["Acme Corp"],
        mentioned_competitors=["Rival Inc"],
    )

    upsert_filing_signal(
        session,
        cik=TEST_CIK,
        accession_number="0002-02",
        form="10-Q",
        item_codes=[],
        filed_date=dt.date(2026, 5, 15),
        extracted=extracted,
    )

    row = session.scalars(
        select(FilingSignal).where(FilingSignal.cik == TEST_CIK)
    ).one()

    assert row.guidance_commentary == "Revenue expected to grow next quarter."
    assert row.mentioned_customers == ["Acme Corp"]
    assert row.mentioned_competitors == ["Rival Inc"]


def test_upsert_filing_signal_with_none_extracted_stores_empty_fields(session):
    upsert_filing_signal(
        session,
        cik=TEST_CIK,
        accession_number="0003-03",
        form="8-K",
        item_codes=["5.03"],
        filed_date=dt.date(2026, 5, 15),
        extracted=None,
    )

    row = session.scalars(
        select(FilingSignal).where(FilingSignal.cik == TEST_CIK)
    ).one()

    assert row.guidance_commentary is None
    assert row.mentioned_customers == []
    assert row.item_codes == ["5.03"]


def test_upsert_filing_signal_updates_on_conflict_not_duplicate(session):
    upsert_filing_signal(
        session,
        cik=TEST_CIK,
        accession_number="0004-04",
        form="8-K",
        item_codes=["2.02"],
        filed_date=dt.date(2026, 5, 15),
        extracted=ExtractedFilingSignal(guidance_commentary="First version."),
    )
    upsert_filing_signal(
        session,
        cik=TEST_CIK,
        accession_number="0004-04",
        form="8-K",
        item_codes=["2.02"],
        filed_date=dt.date(2026, 5, 15),
        extracted=ExtractedFilingSignal(guidance_commentary="Updated version."),
    )

    rows = session.scalars(
        select(FilingSignal).where(FilingSignal.cik == TEST_CIK)
    ).all()

    assert len(rows) == 1
    assert rows[0].guidance_commentary == "Updated version."
