"""
End-to-end pipeline for a single company's stock prices: fetch -> transform
-> upsert -> anomaly detection over full stored history.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from stock_news.ingestion.fetchers import fetch_prices
from stock_news.processing.stock_prices import (
    compute_daily_returns,
    detect_price_anomalies,
    transform_price_history,
)
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import (
    get_stock_price_history,
    upsert_price_anomalies,
    upsert_stock_prices,
)

logger = logging.getLogger(__name__)


@dataclass
class PricePipelineResult:
    cik: str
    ticker: str
    rows_fetched: int = 0
    rows_upserted: int = 0
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def run_price_pipeline(
    cik: str,
    ticker: str,
    session: Session,
    period: str = "5d",
    interval: str = "1d",
    anomaly_window: int = 20,
    anomaly_min_periods: int = 10,
    z_threshold: float = 2.5,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
) -> PricePipelineResult:
    """
    Fetch recent price history for one company, upsert it, then run
    anomaly detection over the company's full stored history.
    """
    result = PricePipelineResult(cik=cik, ticker=ticker)

    try:
        history = fetch_prices(
            ticker,
            period=period,
            interval=interval,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        logger.exception("Failed fetching prices for %s (%s)", ticker, cik)
        result.error = f"fetch: {exc}"
        return result

    if history.empty:
        result.error = "fetch: no price data returned (empty history)"
        return result

    rows = transform_price_history(history, cik)
    result.rows_fetched = len(rows)

    try:
        upsert_stock_prices(session, rows)
        session.commit()
        result.rows_upserted = len(rows)
    except Exception as exc:
        session.rollback()
        logger.exception("Failed upserting prices for %s (%s)", ticker, cik)
        result.error = f"upsert: {exc}"
        return result

    full_history = get_stock_price_history(session, cik)
    with_returns = compute_daily_returns(full_history)
    with_anomalies = detect_price_anomalies(
        with_returns,
        window=anomaly_window,
        min_periods=anomaly_min_periods,
        z_threshold=z_threshold,
    )
    result.anomalies = [row for row in with_anomalies if row["is_anomaly"]]

    if result.anomalies:
        anomaly_rows = [
            {
                "cik": cik,
                "date": row["date"],
                "return_pct": row["return_pct"],
                "z_score": row["z_score"],
            }
            for row in result.anomalies
        ]
        try:
            upsert_price_anomalies(session, anomaly_rows)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("Failed upserting anomalies for %s (%s)", ticker, cik)
            result.error = f"anomaly_upsert: {exc}"

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the price pipeline for one company."
    )
    parser.add_argument("--cik", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--period", default="5d")
    parser.add_argument(
        "--start-date",
        type=dt.date.fromisoformat,
        default=None,
    )

    parser.add_argument(
        "--end-date",
        type=dt.date.fromisoformat,
        default=None,
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    session_factory = get_session_factory()
    with session_factory() as session:
        result = run_price_pipeline(
            cik=args.cik,
            ticker=args.ticker,
            session=session,
            period=args.period,
            start_date=args.start_date,
            end_date=args.end_date,
        )

    logger.info("Price pipeline result: %s", result)
    if result.error:
        sys.exit(1)
