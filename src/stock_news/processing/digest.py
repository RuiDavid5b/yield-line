from collections import defaultdict
from typing import Any

from stock_news.benchmarks import BENCHMARK_TICKERS
from stock_news.ingestion.fetchers import fetch_prices
from stock_news.processing.stock_prices import compute_daily_returns


def fetch_benchmark_returns(period: str = "5d") -> dict[str, float | None]:
    """
    Fetch benchmark index prices live (not persisted) and compute each
    one's latest daily return. Returns None for a ticker if there isn't
    enough data to compute a return (e.g. a fetch failure or a single
    row returned).
    """
    returns: dict[str, float | None] = {}
    for ticker in BENCHMARK_TICKERS:
        history = fetch_prices(ticker, period=period)
        if history.empty:
            returns[ticker] = None
            continue
        rows = [
            {"date": row["Date"].date(), "close": float(row["Close"])}
            for _, row in history.iterrows()
        ]
        with_returns = compute_daily_returns(rows)
        returns[ticker] = with_returns[-1]["return_pct"] if with_returns else None
    return returns


def compute_company_digest(
    company_returns: list[dict[str, Any]],
    benchmark_returns: dict[str, float | None],
) -> dict[str, Any]:
    """
    Build the digest: each company's own return, its industry_segment peer
    average, and diffs against both the peer average and each benchmark.
    """
    valid_by_segment: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in company_returns:
        if row["return_pct"] is not None:
            valid_by_segment[row["industry_segment"]].append(
                (row["cik"], row["return_pct"])
            )

    def peer_avg_excluding_self(cik: str, segment: str) -> float | None:
        others = [r for c, r in valid_by_segment.get(segment, []) if c != cik]
        return sum(others) / len(others) if others else None

    def diff(a: float | None, b: float | None) -> float | None:
        return None if a is None or b is None else a - b

    companies = []
    for row in company_returns:
        peer_avg = peer_avg_excluding_self(row["cik"], row["industry_segment"])
        companies.append(
            {
                "cik": row["cik"],
                "industry_segment": row["industry_segment"],
                "return_pct": row["return_pct"],
                "peer_avg_return_pct": peer_avg,
                "vs_peer_avg": diff(row["return_pct"], peer_avg),
                "vs_soxx": diff(row["return_pct"], benchmark_returns.get("SOXX")),
                "vs_smh": diff(row["return_pct"], benchmark_returns.get("SMH")),
                "vs_spy": diff(row["return_pct"], benchmark_returns.get("SPY")),
            }
        )

    return {
        "companies": companies,
        "benchmarks": {
            "soxx_return": benchmark_returns.get("SOXX"),
            "smh_return": benchmark_returns.get("SMH"),
            "spy_return": benchmark_returns.get("SPY"),
        },
    }
