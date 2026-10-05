"""Comprehensive ranking tests for Relationship Ranker (Phase 5).

Verifies end-to-end ranking logic:
- Microservice / Clean Architecture model
- Multi-path resolution choosing the optimal scoring path
- Top-K preservation and cutoff
- Weight calibration impact on rank positions
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker.config import RankerConfig
from relationship_ranker.graph import GenericGraph
from relationship_ranker.ranker import RelationshipRanker


class TestRankingScenarios(unittest.TestCase):
    """End-to-end ranking scenario tests."""

    def test_section_1_example(self) -> None:
        """Verify the exact conceptual example from Section 1."""
        graph = GenericGraph()
        # file:controllers/UserController.ts
        #   -> AuthService (IMPORT)
        #   -> UserService (IMPORT)
        # AuthService -> UserRepository (IMPORT)
        target = "file:controllers/UserController.ts"
        graph.add_edge(target, "AuthService", "IMPORT")
        graph.add_edge(target, "UserService", "IMPORT")
        graph.add_edge("AuthService", "UserRepository", "IMPORT")

        ranker = RelationshipRanker()
        results = ranker.rank(graph, target)

        self.assertEqual(len(results), 3)

        # Distance 1 nodes ranked higher than Distance 2 node
        self.assertEqual(results[0].distance, 1)
        self.assertEqual(results[1].distance, 1)
        self.assertEqual(results[2].distance, 2)
        self.assertEqual(results[2].node_id, "UserRepository")

    def test_multiple_paths_prefers_strongest_path(self) -> None:
        """Test Section 10: When multiple paths lead to node D, the strongest scoring path is chosen."""
        graph = GenericGraph()
        # Path 1: Target -> WeakBridge (TEST_RELATIONSHIP = 0.5) -> Destination (TEST_RELATIONSHIP = 0.5)
        # Path 2: Target -> StrongBridge (DIRECT_CALL = 1.0) -> Destination (DIRECT_CALL = 1.0)
        graph.add_edge("Target", "WeakBridge", "TEST_RELATIONSHIP")
        graph.add_edge("WeakBridge", "Destination", "TEST_RELATIONSHIP")
        graph.add_edge("Target", "StrongBridge", "DIRECT_CALL")
        graph.add_edge("StrongBridge", "Destination", "DIRECT_CALL")

        ranker = RelationshipRanker()
        results = ranker.rank(graph, "Target")

        dest = next(r for r in results if r.node_id == "Destination")
        # Should follow StrongBridge path
        self.assertEqual(dest.path, ("Target", "StrongBridge", "Destination"))
        self.assertEqual(dest.relationship_type, "DIRECT_CALL")
        self.assertAlmostEqual(dest.score, 1.00 * 0.70)  # strength 1.0 * decay(2)=0.70

    def test_custom_weights_reorder_ranking(self) -> None:
        """Changing relationship weights reverses/adjusts ranking positions."""
        graph = GenericGraph()
        # A --TYPE_REFERENCE--> B
        # A --IMPORT---------> C
        graph.add_edge("A", "B", "TYPE_REFERENCE")
        graph.add_edge("A", "C", "IMPORT")

        # By default: IMPORT(0.70) > TYPE_REFERENCE(0.60) => C ranked before B
        default_ranker = RelationshipRanker()
        def_results = default_ranker.rank(graph, "A")
        self.assertEqual([r.node_id for r in def_results], ["C", "B"])

        # Invert priority: TYPE_REFERENCE=0.99, IMPORT=0.10 => B ranked before C
        custom_cfg = RankerConfig(
            relationship_weights={"TYPE_REFERENCE": 0.99, "IMPORT": 0.10}
        )
        custom_ranker = RelationshipRanker(config=custom_cfg)
        cust_results = custom_ranker.rank(graph, "A")
        self.assertEqual([r.node_id for r in cust_results], ["B", "C"])


if __name__ == "__main__":
    unittest.main()
