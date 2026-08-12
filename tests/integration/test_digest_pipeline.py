"""
Integration test for processing.digest - hits the yfinance API.
"""

from stock_news.processing.digest import fetch_benchmark_returns


def test_fetch_benchmark_returns_real_data():
    result = fetch_benchmark_returns(period="5d")

    assert set(result) == {"SOXX", "SMH", "SPY"}
    assert all(v is not None for v in result.values())
    assert all(isinstance(v, float) for v in result.values())
