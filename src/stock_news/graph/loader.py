"""
Parses graph/companies_graph.yaml, validates it, and loads it into Postgres
and an in-memory networkx graph for agent traversal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import yaml
from sqlalchemy.orm import Session

from stock_news.storage.loaders import upsert_companies

logger = logging.getLogger(__name__)

DEFAULT_GRAPH_PATH = Path(__file__).parent / "companies_graph.yaml"

PLACEHOLDER_CIK = "TODO_VERIFY"


@dataclass(slots=True)
class CompanyNode:
    cik: str
    ticker: str
    name: str
    category: str
    aliases: list[str]
    notes: str
    reporting_currency: str = "USD"


@dataclass(slots=True)
class CompanyEdge:
    source: str  # ticker
    target: str  # ticker
    edge_type: str
    context: str


@dataclass(slots=True)
class CompaniesGraph:
    companies: list[CompanyNode]
    edges: list[CompanyEdge]


def parse_companies_graph(path: Path = DEFAULT_GRAPH_PATH) -> CompaniesGraph:
    """
    Parse and validate the companies graph YAML.

    Raises ValueError on duplicate tickers, duplicate real (non-placeholder)
    CIKs, or edges referencing a ticker not defined among the companies.
    """
    raw: dict[str, Any] = yaml.safe_load(path.read_text())

    companies = [
        CompanyNode(
            cik=c["cik"],
            ticker=c["ticker"],
            name=c["name"],
            category=c["category"],
            aliases=c.get("aliases", []),
            notes=c.get("notes", ""),
            reporting_currency=c.get("reporting_currency", "USD"),
        )
        for c in raw.get("companies", [])
    ]

    tickers = [c.ticker for c in companies]
    duplicate_tickers = {t for t in tickers if tickers.count(t) > 1}
    if duplicate_tickers:
        raise ValueError(f"Duplicate tickers in companies graph: {duplicate_tickers}")

    real_ciks = [c.cik for c in companies if c.cik != PLACEHOLDER_CIK]
    duplicate_ciks = {c for c in real_ciks if real_ciks.count(c) > 1}
    if duplicate_ciks:
        raise ValueError(f"Duplicate CIKs in companies graph: {duplicate_ciks}")

    known_tickers = set(tickers)

    edges = [
        CompanyEdge(
            source=e["source"],
            target=e["target"],
            edge_type=e["edge_type"],
            context=e.get("context", ""),
        )
        for e in raw.get("edges", [])
    ]

    unknown_refs = {
        ref
        for edge in edges
        for ref in (edge.source, edge.target)
        if ref not in known_tickers
    }
    if unknown_refs:
        raise ValueError(
            f"Edges reference tickers not defined in companies: {unknown_refs}"
        )

    return CompaniesGraph(companies=companies, edges=edges)


def build_networkx_graph(companies_graph: CompaniesGraph) -> nx.MultiDiGraph:
    """
    Build an in-memory graph for agent traversal.

    MultiDiGraph, not DiGraph, because two companies can legitimately
    have more than one relationship between them (e.g. Cadence and Arm
    are both competes_with in IP and, separately, could be customer_of
    in some other line of business).
    """
    graph = nx.MultiDiGraph()

    for company in companies_graph.companies:
        graph.add_node(
            company.ticker,
            cik=company.cik,
            name=company.name,
            category=company.category,
            aliases=company.aliases,
            notes=company.notes,
            reporting_currency=company.reporting_currency,
        )

    for edge in companies_graph.edges:
        graph.add_edge(
            edge.source,
            edge.target,
            edge_type=edge.edge_type,
            context=edge.context,
        )

    return graph


def upsert_companies_from_graph(
    session: Session, companies_graph: CompaniesGraph
) -> int:
    """
    Upsert every company node with a real CIK into Postgres. Companies
    still carrying a TODO_VERIFY placeholder are skipped and logged,
    since a wrong CIK would make EDGAR ingestion silently hit nonsense
    URLs for that company.

    Returns the number of companies actually upserted.
    """
    rows = []
    skipped = []
    for company in companies_graph.companies:
        if company.cik == PLACEHOLDER_CIK:
            skipped.append(company.ticker)
            continue
        rows.append(
            {
                "cik": company.cik,
                "ticker": company.ticker,
                "name": company.name,
                "industry_segment": company.category,
                "reporting_currency": company.reporting_currency,
            }
        )

    if skipped:
        logger.warning(
            "Skipping %d companies with unverified CIK placeholders: %s",
            len(skipped),
            skipped,
        )

    upsert_companies(session, rows)
    session.commit()
    return len(rows)


if __name__ == "__main__":
    import sys

    from stock_news.storage.db import get_session_factory

    logging.basicConfig(level=logging.INFO)
    companies_graph = parse_companies_graph()
    logger.info(
        "Parsed companies graph: %d companies, %d edges",
        len(companies_graph.companies),
        len(companies_graph.edges),
    )

    session_factory = get_session_factory()
    with session_factory() as session:
        upserted = upsert_companies_from_graph(session, companies_graph)

    logger.info("Upserted %d companies into Postgres", upserted)
    if upserted < len(companies_graph.companies):
        logger.warning(
            "Some companies were skipped - fix their CIKs before running ingestion pipelines."
        )
        sys.exit(1)
