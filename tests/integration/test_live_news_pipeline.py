from __future__ import annotations

import os

import pytest

from stock_news.pipelines.news import run_news_pipeline
from stock_news.storage.models import Company

pytestmark = pytest.mark.requires_env("CURRENTS_API_KEY")

TEST_CIK = "0000320193"
TEST_TICKER = "AAPL"


@pytest.fixture
def session(db_session):
    db_session.add(
        Company(
            cik=TEST_CIK, ticker=TEST_TICKER, name="Apple Inc.", industry_segment="test"
        )
    )
    db_session.flush()
    yield db_session


def test_run_news_pipeline_fetches_and_persists_real_articles(session):
    result = run_news_pipeline(
        cik=TEST_CIK,
        terms=["Apple Inc"],
        api_key=os.environ["CURRENTS_API_KEY"],
        session=session,
    )

    assert result.error is None
    assert (
        result.articles_upserted
        == result.articles_fetched - result.articles_skipped_no_url
    )
