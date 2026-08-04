"""
Integration test using the SEC EDGAR API.

Requires EDGAR_USER_AGENT to be set in the environment (SEC requires a
descriptive User-Agent - "Your Name your@email.com"), e.g.:
export EDGAR_USER_AGENT="Your Name your@email.com"
"""

import os

import pytest

from stock_news.ingestion.fetchers import fetch_company_facts, fetch_edgar_filings
from stock_news.processing.edgar.extraction import (
    GAAP_METRIC_UNITS,
    GAAP_TAG_CANDIDATES,
    extract_quarterly_metric,
)

TEST_COMPANIES = {
    "Synopsys": "0000883241",
    "NVIDIA": "0001045810",
    "Micron": "0000723125",
}

USER_AGENT = os.environ.get("EDGAR_USER_AGENT", "Personal Project test@example.com")


@pytest.mark.parametrize("company_name,cik", TEST_COMPANIES.items())
def test_fetch_edgar_filings_returns_results_for_real_companies(company_name, cik):
    filings = fetch_edgar_filings(cik=cik, user_agent=USER_AGENT, limit=5)

    assert filings, f"{company_name} (CIK {cik}) returned no filings"
    assert all(f["form"] in ("8-K", "10-Q") for f in filings)


@pytest.mark.parametrize("company_name,cik", TEST_COMPANIES.items())
@pytest.mark.parametrize("metric_name", GAAP_TAG_CANDIDATES.keys())
def test_every_metric_extracts_for_every_real_company(company_name, cik, metric_name):
    facts = fetch_company_facts(cik=cik, user_agent=USER_AGENT)

    rows = extract_quarterly_metric(
        facts,
        cik=cik,
        metric_name=metric_name,
        candidate_tags=GAAP_TAG_CANDIDATES[metric_name],
        unit=GAAP_METRIC_UNITS.get(metric_name, "USD"),
    )

    assert rows, (
        f"No '{metric_name}' data found for {company_name} (CIK {cik}) - "
        f"tried tags {GAAP_TAG_CANDIDATES[metric_name]}. This company may "
        f"report this metric under a different XBRL tag."
    )


@pytest.mark.parametrize("company_name,cik", TEST_COMPANIES.items())
def test_revenue_series_has_multiple_recent_quarters(company_name, cik):
    facts = fetch_company_facts(cik=cik, user_agent=USER_AGENT)

    rows = extract_quarterly_metric(
        facts,
        cik=cik,
        metric_name="revenue",
        candidate_tags=GAAP_TAG_CANDIDATES["revenue"],
    )

    assert len(rows) >= 4, (
        f"Expected at least 4 quarters of revenue for {company_name}, "
        f"got {len(rows)}"
    )
