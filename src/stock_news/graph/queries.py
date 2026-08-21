"""
Read-side queries over the in-memory company graph.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from stock_news.graph.loader import (
    CompaniesGraph,
    build_networkx_graph,
    parse_companies_graph,
)

SYMMETRIC_EDGE_TYPES = {"competes_with"}


@dataclass(slots=True)
class Neighbor:
    ticker: str
    name: str
    industry_segment: str
    edge_type: str
    direction: (
        str  # "out" (this company -> neighbor) or "in" (neighbor -> this company)
    )
    context: str


def load_graph() -> nx.MultiDiGraph:
    """
    Parse and build the graph once.
    """
    companies_graph: CompaniesGraph = parse_companies_graph()
    return build_networkx_graph(companies_graph)


def _add_symmetric_neighbors(
    graph: nx.MultiDiGraph,
    ticker: str,
    edge_type: str | None,
    direction: str,
    neighbors: list[Neighbor],
) -> None:
    other_direction = "in" if direction == "out" else "out"
    edges = (
        graph.in_edges(ticker, data=True)
        if other_direction == "in"
        else graph.out_edges(ticker, data=True)
    )

    for a, b, data in edges:
        if data["edge_type"] not in SYMMETRIC_EDGE_TYPES:
            continue
        if edge_type is not None and data["edge_type"] != edge_type:
            continue

        neighbor_ticker = a if other_direction == "in" else b
        neighbors.append(
            _build_neighbor(graph, neighbor_ticker, data, direction=other_direction)
        )


def get_neighbors(
    graph: nx.MultiDiGraph,
    ticker: str,
    edge_type: str | None = None,
    direction: str = "both",
) -> list[Neighbor]:
    """
    Get a company's graph neighbors, optionally filtered by edge_type
    (e.g. "supplies_to", "customer_of", "competes_with", "licenses_ip_to").

    direction: "out" (edges where `ticker` is the source), "in" (edges
    where `ticker` is the target), or "both" (default). Ignored for
    SYMMETRIC_EDGE_TYPES - those are always returned regardless of
    recorded direction, since "competes_with" has no meaningful
    source/target distinction.
    """
    if ticker not in graph:
        raise KeyError(f"Unknown ticker in company graph: {ticker}")

    neighbors: list[Neighbor] = []

    if direction in ("out", "both"):
        for _, target, data in graph.out_edges(ticker, data=True):
            if edge_type is not None and data["edge_type"] != edge_type:
                continue
            neighbors.append(_build_neighbor(graph, target, data, direction="out"))

    if direction in ("in", "both"):
        for source, _, data in graph.in_edges(ticker, data=True):
            if edge_type is not None and data["edge_type"] != edge_type:
                continue
            neighbors.append(_build_neighbor(graph, source, data, direction="in"))

    if direction != "both":
        _add_symmetric_neighbors(graph, ticker, edge_type, direction, neighbors)

    return neighbors


def _build_neighbor(
    graph: nx.MultiDiGraph, neighbor_ticker: str, edge_data: dict, direction: str
) -> Neighbor:
    node = graph.nodes[neighbor_ticker]
    return Neighbor(
        ticker=neighbor_ticker,
        name=node["name"],
        industry_segment=node["industry_segment"],
        edge_type=edge_data["edge_type"],
        direction=direction,
        context=edge_data["context"],
    )
