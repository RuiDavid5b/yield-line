"""
Unit tests for pipelines.anomaly_explanations.
"""

from stock_news.pipelines import anomaly_explanations as pipeline

ANOMALY = {
    "cik": "0000883241",
    "date": "2026-05-01",
    "return_pct": 0.12,
    "rolling_z_score": 3.1,
    "is_cross_sectional": False,
}
CROSS_SECTIONAL_ANOMALY = {
    "cik": "0000813672",
    "date": "2026-05-01",
    "return_pct": 0.09,
    "rolling_z_score": None,
    "is_cross_sectional": True,
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

    def test_prompt_mentions_own_history_signal(self):
        prompt = pipeline._build_prompt(ANOMALY, COMPANY)
        assert "own history" in prompt

    def test_prompt_mentions_cross_sectional_signal(self):
        prompt = pipeline._build_prompt(CROSS_SECTIONAL_ANOMALY, COMPANY)
        assert "all tracked companies" in prompt

    def test_prompt_mentions_both_when_both_present(self):
        both = {**ANOMALY, "is_cross_sectional": True}
        prompt = pipeline._build_prompt(both, COMPANY)
        assert "own history" in prompt
        assert "all tracked companies" in prompt


class TestRunAnomalyExplanationPipeline:
    def _patch_common(self, monkeypatch, anomalies, companies, agent_responses=None):
        monkeypatch.setattr(
            pipeline,
            "get_dates_needing_explanation",
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
            lambda session, cik, date, explanation: recorded.append(
                (cik, date, explanation)
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
        assert recorded == [
            ("0000883241", "2026-05-01", "This coincided with a guidance raise.")
        ]

    def test_explains_cross_sectional_only_anomaly(self, monkeypatch):
        # No rolling_z_score at all - the exact case the merged query exists for.
        cross_sectional_company = {
            **COMPANY,
            "cik": "0000813672",
            "ticker": "CDNS",
            "name": "Cadence",
        }
        recorded = self._patch_common(
            monkeypatch,
            anomalies=[CROSS_SECTIONAL_ANOMALY],
            companies=[cross_sectional_company],
            agent_responses=["Explained."],
        )
        result = pipeline.run_anomaly_explanation_pipeline(self._fake_session())

        assert result.explained == 1
        assert recorded == [("0000813672", "2026-05-01", "Explained.")]

    def test_thread_id_derived_from_cik_and_date(self, monkeypatch):
        self._patch_common(monkeypatch, anomalies=[ANOMALY], companies=[COMPANY])
        captured = {}

        def capture_thread_id(prompt, **kwargs):
            captured["thread_id"] = kwargs.get("thread_id")
            return "Explained."

        monkeypatch.setattr(pipeline, "run_agent_query", capture_thread_id)

        pipeline.run_anomaly_explanation_pipeline(self._fake_session())

        assert captured["thread_id"] == "anomaly-0000883241-2026-05-01"

    def test_unknown_cik_counted_as_failed_not_crashed(self, monkeypatch):
        self._patch_common(monkeypatch, anomalies=[ANOMALY], companies=[])
        result = pipeline.run_anomaly_explanation_pipeline(self._fake_session())

        assert result.explained == 0
        assert result.failed == 1
        assert "unknown cik" in result.errors[0]

    def test_agent_failure_on_one_anomaly_does_not_block_the_rest(self, monkeypatch):
        anomalies = [ANOMALY, {**ANOMALY, "cik": "0000813672", "date": "2026-05-02"}]
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
            "get_dates_needing_explanation",
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
            lambda session, cik, date, explanation: recorded.append(cik),
        )

        result = pipeline.run_anomaly_explanation_pipeline(self._fake_session())

        assert result.anomalies_seen == 2
        assert result.explained == 1
        assert result.failed == 1
        assert recorded == ["0000813672"]

    def test_each_anomaly_committed_independently(self, monkeypatch):
        anomalies = [ANOMALY, {**ANOMALY, "cik": "0000813672", "date": "2026-05-02"}]
        companies = [
            COMPANY,
            {**COMPANY, "cik": "0000813672", "ticker": "CDNS", "name": "Cadence"},
        ]

        monkeypatch.setattr(
            pipeline,
            "get_dates_needing_explanation",
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

        def raise_on_second_set(session, cik, date, explanation):
            if cik == "0000813672":
                raise RuntimeError("db write failed")

        monkeypatch.setattr(
            pipeline, "set_price_anomaly_explanation", raise_on_second_set
        )

        result = pipeline.run_anomaly_explanation_pipeline(TrackingSession())

        assert result.explained == 1
        assert result.failed == 1
        assert commits == ["commit", "rollback"]
