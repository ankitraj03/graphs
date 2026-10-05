"""Basic Demonstration of the Relationship Ranker (Phase 5).

Demonstrates ranking nodes relative to a target node in a microservice/architecture graph:
- UserController depends on AuthService, UserService, UserRoutes
- AuthService depends on UserRepository
- UserRepository depends on User
- Disconnected component: PaymentService -> Payment (should NOT appear)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on sys.path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker import GenericGraph, RelationshipRanker, TraversalDirection


def main() -> None:
    print("=" * 60)
    print("PHASE 5: RELATIONSHIP RANKER — BASIC DEMONSTRATION")
    print("=" * 60)

    # 1. Build the demonstration graph
    graph = GenericGraph()

    # Connected component: User Domain
    graph.add_edge("UserController", "AuthService", "IMPORT")
    graph.add_edge("UserController", "UserService", "IMPORT")
    graph.add_edge("UserController", "UserRoutes", "DIRECT_CALL")
    graph.add_edge("AuthService", "UserRepository", "IMPORT")
    graph.add_edge("UserRepository", "User", "TYPE_REFERENCE")

    # Disconnected component: Payment Domain
    graph.add_edge("PaymentService", "Payment", "IMPORT")

    print(f"Graph initialized with {graph.node_count} nodes and {graph.edge_count} edges.\n")

    # 2. Run Ranker starting from UserController
    ranker = RelationshipRanker()
    target = "UserController"

    print(f"Running ranking from target: '{target}' (OUTGOING, max_depth=5)...")
    results = ranker.rank(
        graph=graph,
        target_node_id=target,
        direction=TraversalDirection.OUTGOING,
        max_depth=5,
    )

    # 3. Display formatted output
    formatted = ranker.format_results(
        target_node_id=target,
        results=results,
        direction="OUTGOING",
        max_depth=5,
    )
    print(formatted)

    # 4. Verify disconnected nodes
    ranked_node_ids = {r.node_id for r in results}
    assert "PaymentService" not in ranked_node_ids, "PaymentService should be disconnected!"
    assert "Payment" not in ranked_node_ids, "Payment should be disconnected!"
    print("\nVerification passed: Disconnected nodes (PaymentService, Payment) are correctly excluded.")


if __name__ == "__main__":
    main()
