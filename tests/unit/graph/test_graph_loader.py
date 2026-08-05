"""
Tests for graph.loader.
"""

from __future__ import annotations

import pytest

from stock_news.graph.loader import (
    build_networkx_graph,
    parse_companies_graph,
)

VALID_YAML = """
companies:
  - cik: "0001045810"
    ticker: NVDA
    name: NVIDIA Corporation
    category: fabless
    aliases: ["Nvidia"]
    notes: "GPU/AI accelerator design."
  - cik: "0001046179"
    ticker: TSM
    name: Taiwan Semiconductor Manufacturing Company
    category: equipment
    aliases: [TSMC]
    notes: "Leading-edge foundry."
  - cik: "TODO_VERIFY"
    ticker: AMD
    name: Advanced Micro Devices INC
    category: fabless
    aliases: []
    notes: ""

edges:
  - source: NVDA
    target: TSM
    edge_type: customer_of
    context: "TSM fabricates NVDA's leading-edge GPU dies"
  - source: AMD
    target: NVDA
    edge_type: competes_with
    context: "Both are fabless companies that design GPUs"
"""


class TestParseSeedGraph:
    def test_parses_companies_and_edges(self, tmp_path):
        path = tmp_path / "companies_graph.yaml"
        path.write_text(VALID_YAML)

        graph = parse_companies_graph(path)

        assert len(graph.companies) == 3
        assert len(graph.edges) == 2

    def test_parses_company_fields(self, tmp_path):
        path = tmp_path / "companies_graph.yaml"
        path.write_text(VALID_YAML)

        graph = parse_companies_graph(path)
        nvda = next(c for c in graph.companies if c.ticker == "NVDA")

        assert nvda.cik == "0001045810"
        assert nvda.name == "NVIDIA Corporation"
        assert nvda.category == "fabless"
        assert nvda.aliases == ["Nvidia"]

    def test_missing_optional_fields_default_empty(self, tmp_path):
        path = tmp_path / "companies_graph.yaml"
        path.write_text(VALID_YAML)

        graph = parse_companies_graph(path)
        amd = next(c for c in graph.companies if c.ticker == "AMD")

        assert amd.aliases == []
        assert amd.notes == ""

    def test_duplicate_ticker_raises(self, tmp_path):
        yaml_content = VALID_YAML.replace("ticker: TSM", "ticker: NVDA", 1)
        path = tmp_path / "companies_graph.yaml"
        path.write_text(yaml_content)

        with pytest.raises(ValueError, match="Duplicate tickers"):
            parse_companies_graph(path)

    def test_duplicate_real_cik_raises(self, tmp_path):
        yaml_content = VALID_YAML.replace('cik: "0001046179"', 'cik: "0001045810"', 1)
        path = tmp_path / "companies_graph.yaml"
        path.write_text(yaml_content)

        with pytest.raises(ValueError, match="Duplicate CIKs"):
            parse_companies_graph(path)

    def test_duplicate_placeholder_cik_does_not_raise(self, tmp_path):
        # Multiple TODO_VERIFY placeholders are expected and fine - only
        # duplicate *real* CIKs should be treated as an error.
        extra_company = (
            '  - cik: "0000883241"\n'
            "    ticker: SNPS\n"
            "    name: Synopsys\n"
            "    category: ip_eda\n"
            "    aliases: []\n"
            '    notes: "EDA tooling; also licenses IP (DesignWare)."\n'
        )
        yaml_content = VALID_YAML.replace("\nedges:", f"\n{extra_company}\nedges:")
        path = tmp_path / "companies_graph.yaml"
        path.write_text(yaml_content)

        graph = parse_companies_graph(path)
        assert len(graph.companies) == 4

    def test_edge_referencing_unknown_ticker_raises(self, tmp_path):
        yaml_content = VALID_YAML.replace("target: TSM", "target: GHOST", 1)
        path = tmp_path / "companies_graph.yaml"
        path.write_text(yaml_content)

        with pytest.raises(ValueError, match="Edges reference tickers"):
            parse_companies_graph(path)

    def test_empty_edges_section_is_valid(self, tmp_path):
        yaml_content = VALID_YAML.split("edges:")[0]
        path = tmp_path / "companies_graph.yaml"
        path.write_text(yaml_content)

        graph = parse_companies_graph(path)
        assert graph.edges == []


class TestBuildNetworkxGraph:
    def _graph(self, tmp_path):
        path = tmp_path / "companies_graph.yaml"
        path.write_text(VALID_YAML)
        return build_networkx_graph(parse_companies_graph(path))

    def test_nodes_present_with_attributes(self, tmp_path):
        graph = self._graph(tmp_path)

        assert set(graph.nodes) == {"NVDA", "TSM", "AMD"}
        assert graph.nodes["NVDA"]["category"] == "fabless"
        assert graph.nodes["NVDA"]["cik"] == "0001045810"

    def test_edges_present_with_attributes(self, tmp_path):
        graph = self._graph(tmp_path)

        assert graph.has_edge("NVDA", "TSM")
        edge_data = graph.get_edge_data("NVDA", "TSM")[0]
        assert edge_data["edge_type"] == "customer_of"

    def test_multiple_edge_types_between_same_pair_both_preserved(self, tmp_path):
        yaml_content = VALID_YAML.replace(
            "edges:\n",
            'edges:\n  - source: NVDA\n    target: TSM\n    edge_type: competes_with\n    context: "second edge, same pair"\n',
        )
        path = tmp_path / "companies_graph.yaml"
        path.write_text(yaml_content)

        graph = build_networkx_graph(parse_companies_graph(path))
        edge_types = {
            data["edge_type"] for data in graph.get_edge_data("NVDA", "TSM").values()
        }

        assert edge_types == {"customer_of", "competes_with"}
