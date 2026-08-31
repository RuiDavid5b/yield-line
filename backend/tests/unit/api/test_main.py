"""
Unit tests for the API layer.
"""

import pytest
from fastapi.testclient import TestClient

import stock_news.api.main as api_main
from stock_news.api.main import app, get_session


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListCompanies:
    def test_returns_company_list(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main,
            "get_all_companies",
            lambda session: [
                {
                    "cik": "0000883241",
                    "ticker": "SNPS",
                    "name": "Synopsys",
                    "industry_segment": "ip_eda",
                    "reporting_currency": "USD",
                    "aliases": [],
                    "news_disambiguation": [],
                }
            ],
        )
        response = client.get("/companies")
        assert response.status_code == 200
        assert response.json()[0]["ticker"] == "SNPS"


class TestDigestForDate:
    def test_returns_digest_when_present(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main,
            "get_digest",
            lambda session, date: {
                "companies": [
                    {
                        "cik": "A",
                        "industry_segment": "foundry",
                        "return_pct": 0.05,
                        "peer_avg_return_pct": None,
                        "vs_peer_avg": None,
                        "vs_soxx": None,
                        "vs_smh": None,
                        "vs_spy": None,
                        "cross_sectional_z_score": None,
                        "is_cross_sectional_anomaly": False,
                    }
                ],
                "benchmarks": {
                    "soxx_return": 0.01,
                    "smh_return": 0.01,
                    "spy_return": None,
                },
            },
        )
        response = client.get("/digest/2026-06-15")
        assert response.status_code == 200
        assert response.json()["companies"][0]["cik"] == "A"

    def test_returns_404_when_absent(self, client, monkeypatch):
        monkeypatch.setattr(api_main, "get_digest", lambda session, date: None)
        response = client.get("/digest/2020-01-01")
        assert response.status_code == 404

    def test_invalid_date_format_returns_422(self, client):
        response = client.get("/digest/not-a-date")
        assert response.status_code == 422


class TestAskAgent:
    def test_returns_answer(self, client, monkeypatch):
        monkeypatch.setattr(
            api_main,
            "run_agent_query",
            lambda question, thread_id, selected_company: "Synopsys reported...",
        )
        response = client.post(
            "/agent/ask",
            json={
                "question": "How is Synopsys doing?",
                "thread_id": "test-thread-1",
                "selected_company": None,
            },
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "Synopsys reported..."

    def test_missing_question_returns_422(self, client):
        response = client.post("/agent/ask", json={"thread_id": "test-thread-1"})
        assert response.status_code == 422
