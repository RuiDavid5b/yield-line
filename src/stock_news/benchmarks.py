"""
Static benchmark tickers used for sector-relative return comparison in
the Redis digest. Not portfolio companies - no CIK, no filings, no graph
membership. Small and static enough to be a plain constant rather than
a YAML file or DB table.
"""

BENCHMARK_TICKERS: dict[str, str] = {
    "SOXX": "sector_primary",
    "SMH": "sector_secondary",
    "SPY": "market_optional",
}
