"""
Unit tests for the API layer.
"""

import pytest
from fastapi.testclient import TestClient

import stock_news.api.main as api_main
from stock_news.agent import providers
from stock_news.api.main import app, get_session
from stock_news.auth.dependencies import get_current_session, require_csrf
from stock_news.storage.models import LLMProvider


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[get_current_session] = lambda: {
        "session_id": "test-session",
        "user_sub": "test-user",
        "email": "test@example.com",
        "access_token": "test-access-token",
        "csrf_token": "test-csrf-token",
    }
    app.dependency_overrides[require_csrf] = lambda: None

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
        app.dependency_overrides[get_current_session] = lambda: {
            "user_sub": "sub-1",
            "email": "a@example.com",
        }
        app.dependency_overrides[get_session] = lambda: object()

        monkeypatch.setattr(
            api_main, "get_or_create_user", lambda session, sub, email: {"id": 1}
        )
        monkeypatch.setattr(
            api_main,
            "get_user_api_key_encrypted",
            lambda session, user_id: {
                "llm_provider": "anthropic",
                "llm_model": "claude-sonnet-4-6",
                "encrypted_api_key": "ciphertext",
            },
        )
        monkeypatch.setattr(api_main, "decrypt_api_key", lambda ciphertext: "sk-fake")
        monkeypatch.setattr(
            api_main, "build_chat_model", lambda provider, model, key: object()
        )
        monkeypatch.setattr(
            api_main,
            "run_agent_query",
            lambda question, thread_id, selected_company, llm, rate_limit_gemini: "Synopsys reported...",
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

        app.dependency_overrides.clear()

    def test_missing_question_returns_422(self, client):
        response = client.post("/agent/ask", json={"thread_id": "test-thread-1"})
        print(response.status_code, response.json())
        assert response.status_code == 422

    def test_thread_id_is_scoped_by_user_id(self, client, monkeypatch):
        app.dependency_overrides[get_current_session] = lambda: {
            "user_sub": "sub-1",
            "email": "a@example.com",
        }
        app.dependency_overrides[get_session] = lambda: object()

        captured = {}
        monkeypatch.setattr(
            api_main, "get_or_create_user", lambda session, sub, email: {"id": 42}
        )
        monkeypatch.setattr(
            api_main,
            "get_user_api_key_encrypted",
            lambda session, user_id: {
                "llm_provider": "anthropic",
                "llm_model": "claude-sonnet-4-6",
                "encrypted_api_key": "x",
            },
        )
        monkeypatch.setattr(api_main, "decrypt_api_key", lambda x: "sk-fake")
        monkeypatch.setattr(
            api_main, "build_chat_model", lambda provider, model, key: object()
        )

        def fake_run_agent_query(
            question, thread_id, selected_company, llm, rate_limit_gemini
        ):
            captured["thread_id"] = thread_id
            return "answer"

        monkeypatch.setattr(api_main, "run_agent_query", fake_run_agent_query)

        response = client.post(
            "/agent/ask",
            json={"question": "hi", "thread_id": "abc", "selected_company": None},
        )

        assert response.status_code == 200
        assert captured["thread_id"] == "user-42:abc"

        app.dependency_overrides.clear()

    def test_build_chat_model_passes_model_through_for_each_provider(self, monkeypatch):
        captured = {}

        class FakeChatAnthropic:
            def __init__(self, model, api_key):
                captured["anthropic"] = model

        monkeypatch.setattr("langchain_anthropic.ChatAnthropic", FakeChatAnthropic)
        providers.build_chat_model(
            LLMProvider.ANTHROPIC, "claude-sonnet-4-6", "sk-fake"
        )
        assert captured["anthropic"] == "claude-sonnet-4-6"
