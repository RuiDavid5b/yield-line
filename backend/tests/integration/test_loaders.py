"""
Integration tests for storage.loader, hits a real Postgres database, not
mocked.

Skipped if DATABASE_URL isn't set.
"""

import datetime as dt

import pytest
from sqlalchemy import select

from stock_news.processing.edgar.signals import ExtractedFilingSignal
from stock_news.storage.loaders import (
    get_all_companies,
    get_benchmark_returns,
    get_digest_results,
    get_filing_signals,
    get_financial_metrics,
    get_latest_close_prices,
    get_latest_price_anomalies,
    get_news_articles,
    get_period_return,
    get_period_returns,
    get_price_anomalies,
    get_stock_price_history,
    get_unexplained_price_anomalies,
    set_price_anomaly_explanation,
    upsert_benchmark_returns,
    upsert_digest_results,
    upsert_filing_signal,
    upsert_financial_metrics,
    upsert_news_articles,
    upsert_price_anomalies,
    upsert_stock_prices,
)
from stock_news.storage.models import (
    BenchmarkReturn,
    Company,
    DigestResult,
    FilingSignal,
    FinancialMetric,
    NewsArticle,
    PriceAnomaly,
    StockPrice,
)

TEST_CIK = "9999999999"
SECONDARY_CIK = "8888888888"


@pytest.fixture
def session(db_session):
    db_session.add(
        Company(cik=TEST_CIK, ticker="TEST", name="Test Co", industry_segment="test")
    )
    db_session.flush()
    yield db_session


@pytest.fixture
def session_with_second_company(session):
    session.add(
        Company(
            cik=SECONDARY_CIK, ticker="OTHR", name="Other Co", industry_segment="test"
        )
    )
    session.flush()
    yield session


def _metric_row(**overrides):
    row = {
        "cik": TEST_CIK,
        "tag": "revenue",
        "period_start": dt.date(2026, 2, 1),
        "period_end": dt.date(2026, 4, 30),
        "period_type": "quarterly",
        "value": 100.0,
        "unit": "USD",
        "taxonomy": "us-gaap",
        "form": "10-Q",
        "accession_number": "0001-01",
        "filed_date": dt.date(2026, 5, 15),
    }
    row.update(overrides)
    return row


class TestGetFinancialMetrics:
    def test_returns_rows_as_dicts(self, session):
        session.add(FinancialMetric(**_metric_row()))
        session.flush()

        rows = get_financial_metrics(session, TEST_CIK)

        assert len(rows) == 1
        assert all(isinstance(r, dict) for r in rows)
        assert rows[0]["tag"] == "revenue"

    def test_empty_for_unknown_cik(self, session):
        assert get_financial_metrics(session, TEST_CIK) == []

    def test_no_tag_returns_all_metrics(self, session):
        session.add_all(
            [
                FinancialMetric(
                    **_metric_row(
                        tag="revenue",
                        period_end=dt.date(2026, 3, 31),
                        accession_number="0000320193-26-000001",
                    )
                ),
                FinancialMetric(
                    **_metric_row(
                        tag="Revenues",
                        period_end=dt.date(2026, 3, 31),
                        accession_number="0000320193-26-000002",
                    )
                ),
            ]
        )
        session.flush()

        rows = get_financial_metrics(session, TEST_CIK)

        assert {r["tag"] for r in rows} == {"revenue", "Revenues"}

    def test_tag_filter_narrows_to_one_metric(self, session):
        session.add_all(
            [
                FinancialMetric(
                    **_metric_row(
                        tag="revenue",
                        period_end=dt.date(2026, 3, 31),
                        accession_number="0000320193-26-000001",
                    )
                ),
                FinancialMetric(
                    **_metric_row(
                        tag="Revenues",
                        period_end=dt.date(2026, 3, 31),
                        accession_number="0000320193-26-000002",
                    )
                ),
            ]
        )
        session.flush()

        rows = get_financial_metrics(session, TEST_CIK, tag="Revenues")

        assert len(rows) == 1
        assert rows[0]["tag"] == "Revenues"

    def test_date_range_filters_on_period_end(self, session):
        session.add_all(
            [
                FinancialMetric(
                    **_metric_row(
                        period_end=dt.date(2025, 6, 30),
                        accession_number="0000320193-26-000001",
                    )
                ),
                FinancialMetric(
                    **_metric_row(
                        period_end=dt.date(2026, 3, 31),
                        accession_number="0000320193-26-000002",
                    )
                ),
            ]
        )
        session.flush()

        rows = get_financial_metrics(session, TEST_CIK, start_date=dt.date(2026, 1, 1))

        assert len(rows) == 1
        assert rows[0]["period_end"] == dt.date(2026, 3, 31)

    def test_ordered_most_recent_period_first(self, session):
        session.add_all(
            [
                FinancialMetric(
                    **_metric_row(
                        period_end=dt.date(2025, 9, 30),
                        accession_number="0000320193-26-000001",
                    )
                ),
                FinancialMetric(
                    **_metric_row(
                        period_end=dt.date(2026, 3, 31),
                        accession_number="0000320193-26-000002",
                    )
                ),
                FinancialMetric(
                    **_metric_row(
                        period_end=dt.date(2025, 12, 31),
                        accession_number="0000320193-26-000003",
                    )
                ),
            ]
        )
        session.flush()

        rows = get_financial_metrics(session, TEST_CIK)

        assert rows[0]["period_end"] == dt.date(2026, 3, 31)

    def test_limit_caps_result_count(self, session):
        session.add_all(
            [
                FinancialMetric(
                    **_metric_row(
                        period_end=dt.date(2026, i, 1),
                        accession_number=f"0000320193-26-00000{i}",
                    )
                )
                for i in range(1, 4)
            ]
        )
        session.flush()

        rows = get_financial_metrics(session, TEST_CIK, limit=2)

        assert len(rows) == 2


class TestUpsertFinancialMetrics:
    def test_upsert_financial_metrics_inserts_new_rows(self, session):
        upsert_financial_metrics(session, [_metric_row()])

        rows = session.scalars(
            select(FinancialMetric).where(FinancialMetric.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1
        assert rows[0].value == 100.0

    def test_upsert_financial_metrics_updates_on_conflict_not_duplicate(self, session):
        upsert_financial_metrics(session, [_metric_row(value=100.0)])
        upsert_financial_metrics(session, [_metric_row(value=105.0)])

        rows = session.scalars(
            select(FinancialMetric).where(FinancialMetric.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1  # no duplicate row
        assert rows[0].value == 105.0  # value updated

    def test_upsert_financial_metrics_empty_list_is_noop(self, session):
        upsert_financial_metrics(session, [])  # should not raise

        rows = session.scalars(
            select(FinancialMetric).where(FinancialMetric.cik == TEST_CIK)
        ).all()
        assert rows == []


class TestUpsertFilingSignal:
    def test_upsert_filing_signal_stores_extracted_content(self, session):
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

    def test_upsert_filing_signal_with_none_extracted_stores_empty_fields(
        self, session
    ):
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

    def test_upsert_filing_signal_updates_on_conflict_not_duplicate(self, session):
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


def _filing_signal_row(**overrides):
    row = {
        "cik": TEST_CIK,
        "accession_number": "0005-05",
        "form": "8-K",
        "item_codes": ["2.02"],
        "filed_date": dt.date(2026, 5, 1),
        "guidance_commentary": "Raised full-year guidance.",
        "segment_commentary": None,
        "executive_quote_summary": None,
        "mentioned_customers": [],
        "mentioned_competitors": [],
    }
    row.update(overrides)
    return row


class TestGetFilingSignals:
    def test_returns_rows_as_dicts(self, session):
        session.add(FilingSignal(**_filing_signal_row()))
        session.flush()

        rows = get_filing_signals(session, TEST_CIK)

        assert len(rows) == 1
        assert all(isinstance(r, dict) for r in rows)
        assert rows[0]["accession_number"] == "0005-05"

    def test_empty_for_unknown_cik(self, session):
        assert get_filing_signals(session, TEST_CIK) == []

    def test_ordered_most_recent_first(self, session):
        session.add_all(
            [
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0006-01", filed_date=dt.date(2026, 1, 15)
                    )
                ),
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0006-02", filed_date=dt.date(2026, 5, 1)
                    )
                ),
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0006-03", filed_date=dt.date(2026, 3, 1)
                    )
                ),
            ]
        )
        session.flush()

        rows = get_filing_signals(session, TEST_CIK)

        assert [r["filed_date"] for r in rows] == sorted(
            (r["filed_date"] for r in rows), reverse=True
        )
        assert rows[0]["accession_number"] == "0006-02"  # most recent

    def test_start_date_excludes_earlier_filings(self, session):
        session.add_all(
            [
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0007-01", filed_date=dt.date(2026, 1, 1)
                    )
                ),
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0007-02", filed_date=dt.date(2026, 6, 1)
                    )
                ),
            ]
        )
        session.flush()

        rows = get_filing_signals(session, TEST_CIK, start_date=dt.date(2026, 3, 1))

        assert len(rows) == 1
        assert rows[0]["accession_number"] == "0007-02"

    def test_end_date_excludes_later_filings(self, session):
        session.add_all(
            [
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0008-01", filed_date=dt.date(2026, 1, 1)
                    )
                ),
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0008-02", filed_date=dt.date(2026, 6, 1)
                    )
                ),
            ]
        )
        session.flush()

        rows = get_filing_signals(session, TEST_CIK, end_date=dt.date(2026, 3, 1))

        assert len(rows) == 1
        assert rows[0]["accession_number"] == "0008-01"

    def test_start_and_end_date_bound_a_range(self, session):
        session.add_all(
            [
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0009-01", filed_date=dt.date(2026, 1, 1)
                    )
                ),
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0009-02", filed_date=dt.date(2026, 3, 15)
                    )
                ),
                FilingSignal(
                    **_filing_signal_row(
                        accession_number="0009-03", filed_date=dt.date(2026, 6, 1)
                    )
                ),
            ]
        )
        session.flush()

        rows = get_filing_signals(
            session,
            TEST_CIK,
            start_date=dt.date(2026, 2, 1),
            end_date=dt.date(2026, 4, 1),
        )

        assert len(rows) == 1
        assert rows[0]["accession_number"] == "0009-02"

    def test_limit_caps_result_count(self, session):
        session.add_all(
            [
                FilingSignal(
                    **_filing_signal_row(
                        accession_number=f"0010-0{i}", filed_date=dt.date(2026, i, 1)
                    )
                )
                for i in range(1, 4)
            ]
        )
        session.flush()

        rows = get_filing_signals(session, TEST_CIK, limit=2)

        assert len(rows) == 2

    def test_includes_extraction_fields(self, session):
        session.add(
            FilingSignal(
                **_filing_signal_row(
                    mentioned_customers=["Acme Corp"],
                    mentioned_competitors=["Rival Inc"],
                )
            )
        )
        session.flush()

        row = get_filing_signals(session, TEST_CIK)[0]

        assert row["mentioned_customers"] == ["Acme Corp"]
        assert row["mentioned_competitors"] == ["Rival Inc"]

    def test_only_returns_matching_cik(self, session_with_second_company):
        session = session_with_second_company
        session.add(
            FilingSignal(
                **_filing_signal_row(cik=SECONDARY_CIK, accession_number="0011-01")
            )
        )
        session.add(
            FilingSignal(**_filing_signal_row(cik=TEST_CIK, accession_number="0011-02"))
        )
        session.flush()

        rows = get_filing_signals(session, TEST_CIK)

        assert len(rows) == 1
        assert rows[0]["accession_number"] == "0011-02"


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


class TestUpsertStockPrices:
    def test_upsert_stock_prices_inserts_new_rows(self, session):
        upsert_stock_prices(session, [_price_row()])

        rows = session.scalars(
            select(StockPrice).where(StockPrice.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1
        assert rows[0].close == 100.5

    def test_upsert_stock_prices_updates_on_conflict_not_duplicate(self, session):
        upsert_stock_prices(session, [_price_row(close=100.5)])
        upsert_stock_prices(session, [_price_row(close=110.0)])

        rows = session.scalars(
            select(StockPrice).where(StockPrice.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1  # no duplicate row
        assert rows[0].close == 110.0  # value updated

    def test_upsert_stock_prices_multiple_dates_all_inserted(self, session):
        rows = [
            _price_row(date=dt.date(2026, 5, 1), close=100.0),
            _price_row(date=dt.date(2026, 5, 2), close=101.0),
            _price_row(date=dt.date(2026, 5, 3), close=99.5),
        ]
        upsert_stock_prices(session, rows)

        stored = session.scalars(
            select(StockPrice).where(StockPrice.cik == TEST_CIK)
        ).all()

        assert len(stored) == 3

    def test_upsert_stock_prices_empty_list_is_noop(self, session):
        upsert_stock_prices(session, [])  # should not raise

        rows = session.scalars(
            select(StockPrice).where(StockPrice.cik == TEST_CIK)
        ).all()
        assert rows == []


class TestGetStockPriceHistory:
    def test_get_stock_price_history_returns_rows_as_dicts(self, session):
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

    def test_get_stock_price_history_only_returns_matching_cik(
        self, session_with_second_company
    ):
        session = session_with_second_company
        upsert_stock_prices(session, [_price_row(cik=SECONDARY_CIK)])
        upsert_stock_prices(session, [_price_row(cik=TEST_CIK)])

        upsert_stock_prices(session, [_price_row(cik=SECONDARY_CIK)])
        upsert_stock_prices(session, [_price_row(cik=TEST_CIK)])

        history = get_stock_price_history(session, TEST_CIK)

        assert len(history) == 1
        assert history[0]["cik"] == TEST_CIK

    def test_get_stock_price_history_empty_for_unknown_cik(self, session):
        history = get_stock_price_history(session, TEST_CIK)
        assert history == []


class TestGetStockPriceHistoryRangeFiltering:
    def test_no_range_returns_everything(self, session):
        session.add_all(
            [
                StockPrice(
                    cik=TEST_CIK,
                    date=dt.date(2020, 1, 1),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
                StockPrice(
                    cik=TEST_CIK,
                    date=dt.date(2026, 1, 1),
                    open=2,
                    high=2,
                    low=2,
                    close=2,
                    volume=1,
                ),
            ]
        )
        session.flush()

        rows = get_stock_price_history(session, TEST_CIK)

        assert len(rows) == 2

    def test_range_narrows_results(self, session):
        session.add_all(
            [
                StockPrice(
                    cik=TEST_CIK,
                    date=dt.date(2020, 1, 1),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
                StockPrice(
                    cik=TEST_CIK,
                    date=dt.date(2026, 1, 1),
                    open=2,
                    high=2,
                    low=2,
                    close=2,
                    volume=1,
                ),
            ]
        )
        session.flush()

        rows = get_stock_price_history(
            session, TEST_CIK, start_date=dt.date(2025, 1, 1)
        )

        assert len(rows) == 1
        assert rows[0]["date"] == dt.date(2026, 1, 1)

    def test_results_ordered_by_date_ascending(self, session):
        session.add_all(
            [
                StockPrice(
                    cik=TEST_CIK,
                    date=dt.date(2026, 3, 1),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
                StockPrice(
                    cik=TEST_CIK,
                    date=dt.date(2026, 1, 1),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
            ]
        )
        session.flush()

        rows = get_stock_price_history(session, TEST_CIK)

        assert [r["date"] for r in rows] == sorted(r["date"] for r in rows)


class TestGetPeriodReturn:
    def test_computes_return_between_boundaries(self, session):
        upsert_stock_prices(
            session,
            [
                _price_row(cik=TEST_CIK, date=dt.date(2026, 1, 1), close=100.0),
                _price_row(cik=TEST_CIK, date=dt.date(2026, 6, 1), close=120.0),
            ],
        )
        session.flush()

        result = get_period_return(
            session, TEST_CIK, dt.date(2026, 1, 1), dt.date(2026, 6, 1)
        )

        assert result == pytest.approx(0.20)

    def test_falls_back_to_nearest_prior_close_on_weekend_gap(self, session):
        upsert_stock_prices(
            session,
            [
                _price_row(
                    cik=TEST_CIK, date=dt.date(2026, 1, 2), close=100.0
                ),  # Friday
                _price_row(cik=TEST_CIK, date=dt.date(2026, 6, 1), close=110.0),
            ],
        )
        session.flush()

        result = get_period_return(
            session, TEST_CIK, dt.date(2026, 1, 4), dt.date(2026, 6, 1)
        )

        assert result == pytest.approx(0.10)

    def test_no_data_before_start_date_returns_none(self, session):
        upsert_stock_prices(
            session, [_price_row(cik=TEST_CIK, date=dt.date(2026, 6, 1), close=100.0)]
        )
        session.flush()

        result = get_period_return(
            session, TEST_CIK, dt.date(2025, 1, 1), dt.date(2026, 6, 1)
        )

        assert result is None

    def test_no_data_at_all_returns_none(self, session):
        assert (
            get_period_return(
                session, TEST_CIK, dt.date(2026, 1, 1), dt.date(2026, 6, 1)
            )
            is None
        )

    def test_zero_start_close_returns_none(self, session):
        upsert_stock_prices(
            session,
            [
                _price_row(cik=TEST_CIK, date=dt.date(2026, 1, 1), close=0.0),
                _price_row(cik=TEST_CIK, date=dt.date(2026, 6, 1), close=50.0),
            ],
        )
        session.flush()

        assert (
            get_period_return(
                session, TEST_CIK, dt.date(2026, 1, 1), dt.date(2026, 6, 1)
            )
            is None
        )


class TestGetPeriodReturns:
    def test_returns_keyed_by_cik_for_all_companies(self, session):
        upsert_stock_prices(
            session,
            [
                _price_row(cik=TEST_CIK, date=dt.date(2026, 1, 1), close=100.0),
                _price_row(cik=TEST_CIK, date=dt.date(2026, 6, 1), close=110.0),
            ],
        )
        session.flush()

        result = get_period_returns(session, dt.date(2026, 1, 1), dt.date(2026, 6, 1))

        assert TEST_CIK in result
        assert result[TEST_CIK] == pytest.approx(0.10)

    def test_company_with_no_data_maps_to_none_not_omitted(self, session):
        result = get_period_returns(session, dt.date(2026, 1, 1), dt.date(2026, 6, 1))

        assert TEST_CIK in result
        assert result[TEST_CIK] is None


class TestGetLatestClosePrices:
    def test_returns_most_recent_close_per_company(self, session):
        upsert_stock_prices(
            session,
            [
                _price_row(
                    cik=TEST_CIK,
                    date=dt.date.today() - dt.timedelta(days=1),
                    close=100.0,
                ),
                _price_row(cik=TEST_CIK, date=dt.date.today(), close=105.0),
            ],
        )
        session.flush()

        result = get_latest_close_prices(session)

        assert result[TEST_CIK] == pytest.approx(105.0)

    def test_company_with_no_prices_maps_to_none(self, session):
        result = get_latest_close_prices(session)
        assert result[TEST_CIK] is None


def _news_row(**overrides):
    row = {
        "cik": TEST_CIK,
        "url": "https://example.com/test-article",
        "title": "Test headline",
        "description": "Test description.",
        "author": "Test Author",
        "published_at": dt.datetime(2026, 5, 1, 12, 0, 0),
    }
    row.update(overrides)
    return row


class TestUpsertNewsArticles:
    def test_upsert_news_articles_inserts_new_rows(self, session):
        upsert_news_articles(session, [_news_row()])

        rows = session.scalars(
            select(NewsArticle).where(NewsArticle.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1
        assert rows[0].title == "Test headline"

    def test_upsert_news_articles_updates_on_conflict_not_duplicate(self, session):
        upsert_news_articles(session, [_news_row(title="Original title")])
        upsert_news_articles(session, [_news_row(title="Updated title")])

        rows = session.scalars(
            select(NewsArticle).where(NewsArticle.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1  # no duplicate row
        assert rows[0].title == "Updated title"

    def test_upsert_news_articles_different_urls_both_inserted(self, session):
        rows = [
            _news_row(url="https://example.com/article-1"),
            _news_row(url="https://example.com/article-2"),
        ]
        upsert_news_articles(session, rows)

        stored = session.scalars(
            select(NewsArticle).where(NewsArticle.cik == TEST_CIK)
        ).all()

        assert len(stored) == 2

    def test_upsert_news_articles_empty_list_is_noop(self, session):
        upsert_news_articles(session, [])  # should not raise

        rows = session.scalars(
            select(NewsArticle).where(NewsArticle.cik == TEST_CIK)
        ).all()
        assert rows == []

    def test_upsert_news_articles_nullable_fields_stored_as_none(self, session):
        upsert_news_articles(
            session,
            [_news_row(description=None, author=None, published_at=None)],
        )

        row = session.scalars(
            select(NewsArticle).where(NewsArticle.cik == TEST_CIK)
        ).one()

        assert row.description is None
        assert row.author is None
        assert row.published_at is None


class TestGetNewsArticles:
    def test_get_news_articles_returns_rows_as_dicts(self, session):
        upsert_news_articles(
            session,
            [
                _news_row(url="https://example.com/article-1"),
                _news_row(url="https://example.com/article-2"),
            ],
        )

        articles = get_news_articles(session, TEST_CIK)

        assert len(articles) == 2
        assert all(isinstance(a, dict) for a in articles)

    def test_get_news_articles_empty_for_unknown_cik(self, session):
        articles = get_news_articles(session, TEST_CIK)
        assert articles == []

    def test_start_date_excludes_earlier_articles(self, session):
        upsert_news_articles(
            session,
            [
                _news_row(
                    url="https://example.com/old", published_at=dt.datetime(2026, 1, 1)
                ),
                _news_row(
                    url="https://example.com/new", published_at=dt.datetime(2026, 6, 1)
                ),
            ],
        )

        rows = get_news_articles(session, TEST_CIK, start_date=dt.datetime(2026, 3, 1))

        assert len(rows) == 1
        assert rows[0]["url"] == "https://example.com/new"

    def test_end_date_excludes_later_articles(self, session):
        upsert_news_articles(
            session,
            [
                _news_row(
                    url="https://example.com/old", published_at=dt.datetime(2026, 1, 1)
                ),
                _news_row(
                    url="https://example.com/new", published_at=dt.datetime(2026, 6, 1)
                ),
            ],
        )

        rows = get_news_articles(session, TEST_CIK, end_date=dt.datetime(2026, 3, 1))

        assert len(rows) == 1
        assert rows[0]["url"] == "https://example.com/old"

    def test_limit_caps_result_count(self, session):
        upsert_news_articles(
            session,
            [_news_row(url=f"https://example.com/article-{i}") for i in range(5)],
        )

        rows = get_news_articles(session, TEST_CIK, limit=3)

        assert len(rows) == 3

    def test_ordered_most_recent_first(self, session):
        upsert_news_articles(
            session,
            [
                _news_row(
                    url="https://example.com/a", published_at=dt.datetime(2026, 1, 1)
                ),
                _news_row(
                    url="https://example.com/b", published_at=dt.datetime(2026, 6, 1)
                ),
                _news_row(
                    url="https://example.com/c", published_at=dt.datetime(2026, 3, 1)
                ),
            ],
        )

        rows = get_news_articles(session, TEST_CIK)

        assert rows[0]["url"] == "https://example.com/b"  # most recent first

    def test_null_published_at_excluded_by_date_filter(self, session):
        # A row with no published_at can't satisfy a >= comparison in SQL
        # (NULL comparisons are neither true nor false) - an article with
        # an unparseable date (_parse_published_at returning None) silently
        # vanishes from any date-bounded query, though it still appears in
        # the unfiltered get_news_articles(session, cik) call.
        upsert_news_articles(
            session,
            [
                _news_row(url="https://example.com/undated", published_at=None),
                _news_row(
                    url="https://example.com/dated",
                    published_at=dt.datetime(2026, 6, 1),
                ),
            ],
        )

        rows = get_news_articles(session, TEST_CIK, start_date=dt.datetime(2026, 1, 1))

        assert len(rows) == 1
        assert rows[0]["url"] == "https://example.com/dated"


class TestGetAllCompanies:
    def test_get_all_companies_returns_rows_as_dicts(self, session):
        companies = get_all_companies(session)

        assert len(companies) > 0
        assert all(isinstance(c, dict) for c in companies)

    def test_get_all_companies_returns_expected_fields(self, session):
        companies = get_all_companies(session)

        row = next(c for c in companies if c["cik"] == TEST_CIK)
        assert row["ticker"] == "TEST"
        assert row["name"] == "Test Co"
        assert row["industry_segment"] == "test"
        assert row["reporting_currency"] == "USD"

    def test_get_all_companies_includes_aliases_and_disambiguation(self, session):
        companies = get_all_companies(session)

        row = next(c for c in companies if c["cik"] == TEST_CIK)
        assert isinstance(row["aliases"], list)
        assert isinstance(row["news_disambiguation"], list)

    def test_get_all_companies_includes_seeded_company(self, session):
        ciks = {c["cik"] for c in get_all_companies(session)}
        assert TEST_CIK in ciks

    def test_get_all_companies_reflects_new_insert(self, session_with_second_company):
        companies = {c["cik"] for c in get_all_companies(session_with_second_company)}
        assert companies == {TEST_CIK, SECONDARY_CIK}


def _digest_row(**overrides):
    row = {
        "cik": TEST_CIK,
        "date": dt.date(2026, 5, 1),
        "return_pct": 0.02,
        "peer_avg_return_pct": 0.015,
        "vs_peer_avg": 0.005,
        "vs_soxx": 0.01,
        "vs_smh": 0.008,
        "vs_spy": None,
    }
    row.update(overrides)
    return row


class TestUpsertDigestResults:
    def test_upsert_digest_results_inserts_new_rows(self, session):
        upsert_digest_results(session, [_digest_row()])

        rows = session.scalars(
            select(DigestResult).where(DigestResult.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1
        assert float(rows[0].return_pct) == pytest.approx(0.02)

    def test_upsert_digest_results_updates_on_conflict_not_duplicate(self, session):
        upsert_digest_results(session, [_digest_row(return_pct=0.02)])
        upsert_digest_results(session, [_digest_row(return_pct=0.05)])

        rows = session.scalars(
            select(DigestResult).where(DigestResult.cik == TEST_CIK)
        ).all()

        assert len(rows) == 1
        assert float(rows[0].return_pct) == pytest.approx(0.05)

    def test_upsert_digest_results_multiple_dates_all_inserted(self, session):
        rows = [
            _digest_row(date=dt.date(2026, 5, 1)),
            _digest_row(date=dt.date(2026, 5, 2)),
            _digest_row(date=dt.date(2026, 5, 3)),
        ]
        upsert_digest_results(session, rows)

        stored = session.scalars(
            select(DigestResult).where(DigestResult.cik == TEST_CIK)
        ).all()

        assert len(stored) == 3

    def test_upsert_digest_results_empty_list_is_noop(self, session):
        upsert_digest_results(session, [])  # should not raise

        rows = session.scalars(
            select(DigestResult).where(DigestResult.cik == TEST_CIK)
        ).all()
        assert rows == []

    def test_upsert_digest_results_stores_none_fields(self, session):
        upsert_digest_results(
            session,
            [
                _digest_row(
                    return_pct=None,
                    peer_avg_return_pct=None,
                    vs_peer_avg=None,
                    vs_soxx=None,
                    vs_smh=None,
                    vs_spy=None,
                )
            ],
        )

        row = session.scalars(
            select(DigestResult).where(DigestResult.cik == TEST_CIK)
        ).one()

        assert row.return_pct is None
        assert row.peer_avg_return_pct is None
        assert row.vs_peer_avg is None


class TestGetDigestResults:
    def test_get_digest_results_returns_rows_as_dicts(self, session):
        upsert_digest_results(session, [_digest_row(date=dt.date(2026, 5, 1))])

        results = get_digest_results(session, dt.date(2026, 5, 1))

        assert len(results) == 1
        assert isinstance(results[0], dict)
        assert results[0]["cik"] == TEST_CIK
        assert isinstance(results[0]["return_pct"], float)

    def test_get_digest_results_only_returns_matching_date(self, session):
        upsert_digest_results(
            session,
            [
                _digest_row(date=dt.date(2026, 5, 1), return_pct=0.01),
                _digest_row(date=dt.date(2026, 5, 2), return_pct=0.02),
            ],
        )

        results = get_digest_results(session, dt.date(2026, 5, 1))

        assert len(results) == 1
        assert results[0]["return_pct"] == pytest.approx(0.01)

    def test_get_digest_results_empty_for_unknown_date(self, session):
        results = get_digest_results(session, dt.date(2099, 1, 1))
        assert results == []


def _benchmark_row(**overrides):
    row = {
        "ticker": "SOXX",
        "date": dt.date(2026, 5, 1),
        "return_pct": 0.01,
    }
    row.update(overrides)
    return row


class TestUpsertBenchmarkReturns:
    def test_upsert_benchmark_returns_inserts_new_rows(self, session):
        upsert_benchmark_returns(session, [_benchmark_row()])

        rows = session.scalars(
            select(BenchmarkReturn).where(BenchmarkReturn.ticker == "SOXX")
        ).all()

        assert len(rows) == 1
        assert float(rows[0].return_pct) == pytest.approx(0.01)

    def test_upsert_benchmark_returns_updates_on_conflict_not_duplicate(self, session):
        upsert_benchmark_returns(session, [_benchmark_row(return_pct=0.01)])
        upsert_benchmark_returns(session, [_benchmark_row(return_pct=0.03)])

        rows = session.scalars(
            select(BenchmarkReturn).where(BenchmarkReturn.ticker == "SOXX")
        ).all()

        assert len(rows) == 1
        assert float(rows[0].return_pct) == pytest.approx(0.03)

    def test_upsert_benchmark_returns_multiple_tickers_all_inserted(self, session):
        rows = [
            _benchmark_row(ticker="SOXX", return_pct=0.01),
            _benchmark_row(ticker="SMH", return_pct=0.012),
            _benchmark_row(ticker="SPY", return_pct=0.005),
        ]
        upsert_benchmark_returns(session, rows)

        stored = session.scalars(
            select(BenchmarkReturn).where(BenchmarkReturn.date == dt.date(2026, 5, 1))
        ).all()

        assert len(stored) == 3

    def test_upsert_benchmark_returns_empty_list_is_noop(self, session):
        upsert_benchmark_returns(session, [])

        rows = session.scalars(
            select(BenchmarkReturn).where(BenchmarkReturn.ticker == "SOXX")
        ).all()
        assert rows == []

    def test_upsert_benchmark_returns_stores_none(self, session):
        upsert_benchmark_returns(session, [_benchmark_row(return_pct=None)])

        row = session.scalars(
            select(BenchmarkReturn).where(BenchmarkReturn.ticker == "SOXX")
        ).one()

        assert row.return_pct is None


class TestGetBenchmarkReturns:
    def test_get_benchmark_returns_returns_ticker_dict(self, session):
        upsert_benchmark_returns(
            session,
            [
                _benchmark_row(ticker="SOXX", return_pct=0.01),
                _benchmark_row(ticker="SMH", return_pct=0.012),
            ],
        )

        results = get_benchmark_returns(session, dt.date(2026, 5, 1))

        assert results["SOXX"] == pytest.approx(0.01)
        assert results["SMH"] == pytest.approx(0.012)
        assert isinstance(results["SOXX"], float)

    def test_get_benchmark_returns_only_returns_matching_date(self, session):
        upsert_benchmark_returns(
            session,
            [
                _benchmark_row(ticker="SOXX", date=dt.date(2026, 5, 1)),
                _benchmark_row(ticker="SOXX", date=dt.date(2026, 5, 2)),
            ],
        )

        results = get_benchmark_returns(session, dt.date(2026, 5, 2))

        assert set(results) == {"SOXX"}

    def test_get_benchmark_returns_empty_for_unknown_date(self, session):
        results = get_benchmark_returns(session, dt.date(2099, 1, 1))
        assert results == {}


def _anomaly_row(**overrides):
    row = {
        "cik": TEST_CIK,
        "date": dt.date(2026, 5, 1),
        "return_pct": 0.15,
        "z_score": 3.2,
    }
    row.update(overrides)
    return row


class TestGetPriceAnomalies:
    def test_returns_rows_as_dicts(self, session):
        session.add(PriceAnomaly(**_anomaly_row()))
        session.flush()

        rows = get_price_anomalies(session, TEST_CIK)

        assert len(rows) == 1
        assert all(isinstance(r, dict) for r in rows)
        assert float(rows[0]["return_pct"]) == pytest.approx(0.15)

    def test_empty_for_unknown_cik(self, session):
        assert get_price_anomalies(session, TEST_CIK) == []

    def test_ordered_most_recent_first(self, session):
        session.add_all(
            [
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 1, 15))),
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 5, 1))),
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 3, 1))),
            ]
        )
        session.flush()

        rows = get_price_anomalies(session, TEST_CIK)

        assert [r["date"] for r in rows] == sorted(
            (r["date"] for r in rows), reverse=True
        )
        assert rows[0]["date"] == dt.date(2026, 5, 1)

    def test_start_date_excludes_earlier_anomalies(self, session):
        session.add_all(
            [
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 1, 1))),
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 6, 1))),
            ]
        )
        session.flush()

        rows = get_price_anomalies(session, TEST_CIK, start_date=dt.date(2026, 3, 1))

        assert len(rows) == 1
        assert rows[0]["date"] == dt.date(2026, 6, 1)

    def test_end_date_excludes_later_anomalies(self, session):
        session.add_all(
            [
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 1, 1))),
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 6, 1))),
            ]
        )
        session.flush()

        rows = get_price_anomalies(session, TEST_CIK, end_date=dt.date(2026, 3, 1))

        assert len(rows) == 1
        assert rows[0]["date"] == dt.date(2026, 1, 1)

    def test_start_and_end_date_bound_a_range(self, session):
        session.add_all(
            [
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 1, 1))),
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 3, 15))),
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, 6, 1))),
            ]
        )
        session.flush()

        rows = get_price_anomalies(
            session,
            TEST_CIK,
            start_date=dt.date(2026, 2, 1),
            end_date=dt.date(2026, 4, 1),
        )

        assert len(rows) == 1
        assert rows[0]["date"] == dt.date(2026, 3, 15)

    def test_limit_caps_result_count(self, session):
        session.add_all(
            [
                PriceAnomaly(**_anomaly_row(date=dt.date(2026, i, 1)))
                for i in range(1, 4)
            ]
        )
        session.flush()

        rows = get_price_anomalies(session, TEST_CIK, limit=2)

        assert len(rows) == 2

    def test_returns_z_score(self, session):
        session.add(PriceAnomaly(**_anomaly_row(z_score=4.1)))
        session.flush()

        rows = get_price_anomalies(session, TEST_CIK)

        assert float(rows[0]["z_score"]) == pytest.approx(4.1)

    def test_scoped_to_requested_cik_only(self, session_with_second_company):
        session = session_with_second_company
        session.add_all(
            [
                PriceAnomaly(**_anomaly_row(cik=TEST_CIK)),
                PriceAnomaly(
                    **_anomaly_row(cik=SECONDARY_CIK, date=dt.date(2026, 5, 1))
                ),
            ]
        )
        session.flush()

        rows = get_price_anomalies(session, TEST_CIK)

        assert all(r["cik"] == TEST_CIK for r in rows)


class TestUpsertPriceAnomalies:
    def test_upsert_anomalies_inserts_new_row(self, session):
        upsert_price_anomalies(
            session,
            [
                {
                    "cik": TEST_CIK,
                    "date": dt.date(2026, 5, 1),
                    "return_pct": 0.08,
                    "z_score": 3.1,
                }
            ],
        )

        stored = session.scalars(
            select(PriceAnomaly).where(PriceAnomaly.cik == TEST_CIK)
        ).all()
        assert len(stored) == 1
        assert float(stored[0].z_score) == pytest.approx(3.1)

    def test_upsert_anomalies_updates_on_conflict(self, session):
        upsert_price_anomalies(
            session,
            [
                {
                    "cik": TEST_CIK,
                    "date": dt.date(2026, 5, 1),
                    "return_pct": 0.08,
                    "z_score": 3.1,
                }
            ],
        )

        session.flush()

        upsert_price_anomalies(
            session,
            [
                {
                    "cik": TEST_CIK,
                    "date": dt.date(2026, 5, 1),
                    "return_pct": 0.12,
                    "z_score": 4.5,
                }
            ],
        )

        stored = session.scalars(
            select(PriceAnomaly).where(PriceAnomaly.cik == TEST_CIK)
        ).all()
        assert len(stored) == 1
        assert float(stored[0].z_score) == pytest.approx(4.5)

    def test_upsert_anomalies_empty_rows_is_noop(self, session):
        upsert_price_anomalies(session, [])

        stored = session.scalars(
            select(PriceAnomaly).where(PriceAnomaly.cik == TEST_CIK)
        ).all()
        assert stored == []


class TestGetUnexplainedPriceAnomalies:
    def test_returns_anomaly_with_no_explanation(self, session):
        session.add(PriceAnomaly(**_anomaly_row(date=dt.date.today())))
        session.flush()

        rows = get_unexplained_price_anomalies(session)

        assert len(rows) == 1
        assert rows[0]["cik"] == TEST_CIK

    def test_excludes_already_explained_anomaly(self, session):
        session.add(
            PriceAnomaly(
                **_anomaly_row(date=dt.date.today()),
                explanation="Already explained.",
                explained_at=dt.datetime.now(),
            )
        )
        session.flush()

        assert get_unexplained_price_anomalies(session) == []

    def test_excludes_anomaly_older_than_max_age_days(self, session):
        old_date = dt.date.today() - dt.timedelta(days=10)
        session.add(PriceAnomaly(**_anomaly_row(date=old_date)))
        session.flush()

        rows = get_unexplained_price_anomalies(session, max_age_days=7)

        assert rows == []

    def test_includes_anomaly_within_max_age_days(self, session):
        recent_date = dt.date.today() - dt.timedelta(days=5)
        session.add(PriceAnomaly(**_anomaly_row(date=recent_date)))
        session.flush()

        rows = get_unexplained_price_anomalies(session, max_age_days=7)

        assert len(rows) == 1

    def test_boundary_date_exactly_at_cutoff_is_included(self, session):
        boundary_date = dt.date.today() - dt.timedelta(days=7)
        session.add(PriceAnomaly(**_anomaly_row(date=boundary_date)))
        session.flush()

        rows = get_unexplained_price_anomalies(session, max_age_days=7)

        assert len(rows) == 1

    def test_ordered_most_recent_first(self, session):
        session.add_all(
            [
                PriceAnomaly(
                    **_anomaly_row(
                        date=dt.date.today() - dt.timedelta(days=1),
                        return_pct=0.10,
                        z_score=2.6,
                    )
                ),
                PriceAnomaly(
                    **_anomaly_row(date=dt.date.today(), return_pct=0.20, z_score=3.5)
                ),
            ]
        )
        session.flush()

        rows = get_unexplained_price_anomalies(session)

        assert rows[0]["date"] == dt.date.today()

    def test_empty_when_no_anomalies_exist(self, session):
        assert get_unexplained_price_anomalies(session) == []

    def test_default_max_age_is_seven_days(self, session_with_second_company):
        session = session_with_second_company
        just_inside = dt.date.today() - dt.timedelta(days=7)
        just_outside = dt.date.today() - dt.timedelta(days=8)
        session.add_all(
            [
                PriceAnomaly(**_anomaly_row(cik=TEST_CIK, date=just_inside)),
                PriceAnomaly(**_anomaly_row(cik=SECONDARY_CIK, date=just_outside)),
            ]
        )
        session.flush()

        rows = get_unexplained_price_anomalies(session)

        assert len(rows) == 1
        assert rows[0]["cik"] == TEST_CIK


class TestGetLatestAnomalies:
    def test_returns_anomalies_from_most_recent_date_only(self, session):
        older_date = dt.date.today() - dt.timedelta(days=5)
        newer_date = dt.date.today() - dt.timedelta(days=1)
        session.add_all(
            [
                PriceAnomaly(
                    cik=TEST_CIK, date=older_date, return_pct=0.10, z_score=2.6
                ),
                PriceAnomaly(
                    cik=TEST_CIK, date=newer_date, return_pct=0.15, z_score=3.1
                ),
            ]
        )
        session.flush()

        rows = get_latest_price_anomalies(session)

        assert len(rows) == 1
        assert rows[0]["date"] == newer_date

    def test_returns_all_companies_on_the_latest_date(self, session):
        latest = dt.date.today()
        session.add_all(
            [
                PriceAnomaly(cik=TEST_CIK, date=latest, return_pct=0.10, z_score=2.6),
            ]
        )
        session.flush()

        rows = get_latest_price_anomalies(session)

        assert all(r["date"] == latest for r in rows)

    def test_empty_table_returns_empty_list(self, session):
        assert get_latest_price_anomalies(session) == []

    def test_includes_explanation_fields(self, session):
        session.add(
            PriceAnomaly(
                cik=TEST_CIK,
                date=dt.date.today(),
                return_pct=0.10,
                z_score=2.6,
                explanation="Coincided with a guidance raise.",
                explained_at=dt.datetime.now(),
            )
        )
        session.flush()

        rows = get_latest_price_anomalies(session)

        assert rows[0]["explanation"] == "Coincided with a guidance raise."

    def test_unexplained_anomaly_has_none_explanation(self, session):
        session.add(
            PriceAnomaly(
                cik=TEST_CIK, date=dt.date.today(), return_pct=0.10, z_score=2.6
            )
        )
        session.flush()

        rows = get_latest_price_anomalies(session)

        assert rows[0]["explanation"] is None


class TestSetPriceAnomalyExplanation:
    def test_sets_explanation_and_explained_at(self, session):
        anomaly = PriceAnomaly(**_anomaly_row(date=dt.date.today()))
        session.add(anomaly)
        session.flush()

        set_price_anomaly_explanation(
            session, anomaly.id, "This coincided with a guidance raise."
        )
        session.flush()
        session.refresh(anomaly)

        assert anomaly.explanation == "This coincided with a guidance raise."
        assert anomaly.explained_at is not None

    def test_explained_anomaly_no_longer_returned_by_get_unexplained(self, session):
        anomaly = PriceAnomaly(**_anomaly_row(date=dt.date.today()))
        session.add(anomaly)
        session.flush()

        set_price_anomaly_explanation(session, anomaly.id, "Explained.")
        session.flush()

        assert get_unexplained_price_anomalies(session) == []

    def test_unknown_anomaly_id_is_a_silent_noop(self, session):
        set_price_anomaly_explanation(
            session, anomaly_id=999999, explanation="Nothing to update."
        )
