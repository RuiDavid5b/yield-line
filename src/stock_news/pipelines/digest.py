"""
End-to-end daily digest pipeline: pull stored prices -> compute returns
-> compute peer/benchmark digest -> upsert to Postgres -> cache in Redis.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from stock_news.processing.digest import compute_company_digest, fetch_benchmark_returns
from stock_news.processing.stock_prices import compute_daily_returns
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import (
    get_all_companies,
    get_stock_price_history,
    upsert_benchmark_returns,
    upsert_digest_results,
)
from stock_news.storage.redis_client import write_digest

logger = logging.getLogger(__name__)


@dataclass
class DigestPipelineResult:
    date: dt.date
    companies_seen: int = 0
    companies_missing_data: int = 0
    digest_rows_upserted: int = 0
    benchmark_rows_upserted: int = 0
    redis_written: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def _company_return_for_date(
    session: Session, cik: str, industry_segment: str, target_date: dt.date
) -> dict[str, Any]:
    """
    Reduce one company's stored price history down to its return_pct for
    a single date. return_pct is None if that date has no stored row
    (fetch gap, weekend/holiday, or not yet IPO'd).
    """
    history = get_stock_price_history(session, cik)
    with_returns = compute_daily_returns(history)
    row = next((r for r in with_returns if r["date"] == target_date), None)
    return {
        "cik": cik,
        "industry_segment": industry_segment,
        "return_pct": row["return_pct"] if row else None,
    }


def run_digest_pipeline(
    session: Session, date: dt.date | None = None
) -> DigestPipelineResult:
    """
    Compute and persist the digest for one date (default: today).
    """
    target_date = date or dt.date.today()
    result = DigestPipelineResult(date=target_date)

    companies = get_all_companies(session)
    result.companies_seen = len(companies)

    company_returns = [
        _company_return_for_date(session, c["cik"], c["industry_segment"], target_date)
        for c in companies
    ]
    result.companies_missing_data = sum(
        1 for c in company_returns if c["return_pct"] is None
    )

    try:
        benchmark_returns = fetch_benchmark_returns()
    except Exception as exc:
        logger.exception("Failed fetching benchmark returns for %s", target_date)
        result.error = f"benchmark_fetch: {exc}"
        return result

    digest = compute_company_digest(company_returns, benchmark_returns)

    digest_rows = [
        {
            "cik": c["cik"],
            "date": target_date,
            "return_pct": c["return_pct"],
            "peer_avg_return_pct": c["peer_avg_return_pct"],
            "vs_peer_avg": c["vs_peer_avg"],
            "vs_soxx": c["vs_soxx"],
            "vs_smh": c["vs_smh"],
            "vs_spy": c["vs_spy"],
            "cross_sectional_z_score": c["cross_sectional_z_score"],
            "is_cross_sectional_anomaly": c["is_cross_sectional_anomaly"],
        }
        for c in digest["companies"]
    ]
    benchmark_rows = [
        {"ticker": ticker, "date": target_date, "return_pct": return_pct}
        for ticker, return_pct in benchmark_returns.items()
    ]

    try:
        upsert_digest_results(session, digest_rows)
        upsert_benchmark_returns(session, benchmark_rows)
        session.commit()
        result.digest_rows_upserted = len(digest_rows)
        result.benchmark_rows_upserted = len(benchmark_rows)
    except Exception as exc:
        session.rollback()
        logger.exception("Failed upserting digest for %s", target_date)
        result.error = f"upsert: {exc}"
        return result

    try:
        write_digest(target_date, digest)
        result.redis_written = True
    except Exception as exc:
        logger.exception("Failed writing digest to Redis for %s", target_date)
        result.warnings.append(f"redis_write: {exc}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the daily digest pipeline.")
    parser.add_argument(
        "--date", default=None, help="ISO date (YYYY-MM-DD); defaults to today"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    target_date = dt.date.fromisoformat(args.date) if args.date else None
    session_factory = get_session_factory()
    with session_factory() as session:
        result = run_digest_pipeline(session, date=target_date)

    logger.info("Digest pipeline result: %s", result)
    if result.error:
        sys.exit(1)
