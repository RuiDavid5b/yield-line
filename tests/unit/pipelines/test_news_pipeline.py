"""
Tests for pipelines.news.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from stock_news.pipelines.news import run_news_pipeline


class TestRunNewsPipelineUnit:
    @patch("stock_news.pipelines.news.upsert_news_articles")
    @patch("stock_news.pipelines.news.fetch_news")
    def test_happy_path_upserts_all_articles(self, mock_fetch, mock_upsert):
        mock_fetch.return_value = [
            {
                "title": "Article one",
                "description": "Desc one",
                "url": "https://example.com/1",
                "published": "2026-05-01T12:00:00",
                "author": "Author A",
            },
            {
                "title": "Article two",
                "description": "Desc two",
                "url": "https://example.com/2",
                "published": "2026-05-02T09:00:00",
                "author": "Author B",
            },
        ]

        result = run_news_pipeline(
            cik="0000320193",
            terms=["Apple"],
            api_key="fake-key",
            session=MagicMock(),
        )

        assert result.error is None
        assert result.articles_fetched == 2
        assert result.articles_upserted == 2
        assert result.articles_skipped_no_url == 0
        mock_upsert.assert_called_once()

    @patch("stock_news.pipelines.news.upsert_news_articles")
    @patch("stock_news.pipelines.news.fetch_news")
    def test_articles_without_url_are_skipped_and_counted(
        self, mock_fetch, mock_upsert
    ):
        mock_fetch.return_value = [
            {"title": "Has url", "url": "https://example.com/1"},
            {"title": "No url", "url": None},
        ]

        result = run_news_pipeline(
            cik="0000320193",
            terms=["Apple"],
            api_key="fake-key",
            session=MagicMock(),
        )

        assert result.articles_fetched == 2
        assert result.articles_upserted == 1
        assert result.articles_skipped_no_url == 1

    @patch("stock_news.pipelines.news.fetch_news")
    def test_no_articles_returned_is_not_an_error(self, mock_fetch):
        mock_fetch.return_value = []

        result = run_news_pipeline(
            cik="0000320193",
            terms=["Apple"],
            api_key="fake-key",
            session=MagicMock(),
        )

        assert result.error is None
        assert result.articles_fetched == 0
        assert result.articles_upserted == 0

    @patch("stock_news.pipelines.news.fetch_news")
    def test_fetch_failure_captured_on_result_not_raised(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("api down")

        result = run_news_pipeline(
            cik="0000320193",
            terms=["Apple"],
            api_key="fake-key",
            session=MagicMock(),
        )

        assert result.error is not None
        assert "api down" in result.error
        assert result.articles_fetched == 0

    @patch("stock_news.pipelines.news.upsert_news_articles")
    @patch("stock_news.pipelines.news.fetch_news")
    def test_upsert_failure_captured_on_result_not_raised(
        self, mock_fetch, mock_upsert
    ):
        mock_fetch.return_value = [{"title": "Article", "url": "https://example.com/1"}]
        mock_upsert.side_effect = RuntimeError("db unavailable")

        result = run_news_pipeline(
            cik="0000320193",
            terms=["Apple"],
            api_key="fake-key",
            session=MagicMock(),
        )

        assert result.error is not None
        assert "db unavailable" in result.error
        assert result.articles_upserted == 0
