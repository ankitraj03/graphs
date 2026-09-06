---
name: python-engineering
description: >-
  Production-quality Python engineering standards for the `graphs` repository analysis system.
  Covers Python 3.12+, strict typing, dataclasses, protocols, modular architecture,
  exception handling, and standard library-first design.
---

# Python Engineering Standards

This skill defines the engineering discipline, architectural guidelines, and code quality standards for the `graphs` project. Python is the primary implementation language for `graphs`. All code must be robust, maintainable, strictly typed, and designed for large-scale execution without relying on premature native rewrites.

---

## 1. Core Principles

1. **Correctness Before Optimization**: Write clear, mathematically correct, and easily testable Python first. Profile before optimizing.
2. **Standard Library First**: Prioritize Python's standard library (`pathlib`, `dataclasses`, `typing`, `ast`, `multiprocessing`, `concurrent.futures`, `sqlite3`, `contextlib`) before introducing external dependencies.
3. **No Unnecessary Abstractions**: Prefer concrete, simple functions and classes over multi-layered inheritance hierarchies, dynamic metaclass magic, or premature plugin factories.
4. **Strict Typing Everywhere**: Type hints are mandatory on all functions, methods, class attributes, and module interfaces. Code must pass `mypy --strict` and `pyright` in strict mode.
5. **Clear, Maintainable Code**: Write straightforward, self-documenting code. Avoid overly clever one-liners or esoteric idioms that obscure intent.
6. **Explicit Ownership & Lifecycle**: Make resource ownership (file descriptors, database connections, process pools) explicit using context managers. Avoid global mutable state.

---

## 2. Python 3.12+ Language Features

Target **Python 3.12+**. Leverage modern language features:

- **Type Parameter Syntax (PEP 695)**: Use native generic syntax for functions, classes, and type aliases:
  ```python
  type NodeID = str
  type EdgeMap[T] = dict[NodeID, list[T]]

  class GraphStore[N, E]:
      def __init__(self) -> None:
          self._nodes: dict[NodeID, N] = {}
          self._edges: EdgeMap[E] = {}
  ```
- **Override Decorator (PEP 698)**: Mark overridden methods explicitly with `@typing.override` to catch signature mismatches at type-checking time:
  ```python
  from typing import override

  class BaseAnalyzer:
      def analyze(self, path: Path) -> AnalysisResult: ...

  class PythonASTAnalyzer(BaseAnalyzer):
      @override
      def analyze(self, path: Path) -> AnalysisResult: ...
  ```
- **Improved Exception Notes & Tracebacks (PEP 678)**: Enrich runtime errors with `.add_note(...)` when scanning large repositories to include file path context without breaking original tracebacks.

---

## 3. Type System & Protocols

- **Strict Type Annotations**: Every parameter, return type, and class attribute must be typed. Use `None` explicitly for void returns (`def run() -> None:`).
- **Structural Subtyping via Protocols**: Use `typing.Protocol` to define clear, decoupled interfaces for pluggable components (e.g., scanners, analyzers, graph exporters):
  ```python
  from typing import Protocol, runtime_checkable

  @runtime_checkable
  class LanguageAnalyzer(Protocol):
      """Pluggable analyzer contract for specific source languages."""
      
      @property
      def language_id(self) -> str: ...
      
      def can_analyze(self, path: Path) -> bool: ...
      
      def extract_dependencies(self, path: Path, content: str) -> FileAnalysisResult: ...
  ```
- **Immutable Types & Narrowing**: Use `tuple`, `frozenset`, and `Mapping` in function signatures instead of mutable `list`, `set`, and `dict` when the function does not mutate the container.
- **Type Guards**: Use `typing.TypeGuard` or `typing.TypeIs` when filtering heterogeneous collections.

---

## 4. Data Modeling with Dataclasses

- Prefer `dataclasses.dataclass` with `frozen=True` and `slots=True` for data transfer objects, AST tokens, graph nodes, and configuration:
  ```python
  from dataclasses import dataclass
  from pathlib import Path

  @dataclass(frozen=True, slots=True)
  class SourceLocation:
      file_path: Path
      start_line: int
      start_column: int
      end_line: int
      end_column: int

  @dataclass(frozen=True, slots=True)
  class Node:
      id: str
      kind: str
      name: str
      location: SourceLocation | None = None
  ```
- **Rationale for `slots=True`**: Reduces per-instance memory overhead by omitting `__dict__`, crucial when instantiating hundreds of thousands of nodes and edges.
- **Default Factories**: Always use `field(default_factory=...)` for mutable defaults in non-frozen dataclasses.

---

## 5. Filesystem Operations & Path Handling

- **Always use `pathlib.Path`** for high-level path modeling, cross-platform normalization, and clean path math (`parent`, `name`, `suffix`, `relative_to`).
- **Path Canonicalization**: Resolve relative paths against the project root explicitly. Always handle Windows paths cleanly (support path lengths exceeding 260 characters via `\\?\` UNC prefixes when needed).
- **Path Sanitization**: Never concatenate paths as strings. Use `path / "sub"`. Normalize casing consistently on case-insensitive filesystems (Windows/macOS).
- **See `python-performance`** for specific low-level scanning guidelines (`os.scandir` usage for traversing 200,000+ files).

---

## 6. Generators & Iterators for Streaming

- **Never materialize collections of 200,000+ items into memory** (avoid `[f for f in ...]` across the entire tree).
- **Generator Pipelines**: Construct stream-processing pipelines where data flows lazily from discovery to analysis to graph emission:
  ```python
  from collections.abc import Iterator
  from pathlib import Path

  def discover_files(root: Path) -> Iterator[Path]:
      ...

  def filter_supported(files: Iterator[Path]) -> Iterator[Path]:
      for file in files:
          if is_supported(file):
              yield file

  def batch_stream[T](items: Iterator[T], batch_size: int = 1000) -> Iterator[list[T]]:
      batch: list[T] = []
      for item in items:
          batch.append(item)
          if len(batch) >= batch_size:
              yield batch
              batch = []
      if batch:
          yield batch
  ```

---

## 7. Resource Management & Context Managers

- Wrap all file I/O, database transactions, and pool allocations in context managers (`with` statements).
- Build custom context managers using `@contextlib.contextmanager` or class-based `__enter__` / `__exit__`:
  ```python
  import time
  import logging
  from collections.abc import Iterator
  from contextlib import contextmanager

  logger = logging.getLogger(__name__)

  @contextmanager
  def timed_stage(stage_name: str) -> Iterator[None]:
      start = time.perf_counter()
      logger.info(f"Starting stage: {stage_name}")
      try:
          yield
      finally:
          duration = time.perf_counter() - start
          logger.info(f"Completed stage: {stage_name} in {duration:.3f}s")
  ```

---

## 8. Exception Handling

- **Domain-Specific Hierarchy**: Define a clear base exception for the project and specific subclasses:
  ```python
  class GraphsError(Exception):
      """Base exception for all errors originating from the graphs system."""

  class ScanError(GraphsError):
      """Raised when filesystem traversal or access fails."""

  class ParseError(GraphsError):
      """Raised when source file parsing fails."""

  class GraphModelError(GraphsError):
      """Raised on invalid node, edge, or cycle integrity violations."""
  ```
- **Explicit Exception Chaining**: Always use `raise NewException(...) from err` to preserve original causes.
- **Never swallow errors silently**: Avoid bare `except: pass` or `except Exception: pass`. If an error in an individual source file must be tolerated during a massive repository scan, log it at WARNING or ERROR with full context and file path.

---

## 9. Logging & Observability

- Use Python's built-in `logging` module. Never use `print()` for diagnostic output.
- Configure logging through standard formatters with timestamps, log levels, and module names.
- Provide a silent/quiet mode for CLI scripting and verbose/debug modes for diagnostic tracing.
- Keep log messages structured where possible (e.g. `logger.debug("Discovered file", extra={"path": str(p), "size": sz})`).

---

## 10. Configuration & Immutability

- Model system configuration via strongly-typed, immutable dataclasses:
  ```python
  @dataclass(frozen=True, slots=True)
  class ScanConfig:
      root_path: Path
      ignored_patterns: tuple[str, ...] = (".git", ".venv", "node_modules", "build", "dist")
      follow_symlinks: bool = False
      max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB
      worker_count: int = 0  # 0 = auto-detect CPU count
      batch_size: int = 1000
  ```
- Validate configuration upfront at startup before launching scanners or workers.

---

## 11. Modular Architecture & Package Structure

Organize the `graphs` codebase into cohesive, loosely coupled packages:

```text
graphs/
├── __init__.py
├── __main__.py          # CLI entry point
├── config.py            # Strongly-typed configuration
├── core/
│   ├── models.py        # Core domain models (Node, Edge, Location)
│   ├── protocols.py     # Component interfaces (Analyzer, Scanner, Store)
│   └── exceptions.py    # Domain exception hierarchy
├── scanner/
│   ├── discovery.py     # Filesystem walk & filtering
│   ├── metadata.py      # File metadata, hashes, mtime
│   └── pipeline.py      # Parallel batching and streaming pipeline
├── analyzers/
│   ├── base.py          # Abstract/Protocol base analyzer
│   ├── registry.py      # Analyzer plugin registry
│   ├── python/          # Python target analyzer (AST-based)
│   └── cpp/             # C++ target analyzer
├── graph/
│   ├── builder.py       # Graph assembly, deduplication, incremental updates
│   ├── model.py         # In-memory graph structures
│   └── algorithms.py    # BFS, DFS, cycle detection, topological sort
├── storage/
│   ├── base.py          # Storage backend protocol
│   └── sqlite.py        # SQLite disk-backed relational/graph store
└── query/
    └── engine.py        # Query engine for dependency traversal
```

- **Clean `__all__` exports**: Explicitly define `__all__` in public API modules.
- **No Circular Imports**: Strictly maintain a unidirectional dependency flow:
  `scanner -> analyzers -> core/models` and `analyzers -> graph/builder -> storage`.

---

## 12. Testing & Quality Assurance

- All code must be covered by automated tests using `pytest`.
- Separate tests into `tests/unit/`, `tests/integration/`, and `tests/performance/`.
- Use fixtures for test repositories, temporary directories, and mock AST structures.
- Enforce linters and formatters: `ruff check`, `ruff format`, and strict `mypy`.

