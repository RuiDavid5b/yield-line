"""
Integration test for pipelines.anomaly_explanations.
"""

import datetime as dt

import pytest

from stock_news.pipelines import anomaly_explanations as pipeline
from stock_news.storage.models import Company, PriceAnomaly

TEST_CIK = "9999999999"
TEST_TICKER = "ABC"


@pytest.fixture
def session_with_anomaly(db_session):
    db_session.add(
        Company(
            cik=TEST_CIK, ticker=TEST_TICKER, name="Test Co", industry_segment="test"
        )
    )
    db_session.add(
        PriceAnomaly(cik=TEST_CIK, date=dt.date.today(), return_pct=0.15, z_score=3.2)
    )
    db_session.flush()
    yield db_session


def test_run_anomaly_explanation_pipeline_persists_real_explanation(
    session_with_anomaly, monkeypatch
):
    monkeypatch.setattr(
        pipeline, "run_agent_query", lambda prompt, **kwargs: "Mocked explanation text."
    )

    result = pipeline.run_anomaly_explanation_pipeline(session_with_anomaly)

    assert result.anomalies_seen == 1
    assert result.explained == 1
    assert result.failed == 0

    stored = session_with_anomaly.query(PriceAnomaly).filter_by(cik=TEST_CIK).one()
    assert stored.explanation == "Mocked explanation text."
    assert stored.explained_at is not None


def test_already_explained_anomaly_not_reprocessed(session_with_anomaly, monkeypatch):
    calls = []
    monkeypatch.setattr(
        pipeline,
        "run_agent_query",
        lambda prompt, **kwargs: calls.append(prompt) or "Explained.",
    )

    pipeline.run_anomaly_explanation_pipeline(session_with_anomaly)
    result_second_run = pipeline.run_anomaly_explanation_pipeline(session_with_anomaly)

    assert len(calls) == 1  # only the first run actually called the agent
    assert result_second_run.anomalies_seen == 0
