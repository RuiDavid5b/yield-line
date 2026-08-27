"""
Integration tests for the API layer.
"""

import pytest
from fastapi.testclient import TestClient

from stock_news.api.main import app, get_session
from stock_news.storage.models import Company

TEST_CIK = "0000320193"


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_companies_reflects_real_db(client, db_session):
    db_session.add(
        Company(cik=TEST_CIK, ticker="TEST", name="Test Co", industry_segment="test")
    )
    db_session.flush()

    response = client.get("/companies")

    assert response.status_code == 200
    assert any(c["cik"] == TEST_CIK for c in response.json())


def test_unknown_company_prices_returns_empty_list_not_error(client):
    response = client.get(f"/companies/{TEST_CIK}/prices")
    assert response.status_code == 200
    assert response.json() == []
