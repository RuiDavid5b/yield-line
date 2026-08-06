"""
Unit tests for processing.news - pure functions, synthetic data only.
"""

import datetime as dt

from stock_news.processing.news import transform_news_articles


class TestTransformNewsArticles:
    def test_empty_input(self):
        assert transform_news_articles([], cik="0000320193") == []

    def test_maps_fields_correctly(self):
        articles = [
            {
                "title": "Company X announces new fab",
                "description": "Details of the announcement.",
                "url": "https://example.com/article-1",
                "published": "2026-05-01T12:00:00",
                "author": "Jane Doe",
            }
        ]
        result = transform_news_articles(articles, cik="0000320193")

        assert len(result) == 1
        row = result[0]
        assert row["cik"] == "0000320193"
        assert row["url"] == "https://example.com/article-1"
        assert row["title"] == "Company X announces new fab"
        assert row["description"] == "Details of the announcement."
        assert row["author"] == "Jane Doe"
        assert row["published_at"] == dt.datetime(2026, 5, 1, 12, 0, 0)

    def test_drops_articles_without_url(self):
        articles = [
            {"title": "No url here", "url": None, "published": "2026-05-01T12:00:00"},
            {
                "title": "Has url",
                "url": "https://example.com/article-2",
                "published": None,
            },
        ]
        result = transform_news_articles(articles, cik="0000320193")

        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/article-2"

    def test_missing_title_defaults_to_empty_string(self):
        articles = [{"url": "https://example.com/article-3"}]
        result = transform_news_articles(articles, cik="0000320193")

        assert result[0]["title"] == ""

    def test_unparseable_published_date_becomes_none(self):
        articles = [
            {
                "title": "Bad date",
                "url": "https://example.com/article-4",
                "published": "not a real date",
            }
        ]
        result = transform_news_articles(articles, cik="0000320193")

        assert result[0]["published_at"] is None

    def test_missing_published_becomes_none(self):
        articles = [{"title": "No date field", "url": "https://example.com/article-5"}]
        result = transform_news_articles(articles, cik="0000320193")

        assert result[0]["published_at"] is None

    def test_missing_description_and_author_become_none(self):
        articles = [{"title": "Minimal", "url": "https://example.com/article-6"}]
        result = transform_news_articles(articles, cik="0000320193")

        assert result[0]["description"] is None
        assert result[0]["author"] is None

    def test_multiple_articles_preserved_in_order(self):
        articles = [
            {"title": "First", "url": "https://example.com/a"},
            {"title": "Second", "url": "https://example.com/b"},
        ]
        result = transform_news_articles(articles, cik="0000320193")

        assert [r["title"] for r in result] == ["First", "Second"]
