"""
Manually-triggered backfill DAG: fetches ~5 years of filings/metrics and
price history for all tracked companies. Not scheduled - run once (or a
few times, if the Gemini rate limit budget runs out mid-run) to seed
history, then the daily DAG takes over.

Excludes 8-K from filing backfill: high volume, mostly routine, and
anything material is reliably re-surfaced in the next 10-Q/10-K, which
backfill still captures. Metrics need no date range at all - SEC's
companyfacts endpoint always returns full reported history in one call.

No digest or anomaly-explanation tasks here deliberately - computing a
digest per historical date, or an agent explanation per historical
anomaly, is expensive and out of scope for a data backfill. Those stay
exclusively in daily_pipeline, operating on data this DAG seeds.

Safely re-runnable: run_company_pipeline's already_processed check and
run_price_pipeline's upsert-on-conflict mean a partial run (e.g. cut
short by the daily Gemini budget) can simply be triggered again -
already-processed filings and already-stored prices are skipped/
overwritten harmlessly, so only genuinely remaining work happens.
"""

from __future__ import annotations

import datetime as dt
import json
import os

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import dag, task

APP_IMAGE = "stock-news-app:latest"
NETWORK = "stock_news_net"
BACKFILL_YEARS = 1

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
    schedule=None,
    start_date=dt.datetime(2025, 1, 1),
    catchup=False,
    tags=["stock_news", "backfill"],
)
def backfill_pipeline():

    list_companies = app_task(
        task_id="list_companies",
        command="stock_news.scripts.list_companies",
        do_xcom_push=True,
    )

    @task
    def parse_companies(raw: str, **context) -> list[dict]:
        """
        Parses the full company list, then optionally filters it down to
        just the CIKs passed via dag_run.conf - e.g. triggering with
        config {"ciks": ["0000937966", "0001046179"]} runs backfill only
        for those two.
        """
        all_companies = json.loads(raw)
        requested_ciks = context["dag_run"].conf.get("ciks") if context["dag_run"].conf else None
        if requested_ciks:
            return [c for c in all_companies if c["cik"] in requested_ciks]
        return all_companies

    companies = parse_companies(list_companies.output)

    @task
    def backfill_filings_commands(companies: list[dict]) -> list[str]:
        start = (dt.date.today() - dt.timedelta(days=365 * BACKFILL_YEARS)).isoformat()
        end = dt.date.today().isoformat()
        return [
            (
                f"stock_news.pipelines.filings --cik {c['cik']} "
                f"--start-date {start} --end-date {end} "
                f"--exclude-8k --filing-limit 1000"
            )
            for c in companies
        ]

    @task
    def backfill_prices_commands(companies: list[dict]) -> list[str]:
        start = (dt.date.today() - dt.timedelta(days=365 * BACKFILL_YEARS)).isoformat()
        end = dt.date.today().isoformat()
        return [
            f"stock_news.pipelines.stock_prices --cik {c['cik']} --ticker {c['ticker']} "
            f"--start-date {start} --end-date {end}"
            for c in companies
        ]

    DockerOperator.partial(
        task_id="backfill_filings",
        image=APP_IMAGE,
        network_mode=NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        environment=APP_ENV,
        mount_tmp_dir=False,
        pool="gemini_api",
        retries=0,
    ).expand(command=backfill_filings_commands(companies))

    DockerOperator.partial(
        task_id="backfill_prices",
        image=APP_IMAGE,
        network_mode=NETWORK,
        docker_url="unix://var/run/docker.sock",
        auto_remove="success",
        environment=APP_ENV,
        mount_tmp_dir=False,
    ).expand(command=backfill_prices_commands(companies))


backfill_pipeline()
