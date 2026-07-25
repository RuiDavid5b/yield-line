from unittest.mock import MagicMock, patch

import pandas as pd

from stock_news.ingestion.fetchers import (
    fetch_company_facts,
    fetch_edgar_filing_text,
    fetch_edgar_filings,
    fetch_news,
    fetch_prices,
)


@patch("stock_news.ingestion.fetchers.time.sleep")
@patch("stock_news.ingestion.fetchers.requests.get")
def test_fetch_edgar_filings_empty(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_get.return_value = mock_response

    filings = fetch_edgar_filings(
        "1234",
        "Test test@test.com",
    )

    assert filings == []


@patch("stock_news.ingestion.fetchers.time.sleep")
@patch("stock_news.ingestion.fetchers.requests.get")
def test_fetch_edgar_filings_filters_forms(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "filings": {
            "recent": {
                "form": ["8-K", "10-K", "10-Q"],
                "filingDate": [
                    "2025-01-01",
                    "2025-01-02",
                    "2025-01-03",
                ],
                "accessionNumber": [
                    "0001-01",
                    "0002-02",
                    "0003-03",
                ],
                "primaryDocument": [
                    "a.htm",
                    "b.htm",
                    "c.htm",
                ],
            }
        }
    }
    mock_get.return_value = mock_response

    filings = fetch_edgar_filings(
        cik="1234",
        user_agent="Test test@test.com",
    )

    assert len(filings) == 2
    assert filings[0]["form"] == "8-K"
    assert filings[1]["form"] == "10-Q"

    mock_response.raise_for_status.assert_called_once()
    mock_sleep.assert_called_once()


@patch("stock_news.ingestion.fetchers.time.sleep")
@patch("stock_news.ingestion.fetchers.requests.get")
def test_fetch_edgar_filing_text(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.text = "<html>filing</html>"
    mock_get.return_value = mock_response

    text = fetch_edgar_filing_text(
        "https://example.com",
        "Test test@test.com",
    )

    assert text == "<html>filing</html>"
    mock_response.raise_for_status.assert_called_once()
    mock_sleep.assert_called_once()


@patch("stock_news.ingestion.fetchers.time.sleep")
@patch("stock_news.ingestion.fetchers.requests.get")
def test_fetch_company_facts(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "cik": 883241,
        "entityName": "SYNOPSYS INC",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "units": {
                        "USD": [
                            {
                                "start": "2026-02-01",
                                "end": "2026-04-30",
                                "val": 2275985000,
                                "accn": "0000883241-26-000018",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-05-27",
                                "frame": "CY2026Q1",
                            }
                        ]
                    },
                }
            }
        },
    }
    mock_get.return_value = mock_response

    facts = fetch_company_facts("883241", "Test test@test.com")

    assert facts["entityName"] == "SYNOPSYS INC"
    assert "Revenues" in facts["facts"]["us-gaap"]

    mock_response.raise_for_status.assert_called_once()
    mock_sleep.assert_called_once()


@patch("stock_news.ingestion.fetchers.time.sleep")
@patch("stock_news.ingestion.fetchers.requests.get")
def test_fetch_company_facts_pads_cik_and_sends_user_agent(mock_get, mock_sleep):
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_get.return_value = mock_response

    fetch_company_facts("1045810", "Test test@test.com")

    called_url = mock_get.call_args[0][0]
    assert called_url == "https://data.sec.gov/api/xbrl/companyfacts/CIK0001045810.json"

    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["User-Agent"] == "Test test@test.com"


@patch("stock_news.ingestion.fetchers.yf.Ticker")
def test_fetch_prices(mock_ticker):
    df = pd.DataFrame(
        {
            "Open": [1],
            "Close": [2],
        }
    )

    ticker = MagicMock()
    ticker.history.return_value = df
    mock_ticker.return_value = ticker

    result = fetch_prices("SNPS")

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1

    ticker.history.assert_called_once_with(
        period="5d",
        interval="1d",
    )


@patch("stock_news.ingestion.fetchers.requests.get")
def test_fetch_news(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "news": [
            {
                "title": "Synopsys announces...",
                "description": "News description",
                "url": "https://example.com",
                "published": "2026-07-24",
                "author": "Reporter",
            }
        ]
    }
    mock_get.return_value = mock_response

    articles = fetch_news(
        terms=["Synopsys", "SNPS"],
        api_key="abc123",
    )

    assert len(articles) == 1
    assert articles[0]["title"] == "Synopsys announces..."

    mock_response.raise_for_status.assert_called_once()

    mock_get.assert_called_once()

    # Verify the fetcher built the expected query
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["query"] == '"Synopsys" OR "SNPS"'


@patch("stock_news.ingestion.fetchers.requests.get")
def test_fetch_news_empty(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"news": []}
    mock_get.return_value = mock_response

    articles = fetch_news(
        terms=["Synopsys", "SNPS"],
        api_key="key",
    )

    assert articles == []

    _, kwargs = mock_get.call_args
    assert kwargs["params"]["query"] == '"Synopsys" OR "SNPS"'
