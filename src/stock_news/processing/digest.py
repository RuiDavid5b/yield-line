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
