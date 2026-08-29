"""
Redis read/write for the daily digest. Redis holds only the trailing
DIGEST_TTL_SECONDS as a fast-read cache; Postgres (DigestResult /
BenchmarkReturn, via loaders.get_digest_results / get_benchmark_returns)
is the durable, unbounded history callers fall back to on a cache miss.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import redis

from stock_news.config import get_settings

DIGEST_TTL_SECONDS = (
    90 * 24 * 60 * 60
)  # ~1 quarter - matches the Postgres fallback boundary
DIGEST_SCHEMA_VERSION = 2

_LATEST_KEY = "digest:latest"


def _digest_key(date: dt.date) -> str:
    return f"digest:{date.isoformat()}"


def _client() -> redis.Redis:
    return redis.Redis.from_url(str(get_settings().redis_url), decode_responses=True)


def write_digest(date: dt.date, digest: dict[str, Any]) -> None:
    """
    Write a compute_company_digest() result to Redis under both
    digest:{date} (expires after DIGEST_TTL_SECONDS) and digest:latest
    (no TTL - always overwritten to reflect the most recent run, so
    readers don't need to know today's date to get current data).
    """
    payload = json.dumps(
        {"version": DIGEST_SCHEMA_VERSION, "date": date.isoformat(), **digest}
    )
    client = _client()
    client.set(_digest_key(date), payload, ex=DIGEST_TTL_SECONDS)
    client.set(_LATEST_KEY, payload)


def read_digest(date: dt.date) -> dict[str, Any] | None:
    """
    Read a digest for one date. Returns None on a cache miss - expired
    (>90 days), never written, or otherwise absent.
    """
    raw = _client().get(_digest_key(date))
    return json.loads(raw) if raw is not None else None


def read_latest_digest() -> dict[str, Any] | None:
    """
    Read the most recently written digest
    """
    raw = _client().get(_LATEST_KEY)
    return json.loads(raw) if raw is not None else None
