"""Relevance scoring engine for graph relationships and paths.

Isolates scoring calculations from graph traversal algorithms, computing:
    relevance_score = relationship_strength * distance_decay
Supports configurable multi-hop path strength strategies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from relationship_ranker.config import RankerConfig
from relationship_ranker.models import TraversalPath


@dataclass(frozen=True, slots=True)
class ScoreComponents:
    """Detailed breakdown of the relevance score calculation for a path."""

    score: float
    relationship_strength: float
    distance_decay: float


class RelevanceScorer:
    """Computes relevance scores based on relationship strength and distance decay."""

    def __init__(self, config: RankerConfig | None = None) -> None:
        self.config = config or RankerConfig()

    def calculate_path_strength(self, path: TraversalPath) -> float:
        """Compute the effective relationship strength along a traversal path.

        Supported strategies in RankerConfig:
        - 'min' (default): Bottleneck minimum weight across all steps on the path.
        - 'product': Cumulative product of weights along all path steps.
        - 'last_edge': Weight of the final edge directly connecting to the target.
        - 'average': Arithmetic mean of edge weights on the path.
        """
        if not path.steps:
            return 1.0

        weights = [
            self.config.get_relationship_weight(step.edge.relationship_type)
            for step in path.steps
        ]

        strategy = self.config.path_aggregation_strategy
        if strategy == "min":
            return min(weights)
        elif strategy == "product":
            return math.prod(weights)
        elif strategy == "last_edge":
            return weights[-1]
        elif strategy == "average":
            return sum(weights) / len(weights)
        else:
            # Fallback to min
            return min(weights)

    def score_path(self, path: TraversalPath) -> ScoreComponents:
        """Calculate the full score breakdown for a discovered traversal path.

        Formula:
            score = relationship_strength * distance_decay
        """
        if path.distance == 0:
            return ScoreComponents(score=1.0, relationship_strength=1.0, distance_decay=1.0)

        strength = self.calculate_path_strength(path)
        decay = self.config.get_distance_decay(path.distance)
        score = strength * decay

        return ScoreComponents(
            score=score,
            relationship_strength=strength,
            distance_decay=decay,
        )
