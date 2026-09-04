"""
Integration test for pipelines.anomaly_explanations.
"""

import datetime as dt

import pytest

from stock_news.pipelines import anomaly_explanations as pipeline
from stock_news.storage.models import AnomalyExplanation, Company, PriceAnomaly

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

    stored = (
        session_with_anomaly.query(AnomalyExplanation)
        .filter_by(cik=TEST_CIK, date=dt.date.today())
        .one()
    )
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

    assert len(calls) == 1
    assert result_second_run.anomalies_seen == 0


def test_cross_sectional_only_anomaly_gets_explained(db_session, monkeypatch):
    from stock_news.storage.models import DigestResult

    db_session.add(
        Company(
            cik=TEST_CIK, ticker=TEST_TICKER, name="Test Co", industry_segment="test"
        )
    )
    db_session.add(
        DigestResult(
            cik=TEST_CIK,
            date=dt.date.today(),
            return_pct=0.08,
            peer_avg_return_pct=None,
            vs_peer_avg=None,
            vs_soxx=None,
            vs_smh=None,
            vs_spy=None,
            cross_sectional_z_score=3.5,
            is_cross_sectional_anomaly=True,
        )
    )
    db_session.flush()

    monkeypatch.setattr(
        pipeline, "run_agent_query", lambda prompt, **kwargs: "Explained."
    )

    result = pipeline.run_anomaly_explanation_pipeline(db_session)

    assert result.anomalies_seen == 1
    assert result.explained == 1

    stored = (
        db_session.query(AnomalyExplanation)
        .filter_by(cik=TEST_CIK, date=dt.date.today())
        .one()
    )
    assert stored.explanation == "Explained."
