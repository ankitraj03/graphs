"""Configuration models for the Relationship Ranker.

Defines configurable relationship weights, distance-decay tables, and traversal settings.
Documented as initial heuristic values subject to future empirical validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from relationship_ranker.exceptions import ConfigurationError
from relationship_ranker.models import TraversalDirection

# ============================================================================
# Initial Heuristic Defaults
# NOTE: These values are initial engineering heuristics and have not yet been
# scientifically calibrated. They can be freely configured per project/analysis.
# ============================================================================

DEFAULT_RELATIONSHIP_WEIGHTS: dict[str, float] = {
    "DIRECT_CALL": 1.00,
    "IMPORT": 0.70,
    "INCLUDE": 0.70,
    "TYPE_REFERENCE": 0.60,
    "TEST_RELATIONSHIP": 0.50,
}

DEFAULT_FALLBACK_RELATIONSHIP_WEIGHT: float = 0.50

DEFAULT_DISTANCE_DECAY: dict[int, float] = {
    0: 1.00,
    1: 1.00,
    2: 0.70,
    3: 0.40,
    4: 0.20,
}

DEFAULT_FALLBACK_DECAY_FACTOR: float = 0.50
DEFAULT_MAX_DEPTH: int = 5


@dataclass(frozen=True, slots=True)
class RankerConfig:
    """Immutable configuration for traversal, scoring, and ranking."""

    relationship_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_RELATIONSHIP_WEIGHTS)
    )
    fallback_relationship_weight: float = DEFAULT_FALLBACK_RELATIONSHIP_WEIGHT
    distance_decay: dict[int, float] = field(
        default_factory=lambda: dict(DEFAULT_DISTANCE_DECAY)
    )
    fallback_decay_factor: float = DEFAULT_FALLBACK_DECAY_FACTOR
    max_depth: int = DEFAULT_MAX_DEPTH
    direction: TraversalDirection = TraversalDirection.OUTGOING
    path_aggregation_strategy: str = "min"  # "min", "product", "last_edge", "average"

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ConfigurationError(f"max_depth cannot be negative (got {self.max_depth}).")
        if self.fallback_relationship_weight < 0.0 or self.fallback_relationship_weight > 1.0:
            raise ConfigurationError(
                f"fallback_relationship_weight must be in [0.0, 1.0] (got {self.fallback_relationship_weight})."
            )
        for rel, weight in self.relationship_weights.items():
            if weight < 0.0:
                raise ConfigurationError(f"Weight for relationship '{rel}' cannot be negative ({weight}).")
        for dist, decay in self.distance_decay.items():
            if dist < 0 or decay < 0.0:
                raise ConfigurationError(f"Distance decay at {dist} must be non-negative ({decay}).")

    def get_relationship_weight(self, relationship_type: str) -> float:
        """Retrieve the configured weight for a relationship type, or fallback."""
        key = relationship_type.strip().upper()
        return self.relationship_weights.get(key, self.fallback_relationship_weight)

    def get_distance_decay(self, distance: int) -> float:
        """Retrieve the distance decay multiplier for a given graph distance.

        If distance exceeds the defined table, an exponential decay based on the
        furthest defined distance and fallback_decay_factor is computed.
        """
        if distance < 0:
            return 0.0
        if distance in self.distance_decay:
            return self.distance_decay[distance]

        # Dynamic fallback for deep distances beyond the table
        max_defined_dist = max(self.distance_decay.keys(), default=0)
        base_decay = self.distance_decay.get(max_defined_dist, 0.20)
        extra_hops = distance - max_defined_dist
        decay = base_decay * (self.fallback_decay_factor ** extra_hops)
        return max(0.0, min(1.0, decay))
