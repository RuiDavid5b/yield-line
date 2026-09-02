"""
Processes raw fetched news into clean rows.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _truncate(value: str | None, max_length: int) -> str | None:
    if value is None or len(value) <= max_length:
        return value
    return value[: max_length - 1] + "…"


def _parse_published_at(published: str | None) -> dt.datetime | None:
    if not published:
        return None
    try:
        return dt.datetime.fromisoformat(published)
    except ValueError:
        logger.warning("Could not parse published date: %r", published)
        return None


def transform_news_articles(
    articles: list[dict[str, Any]], cik: str
) -> list[dict[str, Any]]:
    """
    Convert raw ingestion.fetchers.fetch_news() output into rows matching
    the NewsArticle schema, associated with a single company (cik).

    Duplicate URLs within the same batch are skipped after the first
    occurrence - handles the case where a multi-term OR query can return
    the same article more than once (it matches on more than one term).
    """
    seen_urls: set[str] = set()
    rows: list[dict[str, Any]] = []
    for article in articles:
        url = article.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        rows.append(
            {
                "cik": cik,
                "url": url,
                "title": _truncate(article.get("title") or "", 500),
                "description": _truncate(article.get("description"), 2000),
                "author": _truncate(article.get("author"), 255),
                "published_at": _parse_published_at(article.get("published")),
            }
        )
    return rows
