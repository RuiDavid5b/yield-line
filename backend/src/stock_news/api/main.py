from __future__ import annotations

import datetime as dt

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from stock_news.agent.graph import run_agent_query
from stock_news.api.models import (
    AgentAnswerOut,
    AgentQuery,
    AnomalyOut,
    CompanyOut,
    CompanyReturnsOut,
    DigestOut,
    FilingSignalOut,
    FinancialMetricOut,
    LatestPricesOut,
    NewsArticleOut,
    ResolvedCompanyOut,
    StockPriceOut,
)
from stock_news.storage.company_lookup import resolve_company
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import (
    get_all_companies,
    get_filing_signals,
    get_financial_metrics,
    get_latest_close_prices,
    get_latest_price_anomalies,
    get_news_articles,
    get_period_returns,
    get_price_anomalies,
    get_stock_price_history,
)
from stock_news.storage.queries import get_digest, get_latest_digest

session_factory = get_session_factory()

app = FastAPI(title="stock-news API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session():
    with session_factory() as session:
        yield session


@app.get("/companies", response_model=list[CompanyOut])
def list_companies(session: Session = Depends(get_session)):
    return get_all_companies(session)


@app.get("/companies/resolve", response_model=list[ResolvedCompanyOut])
def resolve(query: str, session: Session = Depends(get_session)):
    return resolve_company(session, query)


@app.get("/digest/latest", response_model=DigestOut)
def latest_digest(session: Session = Depends(get_session)):
    digest = get_latest_digest(session)
    if digest is None:
        raise HTTPException(status_code=404, detail="No digest cached yet")
    return digest


@app.get("/digest/{date}", response_model=DigestOut)
def digest_for_date(date: dt.date, session: Session = Depends(get_session)):
    digest = get_digest(session, date)
    if digest is None:
        raise HTTPException(status_code=404, detail=f"No digest data for {date}")
    return digest


@app.get("/companies/{cik}/prices", response_model=list[StockPriceOut])
def prices(
    cik: str,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    session: Session = Depends(get_session),
):
    return get_stock_price_history(session, cik, start_date, end_date)


@app.get("/companies/returns", response_model=CompanyReturnsOut)
def companies_returns(
    start_date: dt.date, end_date: dt.date, session: Session = Depends(get_session)
):
    return {"returns": get_period_returns(session, start_date, end_date)}


@app.get("/companies/latest-prices", response_model=LatestPricesOut)
def companies_latest_prices(
    session: Session = Depends(get_session),
) -> dict[str, float | None]:
    return get_latest_close_prices(session)


@app.get("/companies/{cik}/filing-signals", response_model=list[FilingSignalOut])
def filing_signals(
    cik: str,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    limit: int = 10,
    session: Session = Depends(get_session),
):
    return get_filing_signals(session, cik, start_date, end_date, limit)


@app.get("/companies/{cik}/financial-metrics", response_model=list[FinancialMetricOut])
def financial_metrics(
    cik: str,
    tag: str | None = None,
    limit: int = 12,
    session: Session = Depends(get_session),
):
    return get_financial_metrics(session, cik, tag=tag, limit=limit)


@app.get("/companies/{cik}/news", response_model=list[NewsArticleOut])
def news(cik: str, limit: int = 20, session: Session = Depends(get_session)):
    return get_news_articles(session, cik, limit=limit)


@app.get("/companies/{cik}/anomalies", response_model=list[AnomalyOut])
def price_anomalies(
    cik: str,
    limit: int = 10,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    session: Session = Depends(get_session),
):
    return get_price_anomalies(session, cik, start_date, end_date, limit)


@app.get("/anomalies/latest", response_model=list[AnomalyOut])
def latest_price_anomalies(session: Session = Depends(get_session)):
    return get_latest_price_anomalies(session)


@app.post("/agent/ask", response_model=AgentAnswerOut)
def ask_agent(body: AgentQuery):
    return {
        "answer": run_agent_query(body.question, body.thread_id, body.selected_company)
    }
