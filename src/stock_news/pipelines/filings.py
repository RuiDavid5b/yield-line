"""
End-to-end pipeline for a single company: fetch -> classify -> extract ->
upsert, for both filing signals and financial metrics.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from stock_news.ingestion.fetchers import (
    fetch_company_facts,
    fetch_edgar_filing_text,
    fetch_edgar_filings,
)
from stock_news.processing.edgar.extraction import (
    GAAP_METRIC_UNITS,
    GAAP_TAG_CANDIDATES,
    extract_quarterly_metric,
)
from stock_news.processing.edgar.html_cleaning import clean_filing_html
from stock_news.processing.edgar.routing.classifier import classify_filing
from stock_news.processing.edgar.signals import extract_filing_signal
from stock_news.storage.loaders import (
    upsert_filing_signal,
    upsert_financial_metrics,
)
from stock_news.storage.models import FilingSignal

logger = logging.getLogger(__name__)

FILING_FORM_TYPES = ("8-K", "10-Q", "10-K")


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
    filing: dict,
    user_agent: str,
    groq_model_name: str | None,
) -> None:
    text = fetch_edgar_filing_text(filing["primary_doc_url"], user_agent)
    cleaned_text = clean_filing_html(text)
    classification = classify_filing(cleaned_text, form=filing["form"])

    extracted = None
    if classification.should_extract:
        kwargs = {"model_name": groq_model_name} if groq_model_name else {}
        extracted = extract_filing_signal(classification, **kwargs)

    upsert_filing_signal(
        session,
        cik=cik,
        accession_number=filing["accession_number"],
        form=filing["form"],
        item_codes=classification.item_codes,
        filed_date=dt.date.fromisoformat(filing["filing_date"]),
        extracted=extracted,
    )
    session.commit()


def _run_financial_metrics(session: Session, cik: str, user_agent: str) -> int:
    facts = fetch_company_facts(cik, user_agent)

    total_rows = 0
    for metric_name, candidate_tags in GAAP_TAG_CANDIDATES.items():
        rows = extract_quarterly_metric(
            facts,
            cik=cik,
            metric_name=metric_name,
            candidate_tags=candidate_tags,
            unit=GAAP_METRIC_UNITS.get(metric_name, "USD"),
        )
        upsert_financial_metrics(session, rows)
        session.commit()
        total_rows += len(rows)

    return total_rows


def run_company_pipeline(
    cik: str,
    user_agent: str,
    session: Session,
    filing_limit: int = 10,
    groq_model_name: str | None = None,
) -> PipelineResult:
    """
    Run the full fetch -> classify -> extract -> upsert pipeline for one
    company: filing signals (8-K/10-Q/10-K) and financial metrics (XBRL).
    """
    result = PipelineResult(cik=cik)

    already_processed = _get_already_processed_accessions(session, cik)

    filings = fetch_edgar_filings(
        cik, user_agent, form_types=FILING_FORM_TYPES, limit=filing_limit
    )
    result.filings_seen = len(filings)

    for filing in filings:
        if filing["accession_number"] in already_processed:
            result.filings_skipped_already_processed += 1
            continue

        try:
            _process_one_filing(session, cik, filing, user_agent, groq_model_name)
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
