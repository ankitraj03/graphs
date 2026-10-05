"""Unit tests for RelationshipRanker (Phase 5).

Tests:
- Ranking order (score descending, distance ascending)
- Top-K result limits
- Equal-score deterministic tie-breaking (by node_id)
- NodeNotFoundError handling
- Target node inclusion option
- Result serialization and formatting
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker.config import RankerConfig
from relationship_ranker.exceptions import NodeNotFoundError
from relationship_ranker.graph import GenericGraph
from relationship_ranker.ranker import RelationshipRanker


class TestRelationshipRanker(unittest.TestCase):
    """Test suite for RelationshipRanker."""

    def setUp(self) -> None:
        self.graph = GenericGraph()
        self.ranker = RelationshipRanker()

    def test_missing_target_raises_error(self) -> None:
        """Target node not in graph raises NodeNotFoundError."""
        with self.assertRaises(NodeNotFoundError):
            self.ranker.rank(self.graph, "NonExistent")

    def test_single_node_no_edges(self) -> None:
        """Single node without relationships returns empty ranked list."""
        self.graph.add_node("A")
        results = self.ranker.rank(self.graph, "A")
        self.assertEqual(results, [])

        # When include_target=True, returns target at distance 0
        results_with_target = self.ranker.rank(self.graph, "A", include_target=True)
        self.assertEqual(len(results_with_target), 1)
        self.assertEqual(results_with_target[0].node_id, "A")
        self.assertEqual(results_with_target[0].distance, 0)
        self.assertEqual(results_with_target[0].score, 1.0)

    def test_ranking_order(self) -> None:
        """Test 15: Nodes are ranked from most relevant to least relevant."""
        # A --DIRECT_CALL (1.0)--> B  (dist 1, decay 1.0) => 1.00
        # A --IMPORT (0.7)------> C  (dist 1, decay 1.0) => 0.70
        # C --IMPORT (0.7)------> D  (dist 2, decay 0.7) => 0.49
        self.graph.add_edge("A", "B", "DIRECT_CALL")
        self.graph.add_edge("A", "C", "IMPORT")
        self.graph.add_edge("C", "D", "IMPORT")

        ranked = self.ranker.rank(self.graph, "A")
        self.assertEqual(len(ranked), 3)

        self.assertEqual(ranked[0].node_id, "B")
        self.assertAlmostEqual(ranked[0].score, 1.00)
        self.assertEqual(ranked[0].distance, 1)

        self.assertEqual(ranked[1].node_id, "C")
        self.assertAlmostEqual(ranked[1].score, 0.70)
        self.assertEqual(ranked[1].distance, 1)

        self.assertEqual(ranked[2].node_id, "D")
        self.assertAlmostEqual(ranked[2].score, 0.49)
        self.assertEqual(ranked[2].distance, 2)

    def test_top_k(self) -> None:
        """Test 16: Top-K slices results accurately."""
        for i in range(10):
            self.graph.add_edge("Target", f"Node_{i}", "IMPORT")

        top_3 = self.ranker.rank(self.graph, "Target", top_k=3)
        self.assertEqual(len(top_3), 3)

        top_0 = self.ranker.rank(self.graph, "Target", top_k=0)
        self.assertEqual(len(top_0), 0)

        all_nodes = self.ranker.rank(self.graph, "Target", top_k=None)
        self.assertEqual(len(all_nodes), 10)

    def test_equal_score_deterministic_ordering(self) -> None:
        """Test 17: Nodes with equal scores are ordered deterministically by node_id."""
        # A connects to Z, M, B, all with identical relationship and distance
        self.graph.add_edge("A", "Z_Node", "IMPORT")
        self.graph.add_edge("A", "M_Node", "IMPORT")
        self.graph.add_edge("A", "B_Node", "IMPORT")

        ranked1 = self.ranker.rank(self.graph, "A")
        ranked2 = self.ranker.rank(self.graph, "A")

        ids1 = [r.node_id for r in ranked1]
        ids2 = [r.node_id for r in ranked2]

        # Lexicographical ordering for equal scores: B_Node, M_Node, Z_Node
        self.assertEqual(ids1, ["B_Node", "M_Node", "Z_Node"])
        self.assertEqual(ids1, ids2)

    def test_serialization_and_format(self) -> None:
        """Test serialization to dict and format_results human-readable representation."""
        self.graph.add_edge("A", "B", "IMPORT")
        results = self.ranker.rank(self.graph, "A")
        self.assertEqual(len(results), 1)

        d = results[0].to_dict()
        self.assertEqual(d["node_id"], "B")
        self.assertEqual(d["score"], 0.7)
        self.assertEqual(d["distance"], 1)
        self.assertEqual(d["relationship_type"], "IMPORT")
        self.assertEqual(d["path"], ["A", "B"])

        formatted = self.ranker.format_results("A", results)
        self.assertIn("Target Node: A", formatted)
        self.assertIn("1. B", formatted)
        self.assertIn("score:", formatted)
        self.assertIn("path:", formatted)


if __name__ == "__main__":
    unittest.main()
