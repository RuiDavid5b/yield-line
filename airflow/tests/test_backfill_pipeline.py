"""
DAG-level tests for backfill_pipeline.
"""

import pytest
from airflow.dag_processing.dagbag import DagBag


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag()


def test_dagbag_has_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_backfill_pipeline_is_loaded(dagbag):
    assert "backfill_pipeline" in dagbag.dags


class TestBackfillPipelineStructure:
    @pytest.fixture
    def dag(self, dagbag):
        return dagbag.dags["backfill_pipeline"]

    def test_expected_task_ids_present(self, dag):
        expected = {
            "list_companies",
            "parse_companies",
            "backfill_filings_commands",
            "backfill_prices_commands",
            "backfill_filings",
            "backfill_prices",
        }
        assert expected.issubset(set(dag.task_ids))

    def test_is_not_scheduled(self, dag):
        # Manually triggered only - the graph only changes when you
        # decide to run backfill, not on a calendar. A regression here
        # (someone adding a schedule while refactoring) would silently
        # turn a one-off seed job into a recurring one.
        assert dag.schedule is None

    def test_backfill_filings_uses_rate_limit_pool(self, dag):
        task = dag.get_task("backfill_filings")
        assert task.pool == "gemini_api"

    def test_backfill_filings_does_not_auto_retry(self, dag):
        # A rate-limit exhaustion should be re-triggered deliberately as
        # a new run, not auto-retried into the same exhausted budget.
        task = dag.get_task("backfill_filings")
        assert task.retries == 0

    def test_no_digest_or_anomaly_tasks(self, dag):
        # Backfill is explicitly scoped to filings/metrics + prices only -
        # digest and anomaly-explanation are daily_pipeline's job, and
        # running them per historical date/anomaly would be expensive
        # and out of scope. Guards against that scope creeping back in.
        assert "run_digest_pipeline" not in dag.task_ids
        assert "run_anomaly_explanations" not in dag.task_ids

    def test_dag_has_no_cycles(self, dag):
        dag.check_cycle()

    def test_backfill_filings_and_prices_are_independent(self, dag):
        # No data dependency between EDGAR and yfinance backfill - they
        # should not be wired sequentially.
        filings_task = dag.get_task("backfill_filings")
        prices_task = dag.get_task("backfill_prices")
        assert prices_task.task_id not in filings_task.downstream_task_ids
        assert filings_task.task_id not in prices_task.downstream_task_ids
