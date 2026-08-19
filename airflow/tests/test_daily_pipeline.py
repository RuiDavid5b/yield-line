"""
DAG-level tests for daily_pipeline.
"""

import pytest
from airflow.dag_processing.dagbag import DagBag


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag()


def test_dagbag_has_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_daily_pipeline_is_loaded(dagbag):
    assert "daily_pipeline" in dagbag.dags


class TestDailyPipelineStructure:
    @pytest.fixture
    def dag(self, dagbag):
        return dagbag.dags["daily_pipeline"]

    def test_expected_task_ids_present(self, dag):
        expected = {
            "list_companies",
            "parse_companies",
            "price_commands",
            "run_price_pipeline",
            "run_digest_pipeline",
            "is_weekly_run",
            "filings_commands",
            "news_commands",
            "run_filings_pipeline",
            "run_news_pipeline",
        }
        assert expected.issubset(set(dag.task_ids))

    def test_digest_runs_downstream_of_price_tasks(self, dag):
        price_task = dag.get_task("run_price_pipeline")
        digest_task = dag.get_task("run_digest_pipeline")
        assert digest_task.task_id in price_task.downstream_task_ids

    def test_digest_has_all_done_trigger_rule(self, dag):
        digest_task = dag.get_task("run_digest_pipeline")
        assert digest_task.trigger_rule == "all_done"

    def test_filings_pipeline_uses_rate_limit_pool(self, dag):
        filings_task = dag.get_task("run_filings_pipeline")
        assert filings_task.pool == "gemini_api"

    def test_weekly_gate_precedes_filings_and_news(self, dag):
        gate = dag.get_task("is_weekly_run")
        assert "filings_commands" in gate.downstream_task_ids or any(
            "filings" in t for t in gate.downstream_task_ids
        )

    def test_dag_has_no_cycles(self, dag):
        dag.check_cycle()

    def test_schedule_is_daily(self, dag):
        assert dag.schedule == "@daily"
