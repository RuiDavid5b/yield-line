"""
End-to-end pipeline for a single company's news: fetch -> transform ->
upsert.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass

from sqlalchemy.orm import Session

from stock_news.config import get_settings
from stock_news.ingestion.fetchers import fetch_news
from stock_news.processing.news import transform_news_articles
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import upsert_news_articles

logger = logging.getLogger(__name__)


@dataclass
class NewsPipelineResult:
    cik: str
    articles_fetched: int = 0
    articles_upserted: int = 0
    articles_skipped_no_url: int = 0
    articles_skipped_duplicate: int = 0
    error: str | None = None


def run_news_pipeline(
    cik: str,
    terms: list[str],
    api_key: str,
    session: Session,
    language: str = "en",
    limit: int = 20,
    require_any: list[str] | None = None,
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
        articles = fetch_news(
            terms,
            api_key=api_key,
            language=language,
            limit=limit,
            require_any=require_any,
        )
    except Exception as exc:
        logger.exception("Failed fetching news for CIK %s (%s)", cik, terms)
        result.error = f"fetch: {exc}"
        return result

    result.articles_fetched = len(articles)
    rows = transform_news_articles(articles, cik)
    result.articles_skipped_no_url = sum(1 for a in articles if not a.get("url"))
    result.articles_skipped_duplicate = (
        len(articles) - result.articles_skipped_no_url - len(rows)
    )

    try:
        upsert_news_articles(session, rows)
        session.commit()
        result.articles_upserted = len(rows)
    except Exception as exc:
        session.rollback()
        logger.exception("Failed upserting news for CIK %s", cik)
        result.error = f"upsert: {exc}"
        return result

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the news pipeline for one company."
    )
    parser.add_argument("--cik", required=True)
    parser.add_argument(
        "--terms",
        required=True,
        nargs="+",
        help="e.g. --terms 'NVIDIA Corporation' NVDA",
    )
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    session_factory = get_session_factory()
    with session_factory() as session:
        result = run_news_pipeline(
            cik=args.cik,
            terms=args.terms,
            api_key=settings.currents_api_key,
            session=session,
            limit=args.limit,
        )

    logger.info("News pipeline result: %s", result)
    if result.error:
        sys.exit(1)
