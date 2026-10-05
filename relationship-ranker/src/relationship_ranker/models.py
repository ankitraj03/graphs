"""Data models for the Relationship Ranker component.

Strictly independent of prior phases. Generic node and edge representations
capable of modeling files, classes, functions, or any future graph entity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TraversalDirection(str, Enum):
    """Direction for graph traversal from the target node."""

    OUTGOING = "OUTGOING"
    INCOMING = "INCOMING"
    BOTH = "BOTH"

    @classmethod
    def from_str(cls, val: str | TraversalDirection) -> TraversalDirection:
        """Parse string or enum into TraversalDirection."""
        if isinstance(val, cls):
            return val
        clean = val.strip().upper()
        try:
            return cls(clean)
        except ValueError as err:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(f"Invalid traversal direction '{val}'. Must be one of: {valid}") from err


@dataclass(frozen=True, slots=True)
class Node:
    """Generic graph node.

    Architectural requirement: Does not assume nodes are files.
    Can represent files, classes, methods, modules, or any future entity.
    """

    node_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id or not isinstance(self.node_id, str):
            raise ValueError("Node node_id must be a non-empty string.")

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return False
        return self.node_id == other.node_id


@dataclass(frozen=True, slots=True)
class Edge:
    """Generic directed relationship edge between two nodes.

    source --relationship_type--> target
    """

    source: str
    target: str
    relationship_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source or not isinstance(self.source, str):
            raise ValueError("Edge source must be a non-empty string.")
        if not self.target or not isinstance(self.target, str):
            raise ValueError("Edge target must be a non-empty string.")
        if not self.relationship_type or not isinstance(self.relationship_type, str):
            raise ValueError("Edge relationship_type must be a non-empty string.")

    def __hash__(self) -> int:
        return hash((self.source, self.target, self.relationship_type))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Edge):
            return False
        return (
            self.source == other.source
            and self.target == other.target
            and self.relationship_type == other.relationship_type
        )


@dataclass(frozen=True, slots=True)
class PathStep:
    """Represents a single step in a traversal path."""

    from_node: str
    to_node: str
    edge: Edge
    step_direction: TraversalDirection


@dataclass(frozen=True, slots=True)
class TraversalPath:
    """Discovered path from target to a reachable node."""

    target_node_id: str
    distance: int
    nodes: tuple[str, ...]
    steps: tuple[PathStep, ...] = field(default_factory=tuple)

    @property
    def final_edge(self) -> Edge | None:
        """The last edge traversed to reach the target node."""
        if self.steps:
            return self.steps[-1].edge
        return None

    @property
    def primary_relationship_type(self) -> str:
        """The relationship type leading into the destination node."""
        if self.steps:
            return self.steps[-1].edge.relationship_type
        return "UNKNOWN"

    @property
    def primary_direction(self) -> str:
        """The primary traversal direction along this path."""
        if not self.steps:
            return "OUTGOING"
        dirs = {s.step_direction for s in self.steps}
        if len(dirs) == 1:
            return next(iter(dirs)).value
        return "BOTH"


@dataclass(frozen=True, slots=True)
class RankedNode:
    """Rich ranking result model representing a relevant node discovered from the target."""

    node_id: str
    score: float
    distance: int
    relationship_type: str
    direction: str
    path: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize ranked node to a dictionary representation."""
        return {
            "node_id": self.node_id,
            "score": round(self.score, 6),
            "distance": self.distance,
            "relationship_type": self.relationship_type,
            "direction": self.direction,
            "path": list(self.path),
            "metadata": dict(self.metadata),
        }
