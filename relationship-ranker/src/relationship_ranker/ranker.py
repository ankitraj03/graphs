"""Relationship Ranker main orchestration component.

Determines the nearest and most structurally relevant nodes from a target node:
    Rank = BFS traversal + Relationship strength + Distance decay + Top-K
"""

from __future__ import annotations

from typing import Sequence

from relationship_ranker.config import RankerConfig
from relationship_ranker.exceptions import NodeNotFoundError
from relationship_ranker.graph import GenericGraph
from relationship_ranker.models import RankedNode, TraversalDirection
from relationship_ranker.scoring import RelevanceScorer
from relationship_ranker.traversal import BfsTraverser


class RelationshipRanker:
    """Orchestrates graph traversal, scoring, and deterministic ranking."""

    def __init__(
        self,
        config: RankerConfig | None = None,
        scorer: RelevanceScorer | None = None,
        traverser: BfsTraverser | None = None,
    ) -> None:
        self.config = config or RankerConfig()
        self.scorer = scorer or RelevanceScorer(config=self.config)
        self.traverser = traverser or BfsTraverser(config=self.config)

    def rank(
        self,
        graph: GenericGraph,
        target_node_id: str,
        top_k: int | None = None,
        max_depth: int | None = None,
        direction: TraversalDirection | str | None = None,
        include_target: bool = False,
    ) -> list[RankedNode]:
        """Rank reachable nodes in graph by relevance to target_node_id.

        Args:
            graph: The GenericGraph instance.
            target_node_id: The originating node identifier.
            top_k: Optional limit on the number of returned results.
            max_depth: Optional override for traversal depth.
            direction: Optional override for traversal direction (OUTGOING, INCOMING, BOTH).
            include_target: Whether to include the target node itself in the output list.

        Returns:
            List of RankedNode objects sorted from highest relevance to lowest.

        Raises:
            NodeNotFoundError: If target_node_id does not exist in graph.
        """
        if not graph.has_node(target_node_id):
            raise NodeNotFoundError(
                f"Target node '{target_node_id}' does not exist in graph."
            )

        # 1. Execute BFS traversal with path-score evaluation for multiple paths
        paths = self.traverser.traverse(
            graph=graph,
            target_node_id=target_node_id,
            max_depth=max_depth,
            direction=direction,
            score_evaluator=lambda p: self.scorer.score_path(p).score,
        )

        ranked: list[RankedNode] = []

        # 2. Optionally include target node (distance 0)
        if include_target:
            target_node = graph.get_node(target_node_id)
            meta = dict(target_node.metadata) if target_node else {}
            meta.update({"relationship_strength": 1.0, "distance_decay": 1.0})
            ranked.append(
                RankedNode(
                    node_id=target_node_id,
                    score=1.0,
                    distance=0,
                    relationship_type="SELF",
                    direction="SELF",
                    path=(target_node_id,),
                    metadata=meta,
                )
            )

        # 3. Score all discovered nodes
        for node_id, path in paths.items():
            if node_id == target_node_id:
                continue

            score_comp = self.scorer.score_path(path)
            node_obj = graph.get_node(node_id)
            meta = dict(node_obj.metadata) if node_obj else {}
            meta["relationship_strength"] = round(score_comp.relationship_strength, 6)
            meta["distance_decay"] = round(score_comp.distance_decay, 6)

            ranked.append(
                RankedNode(
                    node_id=node_id,
                    score=score_comp.score,
                    distance=path.distance,
                    relationship_type=path.primary_relationship_type,
                    direction=path.primary_direction,
                    path=path.nodes,
                    metadata=meta,
                )
            )

        # 4. Deterministic sorting:
        # - Primary: score descending
        # - Secondary: distance ascending
        # - Tertiary (tie-breaker): node_id ascending (lexicographical)
        ranked.sort(key=lambda r: (-round(r.score, 6), r.distance, r.node_id))

        # 5. Apply Top-K cutoff if specified
        if top_k is not None:
            if top_k < 0:
                return []
            return ranked[:top_k]

        return ranked

    @staticmethod
    def format_results(
        target_node_id: str,
        results: Sequence[RankedNode],
        direction: str = "OUTGOING",
        max_depth: int | None = None,
    ) -> str:
        """Produce human-readable terminal output of ranking results."""
        lines: list[str] = [
            "=" * 50,
            "RELATIONSHIP RANKER RESULTS",
            "=" * 50,
            f"Target Node: {target_node_id}",
            f"Direction:   {direction}",
        ]
        if max_depth is not None:
            lines.append(f"Max Depth:   {max_depth}")
        lines.append(f"Ranked Nodes: {len(results)}")
        lines.append("-" * 50)

        if not results:
            lines.append("  (No relevant nodes found)")
            lines.append("=" * 50)
            return "\n".join(lines)

        for i, item in enumerate(results, 1):
            path_str = " -> ".join(item.path)
            lines.append(f"{i}. {item.node_id}")
            lines.append(f"   score:             {item.score:.4f}")
            lines.append(f"   distance:          {item.distance}")
            lines.append(f"   relationship_type: {item.relationship_type}")
            lines.append(f"   direction:         {item.direction}")
            lines.append(f"   path:              {path_str}")
            lines.append("")

        lines.append("=" * 50)
        return "\n".join(lines)
