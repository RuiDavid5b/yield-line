"""
DAG-level tests for seed_company_graph
"""

import pytest
from airflow.dag_processing.dagbag import DagBag


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    return DagBag()


def test_dagbag_has_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_seed_company_graph_is_loaded(dagbag):
    assert "seed_company_graph" in dagbag.dags


class TestSeedCompanyGraphStructure:
    @pytest.fixture
    def dag(self, dagbag):
        return dagbag.dags["seed_company_graph"]

    def test_is_not_scheduled(self, dag):
        assert dag.schedule is None

    def test_has_single_seed_task(self, dag):
        assert dag.task_ids == ["seed_company_graph"]

    def test_seed_task_runs_graph_loader(self, dag):
        task = dag.get_task("seed_company_graph")
        assert "stock_news.graph.loader" in task.command
