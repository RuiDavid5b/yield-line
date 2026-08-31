"""
Unit tests for storage.queries.get_digest.
"""

import datetime as dt

from stock_news.storage import queries

TEST_DATE = dt.date(2025, 6, 15)


class TestGetDigest:
    def test_cache_hit_returns_cached_value_unmodified(self, monkeypatch):
        cached = {
            "version": queries.DIGEST_SCHEMA_VERSION,
            "companies": [],
            "benchmarks": {},
        }
        monkeypatch.setattr(queries, "read_digest", lambda date: cached)
        pg_calls = []
        monkeypatch.setattr(
            queries, "get_digest_results", lambda s, d: pg_calls.append(d) or []
        )

        result = queries.get_digest(session=None, date=TEST_DATE)

        assert result is cached
        assert pg_calls == []  # Postgres never touched on a clean hit

    def test_cache_miss_falls_back_to_postgres_and_joins_segment(self, monkeypatch):
        monkeypatch.setattr(queries, "read_digest", lambda date: None)
        monkeypatch.setattr(
            queries,
            "get_digest_results",
            lambda s, d: [
                {
                    "cik": "A",
                    "return_pct": 0.05,
                    "peer_avg_return_pct": 0.03,
                    "vs_peer_avg": 0.02,
                    "vs_soxx": 0.01,
                    "vs_smh": 0.01,
                    "vs_spy": None,
                }
            ],
        )
        monkeypatch.setattr(
            queries,
            "get_all_companies",
            lambda s: [{"cik": "A", "industry_segment": "foundry"}],
        )
        monkeypatch.setattr(
            queries,
            "get_benchmark_returns",
            lambda s, d: {"SOXX": 0.01, "SMH": 0.01, "SPY": None},
        )
        written = []
        monkeypatch.setattr(
            queries, "write_digest", lambda date, d: written.append((date, d))
        )

        result = queries.get_digest(session=None, date=TEST_DATE)

        assert result["companies"][0]["industry_segment"] == "foundry"
        assert result["benchmarks"]["soxx_return"] == 0.01
        assert written[0][0] == TEST_DATE  # repopulated Redis

    def test_stale_schema_version_treated_as_miss(self, monkeypatch):
        stale = {
            "version": queries.DIGEST_SCHEMA_VERSION - 1,
            "companies": [],
            "benchmarks": {},
        }
        monkeypatch.setattr(queries, "read_digest", lambda date: stale)
        monkeypatch.setattr(queries, "get_digest_results", lambda s, d: [])
        result = queries.get_digest(session=None, date=TEST_DATE)
        assert (
            result is None
        )  # no rows in Postgres either - just confirms fallback path was taken, not the cached stale value

    def test_no_data_anywhere_returns_none(self, monkeypatch):
        monkeypatch.setattr(queries, "read_digest", lambda date: None)
        monkeypatch.setattr(queries, "get_digest_results", lambda s, d: [])
        result = queries.get_digest(session=None, date=TEST_DATE)
        assert result is None

    def test_redis_repopulate_failure_does_not_prevent_return(self, monkeypatch):
        monkeypatch.setattr(queries, "read_digest", lambda date: None)
        monkeypatch.setattr(
            queries,
            "get_digest_results",
            lambda s, d: [
                {
                    "cik": "A",
                    "return_pct": 0.05,
                    "peer_avg_return_pct": None,
                    "vs_peer_avg": None,
                    "vs_soxx": None,
                    "vs_smh": None,
                    "vs_spy": None,
                }
            ],
        )
        monkeypatch.setattr(
            queries,
            "get_all_companies",
            lambda s: [{"cik": "A", "industry_segment": "foundry"}],
        )
        monkeypatch.setattr(queries, "get_benchmark_returns", lambda s, d: {})

        def raise_write(date, d):
            raise RuntimeError("redis down")

        monkeypatch.setattr(queries, "write_digest", raise_write)

        result = queries.get_digest(session=None, date=TEST_DATE)
        assert (
            result is not None
        )  # still returns the reconstructed data despite the failed repopulate
