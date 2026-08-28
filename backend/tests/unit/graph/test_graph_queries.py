import networkx as nx
import pytest

from stock_news.graph.queries import get_neighbors


@pytest.fixture
def graph() -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    g.add_node("NVDA", name="NVIDIA Corporation", industry_segment="fabless")
    g.add_node("TSM", name="Taiwan Semiconductor", industry_segment="foundry")
    g.add_node("CDNS", name="Cadence Design Systems", industry_segment="ip_eda")
    g.add_node("SNPS", name="Synopsys", industry_segment="ip_eda")

    g.add_edge(
        "NVDA", "TSM", edge_type="customer_of", context="TSM fabricates NVDA's GPUs"
    )
    g.add_edge(
        "CDNS", "SNPS", edge_type="competes_with", context="Both offer EDA tooling"
    )
    return g


class TestGetNeighbors:
    def test_out_direction_finds_directional_edge(self, graph):
        result = get_neighbors(graph, "NVDA", direction="out")
        assert len(result) == 1
        assert result[0].ticker == "TSM"
        assert result[0].direction == "out"

    def test_in_direction_finds_directional_edge_from_other_side(self, graph):
        result = get_neighbors(graph, "TSM", direction="in")
        assert len(result) == 1
        assert result[0].ticker == "NVDA"
        assert result[0].direction == "in"

    def test_out_direction_does_not_find_reverse_of_directional_edge(self, graph):
        result = get_neighbors(graph, "TSM", direction="out")
        assert result == []  # TSM has no outgoing customer_of edge

    def test_symmetric_edge_found_regardless_of_recorded_direction(self, graph):
        # CDNS -> SNPS is recorded once; both companies should see it
        # as a neighbor when asking for "out" or "in" specifically.
        assert [n.ticker for n in get_neighbors(graph, "CDNS", direction="out")] == [
            "SNPS"
        ]
        assert [n.ticker for n in get_neighbors(graph, "SNPS", direction="in")] == [
            "CDNS"
        ]

    def test_symmetric_edge_not_duplicated_with_both(self, graph):
        result = get_neighbors(graph, "CDNS", direction="both")
        assert len(result) == 1  # not double-counted

    def test_edge_type_filter_excludes_non_matching(self, graph):
        result = get_neighbors(
            graph, "NVDA", edge_type="competes_with", direction="both"
        )
        assert result == []

    def test_edge_type_filter_includes_matching(self, graph):
        result = get_neighbors(graph, "NVDA", edge_type="customer_of", direction="both")
        assert len(result) == 1

    def test_neighbor_includes_node_attributes(self, graph):
        result = get_neighbors(graph, "NVDA", direction="out")
        assert result[0].name == "Taiwan Semiconductor"
        assert result[0].industry_segment == "foundry"
        assert result[0].context == "TSM fabricates NVDA's GPUs"

    def test_no_neighbors_returns_empty_list(self, graph):
        g = nx.MultiDiGraph()
        g.add_node("ISOLATED", name="Isolated Co", industry_segment="test")
        assert get_neighbors(g, "ISOLATED", direction="both") == []

    def test_unknown_ticker_raises_key_error(self, graph):
        with pytest.raises(KeyError):
            get_neighbors(graph, "NOTREAL", direction="both")
