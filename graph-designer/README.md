# Graph Builder — Phase 4: Graph Designer

The **Graph Designer** is the independent in-memory directed graph component of the `graphs` static-analysis engine. It models software repository entities (nodes) and their syntactic dependencies (edges), supporting fast bidirectional lookups, cycle-safe traversals, and deterministic serialization.

---

## 1. Purpose & Separation of Concerns

The Graph Designer is designed as a **completely independent component**:
- It has **zero dependencies** on Scanner (Phase 1), Tokenizer (Phase 2), or Connector (Phase 3).
- It does not require a database, operating entirely in-memory with standard C++ data structures.
- It accepts manually or programmatically supplied graph relationships.
- Future phases will connect the pipeline:
  ```text
  Scanner (Phase 1)
        │
        ▼
  Tokenizer (Phase 2)
        │
        ▼
  Connector (Phase 3)
        │
        ▼
  Graph Designer Adapter (Future)
        │
        ▼
  Graph Designer (Phase 4)
  ```

---

## 2. Architecture & Design

### Component Layout
```text
graph-designer/
├── include/
│   ├── relationship_type.h   # RelationshipType enum & string conversions
│   ├── node.h                # Node class & URI identity scheme
│   ├── edge.h                # Edge class & composite hash functor
│   └── graph.h               # Directed Graph adjacency structures & algorithms
├── src/
│   ├── relationship_type.cpp # Canonical string parsing
│   ├── node.cpp              # Path normalization and URI factory
│   ├── edge.cpp              # Edge string representation & metadata access
│   └── graph.cpp             # Adjacency indexing, edge validation, BFS/DFS
├── tests/
│   └── test_graph.cpp        # 11 comprehensive automated tests
├── examples/
│   └── basic_graph.cpp       # Programmatic demonstration program
├── CMakeLists.txt            # CMake build definitions
├── build.bat                 # MSVC and MinGW automated compiler script
└── README.md                 # Technical manual & complexity documentation
```

---

## 3. Node Identity & URI Scheme

Per the architectural decision (**Option B**), nodes use deterministic, repository-safe URI identities:

### Canonical URI Scheme
```text
file:<normalized-repository-relative-path>
```

- **Forward Slashes**: All Windows backslashes (`\`) are normalized to forward slashes (`/`).
- **Clean Relatives**: Leading `./` and `/` are stripped.
- **Examples**:
  - `main.cpp` → `file:main.cpp`
  - `src/user.h` → `file:src/user.h`
  - `backend/services/auth.ts` → `file:backend/services/auth.ts`
- **Extensibility**: In future phases, non-file entities will seamlessly adopt their designated prefixes (`dir:`, `class:`, `function:`) without breaking existing file URI structures.

---

## 4. Edge Semantics & Deduplication

### Relationship Types
The Graph Designer supports three initial relationship types:
- **`INCLUDE`**: Physical header or file inclusion (`#include "header.h"`).
- **`IMPORT`**: Module or package import (`import os`, `require('./utils')`).
- **`REFERENCE`**: General symbolic cross-reference or usage.

### Composite Edge Identity (**Option A**)
An edge's identity is defined strictly by the tuple:
```text
(source_node_id, target_node_id, relationship_type)
```

1. **Multi-Type Support**: Two files can have multiple distinct relationships between them. For example:
   ```text
   file:a.py --IMPORT--> file:b.py
   file:a.py --INCLUDE--> file:b.py
   ```
   Both edges are preserved as distinct, valid directed edges.
2. **Duplicate Edge Rejection**: Inserting an edge with an identical `(source, target, type)` tuple is deduplicated: the operation is rejected, `addEdge` returns `false`, and no duplicate entry is added to adjacency lists.

---

## 5. Self-Edge Behavior (**Option B — Disallow Self-Edges**)

A file cannot depend on itself in software architecture.
- Any attempt to add an edge where `source_id == target_id` (e.g. `addEdge("file:a.cpp", "file:a.cpp", ...)`) is **immediately rejected**.
- `addEdge` and `addRelationship` return `false`.
- The graph remains untouched, maintaining strict acyclic self-integrity.

---

## 6. Graph Data Structures & Algorithmic Complexity

The graph is implemented as an adjacency list backed by hash tables to ensure optimal performance for large repositories (targeting 200,000+ files):

```cpp
std::unordered_map<std::string, Node> nodes_;
std::unordered_set<Edge, EdgeHash> edges_;
std::unordered_map<std::string, std::vector<Edge>> outgoing_edges_;
std::unordered_map<std::string, std::vector<Edge>> incoming_edges_;
```

### Operation Complexity

| Operation | Method | Average Time Complexity | Worst Case | Space Complexity |
| :--- | :--- | :--- | :--- | :--- |
| **Add Node** | `addNode(node)` | $O(1)$ | $O(V)$ (rehash) | $O(1)$ per node |
| **Get Node** | `getNode(id)` | $O(1)$ | $O(V)$ (hash collision) | $O(1)$ |
| **Node Exists** | `hasNode(id)` | $O(1)$ | $O(V)$ | $O(1)$ |
| **Add Edge** | `addEdge(edge)` | $O(1)$ | $O(E)$ (rehash) | $O(1)$ per edge |
| **Edge Exists** | `hasEdge(src, tgt, type)` | $O(1)$ | $O(E)$ | $O(1)$ |
| **Outgoing Edges** | `getOutgoingEdges(id)` | $O(1)$ (const reference, zero copies) | $O(V)$ | $O(1)$ |
| **Incoming Edges** | `getIncomingEdges(id)` | $O(1)$ (const reference, zero copies) | $O(V)$ | $O(1)$ |
| **Outgoing Neighbors** | `getOutgoingNeighbors(id)` | $O(\text{deg}^+(v))$ | $O(\text{deg}^+(v))$ | $O(\text{deg}^+(v))$ |
| **Incoming Neighbors** | `getIncomingNeighbors(id)` | $O(\text{deg}^-(v))$ | $O(\text{deg}^-(v))$ | $O(\text{deg}^-(v))$ |
| **Breadth-First Search** | `bfs(start_id)` | $O(V + E)$ | $O(V + E)$ | $O(V)$ (queue & visited set) |
| **Depth-First Search** | `dfs(start_id)` | $O(V + E)$ | $O(V + E)$ | $O(V)$ (stack & visited set) |
| **Clear Graph** | `clear()` | $O(V + E)$ | $O(V + E)$ | Deallocates all memory |

*Where $V = |Nodes|$, $E = |Edges|$, $\text{deg}^+(v) = \text{out-degree}$, $\text{deg}^-(v) = \text{in-degree}$.*

---

## 7. Traversal & Cycle Safety

Software dependency graphs commonly exhibit cyclical dependencies (e.g. `A → B → C → A`).
- **Cycle Safety**: Both `bfs()` and `dfs()` maintain an explicit `std::unordered_set<std::string> visited`.
- Nodes are visited at most once; cycles never cause infinite recursion or queue overflow.
- **Disconnected Subgraphs**: Traversal explores only the reachable component from the chosen root. Disconnected components remain unaffected.

---

## 8. How to Build & Run

### Building via Batch Script
The `build.bat` script automatically detects `g++` (MinGW) or `cl.exe` (MSVC C++17):

```cmd
cd graph-designer
build.bat
```

### Running Tests
Execute the compiled test binary containing all 11 test scenarios:

```cmd
.\test_graph.exe
```

### Running Example Program
Execute the basic demonstration:

```cmd
.\basic_graph.exe
```

---

## 9. Future Integration with Previous Phases

In a subsequent integration phase, an adapter will bridge Connector output to Graph Designer:

```text
Connector (RelationshipMap)
        │
        ├── Reads: map[source_path] -> list[connected_paths]
        │
        ▼
GraphDesignerAdapter
        │
        ├── Converts source_path to Node("file:<path>")
        ├── Converts target_path to Node("file:<target>")
        └── Calls graph.addRelationship(src, tgt, type)
        │
        ▼
Graph Designer (In-Memory Graph Representation)
```
