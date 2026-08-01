"""
Processes rows into the database.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from stock_news.processing.signals import ExtractedFilingSignal
from stock_news.storage.models import FilingSignal, FinancialMetric, StockPrice


def upsert_financial_metrics(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Insert rows produced by processing.extraction.extract_quarterly_metric,
    updating in place on conflict rather than raising or duplicating.
    """
    if not rows:
        return

    stmt = pg_insert(FinancialMetric).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cik", "tag", "period_start", "period_end", "form"],
        set_={
            "value": stmt.excluded.value,
            "accession_number": stmt.excluded.accession_number,
            "filed_date": stmt.excluded.filed_date,
        },
    )
    session.execute(stmt)
    session.commit()


def upsert_filing_signal(
    session: Session,
    cik: str,
    accession_number: str,
    form: str,
    item_codes: list[str],
    filed_date: dt.date,
    extracted: ExtractedFilingSignal | None,
) -> None:
    """
    Insert or update one filing_signals row.
    """
    values: dict[str, Any] = {
        "cik": cik,
        "accession_number": accession_number,
        "form": form,
        "item_codes": item_codes,
        "filed_date": filed_date,
        "guidance_commentary": extracted.guidance_commentary if extracted else None,
        "segment_commentary": extracted.segment_commentary if extracted else None,
        "executive_quote_summary": (
            extracted.executive_quote_summary if extracted else None
        ),
        "mentioned_customers": extracted.mentioned_customers if extracted else [],
        "mentioned_competitors": (extracted.mentioned_competitors if extracted else []),
    }

    stmt = pg_insert(FilingSignal).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cik", "accession_number"],
        set_={
            "form": stmt.excluded.form,
            "item_codes": stmt.excluded.item_codes,
            "filed_date": stmt.excluded.filed_date,
            "guidance_commentary": stmt.excluded.guidance_commentary,
            "segment_commentary": stmt.excluded.segment_commentary,
            "executive_quote_summary": stmt.excluded.executive_quote_summary,
            "mentioned_customers": stmt.excluded.mentioned_customers,
            "mentioned_competitors": stmt.excluded.mentioned_competitors,
        },
    )
    session.execute(stmt)
    session.commit()


def upsert_stock_prices(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Insert rows produced by processing.prices.transform_price_history,
    updating in place on conflict rather than raising or duplicating.
    """
    if not rows:
        return

    stmt = pg_insert(StockPrice).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cik", "date"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "volume": stmt.excluded.volume,
        },
    )
    session.execute(stmt)
    session.commit()


def get_stock_price_history(session: Session, cik: str) -> list[dict[str, Any]]:
    """
    Fetch all stored price rows for a company, as plain dicts, for use
    with processing.prices.compute_daily_returns / detect_price_anomalies.
    """
    rows = session.execute(
        select(
            StockPrice.cik,
            StockPrice.date,
            StockPrice.open,
            StockPrice.high,
            StockPrice.low,
            StockPrice.close,
            StockPrice.volume,
        ).where(StockPrice.cik == cik)
    ).all()

    return [dict(row._mapping) for row in rows]
