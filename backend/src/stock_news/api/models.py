"""
Pydantic response models for the FastAPI layer.
"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, RootModel


class CompanyOut(BaseModel):
    cik: str
    ticker: str
    name: str
    industry_segment: str
    reporting_currency: str
    aliases: list[str]
    news_disambiguation: list[str]


class ResolvedCompanyOut(CompanyOut):
    match_confidence: float


class StockPriceOut(BaseModel):
    cik: str
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: int


class FilingSignalOut(BaseModel):
    accession_number: str
    form: str
    filed_date: dt.date
    guidance_commentary: str | None
    segment_commentary: str | None
    executive_quote_summary: str | None
    mentioned_customers: list[str]
    mentioned_competitors: list[str]


class CompanyReturnsOut(BaseModel):
    returns: dict[str, float | None]


class LatestPricesOut(RootModel[dict[str, float | None]]):
    pass


class FinancialMetricOut(BaseModel):
    tag: str
    period_start: dt.date
    period_end: dt.date
    period_type: str
    value: float
    unit: str
    form: str
    filed_date: dt.date


class NewsArticleOut(BaseModel):
    cik: str
    url: str
    title: str
    description: str | None
    author: str | None
    published_at: dt.datetime | None


class AnomalyOut(BaseModel):
    cik: str
    date: dt.date
    return_pct: float
    rolling_z_score: float | None
    is_cross_sectional: bool
    explanation: str | None
    explained_at: dt.datetime | None


class DigestCompanyOut(BaseModel):
    cik: str
    industry_segment: str
    return_pct: float | None
    peer_avg_return_pct: float | None
    vs_peer_avg: float | None
    vs_soxx: float | None
    vs_smh: float | None
    vs_spy: float | None
    cross_sectional_z_score: float | None
    is_cross_sectional_anomaly: bool


class DigestBenchmarksOut(BaseModel):
    soxx_return: float | None
    smh_return: float | None
    spy_return: float | None


class DigestOut(BaseModel):
    companies: list[DigestCompanyOut]
    benchmarks: DigestBenchmarksOut


class AgentQuery(BaseModel):
    question: str
    thread_id: str
    selected_company: dict | None = None


class AgentAnswerOut(BaseModel):
    answer: str
