"""BFS traversal engine for the Relationship Ranker.

Traverses a generic directed graph starting from a target node:
- Cycle-safe with explicit cycle detection per path
- Level-by-level BFS distance assignment
- Configurable maximum depth
- Direction-aware: OUTGOING, INCOMING, BOTH
- Deterministic path resolution when multiple paths reach the same node
"""

from __future__ import annotations

from collections import deque
from typing import Callable

from relationship_ranker.config import RankerConfig
from relationship_ranker.graph import GenericGraph
from relationship_ranker.models import Edge, PathStep, TraversalDirection, TraversalPath


class BfsTraverser:
    """Cycle-safe BFS graph traversal engine."""

    def __init__(self, config: RankerConfig | None = None) -> None:
        self.config = config or RankerConfig()

    def traverse(
        self,
        graph: GenericGraph,
        target_node_id: str,
        max_depth: int | None = None,
        direction: TraversalDirection | str | None = None,
        score_evaluator: Callable[[TraversalPath], float] | None = None,
    ) -> dict[str, TraversalPath]:
        """Perform cycle-safe BFS traversal from target_node_id.

        Args:
            graph: The GenericGraph instance to traverse.
            target_node_id: The starting node identifier.
            max_depth: Optional override for maximum traversal depth.
            direction: Optional override for traversal direction (OUTGOING, INCOMING, BOTH).
            score_evaluator: Optional function to score paths when resolving multiple paths
                             to the same node at the same BFS distance.

        Returns:
            Dictionary mapping reached node_id -> optimal TraversalPath.
        """
        if not graph.has_node(target_node_id):
            return {}

        effective_max_depth = self.config.max_depth if max_depth is None else max_depth
        if effective_max_depth < 0:
            return {}

        if direction is None:
            effective_dir = self.config.direction
        else:
            effective_dir = TraversalDirection.from_str(direction)

        # best_paths stores the optimal path for each reached node
        best_paths: dict[str, TraversalPath] = {}
        # visited_distance stores the BFS shortest hop distance to each node
        visited_distance: dict[str, int] = {target_node_id: 0}

        # Queue items: (current_node, distance, path_nodes_tuple, path_steps_tuple)
        queue: deque[tuple[str, int, tuple[str, ...], tuple[PathStep, ...]]] = deque()
        queue.append((target_node_id, 0, (target_node_id,), ()))

        while queue:
            curr_id, dist, path_nodes, steps = queue.popleft()

            if dist >= effective_max_depth:
                continue

            next_dist = dist + 1

            # Discover neighbors based on traversal direction
            transitions: list[tuple[str, Edge, TraversalDirection]] = []

            if effective_dir in (TraversalDirection.OUTGOING, TraversalDirection.BOTH):
                for edge in graph.get_outgoing_edges(curr_id):
                    transitions.append((edge.target, edge, TraversalDirection.OUTGOING))

            if effective_dir in (TraversalDirection.INCOMING, TraversalDirection.BOTH):
                for edge in graph.get_incoming_edges(curr_id):
                    transitions.append((edge.source, edge, TraversalDirection.INCOMING))

            # Deterministic sorting of transitions for reproducible discovery
            transitions.sort(key=lambda t: (t[0], t[1].relationship_type, t[2].value))

            for next_id, edge, step_dir in transitions:
                # 1. Skip self-edges
                if next_id == curr_id:
                    continue

                # 2. Cycle-safety: Do not revisit any node already on the current path
                if next_id in path_nodes:
                    continue

                step = PathStep(
                    from_node=curr_id,
                    to_node=next_id,
                    edge=edge,
                    step_direction=step_dir,
                )
                cand_path = TraversalPath(
                    target_node_id=next_id,
                    distance=next_dist,
                    nodes=path_nodes + (next_id,),
                    steps=steps + (step,),
                )

                # 3. Check if already visited at a shorter BFS distance
                if next_id in visited_distance and visited_distance[next_id] < next_dist:
                    continue

                # 4. If reached at the same BFS distance via another path: resolve best path
                if next_id in visited_distance and visited_distance[next_id] == next_dist:
                    existing_path = best_paths.get(next_id)
                    if existing_path is not None:
                        # Compare paths: prefer higher score; tie-break lexicographically
                        existing_score = (
                            score_evaluator(existing_path) if score_evaluator else 0.0
                        )
                        cand_score = (
                            score_evaluator(cand_path) if score_evaluator else 0.0
                        )

                        if cand_score > existing_score:
                            best_paths[next_id] = cand_path
                        elif cand_score == existing_score and cand_path.nodes < existing_path.nodes:
                            best_paths[next_id] = cand_path
                    continue

                # 5. First time discovering next_id at next_dist
                visited_distance[next_id] = next_dist
                best_paths[next_id] = cand_path
                queue.append((next_id, next_dist, cand_path.nodes, cand_path.steps))

        return best_paths
