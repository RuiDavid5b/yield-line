"""
LangChain tool wrappers over the storage read functions, for the
LangGraph agent's tool-calling loop.
"""

from __future__ import annotations

import datetime as dt

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from stock_news.graph.queries import get_neighbors, load_graph
from stock_news.storage.company_lookup import resolve_company
from stock_news.storage.db import get_session_factory
from stock_news.storage.loaders import (
    get_anomalies_with_explanations,
    get_filing_signals,
    get_financial_metrics,
    get_news_articles,
)
from stock_news.storage.queries import get_digest

_session_factory = get_session_factory()
_graph = load_graph()


class ResolveCompanyArgs(BaseModel):
    query: str = Field(
        description=(
            "A company name, ticker, or alias as mentioned - may be misspelled, e.g. 'Synopys' or 'TSMC'"
        )
    )
    limit: int = Field(
        default=3, description="Max number of candidate matches to return"
    )


@tool(args_schema=ResolveCompanyArgs)
def resolve_company_tool(query: str, limit: int) -> list[dict]:
    """
    Resolve a company mention (name, ticker, or alias - typos okay) to
    tracked companies with their cik/ticker, ranked by confidence.
    Always call this FIRST when a query mentions a company, before
    calling any other tool - use the returned cik/ticker in subsequent
    calls rather than the original free-text mention. Empty result
    means the company isn't tracked.
    """
    with _session_factory() as session:
        return resolve_company(session, query, limit)


class CompanyDateRangeArgs(BaseModel):
    ciks: list[str] = Field(
        description=(
            "Company CIKs to fetch, from resolve_company_tool. Pass all "
            "companies involved in the question in one call."
        )
    )
    start_date: dt.date | None = Field(
        default=None, description="Earliest date to include (inclusive)"
    )
    end_date: dt.date | None = Field(
        default=None, description="Latest date to include (inclusive)"
    )
    limit: int | None = Field(
        default=10, description="Max results per company, most recent first"
    )


@tool(args_schema=CompanyDateRangeArgs)
def get_filing_signals_tool(
    ciks: list[str],
    start_date: dt.date | None,
    end_date: dt.date | None,
    limit: int | None,
) -> dict[str, list[dict]]:
    """
    Get extracted filing signals (guidance commentary, segment commentary,
    executive quotes, named customers/competitors) for a company, most
    recent first. Use for questions about what a company has disclosed
    or said in SEC filings, e.g. guidance changes over recent quarters.
    """
    with _session_factory() as session:
        return {
            cik: get_filing_signals(session, cik, start_date, end_date, limit)
            for cik in ciks
        }


@tool(args_schema=CompanyDateRangeArgs)
def get_news_tool(
    ciks: list[str],
    start_date: dt.date | None,
    end_date: dt.date | None,
    limit: int | None,
) -> dict[str, list[dict]]:
    """
    Get recent news articles mentioning a company, most recent first.
    Use for external commentary/coverage, distinct from the company's
    own SEC filing disclosures.
    """
    with _session_factory() as session:
        start_dt = dt.datetime.combine(start_date, dt.time.min) if start_date else None
        end_dt = dt.datetime.combine(end_date, dt.time.max) if end_date else None
        return {
            cik: get_news_articles(session, cik, start_dt, end_dt, limit)
            for cik in ciks
        }


@tool(args_schema=CompanyDateRangeArgs)
def get_anomalies_tool(
    ciks: list[str],
    start_date: dt.date | None,
    end_date: dt.date | None,
    limit: int | None,
) -> dict[str, list[dict]]:
    """
    Get detected price anomalies for a company, most recent first -
    both anomalies unusual for the company's own history (rolling
    z-score) and anomalies unusual relative to all tracked companies on
    the same day (cross-sectional z-score). A single date can have
    either, both, or neither. Includes any existing explanation. Use to
    check whether/when a company had an unusual price move.
    """
    with _session_factory() as session:
        return {
            cik: get_anomalies_with_explanations(
                session, cik, start_date, end_date, limit
            )
            for cik in ciks
        }


class FinancialMetricsArgs(BaseModel):
    ciks: list[str] = Field(
        description=(
            "Company CIKs to fetch, from resolve_company_tool. Pass all "
            "companies involved in the question in one call."
        )
    )
    tag: str | None = Field(
        default=None,
        description=(
            "XBRL tag name (e.g. 'CapitalExpenditures', 'Revenues', 'NetIncomeLoss'), "
            "applied to every requested company. Omit to see all reported metrics "
            "for each company first."
        ),
    )
    start_date: dt.date | None = Field(
        default=None, description="Earliest period_end to include (inclusive)"
    )
    end_date: dt.date | None = Field(
        default=None, description="Latest period_end to include (inclusive)"
    )
    limit: int | None = Field(
        default=12, description="Max results per company, most recent period first"
    )


@tool(args_schema=FinancialMetricsArgs)
def get_financial_metrics_tool(
    ciks: list[str],
    tag: str | None,
    start_date: dt.date | None,
    end_date: dt.date | None,
    limit: int | None,
) -> dict[str, list[dict]]:
    """
    Get reported financial metrics (structured XBRL data) for a company,
    most recent period first.
    """
    with _session_factory() as session:
        return {
            cik: get_financial_metrics(session, cik, tag, start_date, end_date, limit)
            for cik in ciks
        }


class DigestArgs(BaseModel):
    date: dt.date = Field(description="The date to get the digest for")


@tool(args_schema=DigestArgs)
def get_digest_tool(date: dt.date) -> dict | None:
    """
    Get the cross-company digest for one date: each tracked company's
    daily return, its return relative to its industry peer average, and
    relative to sector benchmarks (SOXX/SMH/SPY). Use for "how did X
    perform relative to peers" or "which subarea moved most" questions.
    Returns None if no digest exists for that date.
    """
    with _session_factory() as session:
        return get_digest(session, date)


class GraphNeighborsArgs(BaseModel):
    ticker: str = Field(description="Company ticker, e.g. 'NVDA'")
    edge_type: str | None = Field(
        default=None,
        description=(
            "Filter to one relationship type: supplies_to, customer_of, competes_with, licenses_ip_to. Omit for all types.",
        ),
    )
    direction: str = Field(
        default="both",
        description="'out' (this company -> neighbor), 'in' (neighbor -> this company), or 'both'",
    )


@tool(args_schema=GraphNeighborsArgs)
def get_graph_neighbors_tool(
    ticker: str, edge_type: str | None, direction: str
) -> dict:
    """
    Get a tracked company's relationships to other tracked companies.
    `ticker` should come from resolve_company_tool's output, not a raw
    user mention. Use to find related companies worth checking when an
    anomaly or news event might have propagated.
    """
    try:
        neighbors = get_neighbors(_graph, ticker, edge_type, direction)
    except KeyError:
        return {"error": f"'{ticker}' is not in the tracked company graph"}
    return {
        "neighbors": [
            {
                "ticker": n.ticker,
                "name": n.name,
                "industry_segment": n.industry_segment,
                "edge_type": n.edge_type,
                "direction": n.direction,
                "context": n.context,
            }
            for n in neighbors
        ]
    }


ALL_TOOLS = [
    resolve_company_tool,
    get_filing_signals_tool,
    get_news_tool,
    get_anomalies_tool,
    get_financial_metrics_tool,
    get_digest_tool,
    get_graph_neighbors_tool,
]
