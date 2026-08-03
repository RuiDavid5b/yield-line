from __future__ import annotations

import os

import pytest

from stock_news.pipelines.news import run_news_pipeline
from stock_news.storage.db import get_session_factory
from stock_news.storage.models import Company, NewsArticle

pytestmark_integration = pytest.mark.skipif(
    not (os.environ.get("DATABASE_URL") and os.environ.get("CURRENTS_API_KEY")),
    reason="DATABASE_URL or CURRENTS_API_KEY not set - skipping integration tests",
)


TEST_CIK = "0000320193"
TEST_TICKER = "AAPL"


@pytest.fixture
def news_session():
    session_factory = get_session_factory()
    with session_factory() as session:
        session.execute(Company.__table__.delete().where(Company.cik == TEST_CIK))
        session.add(
            Company(cik=TEST_CIK, ticker=TEST_TICKER, name="Apple Inc.", subarea="test")
        )
        session.commit()

        yield session

        session.execute(
            NewsArticle.__table__.delete().where(NewsArticle.cik == TEST_CIK)
        )
        session.execute(Company.__table__.delete().where(Company.cik == TEST_CIK))
        session.commit()


@pytestmark_integration
def test_run_news_pipeline_fetches_and_persists_real_articles(news_session):
    result = run_news_pipeline(
        cik=TEST_CIK,
        terms=["Apple Inc"],
        api_key=os.environ["CURRENTS_API_KEY"],
        session=news_session,
    )

    assert result.error is None
    assert (
        result.articles_upserted
        == result.articles_fetched - result.articles_skipped_no_url
    )
