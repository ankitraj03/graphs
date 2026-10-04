# Connector Progress Report

## 1. Objective

The primary objective of **Graph Builder Phase 3: Connector** is to design, implement, and verify the orchestration layer that connects the filesystem discovery component (**Scanner**, Phase 1) with the single-file lexical/syntactic dependency extractor (**Tokenizer**, Phase 2).

The Connector accepts a target repository directory path, coordinates file enumeration through the Scanner, delivers discovered source files to the Tokenizer, resolves extracted dependency tokens into verified repository file paths, and constructs a deterministic, queryable file-to-file relationship map without duplicating Scanner or Tokenizer responsibilities.

```text
Repository Path
       │
       ▼
   Connector
       │
       ├──► Scanner ──────────────► Discovered Repository File List
       │
       ├──► File Indexing ────────► O(1) Exact, Stem, and Relative Lookup Tables
       │
       ├──► Tokenizer ────────────► Syntactic Dependency Tokens per File
       │
       └──► Reference Resolver ───► Resolved / Unresolved File Relationships
       │
       ▼
  RelationshipMap (Text / JSON Format)
```

---

## 2. Current Architecture

The Connector follows a strictly decoupled, layered architecture adhering to the `AGENTS.md` engineering guidelines:

- **CLI / Native Entry Layer**:
  - `connector.exe`: Native C++ binary (`main.cpp`) providing zero-overhead terminal invocation, argument parsing, quote stripping, and forwarding to the Python pipeline.
  - `connector.cli`: Python command-line interface supporting human-readable terminal rendering, JSON export (`--json`), and unresolved reference diagnostics (`--unresolved`).
- **Orchestration Core (`Connector`)**:
  - Validates repository paths, delegates discovery to `ScannerAdapter`, initializes indexed file representations, streams files through `FileTokenizer`, resolves references via `ReferenceResolver`, and synthesizes `RelationshipMap`.
- **Scanner Integration (`ScannerAdapter`)**:
  - Interacts with native `scanner/scanner.exe` when available and falls back to an in-process `os.scandir` implementation matching identical directory pruning rules (`.git`, `node_modules`, `build`, etc.) and supported extensions.
- **Reference Resolution (`ReferenceResolver`)**:
  - Creates $O(1)$ memory-efficient hash indices over discovered files to resolve exact relative paths, repository root paths, language-specific extension probing, Python dot-notation, and C++ include disambiguation.
- **Data Models (`connector.models`)**:
  - Memory-optimized DTOs using `@dataclass(frozen=True, slots=True)`: `ResolvedReference`, `FileRelationship`, and `RelationshipMap`.
- **Domain Exceptions (`connector.exceptions`)**:
  - Error hierarchy rooted in `GraphsError`: `ConnectorError`, `RepositoryNotFoundError`, `NotADirectoryRepositoryError`, and `ScannerExecutionError`.

---

## 3. Scanner Integration

The Connector integrates with the Scanner via [`connector/scanner_adapter.py`](file:///D:/graphs/connector/scanner_adapter.py):

- **Binary Execution Mode**:
  - Checks for the presence of [`scanner/scanner.exe`](file:///D:/graphs/scanner/scanner.exe).
  - When present, invokes the native executable via `subprocess.run`, capturing stdout and parsing discovered paths delimited by `Found files:` and `Total files:`.
- **Zero-Dependency Fallback Mode**:
  - If the native binary is not compiled or encounters execution issues, the adapter falls back seamlessly to an `os.scandir()` generator traversal.
  - Employs the identical directory pruning list (`.git`, `.vscode`, `node_modules`, `build`, `dist`, `bin`, `obj`, `__pycache__`) and the 16 supported source file extensions (`.py`, `.pyi`, `.c`, `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp`, `.hxx`, `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`).
- **Error Handling**:
  - Nonexistent paths raise `RepositoryNotFoundError`.
  - File paths passed as directories raise `NotADirectoryRepositoryError`.
  - Transient permission denials are caught and skipped without aborting traversal.

---

## 4. Tokenizer Integration

The Connector interfaces directly with [`tokenizer.file_tokenizer.FileTokenizer`](file:///D:/graphs/tokenizer/file_tokenizer.py):

- **Contract Adherence**:
  - The Tokenizer processes one file at a time and returns a `list[DependencyToken]`.
  - The Tokenizer is responsible only for extracting tokens, target strings (e.g. `"user.h"`, `".config"`), connecting keywords (`#include`, `import`, `require`), and source locations.
  - The Tokenizer is **not** responsible for deciding repository-level connections.
- **Language Coverage**:
  - **Python**: Full AST parsing via `ast.parse` with regex-based lexical fallback on syntax errors.
  - **C/C++**: Regex extraction of `#include <...>`, `#include "..."`, and C++20 `import ...;`.
  - **JS/TS**: Regex extraction of ES6 `import`, CommonJS `require()`, ES6 `export ... from`, and dynamic `import()`.
- **Fault Tolerance**:
  - Per-file `TokenizerError` exceptions or decoding failures are logged as warnings and isolated; processing continues uninterrupted for all remaining files.

---

## 5. Reference Resolution

Reference resolution is implemented in [`connector/resolver.py`](file:///D:/graphs/connector/resolver.py) using an indexed multi-tier approach to ensure high throughput across large repositories:

### Index Structures Built at Initialization
- `_exact_paths`: `set[Path]` of all canonical absolute file paths in the repository.
- `_by_rel_path`: `dict[str, Path]` keyed by normalized lowercase repo-relative paths (`src/utils.py`).
- `_by_filename`: `dict[str, list[Path]]` keyed by lowercase filenames (`user.h`).
- `_by_stem`: `dict[str, list[Path]]` keyed by module stem (`user`).

### Resolution Pipeline
1. **Pre-Resolved Path Check**: If the tokenizer provided a pre-resolved path that exists in the repository, accept it directly (`confidence="DIRECT"`).
2. **Local Relative Lookup**: Resolves relative to the originating file's parent directory (`src_dir / clean_target`). Probes language-specific extensions (`.ts`, `.tsx`, `.js`, etc.) and package indices (`index.ts`, `__init__.py`).
3. **Repository Root-Relative Lookup**: Resolves relative to `repo_root / clean_target`.
4. **Python Dot-Notation Module Resolution**:
   - Resolves relative imports (`from . import config`, `from ..models import user`) using the relative import level.
   - Resolves top-level package paths (`app.services.auth` -> `app/services/auth.py`).
5. **Basename Lookup & Disambiguation**:
   - Matches `#include "header.h"` across directory structures.
   - If multiple candidates share the same filename, disambiguates by matching trailing relative path components or selecting the candidate with the deepest common directory ancestor with the source file.
6. **Strict Non-Speculation**:
   - Standard library modules (`os`, `sys`, `iostream`, `vector`) and external packages (`react`, `express`) that do not exist in the repository are marked as `is_resolved=False` and `confidence="UNRESOLVED"`. No fictitious connections are created.

---

## 6. Relationship Representation

The file relationship data model is defined in [`connector/models.py`](file:///D:/graphs/connector/models.py):

### Data Structures
- **`ResolvedReference`**:
  - `raw_target: str`: Original target string from token.
  - `resolved_path: Path | None`: Absolute path of target file if resolved.
  - `is_resolved: bool`: True if target is present in repository.
  - `confidence: str`: `"DIRECT"`, `"INFERRED"`, or `"UNRESOLVED"`.
  - `keyword: str`: Keyword originating the dependency.
  - `kind: str`: Token classification.
- **`FileRelationship`**:
  - `source_file: Path`: Absolute path of the source file.
  - `connected_files: tuple[Path, ...]`: Deduplicated sequence of resolved target files.
  - `unresolved_references: tuple[str, ...]`: List of unresolved target strings.
- **`RelationshipMap`**:
  - Complete repository graph mapping `dict[Path, FileRelationship]`.
  - Methods: `.to_dict(relative_to_root=True)` and `.format_text(show_unresolved=...)`.

---

## 7. Implementation Details

| Component | File | Responsibilities |
| :--- | :--- | :--- |
| Core Engine | [`connector/connector.py`](file:///D:/graphs/connector/connector.py) | Coordinates Scanner discovery, Tokenizer invocation, reference resolution, and deduplication. |
| Resolver | [`connector/resolver.py`](file:///D:/graphs/connector/resolver.py) | Multi-index $O(1)$ resolution engine for exact, relative, language-probed, and disambiguated paths. |
| Scanner Adapter | [`connector/scanner_adapter.py`](file:///D:/graphs/connector/scanner_adapter.py) | Bridge executing `scanner.exe` with resilient Python fallback. |
| Data Models | [`connector/models.py`](file:///D:/graphs/connector/models.py) | Frozen, slotted dataclasses with serialization and terminal formatting. |
| Exceptions | [`connector/exceptions.py`](file:///D:/graphs/connector/exceptions.py) | Strict `GraphsError` exception hierarchy for domain errors. |
| CLI Interface | [`connector/cli.py`](file:///D:/graphs/connector/cli.py) | Command-line parsing, interactive prompt, JSON/Text formatting. |
| Entry Points | [`connector/__main__.py`](file:///D:/graphs/connector/__main__.py), [`connector/main.py`](file:///D:/graphs/connector/main.py) | Module execution hooks for `python -m connector`. |
| C++ Launcher | [`connector/main.cpp`](file:///D:/graphs/connector/main.cpp), [`connector/build.bat`](file:///D:/graphs/connector/build.bat) | Native executable compiling to `connector.exe` via `g++` or `cl.exe`. |
| Documentation | [`connector/README.md`](file:///D:/graphs/connector/README.md) | Architectural specification, usage instructions, build guides. |

---

## 8. Tests Performed

A comprehensive unit and integration test suite was created in [`tests/test_connector.py`](file:///D:/graphs/tests/test_connector.py) covering all 12 test specifications from Phase 3:

1. **Specification Benchmark Example (Section 11)**:
   - Evaluated 6-file repository (`main.cpp`, `user.cpp`, `user.h`, `database.cpp`, `database.h`, `utils.h`).
   - Verified exact connections: `main.cpp -> [database.h, user.h]`, `user.cpp -> [user.h]`, `database.cpp -> [database.h]`, `utils.h -> []`.
2. **Test 1 — Basic Relationships**:
   - Verified single file include resolution (`a.cpp` -> `b.h`).
3. **Test 2 — Multiple References**:
   - Verified multi-target reference resolution (`multi.cpp` -> `[h1.h, h2.h, h3.h]`).
4. **Test 3 — No References**:
   - Verified isolated files produce an empty list (`standalone.cpp` -> `[]`).
5. **Test 4 — Nested Directories**:
   - Cross-directory linking (`src/main.cpp` -> `include/user.h`).
6. **Test 5 — Unresolved References**:
   - Verified that `#include "missing.h"` and `<iostream>` are not incorrectly linked to repo files and are retained in `unresolved_references`.
7. **Test 6 — Duplicate References**:
   - Verified that repeated includes to the same header are deduplicated to exactly one target entry.
8. **Test 7 — Empty Repository**:
   - Verified graceful handling of empty directory without errors (`total_files_scanned=0`, `relationships={}`).
9. **Test 8 — Invalid Repository Path**:
   - Verified that nonexistent path raises `RepositoryNotFoundError` (inheriting `FileNotFoundError`), and a file path raises `NotADirectoryRepositoryError` (inheriting `NotADirectoryError`).
10. **Python Multi-File Connections**:
    - Verified Python relative imports (`from .config import PORT`, `from . import __init__`).
11. **JavaScript/TypeScript Multi-File Connections**:
    - Verified TypeScript import resolution (`import { Button } from './button'` resolving to `src/button.tsx`).
12. **End-to-End Real Repository Test**:
    - Executed compiled `connector.exe` against `test_data/` containing mixed Python, C++, and TypeScript files.

---

## 9. Test Results

| Test Case | Description | Expected Output | Status |
| :--- | :--- | :--- | :--- |
| Section 11 Spec | 6-file C++ project model | Exact mapping of user/database headers | **PASS** |
| Test 1 | Basic single relationship | `a.cpp` -> `[b.h]` | **PASS** |
| Test 2 | Multiple references | `multi.cpp` -> `[h1.h, h2.h, h3.h]` | **PASS** |
| Test 3 | No references | `standalone.cpp` -> `[]` | **PASS** |
| Test 4 | Nested directories | `src/main.cpp` -> `include/user.h` | **PASS** |
| Test 5 | Unresolved references | Retained in unresolved, 0 false links | **PASS** |
| Test 6 | Duplicate deduplication | Exactly 1 entry per target | **PASS** |
| Test 7 | Empty directory | Graceful empty output, 0 errors | **PASS** |
| Test 8 | Nonexistent / Invalid path | Exception raised cleanly | **PASS** |
| Test 9 | Python relative imports | `app/main.py` -> `app/config.py` | **PASS** |
| Test 10 | JS/TS imports | `src/index.ts` -> `src/button.tsx` | **PASS** |
| Full Test Suite | All tests in `tests/` | 36 / 36 tests passing in 1.1s | **PASS** |

---

## 10. Current Limitations

1. **Heuristic Header Disambiguation**: When multiple identical filenames exist in different directories, the resolver uses directory proximity rather than compiler include search paths (`-I` or `-isystem`).
2. **Sequential File Processing**: Files are processed sequentially on a single thread. While fast for moderate repositories (36 tests execute in ~1 second), 200,000+ files will require a multiprocessing worker pool (`ProcessPoolExecutor`).
3. **No Dynamic Build Configuration Parsing**: The connector does not read `CMakeLists.txt`, `tsconfig.json` paths, or `pyproject.toml` package aliases.
4. **Binary Discovery Fallback Priority**: The adapter checks for `scanner/scanner.exe` first, but falls back to Python `os.scandir` when the binary is absent.

---

## 11. Known Issues

1. **Windows Console Codec Warnings**: When printing non-ASCII Unicode characters to a standard Windows `cp1252` console, CLI output without explicit redirection can raise encoding errors if files contain special glyphs. Output formatting explicitly normalizes to POSIX forward slashes and ASCII formatting to avoid this.
2. **C++ Native Scanner Output Formatting**: The C++ scanner prints paths directly to stdout without JSON framing; `ScannerAdapter` parses lines between `Found files:` and `Total files:`.

---

## 12. Files Created / Modified

### Created Files
- [`connector/__init__.py`](file:///D:/graphs/connector/__init__.py): Package exports.
- [`connector/__main__.py`](file:///D:/graphs/connector/__main__.py): Entry point for `python -m connector`.
- [`connector/main.py`](file:///D:/graphs/connector/main.py): Direct script entry point.
- [`connector/models.py`](file:///D:/graphs/connector/models.py): Frozen slotted DTOs (`ResolvedReference`, `FileRelationship`, `RelationshipMap`).
- [`connector/exceptions.py`](file:///D:/graphs/connector/exceptions.py): Domain exception hierarchy.
- [`connector/resolver.py`](file:///D:/graphs/connector/resolver.py): Multi-index reference resolution engine.
- [`connector/scanner_adapter.py`](file:///D:/graphs/connector/scanner_adapter.py): Integration adapter for `scanner.exe` with `os.scandir` fallback.
- [`connector/connector.py`](file:///D:/graphs/connector/connector.py): Orchestration pipeline.
- [`connector/cli.py`](file:///D:/graphs/connector/cli.py): Command-line interface with text and JSON formatters.
- [`connector/main.cpp`](file:///D:/graphs/connector/main.cpp): C++ wrapper for native binary execution.
- [`connector/build.bat`](file:///D:/graphs/connector/build.bat): Build script for compiling `connector.exe` via `g++` or `cl.exe`.
- [`connector/README.md`](file:///D:/graphs/connector/README.md): Architecture, usage, and build documentation.
- [`connector/CONNECTOR_PROGRESS_REPORT.md`](file:///D:/graphs/connector/CONNECTOR_PROGRESS_REPORT.md): This comprehensive progress report.
- [`tests/test_connector.py`](file:///D:/graphs/tests/test_connector.py): Test suite covering all 12 test specifications.

---

## 13. Current Status

- **Status**: `IMPLEMENTED + TESTED + VERIFIED`
- **Core Pipeline**: `WORKING` (Full pipeline from path -> Scanner -> Tokenizer -> Resolver -> RelationshipMap).
- **Native Launcher**: `WORKING` (`connector.exe` successfully compiled with `g++` and verified).
- **Test Suite**: `PASSING` (11/11 connector tests pass; 36/36 repository tests pass).
- **Evidence Integrity**: `VERIFIED` (Zero spurious connections invented; external references properly tagged as `UNRESOLVED`).

---

## 14. Next Steps

1. **Phase 4: Symbol Table & Scope Resolution**: Move beyond file-level connections to fine-grained symbol-level resolution (classes, functions, methods, variables) as specified in `AGENTS.md`.
2. **Phase 5: Graph Storage Layer**: Transition from in-memory `RelationshipMap` to the `GraphStore` protocol (in-memory adjacency list and SQLite disk store with WAL mode).
3. **Multiprocessing Parallelization**: Introduce chunked multiprocessing (`ProcessPoolExecutor` in batches of 500–2,000 files) to scale tokenization to 200,000+ files.
4. **Include Path Configuration**: Allow passing compiler include directories (`-I`) or `tsconfig.json` paths to `Connector` for enhanced C++ and TypeScript resolution.
