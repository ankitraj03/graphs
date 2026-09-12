# AGENTS.md — Master Engineering Contract for `graphs`

This document is the authoritative engineering contract and operational manual for all AI agents and engineers working on the `graphs` codebase. It establishes mandatory architectural principles, language strategies, performance constraints, code quality standards, testing requirements, and development workflows.

---

## 1. Project Overview & North Star

- **Project Name**: `graphs`
- **Core Mission**: Build a high-throughput, modular static-analysis and dependency-graph engine capable of scanning massive software repositories (targeting **200,000+ files**), extracting syntax-level and architectural relationships, and constructing a queryable, explainable graph.
- **Implementation Strategy**: **Python-First**. Python (3.12+) is the primary implementation language. Performance-critical bottlenecks may be rewritten in C++ only after empirical profiling proves Python algorithmic and concurrency limits have been exhausted.

---

## 2. High-Level System Architecture

The system is structured as an end-to-end, unidirectional pipeline. Every stage is strictly decoupled behind abstract interfaces (`typing.Protocol`):

```text
Repository
    │
    ▼
File Scanner (Traversal, Ignore Filtering, Binary Detection, Symlinks)
    │
    ▼
File Metadata & Change Detection (Size, mtime_ns, Hashing, Manifest)
    │
    ▼
Language Detection (Extension, Shebang, Content Heuristics)
    │
    ▼
Language Analyzer (Pluggable AST Parsers: Python, C++, etc.)
    │
    ▼
Dependency Extraction (Syntactic Facts, Scopes, Unresolved References)
    │
    ▼
Symbol Resolution & Evidence Aggregator (Cross-File Symbol Table)
    │
    ▼
Graph Builder (Node/Edge Assembly, Stable IDs, Deduplication)
    │
    ▼
Graph Storage (In-Memory Adjacency / SQLite Disk Store)
    │
    ▼
Query Engine (BFS/DFS Traversal, Cycle Detection, Impact Analysis)
    │
    ▼
CLI / API Surface
```

### Architectural Boundaries
1. **Pluggable Language Analyzers**: Language analyzers must implement the `LanguageAnalyzer` protocol. The scanner must **never** contain language-specific parsing logic.
2. **Pluggable Storage**: The graph construction and query layers interact with storage through a `GraphStore` protocol, allowing seamless transition between in-memory graphs, SQLite, or specialized graph databases.
3. **Decoupled Discovery**: The file scanner produces an abstract stream of discovered files; it is agnostic to how files are parsed or stored.

---

## 3. Python-First Engineering Standards

Python code in `graphs` must adhere to production-grade engineering practices:

- **Runtime Target**: Python 3.12+.
- **Standard Library First**: Prioritize Python's standard library (`pathlib`, `ast`, `dataclasses`, `typing`, `multiprocessing`, `concurrent.futures`, `sqlite3`, `contextlib`). Third-party dependencies require clear architectural justification.
- **Strict Typing Everywhere**: Type hints are mandatory across all public and internal interfaces. Code must satisfy `mypy --strict` and `pyright` without warnings.
- **Modern Syntax**:
  - Leverage PEP 695 type parameter syntax: `type NodeID = str`, `class Store[T]: ...`.
  - Use `@typing.override` (PEP 698) for explicit interface/protocol implementations.
- **Data Modeling**:
  - Use `@dataclass(frozen=True, slots=True)` for tokens, graph nodes, edges, locations, and configuration DTOs.
  - `slots=True` is mandatory to minimize per-object memory overhead across millions of instances.
- **Path Operations**:
  - Use `pathlib.Path` for high-level domain paths and cross-platform path math.
  - Use raw `os.scandir` in the tight discovery loop for speed, converting lazily to `Path`.
  - Maintain compatibility with Windows extended-length paths (`\\?\`).
- **Resource Lifecycle**:
  - Manage all files, connections, and worker pools with context managers (`with` statements).
  - Absolutely no global mutable state.
- **Exceptions & Errors**:
  - Inherit from a root `GraphsError` domain hierarchy.
  - Explicitly chain exceptions (`raise SpecificError(...) from err`).
  - Never use bare `except: pass`.
- **Logging**:
  - Use standard `logging` with structured formatting. Never use `print()` for diagnostic output.

---

## 4. Performance & Scalability Protocol (200,000+ Files)

Handling 200,000+ files requires treating performance as an architectural pillar from day one:

1. **Zero-Buffering & Streaming**: Never collect 200,000 file representations or entire ASTs into in-memory lists. Use generator pipelines and batched streams.
2. **Traversal Efficiency**: Use `os.scandir()` instead of `os.walk()` or `Path.iterdir()`. Rely on `DirEntry.stat()` to avoid redundant OS `stat()` system calls.
3. **Memory Management**:
   - String interning (`sys.intern`) is mandatory for high-frequency repeated strings (edge kinds, node kinds, directory prefixes, common extensions).
   - Discard ASTs immediately after symbol and dependency extraction.
   - Bound worker queue sizes to prevent unbounded memory growth under producer-consumer speed mismatches.
4. **Workload-Aware Concurrency**:
   - **I/O Bound**: Use single-threaded discovery or bounded thread pools. Avoid `asyncio` for local file access (local filesystem operations block at the OS level).
   - **CPU Bound (Parsing/Extraction)**: Use `ProcessPoolExecutor` to bypass the GIL. Batch workloads into chunks of **500 to 2,000 files** to minimize IPC serialization overhead.
5. **Database Write Throughput**:
   - In SQLite, enable WAL mode (`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;`).
   - Group writes into explicit batch transactions (`executemany`) of **10,000 to 50,000 entities** (target: >80,000 writes/sec).
6. **Incremental Scanning**:
   - Track `(path, size_bytes, mtime_ns)` in an SQLite state cache.
   - Skip reading or parsing files whose size and modification timestamp match the manifest.
   - Use streaming chunk hashing (BLAKE3/SHA-256) only when timestamps or sizes change.
7. **Empirical Measurement Gate for C++**:
   - Never introduce C++ on speculation.
   - Propose a C++ rewrite only when a specific CPU-bound function consumes >50% of runtime under `py-spy`/`memray` profiling and cannot be optimized algorithmically or via multiprocessing in Python.

---

## 5. Static Analysis & Evidence Attribution

The static analysis engine must produce high-integrity, explainable graphs:

### Relationship Certainty Tiers
1. **Directly Observed (Tier 1)**: Syntactic facts directly present in the AST (e.g. `import os`, `class B(A):`, direct syntactic function calls).
2. **Statically Inferred (Tier 2)**: Resolved via deterministic static analysis (e.g. mapping an imported symbol to a specific file path using project roots, resolving types from annotations).
3. **Unresolved / Ambiguous (Tier 3)**: Dynamic imports, `getattr()` dispatches, or polymorphic calls where static resolution cannot guarantee a unique target.

### Strict Non-Speculation Rule
- **Never invent relationships**: If a symbol cannot be definitively resolved, emit an `UNRESOLVED` reference node or tag the edge with `confidence="UNRESOLVED"`. Never link to an arbitrary matching name.
- **Evidence Retention**: Every dependency edge must record:
  - Originating source file path
  - Precise source location (start line/col, end line/col)
  - Extracted symbol identifier
  - Evidence kind (e.g. `import_statement`, `include_directive`, `call_expression`, `type_annotation`)
  - Human-readable evidence snippet (e.g. `"from utils import helper"`)

---

## 6. Graph Data Model & Traversal

### Node Schema
Nodes represent physical or logical entities with stable, deterministic IDs:
- **Node Types**: `DIRECTORY`, `FILE`, `MODULE`, `PACKAGE`, `NAMESPACE`, `CLASS`, `STRUCT`, `INTERFACE`, `FUNCTION`, `METHOD`, `VARIABLE`.
- **Stable ID Scheme**: Deterministic URI strings (`<kind>:<repo-relative-path>[::<symbol-scope>]`), e.g., `class:src/core/scanner.py::Scanner`.
- **Metadata**: Source location, language identifier, docstrings, visibility.

### Edge Schema
Edges represent typed, evidence-backed relationships:
- **Edge Types**: `CONTAINS`, `IMPORTS`, `INCLUDES`, `CALLS`, `INHERITS`, `IMPLEMENTS`, `USES`, `REFERENCES`, `DEFINES`, `DEPENDS_ON`.
- **Deduplication**: Edges are uniquely keyed by `(source_id, target_id, kind)`. Duplicates merge evidence or increment weights.

### Traversal Discipline
- **BFS (Breadth-First Search)**: Use for unweighted reachability, $k$-hop neighbor queries, and shortest path in hop counts ($O(V + E)$).
- **DFS (Depth-First Search)**: Use for deep path exploration and topological ordering ($O(V + E)$).
- **Tarjan's / Kosaraju's Algorithm**: Use for Strongly Connected Components (SCC) to detect architectural circular dependencies.
- **Dijkstra / A\***: **Only** use when edges have meaningful numerical non-negative weights (e.g. inverse coupling metrics or fragility scores). Do not use Dijkstra for unweighted hop queries.

---

## 7. Repository Scanner Policies

The scanner is responsible for repository discovery and filtering:

- **Traverse Lazily**: Stream directory entries using `os.scandir()`.
- **Default Pruned Directories**: Prune `.git`, `.venv`, `venv`, `node_modules`, `build`, `dist`, `__pycache__`, `.tox`, `.mypy_cache`, and IDE folders at discovery time.
- **Ignore Rules**: Support `.gitignore` and `.ignore` patterns. Prune ignored directories before recursing.
- **Binary Filtering**: Check known binary extensions and inspect the first 1,024 bytes for null bytes (`b'\x00'`). Skip non-text files.
- **Symlink Safeguards**: Do not follow directory symlinks by default. When enabled, track visited `(dev, ino)` / realpaths to prevent cyclic loops.
- **Fault Tolerance**: Catch `PermissionError`, transient `FileNotFoundError`, and encoding errors per file. Log warnings and continue scanning without aborting.

---

## 8. Master Architectural Principles

1. **Correctness Before Optimization**: A fast incorrect graph is useless. Ensure mathematical correctness first.
2. **Profile Before Optimizing**: Base performance work on flamegraphs and metrics, not assumptions.
3. **Evidence Before Inference**: Every edge must retain why it was created.
4. **Keep Components Loosely Coupled**: Depend on protocols, not concrete implementations.
5. **Prefer Simple Designs**: Avoid clever metaclasses, monkey-patching, or excessive layers of abstraction.
6. **No Global Mutable State**: Pass dependencies and state explicitly.
7. **Explicit Ownership & Lifecycle**: Resources are opened and closed deterministically via context managers.
8. **Keep Interfaces Stable**: Do not change public protocol signatures without updating all adapters.
9. **Separate Responsibilities**: The scanner discovers; analyzers parse; the builder links; storage persists.
10. **Avoid Unrelated Refactoring**: Focus edits strictly on the requested feature or fix.
11. **Do Not Silently Change Architecture**: Seek approval before altering core designs or schemas.
12. **Justify Every Dependency**: Reject convenience dependencies that the standard library can easily fulfill.
13. **Preserve Backward Compatibility**: Ensure existing data models and CLI flags continue functioning.
14. **Explainable Decisions**: Document the rationale and tradeoffs for all non-trivial technical choices.
15. **Design for 200,000+ Files**: Every algorithm, data structure, and query must scale gracefully.

---

## 9. AI Agent Operational Guidelines

When acting as an AI engineer on this codebase:

1. **Inspect Before Editing**: Always inspect relevant code, existing tests, and related skills before touching any file.
2. **Small vs Major Changes**:
   - *Small Changes* (bug fixes, localized unit tests, typing cleanups): Proceed directly.
   - *Major Architectural Changes* (schema shifts, concurrency model changes, storage replacements): Explain the problem, present alternatives with tradeoffs, recommend a path, and wait for approval.
3. **Preserve Unrelated Code**: Never reformat or rewrite existing code outside the direct scope of the task.
4. **Do Not Attempt Everything at Once**: Build incrementally. Deliver working, tested slices.

---

## 10. Development & Verification Workflow

For all non-trivial work, adhere to this cycle:

$$\text{EXPLORE} \longrightarrow \text{PLAN} \longrightarrow \text{IMPLEMENT} \longrightarrow \text{BUILD} \longrightarrow \text{TEST} \longrightarrow \text{REVIEW} \longrightarrow \text{BENCHMARK} \longrightarrow \text{DOCUMENT}$$

### Definition of Done
Before completing any task:
1. Code is strictly typed and passes static analysis (`ruff`, `mypy --strict`).
2. All new and existing automated tests pass.
3. If performance is relevant, empirical benchmarks show no regression.
4. No unexpected files or temporary artifacts remain.
5. If tests fail, diagnose and fix the root cause. **Never delete or weaken tests to make a test suite pass.**

---

## 11. Security, Safety & Git Discipline

- **Untrusted Input**: Treat all target repositories as untrusted data. **Never execute code, scripts, or build tools found inside target repositories.**
- **Safe I/O**: Do not run arbitrary subprocesses from scanned files. Guard against path traversal (`../`) vulnerabilities.
- **Privacy**: Never log or export credentials, API keys, or private file contents.
- **Destructive Operations**: Never run destructive filesystem commands (`rm -rf`, deleting databases) without explicit confirmation.
- **Git State**:
  - Inspect `git status` and `git diff` before and after modifications.
  - Never overwrite, checkout, or reset user changes.
  - Keep commits logically atomic.

---

## 12. Skills Reference Directory (`.agents/skills/`)

Consult and leverage project skills as needed:

| Task / Domain | Relevant Skill |
| :--- | :--- |
| Python 3.12+ engineering, typing, dataclasses, protocols | [`python-engineering`](file:///d:/graphs/.agents/skills/python-engineering/SKILL.md) |
| Scaling Python, memory reduction, concurrency, batching | [`python-performance`](file:///d:/graphs/.agents/skills/python-performance/SKILL.md) |
| Python AST analysis, import extraction, scope modeling | [`python-static-analysis`](file:///d:/graphs/.agents/skills/python-static-analysis/SKILL.md) |
| Filesystem traversal, ignore rules, binary detection | [`python-project-scanning`](file:///d:/graphs/.agents/skills/python-project-scanning/SKILL.md) |
| C++ target parsing, include resolution, templates | [`cpp-analysis`](file:///d:/graphs/.agents/skills/cpp-analysis/SKILL.md) |
| Graph schema, stable IDs, storage, BFS/DFS/Tarjan | [`graph-modeling`](file:///d:/graphs/.agents/skills/graph-modeling/SKILL.md) |
| Multi-source evidence, symbol tables, layering rules | [`dependency-analysis`](file:///d:/graphs/.agents/skills/dependency-analysis/SKILL.md) |
| Test taxonomy, malformed inputs, synthetic scale tests | [`testing`](file:///d:/graphs/.agents/skills/testing/SKILL.md) |
| Throughput metrics, cold/warm cache, rewrite criteria | [`benchmarking`](file:///d:/graphs/.agents/skills/benchmarking/SKILL.md) |

---

## 13. Communication & Reporting Standards

When reporting progress or proposing changes, provide:
1. **What changed**: Clear summary of modified or created components.
2. **Why it changed**: Technical rationale and architectural justification.
3. **Files affected**: Clickable markdown links to all touched files.
4. **Tests performed**: Commands executed and verification outcomes.
5. **Results & Metrics**: Quantitative findings (test pass counts, benchmark numbers).
6. **Remaining risks or limitations**: Open items, assumptions, or follow-up tasks.

## 14. Boundaries & Restrictions

Don't use git add ., git commit and git push origin

