"""
Fetch functions for external data sources.
"""

import time
from typing import Any

import pandas as pd
import requests
import yfinance as yf

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_RATE_LIMIT_SECONDS = 0.15  # under the 10 req/sec limit


def fetch_edgar_filings(
    cik: str,
    user_agent: str,
    form_types: tuple[str, ...] = ("8-K", "10-Q"),
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Fetch recent filing metadata for a company from SEC EDGAR.
    """
    url = EDGAR_SUBMISSIONS_URL.format(cik=cik.zfill(10))
    headers = {"User-Agent": user_agent}

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    results: list[dict[str, Any]] = []
    for form, filing_date, accession, primary_doc in zip(
        forms, dates, accessions, primary_docs
    ):
        if form not in form_types:
            continue

        accession_nodash = accession.replace("-", "")
        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(cik)}/{accession_nodash}/{primary_doc}"
        )

        results.append(
            {
                "cik": cik,
                "form": form,
                "filing_date": filing_date,
                "accession_number": accession,
                "primary_document": primary_doc,
                "primary_doc_url": doc_url,
            }
        )

        if len(results) >= limit:
            break

    time.sleep(EDGAR_RATE_LIMIT_SECONDS)
    return results


def fetch_edgar_filing_text(doc_url: str, user_agent: str) -> str:
    """
    Fetch the raw text/HTML body of a single filing document.
    """
    headers = {"User-Agent": user_agent}
    response = requests.get(doc_url, headers=headers, timeout=15)
    response.raise_for_status()
    time.sleep(EDGAR_RATE_LIMIT_SECONDS)
    return response.text


COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def fetch_company_facts(cik: str, user_agent: str) -> dict[str, Any]:
    """
    Fetch all XBRL-tagged financial facts for a company from SEC EDGAR.
    """
    url = COMPANY_FACTS_URL.format(cik=cik.zfill(10))
    headers = {"User-Agent": user_agent}

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    time.sleep(EDGAR_RATE_LIMIT_SECONDS)
    return data


def fetch_prices(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """
    Fetch recent OHLCV price data for a ticker via yfinance.

    Returns a DataFrame with columns including Open, High, Low, Close,
    Volume, and a Date column (index reset). Empty DataFrame if no data
    is returned.
    """
    ticker_obj = yf.Ticker(ticker)
    history = ticker_obj.history(period=period, interval=interval)
    return history.reset_index()


CURRENTS_API_URL = "https://api.currentsapi.services/v1/search"


def fetch_news(
    terms: list[str],
    api_key: str,
    language: str = "en",
    limit: int = 20,
    require_any: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch recent news articles mentioning any of `terms`. If `require_any`
    is given, results must also match at least one of those terms -
    for disambiguating a company term that collides with common words
    (e.g. "Arm").
    """
    base = " OR ".join(f'"{term}"' for term in terms)
    query = f"({base})"
    if require_any:
        context = " OR ".join(f'"{term}"' for term in require_any)
        query = f"{query} AND ({context})"

    params = {
        "query": query,
        "language": language,
        "apiKey": api_key,
    }
    response = requests.get(CURRENTS_API_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    articles = data.get("news", [])[:limit]
    return [
        {
            "title": a.get("title"),
            "description": a.get("description"),
            "url": a.get("url"),
            "published": a.get("published"),
            "author": a.get("author"),
        }
        for a in articles
    ]
