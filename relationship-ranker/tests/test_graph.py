"""Unit tests for GenericGraph model (Phase 5).

Tests:
- Empty graph
- Single node addition
- One edge addition and endpoint auto-registration
- Multiple outgoing edges
- Duplicate edge prevention
- Different relationship types between same endpoints
- Neighbor lookups (incoming, outgoing, undirected)
- Graph clearing
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker.exceptions import InvalidGraphError
from relationship_ranker.graph import GenericGraph
from relationship_ranker.models import Edge, Node


class TestGenericGraph(unittest.TestCase):
    """Test suite for GenericGraph data structure."""

    def setUp(self) -> None:
        self.graph = GenericGraph()

    def test_empty_graph(self) -> None:
        """Test 1: Empty graph has 0 nodes and 0 edges."""
        self.assertEqual(self.graph.node_count, 0)
        self.assertEqual(self.graph.edge_count, 0)
        self.assertFalse(self.graph.has_node("missing"))
        self.assertIsNone(self.graph.get_node("missing"))
        self.assertEqual(self.graph.get_outgoing_neighbors("missing"), [])
        self.assertEqual(self.graph.get_incoming_neighbors("missing"), [])
        self.assertEqual(self.graph.get_neighbors("missing"), [])

    def test_single_node(self) -> None:
        """Test 2: Single node addition and metadata."""
        node = self.graph.add_node("A", metadata={"lang": "python"})
        self.assertEqual(self.graph.node_count, 1)
        self.assertEqual(self.graph.edge_count, 0)
        self.assertTrue(self.graph.has_node("A"))
        self.assertEqual(node.node_id, "A")
        self.assertEqual(node.metadata.get("lang"), "python")

        # Adding same node again does not duplicate
        self.graph.add_node("A")
        self.assertEqual(self.graph.node_count, 1)

    def test_invalid_node(self) -> None:
        """Test invalid node rejection."""
        with self.assertRaises(InvalidGraphError):
            self.graph.add_node("")
        with self.assertRaises(InvalidGraphError):
            self.graph.add_node(123)  # type: ignore

    def test_one_edge(self) -> None:
        """Test 3: One edge addition auto-registers endpoints."""
        edge = self.graph.add_edge("A", "B", "IMPORT")
        self.assertEqual(self.graph.node_count, 2)
        self.assertEqual(self.graph.edge_count, 1)
        self.assertTrue(self.graph.has_node("A"))
        self.assertTrue(self.graph.has_node("B"))
        self.assertEqual(edge.source, "A")
        self.assertEqual(edge.target, "B")
        self.assertEqual(edge.relationship_type, "IMPORT")

    def test_multiple_outgoing_edges(self) -> None:
        """Test 4: Multiple outgoing edges from one node."""
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("A", "C", "INCLUDE")
        self.graph.add_edge("A", "D", "DIRECT_CALL")

        self.assertEqual(self.graph.node_count, 4)
        self.assertEqual(self.graph.edge_count, 3)

        out_neighbors = self.graph.get_outgoing_neighbors("A")
        self.assertEqual(sorted(out_neighbors), ["B", "C", "D"])
        self.assertEqual(self.graph.get_incoming_neighbors("A"), [])
        self.assertEqual(self.graph.get_incoming_neighbors("B"), ["A"])

    def test_duplicate_edges(self) -> None:
        """Test 10: Duplicate edges with identical (source, target, type) are rejected."""
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge(Edge("A", "B", "IMPORT"))

        self.assertEqual(self.graph.edge_count, 1)
        self.assertEqual(len(self.graph.get_outgoing_edges("A")), 1)

    def test_different_relationship_types(self) -> None:
        """Test 11: Different relationship types between same endpoints are preserved."""
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("A", "B", "INCLUDE")

        self.assertEqual(self.graph.node_count, 2)
        self.assertEqual(self.graph.edge_count, 2)
        edges = self.graph.get_outgoing_edges("A")
        types = {e.relationship_type for e in edges}
        self.assertEqual(types, {"IMPORT", "INCLUDE"})

    def test_clear_graph(self) -> None:
        """Test clearing the graph."""
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.clear()
        self.assertEqual(self.graph.node_count, 0)
        self.assertEqual(self.graph.edge_count, 0)


if __name__ == "__main__":
    unittest.main()
