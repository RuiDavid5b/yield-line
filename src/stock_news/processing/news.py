"""
Processes raw fetched news into clean rows.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

logger = logging.getLogger(__name__)


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
    """
    rows: list[dict[str, Any]] = []
    for article in articles:
        url = article.get("url")
        if not url:
            continue

        rows.append(
            {
                "cik": cik,
                "url": url,
                "title": article.get("title") or "",
                "description": article.get("description"),
                "author": article.get("author"),
                "published_at": _parse_published_at(article.get("published")),
            }
        )

    return rows
