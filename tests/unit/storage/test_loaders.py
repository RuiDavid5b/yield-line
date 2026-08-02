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
    get_stock_price_history,
    upsert_filing_signal,
    upsert_financial_metrics,
    upsert_stock_prices,
)
from stock_news.storage.models import Company, FilingSignal, FinancialMetric, StockPrice

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - skipping writer integration tests",
)

TEST_CIK = "9999999999"


@pytest.fixture
def session():
    session_factory = get_session_factory()
    with session_factory() as session:
        session.execute(
            FinancialMetric.__table__.delete().where(FinancialMetric.cik == TEST_CIK)
        )
        session.execute(
            FilingSignal.__table__.delete().where(FilingSignal.cik == TEST_CIK)
        )
        session.execute(StockPrice.__table__.delete().where(StockPrice.cik == TEST_CIK))
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
        session.execute(StockPrice.__table__.delete().where(StockPrice.cik == TEST_CIK))
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


def _price_row(**overrides):
    row = {
        "cik": TEST_CIK,
        "date": dt.date(2026, 5, 1),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1_000_000,
    }
    row.update(overrides)
    return row


def test_upsert_stock_prices_inserts_new_rows(session):
    upsert_stock_prices(session, [_price_row()])

    rows = session.scalars(select(StockPrice).where(StockPrice.cik == TEST_CIK)).all()

    assert len(rows) == 1
    assert rows[0].close == 100.5


def test_upsert_stock_prices_updates_on_conflict_not_duplicate(session):
    upsert_stock_prices(session, [_price_row(close=100.5)])
    upsert_stock_prices(session, [_price_row(close=110.0)])

    rows = session.scalars(select(StockPrice).where(StockPrice.cik == TEST_CIK)).all()

    assert len(rows) == 1  # no duplicate row
    assert rows[0].close == 110.0  # value updated


def test_upsert_stock_prices_multiple_dates_all_inserted(session):
    rows = [
        _price_row(date=dt.date(2026, 5, 1), close=100.0),
        _price_row(date=dt.date(2026, 5, 2), close=101.0),
        _price_row(date=dt.date(2026, 5, 3), close=99.5),
    ]
    upsert_stock_prices(session, rows)

    stored = session.scalars(select(StockPrice).where(StockPrice.cik == TEST_CIK)).all()

    assert len(stored) == 3


def test_upsert_stock_prices_empty_list_is_noop(session):
    upsert_stock_prices(session, [])  # should not raise

    rows = session.scalars(select(StockPrice).where(StockPrice.cik == TEST_CIK)).all()
    assert rows == []


def test_get_stock_price_history_returns_rows_as_dicts(session):
    upsert_stock_prices(
        session,
        [
            _price_row(date=dt.date(2026, 5, 1), close=100.0),
            _price_row(date=dt.date(2026, 5, 2), close=101.0),
        ],
    )

    history = get_stock_price_history(session, TEST_CIK)

    assert len(history) == 2
    assert all(isinstance(row, dict) for row in history)
    assert {row["date"] for row in history} == {
        dt.date(2026, 5, 1),
        dt.date(2026, 5, 2),
    }


def test_get_stock_price_history_only_returns_matching_cik(session):
    other_cik = "8888888888"
    session.add(Company(cik=other_cik, ticker="OTHR", name="Other Co", subarea="test"))
    session.commit()
    upsert_stock_prices(session, [_price_row(cik=other_cik)])
    upsert_stock_prices(session, [_price_row(cik=TEST_CIK)])

    history = get_stock_price_history(session, TEST_CIK)

    assert len(history) == 1
    assert history[0]["cik"] == TEST_CIK

    session.execute(StockPrice.__table__.delete().where(StockPrice.cik == other_cik))
    session.execute(Company.__table__.delete().where(Company.cik == other_cik))
    session.commit()


def test_get_stock_price_history_empty_for_unknown_cik(session):
    history = get_stock_price_history(session, TEST_CIK)
    assert history == []
