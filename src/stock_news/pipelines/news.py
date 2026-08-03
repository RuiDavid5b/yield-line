"""
End-to-end pipeline for a single company's news: fetch -> transform ->
upsert.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from stock_news.ingestion.fetchers import fetch_news
from stock_news.processing.news import transform_news_articles
from stock_news.storage.loaders import upsert_news_articles

logger = logging.getLogger(__name__)


@dataclass
class NewsPipelineResult:
    cik: str
    articles_fetched: int = 0
    articles_upserted: int = 0
    articles_skipped_no_url: int = 0
    error: str | None = None


def run_news_pipeline(
    cik: str,
    terms: list[str],
    api_key: str,
    session: Session,
    language: str = "en",
    limit: int = 20,
) -> NewsPipelineResult:
    """
    Fetch recent news for one company (matched by search terms, typically
    the company name and any common aliases/tickers), transform, and
    upsert.

    Keyword arguments:
    cik: company CIK, used to associate articles with the company.
    terms: search terms passed to fetch_news (e.g. company name, ticker,
        known aliases) - OR'd together in the underlying query.
    """
    result = NewsPipelineResult(cik=cik)

    try:
        articles = fetch_news(terms, api_key=api_key, language=language, limit=limit)
    except Exception as exc:
        logger.exception("Failed fetching news for CIK %s (%s)", cik, terms)
        result.error = f"fetch: {exc}"
        return result

    result.articles_fetched = len(articles)

    rows = transform_news_articles(articles, cik)
    result.articles_skipped_no_url = len(articles) - len(rows)

    try:
        upsert_news_articles(session, rows)
        result.articles_upserted = len(rows)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed upserting news for CIK %s", cik)
        result.error = f"upsert: {exc}"
        return result

    return result
