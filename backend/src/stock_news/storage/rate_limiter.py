"""
Redis-backed sliding-window rate limiter for the Gemini API. State lives
in Redis (not in-process) because DockerOperator spawns a separate
container per company - there's no shared memory to throttle from.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from zoneinfo import ZoneInfo

import redis

from stock_news.config import get_settings

logger = logging.getLogger(__name__)

# Google's documented RPM is 15, but the practical ceiling before hitting
# the TPM cap for filing-sized documents is empirically closer to 3-5/min
# (per observed usage) - default conservative rather than the documented
# limit, since the documented limit isn't the one actually binding.
DEFAULT_RPM_LIMIT = 4
RPM_WINDOW_SECONDS = 60

# 500/day documented; leave headroom for the daily digest and any manual
# runs sharing the same key/budget.
DEFAULT_RPD_LIMIT = 450
GEMINI_QUOTA_TZ = ZoneInfo("America/Los_Angeles")


def _seconds_until_midnight_pacific() -> int:
    now_pacific = dt.datetime.now(GEMINI_QUOTA_TZ)
    tomorrow_midnight = (now_pacific + dt.timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return int((tomorrow_midnight - now_pacific).total_seconds())


class RateLimitExceededError(Exception):
    """Raised when the daily budget is exhausted - not retried, since
    waiting it out would mean blocking for up to 24h inside an Airflow
    task. Today's unprocessed filings are picked up tomorrow instead,
    since run_company_pipeline already skips already-processed
    accessions and simply leaves unprocessed ones for the next run."""


class RateLimiter:
    def __init__(self, key: str, limit: int, window_seconds: int):
        self._client = redis.Redis.from_url(
            str(get_settings().redis_url), decode_responses=True
        )
        self._key = key
        self._limit = limit
        self._window = window_seconds

    def _count_in_window(self, now: float) -> int:
        window_start = now - self._window
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(self._key, 0, window_start)
        pipe.zcard(self._key)
        _, count = pipe.execute()
        return count

    def record(self, now: float) -> None:
        self._client.zadd(self._key, {f"{now}:{id(now)}": now})
        self._client.expire(self._key, self._window * 2)


class DailyCounter:
    """
    Calendar-day-keyed counter, matching Gemini's RPD reset boundary.
    """

    def __init__(self, key_prefix: str):
        self._client = redis.Redis.from_url(
            str(get_settings().redis_url), decode_responses=True
        )
        self._key_prefix = key_prefix

    def _key(self) -> str:
        today_pacific = dt.datetime.now(GEMINI_QUOTA_TZ).date()
        return f"{self._key_prefix}:{today_pacific.isoformat()}"

    def count(self) -> int:
        value = self._client.get(self._key())
        return int(value) if value else 0

    def increment(self) -> None:
        key = self._key()
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, _seconds_until_midnight_pacific())
        pipe.execute()


def acquire_gemini_call(
    rpm_limit: int = DEFAULT_RPM_LIMIT,
    rpd_limit: int = DEFAULT_RPD_LIMIT,
    poll_interval: float = 5.0,
) -> None:
    """
    Call before every Gemini API call. Blocks (sleeping and re-checking)
    while the per-minute window is full - short waits, acceptable within
    a task's execution. Raises immediately if the daily budget is
    exhausted, rather than blocking for hours.
    """
    rpm = RateLimiter("rate_limit:gemini:rpm", rpm_limit, RPM_WINDOW_SECONDS)
    rpd = DailyCounter("rate_limit:gemini:rpd")

    if rpd.count() >= rpd_limit:
        raise RateLimitExceededError(
            f"Daily Gemini call budget ({rpd_limit}) exhausted for today - "
            "remaining filings will be picked up on the next run."
        )

    while True:
        now = time.time()
        if rpm._count_in_window(now) < rpm_limit:
            rpm.record(now)
            rpd.increment()
            return
        logger.info("Gemini RPM limit reached, waiting %.0fs", poll_interval)
        time.sleep(poll_interval)
