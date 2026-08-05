from __future__ import annotations

from stock_news.graph.loader import (
    parse_companies_graph,
    upsert_companies_from_graph,
)
from stock_news.storage.models import Company

VALID_YAML = """
companies:
  - cik: "9999999901"
    ticker: TESTA
    name: Test Company A
    category: fabless
    aliases: ["Test Co A"]
    notes: "Synthetic company for graph loader tests."
  - cik: "9999999902"
    ticker: TESTB
    name: Test Company B
    category: equipment
    aliases: []
    notes: "Synthetic company for graph loader tests."
  - cik: "TODO_VERIFY"
    ticker: TESTC
    name: Test Company C
    category: fabless
    aliases: []
    notes: ""

edges:
  - source: TESTA
    target: TESTB
    edge_type: customer_of
    context: "TESTB supplies a component used in TESTA's product"
  - source: TESTC
    target: TESTA
    edge_type: competes_with
    context: "Both are fabless companies in the same market"
"""

TEST_TICKERS = ["TESTA", "TESTB", "TESTC"]


def test_upsert_companies_from_graph_skips_placeholder_ciks(tmp_path, db_session):
    path = tmp_path / "companies_graph.yaml"
    path.write_text(VALID_YAML)
    companies_graph = parse_companies_graph(path)

    upserted_count = upsert_companies_from_graph(db_session, companies_graph)

    stored = db_session.query(Company).filter(Company.ticker.in_(TEST_TICKERS)).all()

    assert upserted_count == 2  # TESTA and TESTB have real CIKs; TESTC is a placeholder
    assert {c.ticker for c in stored} == {"TESTA", "TESTB"}
