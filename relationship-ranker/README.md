# Phase 5: Relationship Ranker

The **Relationship Ranker** is an independent, in-memory graph ranking engine for the `graphs` static-analysis architecture. Given a target node (such as a source file, class, or function) and an in-memory graph, it discovers and ranks the nearest, most structurally relevant nodes.

---

## 1. Why the Relationship Ranker Exists

In massive repositories (targeting 200,000+ files), inspecting or traversing an entire dependency graph is computationally prohibitive and generates excessive noise. An AI agent or developer investigating a bug or planning a refactoring operation needs to answer:

> *"Starting from this specific entity, which other entities are structurally closest and most relevant, and why?"*

The Relationship Ranker provides a deterministic, mathematically grounded structural relevance score for every reachable entity.

---

## 2. Core Responsibilities & Non-Goals

### What the Relationship Ranker DOES:
1. **Structural Proximity**: Computes BFS shortest hop distances from the target node.
2. **Relationship Weighting**: Evaluates edge relationship types using configurable weights.
3. **Distance Decay**: Penalizes nodes that are further away in the graph.
4. **Relevance Scoring**: Computes $\text{score} = \text{relationship\_strength} \times \text{distance\_decay}$.
5. **Path Attribution**: Explains *why* a node is relevant by retaining the full path of entities and relationships.
6. **Multi-Directional Traversal**: Supports `OUTGOING`, `INCOMING`, and `BOTH` (bidirectional) traversals.
7. **Deterministic Top-K**: Returns the top $K$ most relevant nodes with deterministic tie-breaking.

### What the Relationship Ranker DOES NOT do:
- **No Natural Language / Task Understanding**: Does not parse user intent or conversational queries (reserved for later phases).
- **No Vector DBs or Embeddings**: Operates purely on explicit syntactic and structural graph edges without probabilistic vectors.
- **No LLM / External AI API Calls**: Calculates relevance entirely in-memory using deterministic graph algorithms.
- **No Persistence or Database**: Does not read or write to disk, SQLite, PostgreSQL, or Neo4j.
- **No Coupling to Previous Phases**: Does not import or depend on Scanner, Tokenizer, Connector, or Graph Designer.

---

## 3. Architecture & Separation of Concerns

```text
                  GenericGraph
                        │
                        ▼
                Target Node ID
                        │
                        ▼
             ┌─────────────────────┐
             │    BfsTraverser     │  ◄── Cycle-safe, directional, bounded BFS
             └──────────┬──────────┘
                        │ Discovered TraversalPaths
                        ▼
             ┌─────────────────────┐
             │   RelevanceScorer   │  ◄── Strength × Distance Decay
             └──────────┬──────────┘
                        │ Scored Paths
                        ▼
             ┌─────────────────────┐
             │ RelationshipRanker  │  ◄── Deterministic Sorting & Top-K Slicing
             └──────────┬──────────┘
                        │
                        ▼
                 list[RankedNode]
```

### Component Layout
```text
relationship-ranker/
├── README.md                  # Complete architectural documentation & benchmarks
├── requirements.txt           # Standard library only (no external dependencies)
├── run_tests.py               # Test discovery runner
├── src/
│   └── relationship_ranker/
│       ├── __init__.py        # Public library API exports
│       ├── models.py          # Node, Edge, TraversalPath, RankedNode, TraversalDirection
│       ├── graph.py           # GenericGraph in-memory directed property graph
│       ├── config.py          # Configurable weights, decay tables, and settings
│       ├── scoring.py         # RelevanceScorer (strength * decay calculation)
│       ├── traversal.py       # Cycle-safe BFS traversal engine
│       ├── ranker.py          # RelationshipRanker coordinator & formatting
│       └── exceptions.py      # RankerError domain hierarchy
├── tests/
│       ├── test_graph.py      # Node/edge creation, deduplication, neighbors
│       ├── test_traversal.py  # BFS distances, max depth, incoming/bidirectional
│       ├── test_scoring.py    # Weights, decay curves, path aggregation
│       ├── test_ranker.py     # Deterministic ranking order, Top-K, serialization
│       ├── test_cycles.py     # Self-edges, mutual recursion, complex rings
│       ├── test_direction.py  # Outgoing vs incoming vs bidirectional isolation
│       ├── test_ranking.py    # Microservice scenarios, multi-path selection
│       └── test_performance.py # 1k, 10k, 100k synthetic scale benchmarks
└── examples/
        └── basic_ranking.py   # Executable terminal demonstration
```

---

## 4. Graph Model

The ranker uses generic models that do not assume nodes are files:

- **`Node`**: Immutable entity with `node_id: str` and optional `metadata: dict`. Represents files today, and classes, functions, or modules in future phases.
- **`Edge`**: Directed relationship `source --relationship_type--> target` with optional `metadata: dict`.
- **`GenericGraph`**: Adjacency-list graph providing $O(1)$ node lookup, duplicate edge suppression, and fast incoming/outgoing neighbor retrieval.

---

## 5. Scoring & Ranking Formulation

### 1. Relationship Weights (Configurable Heuristics)
Initial default heuristic weights (calibrated for software architecture):

| Relationship Type | Default Weight | Architectural Rationale |
| :--- | :---: | :--- |
| `DIRECT_CALL` | **1.00** | Direct invocation indicates immediate coupling |
| `IMPORT` | **0.70** | Module dependence indicates architectural coupling |
| `INCLUDE` | **0.70** | Physical header inclusion indicates direct compile dependency |
| `TYPE_REFERENCE` | **0.60** | Type annotations indicate static interface usage |
| `TEST_RELATIONSHIP`| **0.50** | Unit test linkage indicates test coverage |
| *Unknown / Custom* | **0.50** | Configurable fallback for unclassified edges |

*Note: These weights are configurable heuristics and have not yet been scientifically validated.*

### 2. Distance Decay (Configurable)
Proximity decreases relevance across graph hops:

$$\text{decay}(d) = \begin{cases} 1.00 & d = 0 \\ 1.00 & d = 1 \\ 0.70 & d = 2 \\ 0.40 & d = 3 \\ 0.20 & d = 4 \\ 0.20 \times 0.50^{(d - 4)} & d > 4 \end{cases}$$

### 3. Relevance Score Formula
$$\text{Relevance Score} = \text{relationship\_strength} \times \text{distance\_decay}$$

For multi-hop paths, `relationship_strength` defaults to the conservative bottleneck minimum:
$$\text{relationship\_strength}(P) = \min_{e \in P} \text{weight}(e)$$
*(Configurable to `product`, `last_edge`, or `average`).*

### 4. Multiple Path Resolution
When a node is reached via multiple paths at the same minimum BFS hop count:
$$\text{Selected Path} = \arg\max_{P} \text{score}(P)$$
Ties are resolved deterministically using lexicographical path comparison.

### 5. Deterministic Tie-Breaking
Ranked results are ordered by:
1. `score` (descending)
2. `distance` (ascending)
3. `node_id` (alphabetical ascending)

---

## 6. Traversal Directions

- **`OUTGOING`**: Follows dependency targets (`A -> B`). Answers: *"What does A depend on?"*
- **`INCOMING`**: Follows dependency sources (`B <- A`). Answers: *"Who depends on A (callers, importers)?"*
- **`BOTH`**: Explores the full connected neighborhood regardless of edge orientation.

---

## 7. Performance Benchmarks

Empirical performance measured on synthetic graphs of varying scale:

| Graph Scale | Total Nodes | Total Edges | Graph Build Time | Ranking Time ($d \le 5$, Top-50) | Peak Memory |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **1,000 nodes** | 1,000 | 999 | 0.0586 s | **0.0082 s** (8.2 ms) | 0.59 MB |
| **10,000 nodes** | 10,000 | 9,999 | 0.5842 s | **0.0208 s** (20.8 ms) | 6.05 MB |
| **100,000 nodes** | 100,000 | 99,999 | 6.5261 s | **0.0107 s** (10.7 ms) | 63.15 MB |

### Algorithmic Complexity:
- **Time Complexity**: $O(V_{local} + E_{local})$ where $V_{local}$ and $E_{local}$ are the nodes and edges within the $k$-hop neighborhood ($k = \text{max\_depth}$). Ranking does not scale with total graph size, guaranteeing sub-50ms execution even on 100,000+ nodes.
- **Space Complexity**: $O(V_{local})$ for the BFS queue and visited tracking.

---

## 8. Usage Example

```python
from relationship_ranker import GenericGraph, RelationshipRanker, TraversalDirection

# 1. Initialize graph
graph = GenericGraph()
graph.add_edge("UserController", "AuthService", "IMPORT")
graph.add_edge("UserController", "UserRoutes", "DIRECT_CALL")
graph.add_edge("AuthService", "UserRepository", "IMPORT")

# 2. Rank relevant nodes from UserController
ranker = RelationshipRanker()
ranked_nodes = ranker.rank(
    graph=graph,
    target_node_id="UserController",
    top_k=5,
    direction=TraversalDirection.OUTGOING,
)

# 3. Print ranked output
for node in ranked_nodes:
    print(f"{node.node_id}: score={node.score:.4f}, dist={node.distance}, path={' -> '.join(node.path)}")
```

Terminal output:
```text
UserRoutes: score=1.0000, dist=1, path=UserController -> UserRoutes
AuthService: score=0.7000, dist=1, path=UserController -> AuthService
UserRepository: score=0.4900, dist=2, path=UserController -> AuthService -> UserRepository
```

---

## 9. Future Integration with Graph Designer

In a subsequent integration step, an adapter will bridge Graph Designer's C++ representation into `GenericGraph`:

```text
Graph Designer (C++)
        │
        ▼ (JSON or C-API export)
GraphDesignerRankerAdapter
        │
        ▼
   GenericGraph
        │
        ▼
RelationshipRanker
```

Because Phase 5 defines clean, generic interfaces (`GenericGraph`, `Node`, `Edge`), no internal ranker logic will need modification when integrating with Graph Designer or SQLite disk storage.
