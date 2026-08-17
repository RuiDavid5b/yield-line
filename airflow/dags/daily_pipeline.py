# airflow/dags/daily_pipeline.py
from __future__ import annotations

import datetime as dt
import json
import os

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import dag, task

APP_IMAGE = "stock-news-app:latest"
NETWORK = "stock_news_net"
FILINGS_NEWS_WEEKDAY = 0  # Monday

# Must be manually kept in sync with config.py's Settings fields when a
# new setting is added. 'stock_news' is not importable in order to keep it
# decoupled from airflow, though it causes this issue
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

# Shared by every DockerOperator below - each spawned container is a
# sibling of the Airflow scheduler (via the mounted docker.sock), not a
# child, so network/image/env-file all need to be repeated per task
# rather than inherited.
_COMMON_DOCKER_KWARGS = dict(
    image=APP_IMAGE,
    network_mode=NETWORK,
    docker_url="unix://var/run/docker.sock",
    auto_remove="success",
    environment=APP_ENV,
    mount_tmp_dir=False,
)


def app_task(task_id: str, command: str, **kwargs) -> DockerOperator:
    return DockerOperator(
        task_id=task_id, command=command, **_COMMON_DOCKER_KWARGS, **kwargs
    )


@dag(
    schedule="@daily",
    start_date=dt.datetime(2025, 1, 1),
    catchup=False,
    tags=["stock_news"],
)
def daily_pipeline():

    list_companies = app_task(
        task_id="list_companies",
        command="stock_news.scripts.list_companies",
    )

    @task
    def parse_companies(raw: str) -> list[dict]:
        return json.loads(raw)

    companies = parse_companies(list_companies.output)

    @task
    def price_commands(companies: list[dict]) -> list[str]:
        return [
            f"stock_news.pipelines.stock_prices --cik {c['cik']} --ticker {c['ticker']}"
            for c in companies
        ]

    run_price_tasks = DockerOperator.partial(
        task_id="run_price_pipeline",
        map_index_template="{{ task.command }}",
        **_COMMON_DOCKER_KWARGS,
    ).expand(command=price_commands(companies))

    run_digest = app_task(
        task_id="run_digest_pipeline",
        command="stock_news.pipelines.digest",
        trigger_rule="all_done",
    )
    run_price_tasks >> run_digest

    @task.short_circuit
    def is_weekly_run() -> bool:
        return dt.date.today().weekday() == FILINGS_NEWS_WEEKDAY

    @task
    def filings_commands(companies: list[dict]) -> list[str]:
        return [f"stock_news.pipelines.filings --cik {c['cik']}" for c in companies]

    @task
    def news_commands(companies: list[dict]) -> list[str]:
        return [
            f"stock_news.pipelines.news --cik {c['cik']} --terms {c['name']!r} {c['ticker']}"
            for c in companies
        ]

    weekly_gate = is_weekly_run()

    run_filings_tasks = DockerOperator.partial(
        task_id="run_filings_pipeline",
        map_index_template="{{ task.command }}",
        **_COMMON_DOCKER_KWARGS,
    ).expand(command=filings_commands(companies))

    run_news_tasks = DockerOperator.partial(
        task_id="run_news_pipeline",
        map_index_template="{{ task.command }}",
        **_COMMON_DOCKER_KWARGS,
    ).expand(command=news_commands(companies))

    weekly_gate >> [run_filings_tasks, run_news_tasks]


daily_pipeline()
