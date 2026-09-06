---
name: graph-modeling
description: >-
  Language-independent graph data modeling for the `graphs` repository analysis system.
  Defines node types, edge types, stable deterministic IDs, metadata, source locations,
  storage representations, deduplication, and traversal algorithms (BFS, DFS, Dijkstra, SCC).
---

# Graph Modeling Architecture

This skill defines the language-independent graph schema, data modeling principles, storage representations, and graph algorithms for the `graphs` project.

---

## 1. Graph Model Foundations

1. **Extensible & Polymorphic**: The graph schema is open. It accommodates languages with distinct paradigms (object-oriented, procedural, functional, polyglot repositories) without requiring all repositories to support all node or edge types.
2. **Stable, Deterministic IDs**: Node and edge identifiers must be reproducible across subsequent scans. They must not rely on transient database autoincrement primary keys.
3. **Evidence-Bearing Edges**: Every relationship edge stores the reasoning, source location, and confidence level of why the edge exists.
4. **No Invented Nodes or Edges**: The graph represents observed code relationships and verified static inferences only.

---

## 2. Node Schema & Taxonomy

### Canonical Node Types

| Node Type | Scope / Description | Example |
| :--- | :--- | :--- |
| `DIRECTORY` | Physical filesystem container | `dir:src/core` |
| `FILE` | Physical source or resource file | `file:src/core/scanner.py` |
| `MODULE` | Logical code compilation or import unit | `module:graphs.scanner` |
| `NAMESPACE` | Logical grouping/symbol scope | `namespace:std::chrono` |
| `CLASS` | User-defined class or object type | `class:graphs.core.Node` |
| `STRUCT` | Lightweight record or value type | `struct:SourceLocation` |
| `INTERFACE` | Abstract protocol or interface contract | `interface:LanguageAnalyzer` |
| `FUNCTION` | Free or module-level callable routine | `function:graphs.scanner.fast_walk` |
| `METHOD` | Member function bound to a class/struct | `method:GraphBuilder.add_edge` |
| `VARIABLE` | Named variable, field, constant, or attribute | `variable:DEFAULT_BATCH_SIZE` |

### Deterministic Stable Node IDs
Node IDs follow a canonical URI-like scheme:
```text
<kind>:<repository-relative-path>[::<symbol-scope>]

Examples:
file:src/scanner/discovery.py
class:src/scanner/discovery.py::FileDiscoveryService
method:src/scanner/discovery.py::FileDiscoveryService::discover_all
function:src/utils/hashing.py::blake3_digest
```

### Node Data Model (Python 3.12)
```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True, slots=True)
class SourceLocation:
    file_path: Path
    start_line: int
    start_column: int
    end_line: int
    end_column: int

@dataclass(frozen=True, slots=True)
class GraphNode:
    id: str
    kind: str
    name: str
    qualified_name: str
    location: SourceLocation | None = None
    language: str | None = None
    docstring: str | None = None
    metadata: dict[str, Any] | None = None
```

---

## 3. Edge Schema & Relationship Taxonomy

### Canonical Edge Types

| Edge Type | Semantics | Typical Source -> Target |
| :--- | :--- | :--- |
| `CONTAINS` | Structural nesting or ownership | `DIRECTORY -> FILE`, `MODULE -> CLASS`, `CLASS -> METHOD` |
| `DEFINES` | Declaration/definition of a symbol | `FILE -> FUNCTION`, `CLASS -> VARIABLE` |
| `IMPORTS` | Import of a module or symbol | `MODULE -> MODULE`, `FILE -> MODULE` |
| `INCLUDES` | Physical inclusion (C/C++ `#include`) | `FILE -> FILE` |
| `CALLS` | Invocation of a routine | `FUNCTION -> FUNCTION`, `METHOD -> METHOD` |
| `INHERITS` | Subclassing / base type derivation | `CLASS -> CLASS`, `STRUCT -> STRUCT` |
| `IMPLEMENTS` | Interface or protocol implementation | `CLASS -> INTERFACE` |
| `USES` | Type usage (parameter, field, return) | `METHOD -> CLASS`, `VARIABLE -> CLASS` |
| `REFERENCES` | General symbolic reference or read | `FUNCTION -> VARIABLE` |
| `DEPENDS_ON` | High-level or inferred package dependency | `MODULE -> MODULE`, `PACKAGE -> PACKAGE` |

### Edge Data Model
```python
@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: str
    target_id: str
    kind: str
    evidence_source: str      # e.g., "ast_import", "include_directive", "call_expression"
    confidence: str           # "OBSERVED", "INFERRED", "UNRESOLVED"
    weight: float = 1.0       # Meaningful weight (e.g., call count, coupling score)
    location: SourceLocation | None = None
    metadata: dict[str, Any] | None = None
```

---

## 4. Graph Construction & Deduplication

When assembling graphs for 200,000+ files:

1. **Deduplication Strategy**:
   - Nodes are keyed by their stable `id`. If multiple analyzers or passes emit the same node, attributes are merged (e.g. combining declaration location with definition location).
   - Edges are keyed by `(source_id, target_id, kind)`. Duplicate edges increment an observation count or combine evidence sources rather than creating duplicate records.
2. **Incremental Graph Assembly**:
   - Nodes and edges are partitioned by their originating file path.
   - When a file changes, remove all nodes and outgoing edges previously originating from that file path before inserting updated entities.

---

## 5. Storage Representations

### In-Memory Representation
- For fast algorithms on loaded subgraphs: Adjacency list via dictionary of lists or compact contiguous index arrays:
  ```python
  class AdjacencyGraph:
      def __init__(self) -> None:
          self.nodes: dict[str, GraphNode] = {}
          self.out_edges: dict[str, list[GraphEdge]] = {}
          self.in_edges: dict[str, list[GraphEdge]] = {}
  ```

### Relational / Disk Storage (SQLite Schema)
```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    file_path TEXT,
    start_line INTEGER,
    start_col INTEGER,
    end_line INTEGER,
    end_col INTEGER,
    language TEXT,
    docstring TEXT,
    metadata_json TEXT
);

CREATE TABLE edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    evidence_source TEXT NOT NULL,
    confidence TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    file_path TEXT,
    line INTEGER,
    metadata_json TEXT,
    PRIMARY KEY (source_id, target_id, kind),
    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE INDEX idx_edges_target ON edges (target_id, kind);
CREATE INDEX idx_edges_source ON edges (source_id, kind);
CREATE INDEX idx_nodes_file ON nodes (file_path);
```

---

## 6. Graph Query & Traversal Algorithms

Choose algorithms matched to query semantics:

### 1. BFS (Breadth-First Search) — Unweighted Shortest Path & Reachability
- **When to use**: Answering "What are all dependencies reachable within $k$ hops?" or "Find the shortest dependency chain in number of hops between Module A and Module B."
- **Complexity**: $O(V + E)$.

### 2. DFS (Depth-First Search) — Path Exploration & Topological Ordering
- **When to use**: Deep dependency trace, topological sort for build order determination, cycle back-edge detection.
- **Complexity**: $O(V + E)$.

### 3. Dijkstra / A* — Weighted Path Optimization Only
- **CRITICAL**: Do NOT use Dijkstra for unweighted hop queries.
- **When to use**: Only when meaningful non-negative edge weights exist, such as:
  - Dependency coupling distance: $W = \frac{1}{\text{call\_count}}$.
  - Fragility risk metrics where edges have migration cost penalties.
- **Complexity**: $O(E + V \log V)$.

### 4. Tarjan's / Kosaraju's Algorithm — Strongly Connected Components (SCC)
- **When to use**: Detecting architectural dependency cycles (e.g. Module A -> Module B -> Module C -> Module A).
- Each SCC with $|V| > 1$ represents a circular dependency violation.

### 5. Architectural Centrality & Fan-In / Fan-Out
- **In-Degree (Fan-In)**: Number of components that depend on this node. High fan-in indicates core foundation libraries or high-risk change targets.
- **Out-Degree (Fan-Out)**: Number of external components this node depends on. High fan-out indicates high coupling or coordination modules.

