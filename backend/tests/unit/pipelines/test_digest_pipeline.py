"""
Unit tests for pipelines.digest
"""

import datetime as dt

import pytest

from stock_news.pipelines import digest as digest_pipeline

TEST_DATE = dt.date(2025, 6, 15)


class TestCompanyReturnForDate:
    def test_returns_none_when_date_missing_from_history(self, monkeypatch):
        monkeypatch.setattr(
            digest_pipeline, "get_stock_price_history", lambda session, cik: []
        )
        result = digest_pipeline._company_return_for_date(
            session=None, cik="A", industry_segment="foundry", target_date=TEST_DATE
        )
        assert result == {"cik": "A", "industry_segment": "foundry", "return_pct": None}

    def test_returns_computed_value_when_date_present(self, monkeypatch):
        history = [
            {"date": TEST_DATE - dt.timedelta(days=1), "close": 100.0},
            {"date": TEST_DATE, "close": 110.0},
        ]
        monkeypatch.setattr(
            digest_pipeline, "get_stock_price_history", lambda session, cik: history
        )
        result = digest_pipeline._company_return_for_date(
            session=None, cik="A", industry_segment="foundry", target_date=TEST_DATE
        )
        assert result["return_pct"] == pytest.approx(0.10)


class TestRunDigestPipeline:
    def _patch_common(self, monkeypatch, companies, benchmark_returns):
        monkeypatch.setattr(
            digest_pipeline, "get_all_companies", lambda session: companies
        )
        monkeypatch.setattr(
            digest_pipeline, "fetch_benchmark_returns", lambda: benchmark_returns
        )
        monkeypatch.setattr(
            digest_pipeline,
            "_company_return_for_date",
            lambda session, cik, seg, date: {
                "cik": cik,
                "industry_segment": seg,
                "return_pct": 0.05,
            },
        )
        monkeypatch.setattr(
            digest_pipeline, "upsert_digest_results", lambda s, rows: None
        )
        monkeypatch.setattr(
            digest_pipeline, "upsert_benchmark_returns", lambda s, rows: None
        )
        monkeypatch.setattr(digest_pipeline, "write_digest", lambda date, d: None)

    def test_happy_path_counts(self, monkeypatch):
        companies = [{"cik": "A", "industry_segment": "foundry"}]
        self._patch_common(
            monkeypatch, companies, {"SOXX": 0.01, "SMH": 0.01, "SPY": None}
        )

        class FakeSession:
            def commit(self):
                pass

            def rollback(self):
                pass

        result = digest_pipeline.run_digest_pipeline(FakeSession(), date=TEST_DATE)

        assert result.error is None
        assert result.companies_seen == 1
        assert result.digest_rows_upserted == 1
        assert result.benchmark_rows_upserted == 3
        assert result.redis_written is True

    def test_benchmark_fetch_failure_short_circuits(self, monkeypatch):
        monkeypatch.setattr(digest_pipeline, "get_all_companies", lambda session: [])

        def raise_fetch():
            raise RuntimeError("network down")

        monkeypatch.setattr(digest_pipeline, "fetch_benchmark_returns", raise_fetch)

        result = digest_pipeline.run_digest_pipeline(session=None, date=TEST_DATE)
        assert result.error is not None
        assert "benchmark_fetch" in result.error

    def test_postgres_failure_prevents_redis_write(self, monkeypatch):
        companies = [{"cik": "A", "industry_segment": "foundry"}]
        self._patch_common(
            monkeypatch, companies, {"SOXX": 0.01, "SMH": 0.01, "SPY": 0.01}
        )

        def raise_upsert(session, rows):
            raise RuntimeError("db down")

        monkeypatch.setattr(digest_pipeline, "upsert_digest_results", raise_upsert)
        redis_calls = []
        monkeypatch.setattr(
            digest_pipeline, "write_digest", lambda date, d: redis_calls.append(date)
        )

        class FakeSession:
            def commit(self):
                pass

            def rollback(self):
                pass

        result = digest_pipeline.run_digest_pipeline(FakeSession(), date=TEST_DATE)

        assert result.error is not None
        assert redis_calls == []  # Redis never touched after a Postgres failure

    def test_redis_failure_does_not_fail_pipeline(self, monkeypatch):
        companies = [{"cik": "A", "industry_segment": "foundry"}]
        self._patch_common(
            monkeypatch, companies, {"SOXX": 0.01, "SMH": 0.01, "SPY": 0.01}
        )

        def raise_redis(date, d):
            raise RuntimeError("redis down")

        monkeypatch.setattr(digest_pipeline, "write_digest", raise_redis)

        class FakeSession:
            def commit(self):
                pass

            def rollback(self):
                pass

        result = digest_pipeline.run_digest_pipeline(FakeSession(), date=TEST_DATE)

        assert result.error is None  # not fatal
        assert result.redis_written is False
        assert any("redis_write" in w for w in result.warnings)
