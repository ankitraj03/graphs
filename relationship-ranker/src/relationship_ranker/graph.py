"""Generic in-memory directed graph model for the Relationship Ranker.

Strictly independent of prior phases. Provides O(1) node and edge indexing
and fast retrieval of outgoing, incoming, and undirected neighbors.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from relationship_ranker.exceptions import InvalidGraphError
from relationship_ranker.models import Edge, Node


class GenericGraph:
    """In-memory directed property graph backed by adjacency maps and hash sets."""

    def __init__(self) -> None:
        self._nodes: dict[str, Node] = {}
        self._edges: set[Edge] = set()
        self._outgoing_edges: dict[str, list[Edge]] = defaultdict(list)
        self._incoming_edges: dict[str, list[Edge]] = defaultdict(list)

    @property
    def node_count(self) -> int:
        """Total number of unique nodes in the graph."""
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Total number of unique edges in the graph."""
        return len(self._edges)

    @property
    def nodes(self) -> dict[str, Node]:
        """Read-only view of nodes dictionary."""
        return dict(self._nodes)

    @property
    def edges(self) -> set[Edge]:
        """Read-only view of edges set."""
        return set(self._edges)

    def add_node(self, node: Node | str, metadata: dict[str, Any] | None = None) -> Node:
        """Add a node to the graph if not already present.

        Args:
            node: Node instance or string node_id.
            metadata: Optional dictionary of node attributes.

        Returns:
            The registered Node instance.
        """
        if isinstance(node, str):
            node_id = node.strip()
            if not node_id:
                raise InvalidGraphError("Cannot add a node with an empty node_id.")
            node_obj = Node(node_id=node_id, metadata=metadata or {})
        elif isinstance(node, Node):
            node_obj = node
        else:
            raise InvalidGraphError(f"Expected Node or str, got {type(node).__name__}")

        if node_obj.node_id not in self._nodes:
            self._nodes[node_obj.node_id] = node_obj

        return self._nodes[node_obj.node_id]

    def has_node(self, node_id: str) -> bool:
        """Check whether a node exists in the graph."""
        return node_id in self._nodes

    def get_node(self, node_id: str) -> Node | None:
        """Retrieve a Node by its ID, or None if not found."""
        return self._nodes.get(node_id)

    def add_edge(
        self,
        source_or_edge: Edge | str,
        target: str | None = None,
        relationship_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Edge:
        """Add a directed edge linking source to target.

        Supports two invocation styles:
            graph.add_edge(Edge(source, target, rel_type))
            graph.add_edge(source, target, rel_type, metadata)

        Automatically registers endpoint nodes if they do not yet exist.
        Deduplicates identical (source, target, relationship_type) edges.
        """
        if isinstance(source_or_edge, Edge):
            edge = source_or_edge
        else:
            if target is None or relationship_type is None:
                raise InvalidGraphError(
                    "Must supply target and relationship_type when adding edge by strings."
                )
            edge = Edge(
                source=source_or_edge,
                target=target,
                relationship_type=relationship_type,
                metadata=metadata or {},
            )

        # Register endpoints if not present
        if edge.source not in self._nodes:
            self.add_node(edge.source)
        if edge.target not in self._nodes:
            self.add_node(edge.target)

        # Duplicate edge prevention: identical (source, target, relationship_type)
        if edge in self._edges:
            return edge

        self._edges.add(edge)
        self._outgoing_edges[edge.source].append(edge)
        self._incoming_edges[edge.target].append(edge)
        return edge

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        """Return a copy of all outgoing edges originating from node_id."""
        return list(self._outgoing_edges.get(node_id, []))

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        """Return a copy of all incoming edges terminating at node_id."""
        return list(self._incoming_edges.get(node_id, []))

    def get_outgoing_neighbors(self, node_id: str) -> list[str]:
        """Return unique node IDs directly reached via outgoing edges from node_id."""
        seen: set[str] = set()
        neighbors: list[str] = []
        for edge in self._outgoing_edges.get(node_id, []):
            if edge.target not in seen:
                seen.add(edge.target)
                neighbors.append(edge.target)
        return neighbors

    def get_incoming_neighbors(self, node_id: str) -> list[str]:
        """Return unique node IDs pointing directly into node_id via incoming edges."""
        seen: set[str] = set()
        neighbors: list[str] = []
        for edge in self._incoming_edges.get(node_id, []):
            if edge.source not in seen:
                seen.add(edge.source)
                neighbors.append(edge.source)
        return neighbors

    def get_neighbors(self, node_id: str) -> list[str]:
        """Return all unique adjacent node IDs (union of incoming and outgoing neighbors)."""
        seen: set[str] = set()
        neighbors: list[str] = []
        for n in self.get_outgoing_neighbors(node_id):
            if n not in seen:
                seen.add(n)
                neighbors.append(n)
        for n in self.get_incoming_neighbors(node_id):
            if n not in seen:
                seen.add(n)
                neighbors.append(n)
        return neighbors

    def clear(self) -> None:
        """Deallocate and clear all nodes and edges from the graph."""
        self._nodes.clear()
        self._edges.clear()
        self._outgoing_edges.clear()
        self._incoming_edges.clear()
