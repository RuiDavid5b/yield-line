"""
End-to-end pipeline for a single company: fetch -> classify -> extract ->
upsert, for both filing signals and financial metrics.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_news.config import get_settings
from stock_news.ingestion.fetchers import (
    fetch_company_facts,
    fetch_edgar_filing_text,
    fetch_edgar_filings,
)
from stock_news.processing.edgar.extraction import (
    TAG_CANDIDATES_BY_TAXONOMY,
    build_unit_priority,
    extract_quarterly_metric,
)
from stock_news.processing.edgar.html_cleaning import clean_filing_html
from stock_news.processing.edgar.routing.classifier import classify_filing
from stock_news.processing.edgar.signals import extract_filing_signal
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import (
    upsert_filing_signal,
    upsert_financial_metrics,
)
from stock_news.storage.models import Company, FilingSignal

logger = logging.getLogger(__name__)

FILING_FORM_TYPES = ("8-K", "10-Q", "10-K", "20-F", "6-K")


@dataclass
class PipelineResult:
    cik: str
    filings_seen: int = 0
    filings_skipped_already_processed: int = 0
    filings_processed: int = 0
    filings_failed: int = 0
    metrics_upserted: int = 0
    errors: list[str] = field(default_factory=list)


def _get_already_processed_accessions(session: Session, cik: str) -> set[str]:
    return set(
        session.scalars(
            select(FilingSignal.accession_number).where(FilingSignal.cik == cik)
        ).all()
    )


def _process_one_filing(
    session: Session,
    cik: str,
    company_name: str,
    filing: dict,
    user_agent: str,
    llm_model_name: str | None,
) -> None:
    text = fetch_edgar_filing_text(filing["primary_doc_url"], user_agent)
    cleaned_text = clean_filing_html(
        text, detect_font_headings=(filing["form"].upper() == "20-F")
    )
    classification = classify_filing(cleaned_text, form=filing["form"])

    extracted = None
    if classification.should_extract:
        kwargs = {"model_name": llm_model_name} if llm_model_name else {}
        extracted = extract_filing_signal(
            classification, company_name=company_name, **kwargs
        )

    upsert_filing_signal(
        session,
        cik=cik,
        accession_number=filing["accession_number"],
        form=filing["form"],
        item_codes=classification.item_codes,
        filed_date=filing["filing_date"],
        extracted=extracted,
    )
    session.commit()
    logger.info(
        "Processed filing %s (%s, %s) for CIK %s",
        filing["accession_number"],
        filing["form"],
        filing["filing_date"],
        cik,
    )


def _detect_taxonomy(facts: dict[str, Any]) -> str:
    available = facts.get("facts", {})
    if "us-gaap" in available:
        return "us-gaap"
    if "ifrs-full" in available:
        return "ifrs-full"
    raise ValueError("Company facts contain neither us-gaap nor ifrs-full data")


def _run_financial_metrics(session: Session, cik: str, user_agent: str) -> int:
    facts = fetch_company_facts(cik, user_agent)
    taxonomy = _detect_taxonomy(facts)
    candidates_by_metric = TAG_CANDIDATES_BY_TAXONOMY[taxonomy]

    company = session.get(Company, cik)
    reporting_currency = company.reporting_currency if company else "USD"
    currencies = ["USD"] if reporting_currency == "USD" else ["USD", reporting_currency]

    total_rows = 0
    for metric_name, candidate_tags in candidates_by_metric.items():
        rows = extract_quarterly_metric(
            facts,
            cik=cik,
            metric_name=metric_name,
            candidate_tags=candidate_tags,
            units=build_unit_priority(metric_name, currencies),
            taxonomy=taxonomy,
        )
        upsert_financial_metrics(session, rows)
        session.commit()
        total_rows += len(rows)

    return total_rows


def run_company_pipeline(
    cik: str,
    user_agent: str,
    session: Session,
    form_types: tuple[str, ...] = FILING_FORM_TYPES,
    filing_limit: int | None = 10,
    llm_model_name: str | None = None,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> PipelineResult:
    """
    Run the full fetch -> classify -> extract -> upsert pipeline for one
    company: filing signals (8-K/10-Q/10-K) and financial metrics (XBRL).
    """
    result = PipelineResult(cik=cik)

    company = session.get(Company, cik)
    company_name = company.name if company else cik

    already_processed = _get_already_processed_accessions(session, cik)

    filings = fetch_edgar_filings(
        cik,
        user_agent,
        form_types=form_types,
        limit=filing_limit,
        start_date=start_date,
        end_date=end_date,
    )
    result.filings_seen = len(filings)

    for i, filing in enumerate(filings, start=1):
        if filing["accession_number"] in already_processed:
            result.filings_skipped_already_processed += 1
            continue

        logger.info(
            "Processing filing %d/%d for CIK %s: %s",
            i,
            len(filings),
            cik,
            filing["accession_number"],
        )

        try:
            _process_one_filing(
                session, cik, company_name, filing, user_agent, llm_model_name
            )
            result.filings_processed += 1
        except Exception as exc:
            session.rollback()
            logger.exception(
                "Failed processing filing %s for CIK %s",
                filing.get("accession_number"),
                cik,
            )
            result.filings_failed += 1
            result.errors.append(f"{filing.get('accession_number')}: {exc}")

    try:
        result.metrics_upserted = _run_financial_metrics(session, cik, user_agent)
    except Exception as exc:
        session.rollback()
        logger.exception("Failed processing financial metrics for CIK %s", cik)
        result.errors.append(f"financial_metrics: {exc}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the filings pipeline for one company."
    )
    parser.add_argument("--cik", required=True)
    parser.add_argument(
        "--exclude-8k",
        action="store_true",
        help="Skip 8-K filings (useful for backfill).",
    )
    parser.add_argument(
        "--filing-limit",
        type=int,
        default=None,
        help="Maximum number of filings to process. Omit for no limit.",
    )
    parser.add_argument(
        "--start-date",
        type=dt.date.fromisoformat,
        default=None,
        help="Only process filings filed on/after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=dt.date.fromisoformat,
        default=None,
        help="Only process filings filed on/before this date (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    session_factory = get_session_factory()
    form_types = tuple(
        f for f in FILING_FORM_TYPES if not (args.exclude_8k and f == "8-K")
    )
    with session_factory() as session:
        result = run_company_pipeline(
            cik=args.cik,
            user_agent=settings.edgar_user_agent,
            session=session,
            form_types=form_types,
            filing_limit=args.filing_limit,
            start_date=args.start_date,
            end_date=args.end_date,
        )

    logger.info("Filings pipeline result: %s", result)
    if result.errors:
        sys.exit(1)
