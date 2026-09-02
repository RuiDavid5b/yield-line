from __future__ import annotations

import json
import os

import pendulum
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.operators.python import get_current_context
from airflow.sdk import dag, task

APP_IMAGE = "stock-news-app:latest"
NETWORK = "stock_news_net"

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
    schedule="15 16 * * 1-5",  # 4:15 PM, Mon-Fri
    start_date=pendulum.datetime(2025, 1, 1, tz="America/New_York"),
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
    )
    run_price_tasks >> run_digest

    @task
    def filings_commands(companies: list[dict], logical_date) -> list[str]:
        end_date = logical_date.date()
        start_date = end_date - pendulum.duration(days=7)

        return [
            (
                f"stock_news.pipelines.filings "
                f"--cik {c['cik']} "
                f"--filing-limit 5 "
                f"--start-date {start_date} "
                f"--end-date {end_date}"
            )
            for c in companies
        ]

    @task
    def news_commands(companies: list[dict]) -> list[str]:
        commands = []
        for c in companies:
            terms = [c["name"], *c.get("aliases", [])]
            if len(c["ticker"]) > 2 or c["ticker"].isupper():
                terms.append(c["ticker"])
            term_args = " ".join(f"{t!r}" for t in terms)

            command = f"stock_news.pipelines.news --cik {c['cik']} --terms {term_args}"

            disambiguation = c.get("news_disambiguation")
            if disambiguation:
                require_args = " ".join(f"{t!r}" for t in disambiguation)
                command += f" --require-any {require_args}"

            commands.append(command)
        return commands

    run_filings_tasks = DockerOperator.partial(
        task_id="run_filings_pipeline",
        map_index_template="{{ task.command }}",
        **_COMMON_DOCKER_KWARGS,
        pool="gemini_api",
    ).expand(command=filings_commands(companies))

    run_news_tasks = DockerOperator.partial(
        task_id="run_news_pipeline",
        map_index_template="{{ task.command }}",
        **_COMMON_DOCKER_KWARGS,
    ).expand(command=news_commands(companies))

    run_anomaly_explanations = app_task(
        task_id="run_anomaly_explanations",
        command="stock_news.pipelines.anomaly_explanations",
        pool="gemini_api",
        trigger_rule="all_done",
    )
    [run_digest, run_filings_tasks, run_news_tasks] >> run_anomaly_explanations


daily_pipeline()
