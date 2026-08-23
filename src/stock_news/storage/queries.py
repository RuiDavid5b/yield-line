"""
Read-side composition over Redis + Postgres for data written by the
digest pipeline.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from sqlalchemy.orm import Session

from stock_news.storage.loaders import (
    get_all_companies,
    get_benchmark_returns,
    get_digest_results,
)
from stock_news.storage.redis_client import (
    DIGEST_SCHEMA_VERSION,
    read_digest,
    write_digest,
)

logger = logging.getLogger(__name__)


def get_digest(session: Session, date: dt.date) -> dict[str, Any] | None:
    """
    Fetch the digest for one date: Redis first, falling back to
    reconstructing from Postgres on a miss (expired past the 90-day TTL,
    never cached, or a schema-version mismatch). A successful Postgres
    reconstruction is written back to Redis before returning, so a
    repeated query for the same date is fast on the next call.
    """
    cached = read_digest(date)
    if cached is not None and cached.get("version") == DIGEST_SCHEMA_VERSION:
        return cached

    if cached is not None:
        logger.warning(
            "Cached digest for %s has stale schema version %s (current: %s) - "
            "reconstructing from Postgres",
            date,
            cached.get("version"),
            DIGEST_SCHEMA_VERSION,
        )

    digest_rows = get_digest_results(session, date)
    if not digest_rows:
        return None

    segment_by_cik = {
        c["cik"]: c["industry_segment"] for c in get_all_companies(session)
    }
    companies = [
        {**row, "industry_segment": segment_by_cik.get(row["cik"])}
        for row in digest_rows
    ]

    benchmark_returns = get_benchmark_returns(session, date)
    digest = {
        "companies": companies,
        "benchmarks": {
            "soxx_return": benchmark_returns.get("SOXX"),
            "smh_return": benchmark_returns.get("SMH"),
            "spy_return": benchmark_returns.get("SPY"),
        },
    }

    try:
        write_digest(date, digest)
    except Exception:
        logger.warning(
            "Failed repopulating Redis after Postgres fallback for %s",
            date,
            exc_info=True,
        )

    return digest


def get_latest_digest(session: Session) -> dict[str, Any] | None:
    """
    Fetch the most recently cached digest.
    """
    from stock_news.storage.redis_client import read_latest_digest

    return read_latest_digest()
