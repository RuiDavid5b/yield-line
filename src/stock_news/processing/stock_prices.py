"""
Processes stored stock price rows: return calculation and anomaly detection.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

_STD_EPSILON = 1e-9


def compute_daily_returns(prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Compute day-over-day percentage returns from stored price rows.

    Keyword arguments:
    prices: rows with at least "date" and "close" keys, one per company,
        in any order. Typically the output of a query against StockPrice
        for a single cik.
    """
    if not prices:
        return []

    sorted_rows = sorted(prices, key=lambda r: r["date"])
    closes = [row["close"] for row in sorted_rows]

    returns: list[float | None] = [None]
    for prev_close, close in zip(closes, closes[1:]):
        returns.append(None if prev_close == 0 else (close - prev_close) / prev_close)

    return [
        {**row, "return_pct": return_pct}
        for row, return_pct in zip(sorted_rows, returns)
    ]


def detect_price_anomalies(
    prices_with_returns: list[dict[str, Any]],
    window: int = 20,
    min_periods: int = 10,
    z_threshold: float = 2.5,
) -> list[dict[str, Any]]:
    """
    Flag anomalous daily moves using a rolling z-score of returns.

    Keyword arguments:
    prices_with_returns: output of compute_daily_returns(), sorted or not
        (this function re-sorts by date).
    window: number of prior trading days used to compute the rolling
        mean/std that each day's return is compared against.
    min_periods: minimum number of prior days required before a z-score
        is computed at all; rows before this have is_anomaly=False and
        z_score=None regardless of the actual move size.
    z_threshold: absolute z-score above which a day is flagged.
    """
    if not prices_with_returns:
        return []

    sorted_rows = sorted(prices_with_returns, key=lambda r: r["date"])
    returns = pd.Series([row["return_pct"] for row in sorted_rows], dtype="float64")

    prior_returns = returns.shift(1)
    rolling_mean = prior_returns.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = prior_returns.rolling(window=window, min_periods=min_periods).std()

    z_scores = (returns - rolling_mean) / rolling_std
    z_scores = z_scores.where(rolling_std > _STD_EPSILON)

    result: list[dict[str, Any]] = []
    for row, z in zip(sorted_rows, z_scores):
        z_value = None if pd.isna(z) else float(z)
        is_anomaly = z_value is not None and abs(z_value) >= z_threshold
        result.append({**row, "z_score": z_value, "is_anomaly": is_anomaly})

    return result


def transform_price_history(history: pd.DataFrame, cik: str) -> list[dict[str, Any]]:
    """
    Convert a raw yfinance history DataFrame (as returned by
    ingestion.fetchers.fetch_prices) into rows matching the StockPrice
    schema.
    """
    return [
        {
            "cik": cik,
            "date": row["Date"].date(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        }
        for _, row in history.iterrows()
    ]
