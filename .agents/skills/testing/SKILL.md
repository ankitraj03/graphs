---
name: testing
description: >-
  Comprehensive testing framework and test taxonomy for the `graphs` repository analysis system.
  Covers unit, integration, scanner, parser, graph, malformed source, synthetic large-repo,
  regression, and performance test suites.
---

# Testing Strategy & Quality Assurance

This skill defines the complete testing methodology for the `graphs` system. Every major feature, scanner optimization, language analyzer, and graph algorithm must be backed by automated tests.

---

## 1. Testing Philosophy

1. **Every Feature Requires Tests**: No feature or optimization is merged without automated test coverage.
2. **Never Crash on Bad Input**: Target repositories will contain syntax errors, broken symlinks, truncated files, and non-UTF8 encodings. The scanner and analyzers must record diagnostic warnings and continue gracefully.
3. **Deterministic Test Execution**: Tests must not depend on ambient filesystem state, user home directories, or network access.
4. **Fast Unit Tests, Isolated Large Tests**: Unit tests must execute in seconds; large synthetic repository tests are partitioned into separate test runs.

---

## 2. Test Taxonomy & Suite Organization

Test directory structure:
```text
tests/
├── unit/
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_path_utils.py
│   ├── test_stable_ids.py
│   └── test_hash.py
├── scanner/
│   ├── test_discovery.py
│   ├── test_filtering.py
│   ├── test_symlinks.py
│   ├── test_permissions.py
│   └── test_incremental.py
├── parsers/
│   ├── test_python_ast.py
│   ├── test_python_features_312.py
│   ├── test_cpp_analyzer.py
│   └── test_malformed_sources.py
├── graph/
│   ├── test_builder.py
│   ├── test_deduplication.py
│   ├── test_sqlite_storage.py
│   ├── test_traversal_bfs_dfs.py
│   ├── test_cycle_detection_scc.py
│   └── test_dijkstra.py
├── integration/
│   ├── test_end_to_end_scan.py
│   └── test_query_engine.py
├── regression/
│   ├── test_golden_snapshots.py
│   └── fixtures/golden_graphs/
└── performance/
    ├── test_synthetic_scale.py
    └── test_memory_ceiling.py
```

---

## 3. Test Categories & Implementation Guidelines

### 1. Unit Tests
- Test pure functions in total isolation (path normalization, ignore pattern matching, stable ID generators).
- Verify edge cases: empty strings, root paths, case-sensitivity on Windows vs Linux.

### 2. Scanner Tests
- **Symlink Cycles**: Create a directory symlink pointing to its parent; verify traversal detects the cycle and terminates without an infinite loop.
- **Deep Hierarchies**: Test directory trees 50+ levels deep; ensure no recursion limit exceptions (`RecursionError`).
- **Hidden & Ignored Directories**: Ensure `.git`, `.venv`, and `node_modules` are skipped at directory level and never yielded.
- **Path Length Extremes**: Test path lengths > 260 characters on Windows with `\\?\` prefix support.

### 3. Parser & Language Analyzer Tests
- **Modern Syntax Support**: Test Python 3.12 syntax (PEP 695 type parameters `type X[T] = list[T]`, `@typing.override`).
- **Import Variants**: Absolute imports, relative imports (`from ..foo import bar`), wildcard imports, aliased imports.
- **Scope Nesting**: Functions inside functions, classes inside classes, methods in dataclasses.
- **C++ Constructs**: Headers with pragma once, namespaces, template classes, virtual inheritance.

### 4. Malformed Source Tests
Verify that analyzer failures on broken files do not crash the engine:
- **Syntax Errors**: Python files containing incomplete blocks or invalid tokens (`def foo(`).
- **Truncated Files**: Files cut off mid-statement.
- **Invalid Encodings**: Files containing arbitrary non-UTF-8 byte sequences.
- **Zero-Byte Files**: Empty source files.
- **Binary Files Disguised as Source**: An ELF or PE binary renamed to `module.py`.
- **Expected Outcome**: Test asserts that a `DiagnosticEvent` is emitted with level `WARNING`, and the scanner proceeds to subsequent files.

### 5. Graph Data Model & Storage Tests
- **ID Determinism**: Assert identical source code yields identical node IDs across repeated runs.
- **Edge Deduplication**: Inserting the same edge multiple times must update weight or evidence, never duplicate rows.
- **Storage Round-Trip**: Nodes and edges stored in SQLite must deserialize identically.
- **Algorithm Correctness**:
  - Test cycle detection on known cyclic graphs (A -> B -> C -> A) and assert exact cycle output.
  - Test BFS hop-distance accuracy.
  - Test Dijkstra shortest-path accuracy only on graphs with explicit non-negative edge weights.

### 6. Regression & Golden Snapshot Tests
- Maintain a suite of small, stable test repositories under `tests/fixtures/sample_repos/`.
- Run full scan and export the graph to a canonical JSON or SQLite representation.
- Compare output against verified "golden" snapshots. Any deviation flags an architectural regression.

### 7. Large Repository Synthetic Tests
- Generate synthetic repositories on-the-fly using `tmp_path`:
  ```python
  def generate_synthetic_repo(root: Path, file_count: int) -> None:
      for i in range(file_count):
          dir_path = root / f"pkg_{i % 50}"
          dir_path.mkdir(parents=True, exist_ok=True)
          file_path = dir_path / f"module_{i}.py"
          target = (i + 1) % file_count
          file_path.write_text(f"import pkg_{target % 50}.module_{target}\n")
  ```
- Run scan with 1,000 to 50,000 files in CI. Assert:
  - Zero unhandled exceptions.
  - Peak memory usage (`tracemalloc.get_traced_memory()[1]`) remains bounded by a fixed ceiling (e.g. < 250 MB).

---

## 4. Test Execution & CI Automation

Configure `pytest.ini` with distinct test markers:
```ini
[pytest]
markers =
    unit: Fast unit tests
    integration: End-to-end integration tests
    scanner: Filesystem scanning and filtering tests
    parser: Language-specific AST and syntax tests
    graph: Graph algorithms and storage tests
    slow: Tests running > 5 seconds
    scale: Large-scale synthetic repository benchmarks
```

Commands:
- Fast developer check: `pytest -m "not (slow or scale)"`
- Full test suite: `pytest`
- Memory-leak check: `pytest -m scale --memray`

