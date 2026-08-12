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
        # compute_daily_returns returns [None] for a lone row - first row
        # always has no prior close to compare against.
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
        # fetch_benchmark_returns only returns floats, so this test targets
        # the row construction directly via a spy, not the public return type.
        captured = {}
        original = digest.compute_daily_returns

        def spy(rows):
            captured["rows"] = rows
            return original(rows)

        monkeypatch.setattr(digest, "compute_daily_returns", spy)
        digest.fetch_benchmark_returns()
        assert all(isinstance(r["date"], dt.date) for r in captured["rows"])
        assert all(not isinstance(r["date"], pd.Timestamp) for r in captured["rows"])
