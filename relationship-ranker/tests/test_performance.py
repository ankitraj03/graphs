"""Performance benchmark for Relationship Ranker (Phase 5).

Measures:
- Graph construction time
- BFS traversal and ranking time
- Memory usage (via tracemalloc)
Across scale benchmarks:
- 1,000 nodes
- 10,000 nodes
- 100,000 nodes
"""

from __future__ import annotations

import sys
import time
import tracemalloc
import unittest
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from relationship_ranker.graph import GenericGraph
from relationship_ranker.ranker import RelationshipRanker


def build_synthetic_graph(node_count: int, branching_factor: int = 3) -> GenericGraph:
    """Construct a synthetic tree-like graph with node_count nodes."""
    graph = GenericGraph()
    rel_types = ("IMPORT", "INCLUDE", "DIRECT_CALL", "TYPE_REFERENCE")

    for i in range(node_count):
        node_id = f"node_{i}"
        graph.add_node(node_id)

    # Connect nodes in a branching hierarchy
    for i in range(node_count):
        for b in range(1, branching_factor + 1):
            child_idx = i * branching_factor + b
            if child_idx < node_count:
                rel = rel_types[(i + b) % len(rel_types)]
                graph.add_edge(f"node_{i}", f"node_{child_idx}", rel)

    return graph


def run_benchmark_scale(node_count: int) -> dict[str, float]:
    """Run a single scale benchmark and return timing and memory metrics."""
    tracemalloc.start()
    t0 = time.perf_counter()
    graph = build_synthetic_graph(node_count=node_count, branching_factor=3)
    t_build = time.perf_counter() - t0

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    ranker = RelationshipRanker()
    t1 = time.perf_counter()
    results = ranker.rank(graph, "node_0", max_depth=5, top_k=50)
    t_rank = time.perf_counter() - t1

    return {
        "node_count": float(node_count),
        "edge_count": float(graph.edge_count),
        "build_time_sec": t_build,
        "rank_time_sec": t_rank,
        "peak_memory_mb": peak_mem / (1024 * 1024),
        "ranked_count": float(len(results)),
    }


class TestPerformance(unittest.TestCase):
    """Automated unit test verifying scale tests run cleanly."""

    def test_synthetic_1000_nodes(self) -> None:
        """Verify performance on 1,000 nodes."""
        metrics = run_benchmark_scale(1_000)
        self.assertEqual(metrics["node_count"], 1000)
        self.assertGreater(metrics["ranked_count"], 0)
        # Should be sub-second
        self.assertLess(metrics["rank_time_sec"], 0.5)

    def test_synthetic_10000_nodes(self) -> None:
        """Verify performance on 10,000 nodes."""
        metrics = run_benchmark_scale(10_000)
        self.assertEqual(metrics["node_count"], 10000)
        self.assertGreater(metrics["ranked_count"], 0)
        self.assertLess(metrics["rank_time_sec"], 1.0)


def main() -> None:
    print("=" * 70)
    print("RELATIONSHIP RANKER — PERFORMANCE BENCHMARK (PHASE 5)")
    print("=" * 70)
    print(f"{'Scale':<12} | {'Nodes':<10} | {'Edges':<10} | {'Build Time':<12} | {'Rank Time':<12} | {'Peak Mem':<10}")
    print("-" * 70)

    scales = (1_000, 10_000, 100_000)
    for scale in scales:
        m = run_benchmark_scale(scale)
        print(
            f"{scale:<12,} | "
            f"{int(m['node_count']):<10,} | "
            f"{int(m['edge_count']):<10,} | "
            f"{m['build_time_sec']:.4f}s      | "
            f"{m['rank_time_sec']:.5f}s     | "
            f"{m['peak_memory_mb']:.2f} MB"
        )

    print("=" * 70)
    print("Benchmark complete.")


if __name__ == "__main__":
    main()
