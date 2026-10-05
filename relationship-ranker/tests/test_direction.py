"""Unit tests for traversal direction handling in Relationship Ranker (Phase 5).

Tests:
- OUTGOING direction traversal
- INCOMING direction traversal
- BOTH (bidirectional) traversal
- Path direction tagging on RankedNode
- Complete isolation of non-traversed directions
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker.graph import GenericGraph
from relationship_ranker.models import TraversalDirection
from relationship_ranker.ranker import RelationshipRanker


class TestDirectionalTraversal(unittest.TestCase):
    """Test suite for traversal direction semantics."""

    def setUp(self) -> None:
        self.graph = GenericGraph()
        self.ranker = RelationshipRanker()

        # Build asymmetric star:
        # Caller1 -> Target
        # Caller2 -> Target
        # Target -> Callee1
        # Target -> Callee2
        # Callee1 -> SubCallee
        self.graph.add_edge("Caller1", "Target", "DIRECT_CALL")
        self.graph.add_edge("Caller2", "Target", "IMPORT")
        self.graph.add_edge("Target", "Callee1", "INCLUDE")
        self.graph.add_edge("Target", "Callee2", "IMPORT")
        self.graph.add_edge("Callee1", "SubCallee", "IMPORT")

    def test_outgoing_only(self) -> None:
        """OUTGOING traversal reaches only Callee1, Callee2, SubCallee."""
        results = self.ranker.rank(
            self.graph,
            "Target",
            direction=TraversalDirection.OUTGOING,
        )
        node_ids = {r.node_id for r in results}
        self.assertEqual(node_ids, {"Callee1", "Callee2", "SubCallee"})
        self.assertNotIn("Caller1", node_ids)
        self.assertNotIn("Caller2", node_ids)

        for r in results:
            self.assertEqual(r.direction, "OUTGOING")

    def test_incoming_only(self) -> None:
        """INCOMING traversal reaches only Caller1, Caller2."""
        results = self.ranker.rank(
            self.graph,
            "Target",
            direction=TraversalDirection.INCOMING,
        )
        node_ids = {r.node_id for r in results}
        self.assertEqual(node_ids, {"Caller1", "Caller2"})
        self.assertNotIn("Callee1", node_ids)
        self.assertNotIn("Callee2", node_ids)
        self.assertNotIn("SubCallee", node_ids)

        for r in results:
            self.assertEqual(r.direction, "INCOMING")

    def test_bidirectional(self) -> None:
        """BOTH traversal reaches all connected nodes in both directions."""
        results = self.ranker.rank(
            self.graph,
            "Target",
            direction=TraversalDirection.BOTH,
        )
        node_ids = {r.node_id for r in results}
        self.assertEqual(node_ids, {"Caller1", "Caller2", "Callee1", "Callee2", "SubCallee"})

        caller1_node = next(r for r in results if r.node_id == "Caller1")
        callee1_node = next(r for r in results if r.node_id == "Callee1")

        self.assertEqual(caller1_node.direction, "INCOMING")
        self.assertEqual(callee1_node.direction, "OUTGOING")


if __name__ == "__main__":
    unittest.main()
