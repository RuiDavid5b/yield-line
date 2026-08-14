"""
Integration tests for storage.redis_client - hits a real Redis instance.
Skipped if REDIS_URL isn't set.
"""

import datetime as dt

import pytest

from stock_news.storage import redis_client

pytestmark = pytest.mark.requires_env("REDIS_URL")

TEST_DATE = dt.date(2025, 6, 15)


@pytest.fixture(autouse=True)
def cleanup():
    yield
    client = redis_client._client()
    client.delete(redis_client._digest_key(TEST_DATE))
    client.delete(redis_client._LATEST_KEY)


def test_write_then_read_digest_round_trips():
    digest = {
        "companies": [{"cik": "0001045810", "return_pct": 0.03}],
        "benchmarks": {"soxx_return": 0.01},
    }
    redis_client.write_digest(TEST_DATE, digest)

    result = redis_client.read_digest(TEST_DATE)
    assert result["companies"] == digest["companies"]
    assert result["benchmarks"] == digest["benchmarks"]
    assert result["version"] == redis_client.DIGEST_SCHEMA_VERSION


def test_read_missing_date_returns_none():
    assert redis_client.read_digest(dt.date(2020, 1, 1)) is None


def test_write_updates_latest():
    digest = {"companies": [], "benchmarks": {}}
    redis_client.write_digest(TEST_DATE, digest)

    assert redis_client.read_latest_digest()["date"] == TEST_DATE.isoformat()


def test_second_write_overwrites_latest_not_previous_date():
    redis_client.write_digest(
        TEST_DATE, {"companies": [{"cik": "A"}], "benchmarks": {}}
    )
    later_date = TEST_DATE + dt.timedelta(days=1)
    redis_client.write_digest(
        later_date, {"companies": [{"cik": "B"}], "benchmarks": {}}
    )

    assert redis_client.read_latest_digest()["date"] == later_date.isoformat()
    assert redis_client.read_digest(TEST_DATE)["companies"][0]["cik"] == "A"

    redis_client._client().delete(redis_client._digest_key(later_date))
