"""
Manual debug script - runs each EDGAR processing step for one filing and
prints intermediate output. Does not touch the database.

Usage:
    python -m stock_news.debug.inspect_filing --cik 0000320193 --form 10-Q
    python -m stock_news.debug.inspect_filing --cik 0000937966 --form 20-F
"""

from __future__ import annotations

import argparse
import os

from stock_news.ingestion.fetchers import fetch_edgar_filing_text, fetch_edgar_filings
from stock_news.processing.edgar.html_cleaning import clean_filing_html
from stock_news.processing.edgar.routing.classifier import classify_filing
from stock_news.processing.edgar.signals import extract_filing_signal
from stock_news.storage.db import get_session_factory
from stock_news.storage.models import Company


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cik", required=True)
    parser.add_argument("--form", default=None, help="e.g. 10-Q, 8-K, 20-F")
    parser.add_argument(
        "--index", type=int, default=0, help="which matching filing (0 = most recent)"
    )
    parser.add_argument(
        "--name", default=None, help="override company name (skips DB lookup)"
    )
    args = parser.parse_args()

    user_agent = os.environ["EDGAR_USER_AGENT"]
    form_types = (args.form,) if args.form else ("8-K", "10-Q", "10-K", "20-F", "6-K")

    if args.name:
        company_name = args.name
    else:
        session_factory = get_session_factory()
        with session_factory() as session:
            company = session.get(Company, args.cik)
        company_name = company.name if company else args.cik
        print(f"Company name (from DB): {company_name}\n")

    filings = fetch_edgar_filings(
        args.cik, user_agent, form_types=form_types, limit=args.index + 1
    )
    if not filings:
        print("No filings found.")
        return

    filing = filings[args.index]
    print(f"Filing: {filing}\n")

    raw_html = fetch_edgar_filing_text(filing["primary_doc_url"], user_agent)
    print(f"Raw HTML length: {len(raw_html)}")

    cleaned = clean_filing_html(raw_html, filing["form"].upper() == "20-F")
    print(f"Cleaned text length: {len(cleaned)}")
    print("---- First 1000 chars ----")
    print(cleaned[:1000], "\n")

    classification = classify_filing(cleaned, form=filing["form"])
    print(f"should_extract: {classification.should_extract}")
    print(f"item_codes: {classification.item_codes}")
    for name, text in classification.sections.items():
        print(f"\n---- Section: {name} ({len(text)} chars) ----")
        print(text[:1500])

    if classification.should_extract:
        signal = extract_filing_signal(classification, company_name=company_name)
        print("\n---- Extracted signal ----")
        print(signal)
    else:
        print("\nshould_extract is False - no LLM call made.")


if __name__ == "__main__":
    main()
