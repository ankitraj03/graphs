"""Unit tests for BfsTraverser (Phase 5).

Tests:
- BFS distance calculation
- Maximum depth bounds
- Incoming and Bidirectional traversal
- Cycle termination
- Disconnected components
- Multiple paths resolution
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker.config import RankerConfig
from relationship_ranker.graph import GenericGraph
from relationship_ranker.models import TraversalDirection
from relationship_ranker.traversal import BfsTraverser


class TestBfsTraverser(unittest.TestCase):
    """Test suite for BfsTraverser."""

    def setUp(self) -> None:
        self.graph = GenericGraph()
        self.traverser = BfsTraverser()

    def test_bfs_distance_calculation(self) -> None:
        """Test 7: BFS distance is accurate level-by-level."""
        # A -> B -> C -> D
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("B", "C", "IMPORT")
        self.graph.add_edge("C", "D", "IMPORT")

        paths = self.traverser.traverse(self.graph, "A", max_depth=10)
        self.assertEqual(paths["B"].distance, 1)
        self.assertEqual(paths["C"].distance, 2)
        self.assertEqual(paths["D"].distance, 3)

        self.assertEqual(paths["B"].nodes, ("A", "B"))
        self.assertEqual(paths["C"].nodes, ("A", "B", "C"))
        self.assertEqual(paths["D"].nodes, ("A", "B", "C", "D"))

    def test_maximum_depth(self) -> None:
        """Test 8: Traversal does not explore beyond max_depth."""
        # A -> B -> C -> D -> E
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("B", "C", "IMPORT")
        self.graph.add_edge("C", "D", "IMPORT")
        self.graph.add_edge("D", "E", "IMPORT")

        paths_depth_2 = self.traverser.traverse(self.graph, "A", max_depth=2)
        self.assertIn("B", paths_depth_2)
        self.assertIn("C", paths_depth_2)
        self.assertNotIn("D", paths_depth_2)
        self.assertNotIn("E", paths_depth_2)

        paths_depth_0 = self.traverser.traverse(self.graph, "A", max_depth=0)
        self.assertEqual(paths_depth_0, {})

    def test_incoming_traversal(self) -> None:
        """Test 5: Incoming traversal follows incoming edges."""
        # X -> A and Y -> A and Z -> X
        self.graph.add_edge("X", "A", "IMPORT")
        self.graph.add_edge("Y", "A", "DIRECT_CALL")
        self.graph.add_edge("Z", "X", "IMPORT")
        self.graph.add_edge("A", "W", "IMPORT")  # Outgoing, should not be reached

        paths = self.traverser.traverse(
            self.graph,
            "A",
            direction=TraversalDirection.INCOMING,
            max_depth=5,
        )
        self.assertIn("X", paths)
        self.assertIn("Y", paths)
        self.assertIn("Z", paths)
        self.assertNotIn("W", paths)

        self.assertEqual(paths["X"].distance, 1)
        self.assertEqual(paths["Y"].distance, 1)
        self.assertEqual(paths["Z"].distance, 2)
        self.assertEqual(paths["Z"].nodes, ("A", "X", "Z"))

    def test_bidirectional_traversal(self) -> None:
        """Test 6: Bidirectional traversal follows both outgoing and incoming edges."""
        # In: X -> A. Out: A -> B. Out: B -> C.
        self.graph.add_edge("X", "A", "IMPORT")
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("B", "C", "IMPORT")

        paths = self.traverser.traverse(
            self.graph,
            "A",
            direction=TraversalDirection.BOTH,
            max_depth=5,
        )
        self.assertIn("X", paths)
        self.assertIn("B", paths)
        self.assertIn("C", paths)
        self.assertEqual(paths["X"].distance, 1)
        self.assertEqual(paths["B"].distance, 1)
        self.assertEqual(paths["C"].distance, 2)

    def test_cycle_handling(self) -> None:
        """Test 9: Cyclical graphs (A -> B -> C -> A) terminate safely without infinite loop."""
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("B", "C", "IMPORT")
        self.graph.add_edge("C", "A", "IMPORT")

        paths = self.traverser.traverse(self.graph, "A", max_depth=10)
        self.assertEqual(len(paths), 2)
        self.assertIn("B", paths)
        self.assertIn("C", paths)
        self.assertEqual(paths["B"].distance, 1)
        self.assertEqual(paths["C"].distance, 2)

    def test_disconnected_components(self) -> None:
        """Test 18: Disconnected components are not reached."""
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("C", "D", "IMPORT")

        paths = self.traverser.traverse(self.graph, "A", max_depth=10)
        self.assertIn("B", paths)
        self.assertNotIn("C", paths)
        self.assertNotIn("D", paths)

    def test_multiple_paths_same_distance(self) -> None:
        """Test 20: When multiple paths reach a node at same distance, evaluator picks the best."""
        # Path 1: A -> B -> D (A->B IMPORT=0.7, B->D IMPORT=0.7) -> min=0.7
        # Path 2: A -> C -> D (A->C DIRECT_CALL=1.0, C->D DIRECT_CALL=1.0) -> min=1.0
        self.graph.add_edge("A", "B", "IMPORT")
        self.graph.add_edge("B", "D", "IMPORT")
        self.graph.add_edge("A", "C", "DIRECT_CALL")
        self.graph.add_edge("C", "D", "DIRECT_CALL")

        weights = {"IMPORT": 0.70, "DIRECT_CALL": 1.00}

        def score_fn(path):
            return min(weights.get(s.edge.relationship_type, 0.5) for s in path.steps)

        paths = self.traverser.traverse(
            self.graph,
            "A",
            max_depth=5,
            score_evaluator=score_fn,
        )
        self.assertEqual(paths["D"].distance, 2)
        # Should pick the higher scoring path via C
        self.assertEqual(paths["D"].nodes, ("A", "C", "D"))


if __name__ == "__main__":
    unittest.main()
