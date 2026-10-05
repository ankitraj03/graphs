"""Unit tests for RelevanceScorer (Phase 5).

Tests:
- Relationship weights configuration and retrieval
- Distance decay configuration and decay curves
- Score calculation formula: relationship_strength * distance_decay
- Unknown relationship type fallback weight
- Multi-hop path aggregation strategies (min, product, last_edge, average)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker.config import RankerConfig
from relationship_ranker.models import Edge, PathStep, TraversalDirection, TraversalPath
from relationship_ranker.scoring import RelevanceScorer


class TestRelevanceScorer(unittest.TestCase):
    """Test suite for RelevanceScorer and RankerConfig."""

    def test_default_relationship_weights(self) -> None:
        """Test 12: Default relationship weights match specification."""
        config = RankerConfig()
        self.assertEqual(config.get_relationship_weight("DIRECT_CALL"), 1.00)
        self.assertEqual(config.get_relationship_weight("IMPORT"), 0.70)
        self.assertEqual(config.get_relationship_weight("INCLUDE"), 0.70)
        self.assertEqual(config.get_relationship_weight("TYPE_REFERENCE"), 0.60)
        self.assertEqual(config.get_relationship_weight("TEST_RELATIONSHIP"), 0.50)

    def test_unknown_relationship_fallback(self) -> None:
        """Test 19: Unknown relationship type falls back to configurable default."""
        config = RankerConfig(fallback_relationship_weight=0.42)
        self.assertEqual(config.get_relationship_weight("NON_EXISTENT_REL"), 0.42)
        self.assertEqual(config.get_relationship_weight("custom_type"), 0.42)

    def test_custom_relationship_weights(self) -> None:
        """Test custom relationship weights configuration."""
        custom_weights = {"INHERITS": 0.95, "CALLS": 0.85}
        config = RankerConfig(relationship_weights=custom_weights, fallback_relationship_weight=0.30)
        self.assertEqual(config.get_relationship_weight("INHERITS"), 0.95)
        self.assertEqual(config.get_relationship_weight("CALLS"), 0.85)
        self.assertEqual(config.get_relationship_weight("IMPORT"), 0.30)

    def test_distance_decay(self) -> None:
        """Test 13: Configurable distance decay values."""
        config = RankerConfig()
        self.assertEqual(config.get_distance_decay(0), 1.00)
        self.assertEqual(config.get_distance_decay(1), 1.00)
        self.assertEqual(config.get_distance_decay(2), 0.70)
        self.assertEqual(config.get_distance_decay(3), 0.40)
        self.assertEqual(config.get_distance_decay(4), 0.20)
        # Distance > 4 falls back exponentially
        self.assertAlmostEqual(config.get_distance_decay(5), 0.10)
        self.assertAlmostEqual(config.get_distance_decay(6), 0.05)

    def test_score_calculation(self) -> None:
        """Test 14: Score formula: relationship_strength * distance_decay."""
        config = RankerConfig(
            relationship_weights={"IMPORT": 0.80},
            distance_decay={1: 1.00, 2: 0.70, 3: 0.50},
        )
        scorer = RelevanceScorer(config)

        # 1-hop path with IMPORT at distance 1
        e1 = Edge("A", "B", "IMPORT")
        step1 = PathStep("A", "B", e1, TraversalDirection.OUTGOING)
        path1 = TraversalPath(target_node_id="B", distance=1, nodes=("A", "B"), steps=(step1,))

        res1 = scorer.score_path(path1)
        self.assertAlmostEqual(res1.relationship_strength, 0.80)
        self.assertAlmostEqual(res1.distance_decay, 1.00)
        self.assertAlmostEqual(res1.score, 0.80)

        # 2-hop path with IMPORT at distance 2
        e2 = Edge("B", "C", "IMPORT")
        step2 = PathStep("B", "C", e2, TraversalDirection.OUTGOING)
        path2 = TraversalPath(target_node_id="C", distance=2, nodes=("A", "B", "C"), steps=(step1, step2))

        res2 = scorer.score_path(path2)
        self.assertAlmostEqual(res2.relationship_strength, 0.80)
        self.assertAlmostEqual(res2.distance_decay, 0.70)
        self.assertAlmostEqual(res2.score, 0.80 * 0.70)

    def test_path_aggregation_strategies(self) -> None:
        """Test different path aggregation strategies for multi-hop paths."""
        e1 = Edge("A", "B", "DIRECT_CALL")  # weight 1.0
        e2 = Edge("B", "C", "IMPORT")       # weight 0.5
        steps = (
            PathStep("A", "B", e1, TraversalDirection.OUTGOING),
            PathStep("B", "C", e2, TraversalDirection.OUTGOING),
        )
        path = TraversalPath(target_node_id="C", distance=2, nodes=("A", "B", "C"), steps=steps)

        # 1. Strategy "min": min(1.0, 0.5) = 0.5
        cfg_min = RankerConfig(
            relationship_weights={"DIRECT_CALL": 1.0, "IMPORT": 0.5},
            path_aggregation_strategy="min",
        )
        scorer_min = RelevanceScorer(cfg_min)
        self.assertEqual(scorer_min.calculate_path_strength(path), 0.5)

        # 2. Strategy "product": 1.0 * 0.5 = 0.5
        cfg_prod = RankerConfig(
            relationship_weights={"DIRECT_CALL": 0.8, "IMPORT": 0.5},
            path_aggregation_strategy="product",
        )
        scorer_prod = RelevanceScorer(cfg_prod)
        self.assertAlmostEqual(scorer_prod.calculate_path_strength(path), 0.8 * 0.5)

        # 3. Strategy "average": (1.0 + 0.5) / 2 = 0.75
        cfg_avg = RankerConfig(
            relationship_weights={"DIRECT_CALL": 1.0, "IMPORT": 0.5},
            path_aggregation_strategy="average",
        )
        scorer_avg = RelevanceScorer(cfg_avg)
        self.assertEqual(scorer_avg.calculate_path_strength(path), 0.75)


if __name__ == "__main__":
    unittest.main()
