import pytest

from stock_news.storage import company_lookup

FAKE_COMPANIES = [
    {"cik": "0000883241", "ticker": "SNPS", "name": "Synopsys", "aliases": []},
    {
        "cik": "0001045810",
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "aliases": ["Nvidia"],
    },
    {
        "cik": "0001046179",
        "ticker": "TSM",
        "name": "Taiwan Semiconductor Manufacturing Company",
        "aliases": ["TSMC"],
    },
]


@pytest.fixture(autouse=True)
def patch_companies(monkeypatch):
    monkeypatch.setattr(
        company_lookup, "get_all_companies", lambda session: FAKE_COMPANIES
    )


class TestResolveCompany:
    def test_exact_ticker_match_wins_outright(self):
        result = company_lookup.resolve_company(session=None, query="SNPS")
        assert len(result) == 1
        assert result[0]["cik"] == "0000883241"
        assert result[0]["match_confidence"] == 1.0

    def test_exact_ticker_match_case_insensitive(self):
        result = company_lookup.resolve_company(session=None, query="snps")
        assert result[0]["ticker"] == "SNPS"

    def test_typo_in_name_still_resolves(self):
        result = company_lookup.resolve_company(session=None, query="Synopys")
        assert result[0]["ticker"] == "SNPS"
        assert result[0]["match_confidence"] >= 0.6

    def test_partial_name_resolves_via_substring(self):
        result = company_lookup.resolve_company(session=None, query="Cadence")
        result = company_lookup.resolve_company(
            session=None, query="Taiwan Semiconductor"
        )
        assert result[0]["ticker"] == "TSM"
        assert result[0]["match_confidence"] == pytest.approx(0.95)

    def test_alias_resolves(self):
        result = company_lookup.resolve_company(session=None, query="TSMC")
        assert result[0]["ticker"] == "TSM"

    def test_unrelated_query_returns_empty(self):
        result = company_lookup.resolve_company(
            session=None, query="Completely Unrelated Widget Corp"
        )
        assert result == []

    def test_limit_caps_results(self):
        result = company_lookup.resolve_company(
            session=None, query="a", limit=1, cutoff=0.0
        )
        assert len(result) == 1

    def test_results_sorted_by_confidence_descending(self):
        result = company_lookup.resolve_company(
            session=None, query="NVIDIA", cutoff=0.0
        )
        scores = [r["match_confidence"] for r in result]
        assert scores == sorted(scores, reverse=True)
