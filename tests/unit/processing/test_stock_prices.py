"""
Unit tests for processing.prices - pure functions, synthetic data only.
"""

import datetime as dt

from stock_news.processing.stock_prices import (
    compute_daily_returns,
    detect_price_anomalies,
)


def _dates(n: int, start: dt.date = dt.date(2025, 1, 1)) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range(n)]


def _rows(closes: list[float], cik: str = "0000320193") -> list[dict]:
    return [
        {"cik": cik, "date": date, "close": close}
        for date, close in zip(_dates(len(closes)), closes)
    ]


class TestComputeDailyReturns:
    def test_empty_input(self):
        assert compute_daily_returns([]) == []

    def test_first_row_has_no_return(self):
        rows = _rows([100.0, 101.0, 99.0])
        result = compute_daily_returns(rows)
        assert result[0]["return_pct"] is None

    def test_computes_expected_percentages(self):
        rows = _rows([100.0, 110.0, 99.0])
        result = compute_daily_returns(rows)
        assert result[1]["return_pct"] == 0.10
        assert result[2]["return_pct"] == (99.0 - 110.0) / 110.0

    def test_zero_previous_close_yields_none(self):
        rows = _rows([0.0, 50.0])
        result = compute_daily_returns(rows)
        assert result[1]["return_pct"] is None

    def test_sorts_unsorted_input(self):
        dates = _dates(3)
        rows = [
            {"cik": "x", "date": dates[2], "close": 120.0},
            {"cik": "x", "date": dates[0], "close": 100.0},
            {"cik": "x", "date": dates[1], "close": 110.0},
        ]
        result = compute_daily_returns(rows)
        assert [r["date"] for r in result] == dates

    def test_preserves_other_keys(self):
        rows = _rows([100.0, 105.0])
        result = compute_daily_returns(rows)
        assert result[0]["cik"] == "0000320193"
        assert "date" in result[0] and "close" in result[0]


class TestDetectPriceAnomalies:
    def _stable_then_spike(
        self, n_stable: int = 15, spike_return: float = 0.20
    ) -> list[dict]:
        daily_variation = [0.0008, 0.0012, 0.0009, 0.0011, 0.0010, 0.0013, 0.0007]
        closes = [100.0]
        for i in range(n_stable):
            closes.append(closes[-1] * (1 + daily_variation[i % len(daily_variation)]))
        closes.append(closes[-1] * (1 + spike_return))
        rows = _rows(closes)
        return compute_daily_returns(rows)

    def test_empty_input(self):
        assert detect_price_anomalies([]) == []

    def test_flags_large_deviation_after_min_periods(self):
        rows = self._stable_then_spike()
        result = detect_price_anomalies(
            rows, window=20, min_periods=10, z_threshold=2.5
        )
        assert result[-1]["is_anomaly"] is True
        assert result[-1]["z_score"] is not None
        assert abs(result[-1]["z_score"]) >= 2.5

    def test_stable_days_not_flagged(self):
        rows = self._stable_then_spike()
        stable_days = detect_price_anomalies(
            rows, window=20, min_periods=10, z_threshold=2.5
        )[10:-1]
        assert all(day["is_anomaly"] is False for day in stable_days)

    def test_respects_min_periods(self):
        rows = compute_daily_returns(_rows([100.0, 100.0, 200.0]))
        result = detect_price_anomalies(rows, min_periods=10)
        assert result[2]["z_score"] is None
        assert result[2]["is_anomaly"] is False

    def test_first_row_always_unflagged(self):
        rows = self._stable_then_spike()
        result = detect_price_anomalies(rows)
        assert result[0]["z_score"] is None
        assert result[0]["is_anomaly"] is False

    def test_zero_variance_window_does_not_flag_or_error(self):
        rows = compute_daily_returns(_rows([100.0 * (1.01**i) for i in range(15)]))
        result = detect_price_anomalies(rows, window=10, min_periods=5)
        assert all(day["z_score"] is None for day in result[5:])
        assert all(day["is_anomaly"] is False for day in result)

    def test_sorts_unsorted_input(self):
        rows = self._stable_then_spike()
        shuffled = list(reversed(rows))
        result = detect_price_anomalies(shuffled)
        assert [r["date"] for r in result] == [r["date"] for r in rows]

    def test_preserves_other_keys(self):
        rows = self._stable_then_spike()
        result = detect_price_anomalies(rows)
        assert all("cik" in r and "close" in r and "return_pct" in r for r in result)
