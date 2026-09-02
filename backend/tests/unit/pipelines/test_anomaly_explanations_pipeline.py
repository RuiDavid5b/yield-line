"""
Unit tests for pipelines.anomaly_explanations.
"""

from stock_news.pipelines import anomaly_explanations as pipeline

ANOMALY = {
    "id": 1,
    "cik": "0000883241",
    "date": "2026-05-01",
    "return_pct": 0.12,
    "z_score": 3.1,
}
COMPANY = {
    "cik": "0000883241",
    "ticker": "SNPS",
    "name": "Synopsys",
    "industry_segment": "ip_eda",
}


class TestBuildPrompt:
    def test_prompt_includes_ticker_and_return(self):
        prompt = pipeline._build_prompt(ANOMALY, COMPANY)
        assert "SNPS" in prompt
        assert "12.00%" in prompt
        assert "resolve_company_tool" in prompt


class TestRunAnomalyExplanationPipeline:
    def _patch_common(self, monkeypatch, anomalies, companies, agent_responses=None):
        monkeypatch.setattr(
            pipeline,
            "get_unexplained_price_anomalies",
            lambda session, max_age_days=7: anomalies,
        )
        monkeypatch.setattr(pipeline, "get_all_companies", lambda session: companies)

        responses = iter(agent_responses or [])
        monkeypatch.setattr(
            pipeline, "run_agent_query", lambda prompt, **kwargs: next(responses)
        )

        recorded = []
        monkeypatch.setattr(
            pipeline,
            "set_price_anomaly_explanation",
            lambda session, anomaly_id, explanation: recorded.append(
                (anomaly_id, explanation)
            ),
        )
        return recorded

    def _fake_session(self):
        class FakeSession:
            def commit(self):
                pass

            def rollback(self):
                pass

        return FakeSession()

    def test_no_anomalies_is_a_noop(self, monkeypatch):
        self._patch_common(monkeypatch, anomalies=[], companies=[])
        result = pipeline.run_anomaly_explanation_pipeline(self._fake_session())
        assert result.anomalies_seen == 0
        assert result.explained == 0
        assert result.failed == 0

    def test_explains_each_anomaly_and_persists(self, monkeypatch):
        recorded = self._patch_common(
            monkeypatch,
            anomalies=[ANOMALY],
            companies=[COMPANY],
            agent_responses=["This coincided with a guidance raise."],
        )
        result = pipeline.run_anomaly_explanation_pipeline(self._fake_session())

        assert result.anomalies_seen == 1
        assert result.explained == 1
        assert result.failed == 0
        assert recorded == [(1, "This coincided with a guidance raise.")]

    def test_unknown_cik_counted_as_failed_not_crashed(self, monkeypatch):
        self._patch_common(monkeypatch, anomalies=[ANOMALY], companies=[])
        result = pipeline.run_anomaly_explanation_pipeline(self._fake_session())

        assert result.explained == 0
        assert result.failed == 1
        assert "unknown cik" in result.errors[0]

    def test_agent_failure_on_one_anomaly_does_not_block_the_rest(self, monkeypatch):
        anomalies = [ANOMALY, {**ANOMALY, "id": 2, "cik": "0000813672"}]
        companies = [
            COMPANY,
            {
                **COMPANY,
                "cik": "0000813672",
                "ticker": "CDNS",
                "name": "Cadence Design Systems",
            },
        ]

        monkeypatch.setattr(
            pipeline,
            "get_unexplained_price_anomalies",
            lambda session, max_age_days=7: anomalies,
        )
        monkeypatch.setattr(pipeline, "get_all_companies", lambda session: companies)

        def flaky_agent(prompt, **kwargs):
            if "SNPS" in prompt:
                raise RuntimeError("agent call failed")
            return "Explained fine."

        monkeypatch.setattr(pipeline, "run_agent_query", flaky_agent)
        recorded = []
        monkeypatch.setattr(
            pipeline,
            "set_price_anomaly_explanation",
            lambda session, anomaly_id, explanation: recorded.append(anomaly_id),
        )

        result = pipeline.run_anomaly_explanation_pipeline(self._fake_session())

        assert result.anomalies_seen == 2
        assert result.explained == 1
        assert result.failed == 1
        assert recorded == [2]

    def test_each_anomaly_committed_independently(self, monkeypatch):
        anomalies = [ANOMALY, {**ANOMALY, "id": 2, "cik": "0000813672"}]
        companies = [
            COMPANY,
            {**COMPANY, "cik": "0000813672", "ticker": "CDNS", "name": "Cadence"},
        ]

        monkeypatch.setattr(
            pipeline,
            "get_unexplained_price_anomalies",
            lambda session, max_age_days=7: anomalies,
        )
        monkeypatch.setattr(pipeline, "get_all_companies", lambda session: companies)
        monkeypatch.setattr(
            pipeline, "run_agent_query", lambda prompt, **kwargs: "Explained."
        )

        commits = []

        class TrackingSession:
            def commit(self):
                commits.append("commit")

            def rollback(self):
                commits.append("rollback")

        def raise_on_second_set(session, anomaly_id, explanation):
            if anomaly_id == 2:
                raise RuntimeError("db write failed")

        monkeypatch.setattr(
            pipeline, "set_price_anomaly_explanation", raise_on_second_set
        )

        result = pipeline.run_anomaly_explanation_pipeline(TrackingSession())

        assert result.explained == 1
        assert result.failed == 1
        assert commits == ["commit", "rollback"]
