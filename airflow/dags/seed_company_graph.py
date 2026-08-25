"""
One-off/manually-triggered DAG: parses graph/companies_graph.yaml and
upserts it into Postgres. Not scheduled - the graph only changes when
the YAML is edited. Must trigger manually after editing companies_graph.yaml
to update.
"""

from __future__ import annotations

import datetime as dt
import os

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import dag

APP_IMAGE = "stock-news-app:latest"
NETWORK = "stock_news_net"

APP_ENV = {
    k: os.environ[k]
    for k in (
        "DATABASE_URL",
        "REDIS_URL",
        "EDGAR_USER_AGENT",
        "CURRENTS_API_KEY",
        "GOOGLE_API_KEY",
    )
    if k in os.environ
}


@dag(
    schedule=None,
    start_date=dt.datetime(2026, 1, 1),
    catchup=False,
    tags=["stock_news"],
)
def seed_company_graph():
    DockerOperator(
        task_id="seed_company_graph",
        image=APP_IMAGE,
        command="stock_news.graph.loader",
        network_mode=NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        environment=APP_ENV,
        mount_tmp_dir=False,
    )


seed_company_graph()
