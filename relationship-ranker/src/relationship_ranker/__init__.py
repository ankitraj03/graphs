"""Phase 5: Relationship Ranker package.

An independent, in-memory graph ranking library that determines the nearest
and most structurally relevant nodes from a target node using BFS traversal,
relationship weighting, distance decay, and deterministic Top-K ranking.
"""

from __future__ import annotations

from relationship_ranker.config import (
    DEFAULT_DISTANCE_DECAY,
    DEFAULT_FALLBACK_DECAY_FACTOR,
    DEFAULT_FALLBACK_RELATIONSHIP_WEIGHT,
    DEFAULT_MAX_DEPTH,
    DEFAULT_RELATIONSHIP_WEIGHTS,
    RankerConfig,
)
from relationship_ranker.exceptions import (
    ConfigurationError,
    InvalidGraphError,
    NodeNotFoundError,
    RankerError,
)
from relationship_ranker.graph import GenericGraph
from relationship_ranker.models import (
    Edge,
    Node,
    PathStep,
    RankedNode,
    TraversalDirection,
    TraversalPath,
)
from relationship_ranker.ranker import RelationshipRanker
from relationship_ranker.scoring import RelevanceScorer, ScoreComponents
from relationship_ranker.traversal import BfsTraverser

__all__ = [
    "BfsTraverser",
    "ConfigurationError",
    "DEFAULT_DISTANCE_DECAY",
    "DEFAULT_FALLBACK_DECAY_FACTOR",
    "DEFAULT_FALLBACK_RELATIONSHIP_WEIGHT",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_RELATIONSHIP_WEIGHTS",
    "Edge",
    "GenericGraph",
    "InvalidGraphError",
    "Node",
    "NodeNotFoundError",
    "PathStep",
    "RankedNode",
    "RankerConfig",
    "RankerError",
    "RelationshipRanker",
    "RelevanceScorer",
    "ScoreComponents",
    "TraversalDirection",
    "TraversalPath",
]
