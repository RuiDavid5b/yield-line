import datetime as dt

import pandas as pd
import pytest

from stock_news.processing import digest


def _history_df(
    closes: list[float], start: dt.date = dt.date(2025, 1, 1)
) -> pd.DataFrame:
    dates = [start + dt.timedelta(days=i) for i in range(len(closes))]
    return pd.DataFrame({"Date": pd.to_datetime(dates), "Close": closes})


class TestFetchBenchmarkReturns:
    def test_computes_expected_return_per_ticker(self, monkeypatch):
        monkeypatch.setattr(
            digest,
            "fetch_prices",
            lambda ticker, period="5d": _history_df([100.0, 110.0]),
        )
        result = digest.fetch_benchmark_returns()
        assert set(result) == {"SOXX", "SMH", "SPY"}
        assert result["SOXX"] == pytest.approx(0.10)

    def test_empty_history_yields_none(self, monkeypatch):
        monkeypatch.setattr(
            digest, "fetch_prices", lambda ticker, period="5d": pd.DataFrame()
        )
        result = digest.fetch_benchmark_returns()
        assert all(v is None for v in result.values())

    def test_single_row_history_yields_none(self, monkeypatch):
        monkeypatch.setattr(
            digest, "fetch_prices", lambda ticker, period="5d": _history_df([100.0])
        )
        result = digest.fetch_benchmark_returns()
        assert all(v is None for v in result.values())

    def test_per_ticker_failure_does_not_affect_others(self, monkeypatch):
        def fake_fetch(ticker, period="5d"):
            if ticker == "SPY":
                return pd.DataFrame()
            return _history_df([100.0, 105.0])

        monkeypatch.setattr(digest, "fetch_prices", fake_fetch)
        result = digest.fetch_benchmark_returns()
        assert result["SPY"] is None
        assert result["SOXX"] == pytest.approx(0.05)
        assert result["SMH"] == pytest.approx(0.05)

    def test_date_field_is_plain_date_not_timestamp(self, monkeypatch):
        monkeypatch.setattr(
            digest,
            "fetch_prices",
            lambda ticker, period="5d": _history_df([100.0, 101.0]),
        )
        captured = {}
        original = digest.compute_daily_returns

        def spy(rows):
            captured["rows"] = rows
            return original(rows)

        monkeypatch.setattr(digest, "compute_daily_returns", spy)
        digest.fetch_benchmark_returns()
        assert all(isinstance(r["date"], dt.date) for r in captured["rows"])
        assert all(not isinstance(r["date"], pd.Timestamp) for r in captured["rows"])


class TestComputeCompanyDigest:
    def _row(self, cik: str, segment: str, return_pct: float | None) -> dict:
        return {"cik": cik, "industry_segment": segment, "return_pct": return_pct}

    def _benchmarks(self, soxx=0.01, smh=0.012, spy=0.005) -> dict:
        return {"SOXX": soxx, "SMH": smh, "SPY": spy}

    def test_peer_avg_excludes_self(self):
        rows = [
            self._row("A", "foundry", 0.10),
            self._row("B", "foundry", 0.20),
        ]
        result = digest.compute_company_digest(rows, self._benchmarks())
        by_cik = {c["cik"]: c for c in result["companies"]}
        assert by_cik["A"]["peer_avg_return_pct"] == pytest.approx(0.20)
        assert by_cik["B"]["peer_avg_return_pct"] == pytest.approx(0.10)

    def test_peer_avg_ignores_other_segments(self):
        rows = [
            self._row("A", "foundry", 0.10),
            self._row("B", "foundry", 0.20),
            self._row("C", "ip_eda", 0.99),
        ]
        result = digest.compute_company_digest(rows, self._benchmarks())
        by_cik = {c["cik"]: c for c in result["companies"]}
        assert by_cik["A"]["peer_avg_return_pct"] == pytest.approx(0.20)
        assert by_cik["C"]["peer_avg_return_pct"] is None  # sole ip_eda company

    def test_missing_company_excluded_from_peer_avg_but_present_in_output(self):
        rows = [
            self._row("A", "foundry", 0.10),
            self._row("B", "foundry", None),
            self._row("C", "foundry", 0.30),
        ]
        result = digest.compute_company_digest(rows, self._benchmarks())
        by_cik = {c["cik"]: c for c in result["companies"]}
        assert by_cik["B"]["return_pct"] is None
        assert by_cik["B"]["peer_avg_return_pct"] == pytest.approx(0.20)  # avg of A, C
        assert by_cik["A"]["peer_avg_return_pct"] == pytest.approx(
            0.30
        )  # only C, B excluded (no data)

    def test_all_companies_in_segment_missing_yields_none_peer_avg(self):
        rows = [
            self._row("A", "foundry", None),
            self._row("B", "foundry", None),
        ]
        result = digest.compute_company_digest(rows, self._benchmarks())
        assert all(c["peer_avg_return_pct"] is None for c in result["companies"])

    def test_benchmarks_passed_through(self):
        rows = [self._row("A", "foundry", 0.10)]
        result = digest.compute_company_digest(
            rows, {"SOXX": 0.02, "SMH": 0.03, "SPY": None}
        )
        assert result["benchmarks"] == {
            "soxx_return": 0.02,
            "smh_return": 0.03,
            "spy_return": None,
        }

    def test_empty_company_returns(self):
        result = digest.compute_company_digest([], self._benchmarks())
        assert result["companies"] == []
        assert result["benchmarks"]["soxx_return"] is not None

    def test_diffs_computed_correctly(self):
        rows = [
            self._row("A", "foundry", 0.10),
            self._row("B", "foundry", 0.20),
        ]
        result = digest.compute_company_digest(
            rows, {"SOXX": 0.05, "SMH": 0.04, "SPY": None}
        )
        by_cik = {c["cik"]: c for c in result["companies"]}
        assert by_cik["A"]["vs_peer_avg"] == pytest.approx(0.10 - 0.20)
        assert by_cik["A"]["vs_soxx"] == pytest.approx(0.10 - 0.05)
        assert by_cik["A"]["vs_smh"] == pytest.approx(0.10 - 0.04)
        assert by_cik["A"]["vs_spy"] is None  # SPY missing

    def test_diff_none_when_own_return_missing(self):
        rows = [self._row("A", "foundry", None)]
        result = digest.compute_company_digest(rows, self._benchmarks())
        c = result["companies"][0]
        assert c["vs_peer_avg"] is None
        assert c["vs_soxx"] is None
