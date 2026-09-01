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
    GAAP_TAG_CANDIDATES,
    TAG_CANDIDATES_BY_TAXONOMY,
    build_unit_priority,
    extract_metric,
)

TEST_COMPANIES = {
    "Synopsys": "0000883241",
    "NVIDIA": "0001045810",
    "Micron": "0000723125",
}

pytestmark = pytest.mark.requires_env("EDGAR_USER_AGENT")


@pytest.mark.parametrize("company_name,cik", TEST_COMPANIES.items())
def test_fetch_edgar_filings_returns_results_for_real_companies(company_name, cik):
    filings = fetch_edgar_filings(
        cik=cik, user_agent=os.environ["EDGAR_USER_AGENT"], limit=5
    )

    assert filings, f"{company_name} (CIK {cik}) returned no filings"
    assert all("form" in f for f in filings)


@pytest.mark.parametrize("company_name,cik", TEST_COMPANIES.items())
@pytest.mark.parametrize("metric_name", GAAP_TAG_CANDIDATES.keys())
def test_every_metric_extracts_for_every_real_company(company_name, cik, metric_name):
    facts = fetch_company_facts(cik=cik, user_agent=os.environ["EDGAR_USER_AGENT"])

    rows = extract_metric(
        facts,
        cik=cik,
        metric_name=metric_name,
        candidate_tags=GAAP_TAG_CANDIDATES[metric_name],
        units=build_unit_priority(metric_name, ["USD"]),
    )

    assert rows, (
        f"No '{metric_name}' data found for {company_name} (CIK {cik}) - "
        f"tried tags {GAAP_TAG_CANDIDATES[metric_name]}. This company may "
        f"report this metric under a different XBRL tag."
    )
    assert all(row["unit"].startswith("USD") for row in rows), (
        f"Expected USD-denominated data for {company_name}'s {metric_name}, "
        f"got units: {sorted({row['unit'] for row in rows})}"
    )
    assert all(row["taxonomy"] == "us-gaap" for row in rows)


@pytest.mark.parametrize("company_name,cik", TEST_COMPANIES.items())
def test_revenue_series_has_multiple_recent_quarters(company_name, cik):
    facts = fetch_company_facts(cik=cik, user_agent=os.environ["EDGAR_USER_AGENT"])

    rows = extract_metric(
        facts,
        cik=cik,
        metric_name="revenue",
        candidate_tags=GAAP_TAG_CANDIDATES["revenue"],
        units=build_unit_priority("revenue", ["USD"]),
    )

    assert len(rows) >= 4, (
        f"Expected at least 4 quarters of revenue for {company_name}, "
        f"got {len(rows)}"
    )


FOREIGN_TEST_COMPANIES = {
    "ASML": {"cik": "0000937966", "taxonomy": "us-gaap", "fallback_currency": "EUR"},
    "TSMC": {"cik": "0001046179", "taxonomy": "ifrs-full", "fallback_currency": "TWD"},
}


@pytest.mark.parametrize(
    "company_name,info",
    FOREIGN_TEST_COMPANIES.items(),
    ids=FOREIGN_TEST_COMPANIES.keys(),
)
def test_foreign_filer_net_income_resolves_to_expected_taxonomy_and_currency(
    company_name, info
):
    facts = fetch_company_facts(
        cik=info["cik"], user_agent=os.environ["EDGAR_USER_AGENT"]
    )
    candidates_by_metric = TAG_CANDIDATES_BY_TAXONOMY[info["taxonomy"]]

    rows = extract_metric(
        facts,
        cik=info["cik"],
        metric_name="net_income",
        candidate_tags=candidates_by_metric["net_income"],
        units=build_unit_priority("net_income", ["USD", info["fallback_currency"]]),
        period_type="annual",
        taxonomy=info["taxonomy"],
    )

    assert rows, f"No net_income data found for {company_name}"
    assert all(row["taxonomy"] == info["taxonomy"] for row in rows)
    # Should have fallen back to native currency if USD wasn't available -
    # net_income specifically is unlikely to have a USD convenience figure.
    units_used = {row["unit"] for row in rows}
    assert units_used <= {"USD", info["fallback_currency"]}
