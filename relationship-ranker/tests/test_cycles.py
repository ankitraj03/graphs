"""Dedicated cycle safety tests for Relationship Ranker (Phase 5).

Verifies that cyclical graphs never cause infinite loops, queue overflow,
or erroneous distance metrics:
- Self-edges (A -> A)
- 2-node mutual recursion (A <-> B)
- Multi-node rings (A -> B -> C -> D -> A)
- Entangled interlocking cycles
- Cycles with incoming, outgoing, and bidirectional traversals
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


class TestCycleSafety(unittest.TestCase):
    """Test suite verifying robust cycle handling across all traversal modes."""

    def setUp(self) -> None:
        self.graph = GenericGraph()
        self.ranker = RelationshipRanker()

    def test_self_edge(self) -> None:
        """Self-edge (A -> A) is safely skipped and does not re-visit self."""
        self.graph.add_edge("A", "A", "IMPORT")
        self.graph.add_edge("A", "B", "IMPORT")

        ranked = self.ranker.rank(self.graph, "A")
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].node_id, "B")

    def test_two_node_mutual_recursion(self) -> None:
        """Two nodes importing each other (A <-> B) terminate safely."""
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("B", "A", "IMPORT")

        # OUTGOING
        ranked_out = self.ranker.rank(self.graph, "A", direction=TraversalDirection.OUTGOING)
        self.assertEqual(len(ranked_out), 1)
        self.assertEqual(ranked_out[0].node_id, "B")
        self.assertEqual(ranked_out[0].distance, 1)

        # INCOMING
        ranked_in = self.ranker.rank(self.graph, "A", direction=TraversalDirection.INCOMING)
        self.assertEqual(len(ranked_in), 1)
        self.assertEqual(ranked_in[0].node_id, "B")

        # BOTH
        ranked_both = self.ranker.rank(self.graph, "A", direction=TraversalDirection.BOTH)
        self.assertEqual(len(ranked_both), 1)
        self.assertEqual(ranked_both[0].node_id, "B")

    def test_multi_node_cycle(self) -> None:
        """Large cyclic ring: A -> B -> C -> D -> E -> A."""
        nodes = ["A", "B", "C", "D", "E"]
        for i in range(len(nodes)):
            src = nodes[i]
            tgt = nodes[(i + 1) % len(nodes)]
            self.graph.add_edge(src, tgt, "IMPORT")

        ranked = self.ranker.rank(self.graph, "A", max_depth=10)
        self.assertEqual(len(ranked), 4)

        # Distances along the ring: B=1, C=2, D=3, E=4
        distances = {r.node_id: r.distance for r in ranked}
        self.assertEqual(distances["B"], 1)
        self.assertEqual(distances["C"], 2)
        self.assertEqual(distances["D"], 3)
        self.assertEqual(distances["E"], 4)

    def test_entangled_cycles(self) -> None:
        """Multiple intertwined cycles with cross-edges."""
        # Cycle 1: A -> B -> C -> A
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("B", "C", "IMPORT")
        self.graph.add_edge("C", "A", "IMPORT")

        # Cycle 2: B -> D -> E -> B
        self.graph.add_edge("B", "D", "IMPORT")
        self.graph.add_edge("D", "E", "IMPORT")
        self.graph.add_edge("E", "B", "IMPORT")

        # Cross-edge: E -> C
        self.graph.add_edge("E", "C", "IMPORT")

        ranked = self.ranker.rank(self.graph, "A", max_depth=10)
        node_ids = {r.node_id for r in ranked}
        self.assertEqual(node_ids, {"B", "C", "D", "E"})


if __name__ == "__main__":
    unittest.main()
