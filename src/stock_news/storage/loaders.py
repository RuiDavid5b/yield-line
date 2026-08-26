"""
Processes rows into the database.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from stock_news.processing.edgar.signals import ExtractedFilingSignal
from stock_news.storage.models import (
    BenchmarkReturn,
    Company,
    DigestResult,
    FilingSignal,
    FinancialMetric,
    NewsArticle,
    PriceAnomaly,
    StockPrice,
)


def get_financial_metrics(
    session: Session,
    cik: str,
    tag: str | None = None,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch reported financial metrics for a company, optionally filtered
    to one XBRL tag (e.g. "CapitalExpenditures", "Revenues") and/or a
    date range on period_end, most recent first.
    """
    stmt = select(
        FinancialMetric.tag,
        FinancialMetric.period_start,
        FinancialMetric.period_end,
        FinancialMetric.period_type,
        FinancialMetric.value,
        FinancialMetric.unit,
        FinancialMetric.form,
        FinancialMetric.filed_date,
    ).where(FinancialMetric.cik == cik)

    if tag is not None:
        stmt = stmt.where(FinancialMetric.tag == tag)
    if start_date is not None:
        stmt = stmt.where(FinancialMetric.period_end >= start_date)
    if end_date is not None:
        stmt = stmt.where(FinancialMetric.period_end <= end_date)

    stmt = stmt.order_by(FinancialMetric.period_end.desc())
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = session.execute(stmt).all()
    return [dict(row._mapping) for row in rows]


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
            "unit": stmt.excluded.unit,
            "taxonomy": stmt.excluded.taxonomy,
            "accession_number": stmt.excluded.accession_number,
            "filed_date": stmt.excluded.filed_date,
        },
    )
    session.execute(stmt)


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


def get_filing_signals(
    session: Session,
    cik: str,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch filing signals for a company, optionally bounded by date range,
    most recent first. For agent tool use - e.g. "guidance shifts over
    the last 6 quarters".
    """
    stmt = select(
        FilingSignal.accession_number,
        FilingSignal.form,
        FilingSignal.filed_date,
        FilingSignal.guidance_commentary,
        FilingSignal.segment_commentary,
        FilingSignal.executive_quote_summary,
        FilingSignal.mentioned_customers,
        FilingSignal.mentioned_competitors,
    ).where(FilingSignal.cik == cik)

    if start_date is not None:
        stmt = stmt.where(FilingSignal.filed_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(FilingSignal.filed_date <= end_date)

    stmt = stmt.order_by(FilingSignal.filed_date.desc())
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = session.execute(stmt).all()
    return [dict(row._mapping) for row in rows]


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


def upsert_price_anomalies(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Insert rows produced by processing.stock_prices.detect_price_anomalies,
    already filtered down to is_anomaly=True rows, updating in place on
    conflict rather than raising or duplicating. One row per company per
    anomalous date.
    """
    if not rows:
        return

    stmt = pg_insert(PriceAnomaly).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cik", "date"],
        set_={
            "return_pct": stmt.excluded.return_pct,
            "z_score": stmt.excluded.z_score,
        },
    )
    session.execute(stmt)


def get_price_anomalies(
    session: Session,
    cik: str,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch detected anomalies for a company, optionally bounded by date
    range, most recent first.
    """
    stmt = select(
        PriceAnomaly.cik,
        PriceAnomaly.date,
        PriceAnomaly.return_pct,
        PriceAnomaly.z_score,
        PriceAnomaly.explanation,
        PriceAnomaly.explained_at,
    ).where(PriceAnomaly.cik == cik)

    if start_date is not None:
        stmt = stmt.where(PriceAnomaly.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(PriceAnomaly.date <= end_date)

    stmt = stmt.order_by(PriceAnomaly.date.desc())
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = session.execute(stmt).all()
    return [dict(row._mapping) for row in rows]


def get_unexplained_price_anomalies(
    session: Session, max_age_days: int = 7
) -> list[dict[str, Any]]:
    """
    Fetch all anomalies with no explanation yet, across all companies -
    what run_digest_pipeline's agent-wiring step should process each run.
    """
    cutoff = dt.date.today() - dt.timedelta(days=max_age_days)
    rows = session.execute(
        select(
            PriceAnomaly.id,
            PriceAnomaly.cik,
            PriceAnomaly.date,
            PriceAnomaly.return_pct,
            PriceAnomaly.z_score,
        )
        .where(PriceAnomaly.explanation.is_(None), PriceAnomaly.date >= cutoff)
        .order_by(PriceAnomaly.date.desc())
    ).all()
    return [dict(row._mapping) for row in rows]


def set_price_anomaly_explanation(
    session: Session, anomaly_id: int, explanation: str
) -> None:
    """
    Record an agent-generated explanation for one anomaly. Direct update
    by id, not an upsert.
    """
    session.execute(
        update(PriceAnomaly)
        .where(PriceAnomaly.id == anomaly_id)
        .values(explanation=explanation, explained_at=func.now())
    )


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

    numeric_fields = ("open", "high", "low", "close")
    results = []
    for row in rows:
        row_dict = dict(row._mapping)
        for field in numeric_fields:
            if row_dict[field] is not None:
                row_dict[field] = float(row_dict[field])
        results.append(row_dict)
    return results


def upsert_news_articles(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Insert rows produced by processing.news.transform_news_articles,
    updating in place on conflict rather than raising or duplicating.
    """
    if not rows:
        return

    stmt = pg_insert(NewsArticle).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cik", "url"],
        set_={
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "author": stmt.excluded.author,
            "published_at": stmt.excluded.published_at,
        },
    )
    session.execute(stmt)


def get_news_articles(
    session: Session,
    cik: str,
    start_date: dt.datetime | None = None,
    end_date: dt.datetime | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch stored news articles for a company, optionally bounded by
    published_at range, most recent first.
    """
    stmt = select(
        NewsArticle.cik,
        NewsArticle.url,
        NewsArticle.title,
        NewsArticle.description,
        NewsArticle.author,
        NewsArticle.published_at,
    ).where(NewsArticle.cik == cik)

    if start_date is not None:
        stmt = stmt.where(NewsArticle.published_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(NewsArticle.published_at <= end_date)

    stmt = stmt.order_by(NewsArticle.published_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit)

    rows = session.execute(stmt).all()
    return [dict(row._mapping) for row in rows]


def upsert_companies(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Insert or update company rows, typically from graph.loader parsing
    the seed graph YAML.
    """
    if not rows:
        return

    stmt = pg_insert(Company).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cik"],
        set_={
            "ticker": stmt.excluded.ticker,
            "name": stmt.excluded.name,
            "industry_segment": stmt.excluded.industry_segment,
            "reporting_currency": stmt.excluded.reporting_currency,
            "aliases": stmt.excluded.aliases,
            "news_disambiguation": stmt.excluded.news_disambiguation,
        },
    )
    session.execute(stmt)


def get_all_companies(session: Session) -> list[dict[str, Any]]:
    """
    Return all tracked companies as plain dicts, for Airflow dynamic task
    mapping (.expand()) over ingestion tasks. Plain dicts, not ORM
    instances, since these cross into Airflow's XCom/serialization layer.
    """
    companies = session.scalars(select(Company)).all()
    return [
        {
            "cik": c.cik,
            "ticker": c.ticker,
            "name": c.name,
            "industry_segment": c.industry_segment,
            "reporting_currency": c.reporting_currency,
            "aliases": c.aliases,
            "news_disambiguation": c.news_disambiguation,
        }
        for c in companies
    ]


def upsert_digest_results(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Insert rows produced by processing.digest.compute_company_digest
    (reshaped per-company), updating in place on conflict rather than
    raising or duplicating. One row per company per date.
    """
    if not rows:
        return

    stmt = pg_insert(DigestResult).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["cik", "date"],
        set_={
            "return_pct": stmt.excluded.return_pct,
            "peer_avg_return_pct": stmt.excluded.peer_avg_return_pct,
            "vs_peer_avg": stmt.excluded.vs_peer_avg,
            "vs_soxx": stmt.excluded.vs_soxx,
            "vs_smh": stmt.excluded.vs_smh,
            "vs_spy": stmt.excluded.vs_spy,
        },
    )
    session.execute(stmt)


def upsert_benchmark_returns(session: Session, rows: list[dict[str, Any]]) -> None:
    """
    Insert rows produced by processing.digest.fetch_benchmark_returns
    (reshaped per-ticker), updating in place on conflict rather than
    raising or duplicating. One row per benchmark ticker per date.
    """
    if not rows:
        return

    stmt = pg_insert(BenchmarkReturn).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker", "date"],
        set_={"return_pct": stmt.excluded.return_pct},
    )
    session.execute(stmt)


def get_digest_results(session: Session, date: dt.date) -> list[dict[str, Any]]:
    """
    Fetch all companies' digest rows for one date, as plain dicts.
    Mirrors the shape of Redis's digest:{date} blob's "companies" list,
    for reconstructing that blob on a cache miss. Numeric columns are
    cast to float, since every consumer (compute_company_digest,
    fetch_benchmark_returns, the Redis JSON blob) works in plain floats.
    """
    rows = session.execute(
        select(
            DigestResult.cik,
            DigestResult.return_pct,
            DigestResult.peer_avg_return_pct,
            DigestResult.vs_peer_avg,
            DigestResult.vs_soxx,
            DigestResult.vs_smh,
            DigestResult.vs_spy,
        ).where(DigestResult.date == date)
    ).all()

    numeric_fields = (
        "return_pct",
        "peer_avg_return_pct",
        "vs_peer_avg",
        "vs_soxx",
        "vs_smh",
        "vs_spy",
    )
    results = []
    for row in rows:
        row_dict = dict(row._mapping)
        for field in numeric_fields:
            if row_dict[field] is not None:
                row_dict[field] = float(row_dict[field])
        results.append(row_dict)
    return results


def get_benchmark_returns(session: Session, date: dt.date) -> dict[str, float | None]:
    """
    Fetch benchmark returns for one date as a ticker -> return_pct dict.
    Mirrors fetch_benchmark_returns()'s return shape, for reconstructing
    Redis's digest:{date} blob's "benchmarks" section on a cache miss.
    Cast to float for the same reason as get_digest_results.
    """
    rows = session.execute(
        select(BenchmarkReturn.ticker, BenchmarkReturn.return_pct).where(
            BenchmarkReturn.date == date
        )
    ).all()

    return {
        ticker: (float(return_pct) if return_pct is not None else None)
        for ticker, return_pct in rows
    }
