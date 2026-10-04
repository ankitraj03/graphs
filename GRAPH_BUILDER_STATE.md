# Graph Builder — Project State & Memory

**Last Updated**: 2026-10-04  
**Maintained By**: `graph-builder-validator` (Graph Builder Validator Agent)  
**Engineering Contract**: [`AGENTS.md`](file:///D:/graphs/AGENTS.md)

---

## 1. Project Phase Tracker

| Phase | Component | Primary Language | Status | Verification State |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | **Scanner** | C++17 (`std::filesystem`) | **COMPLETE** | Verified via `test_scanner.exe`, standalone tests, and CLI |
| **Phase 2** | **Tokenizer** | Python 3.12+ (`ast`, `re`) | **COMPLETE** | Verified via 25 unit/integration tests in `tests/` |
| **Phase 3** | **Connector** | Python 3.12+ (C++ launcher) | **COMPLETE** | Verified via 11 tests in `test_connector.py` & audit |
| **Phase 4** | **Graph Representation** | Python 3.12+ | **NOT STARTED** | Next milestone |
| **Phase 5** | **Storage & Persistence** | SQLite (WAL mode) / In-Memory | **PLANNED** | Schema and WAL batching outlined in `AGENTS.md` |
| **Phase 6** | **Incremental Scans** | Python 3.12+ (mtime, BLAKE3) | **PLANNED** | State caching and dirty file detection |
| **Phase 7** | **Query Engine** | Python 3.12+ | **PLANNED** | BFS/DFS traversal, cycle detection, SCC Tarjan |
| **Phase 8** | **AI / Agent Layer** | Python 3.12+ | **PLANNED** | High-level repository explanation and impact analysis |

---

## 2. Core Architectural Separation

```text
Repository Path
      │
      ▼
  CONNECTOR (Orchestration & Resolution)
      │
      ├──► SCANNER ──────────────► Repository File Paths (What files exist?)
      │
      ├──► TOKENIZER ────────────► Syntactic Tokens (What references exist in each file?)
      │
      └──► REFERENCE RESOLVER ───► Resolved File-to-File Connections (Which files connect?)
```

1. **Scanner Responsibility**: Answers *"What files exist in the repository?"*. Never parses or tokenizes file contents.
2. **Tokenizer Responsibility**: Answers *"What references/tokens exist inside this single file?"*. Never traverses directories.
3. **Connector Responsibility**: Answers *"Which repository files are actually connected?"*. Orchestrates Scanner and Tokenizer, resolves references against $O(1)$ repository hash indices, deduplicates links, and retains unresolved references without speculation.

---

## 3. Implemented Features & Milestones

### Phase 1 — Scanner (`scanner/`)
- **Native Binary**: [`scanner/scanner.exe`](file:///D:/graphs/scanner/scanner.exe) (301 KB, compiled via MSVC/MinGW with C++17).
- **Supported Extensions (16)**: `.py`, `.pyi`, `.c`, `.cpp`, `.cc`, `.cxx`, `.h`, `.hpp`, `.hxx`, `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`.
- **Directory Pruning (8)**: `.git`, `.vscode`, `node_modules`, `build`, `dist`, `bin`, `obj`, `__pycache__` pruned before descent via `disable_recursion_pending()`.
- **Sorting**: Deterministic lexicographical path order via `std::sort`.

### Phase 2 — Tokenizer (`tokenizer/`)
- **Single-File Contract**: Strict boundary enforced (directory traversal removed in commit `3e67df6`).
- **Python AST + Lexical Fallback**: Full import extraction via `ast.parse` with regex fallback on `SyntaxError`.
- **C/C++ Support**: `#include <...>`, `#include "..."`, C++20 `import ...;`.
- **JS/TS Support**: ES6 `import`/`export`, CommonJS `require()`, dynamic `import()`.
- **Models**: `@dataclass(frozen=True, slots=True)` with string interning (`sys.intern`) on `kind` and `keyword`.

### Phase 3 — Connector (`connector/`)
- **Dual Invocation**: Native C++ wrapper binary ([`connector.exe`](file:///D:/graphs/connector.exe)) and Python CLI module (`python -m connector`).
- **Zero-Dependency Fallback**: Seamless fallback to `os.scandir` when `scanner.exe` is absent; 100% parity verified.
- **Reference Resolution Pipeline**:
  1. Tokenizer pre-resolved path check.
  2. Local directory-relative lookup with extension probing (`.ts`, `.js`, `index.*`).
  3. Repository root-relative lookup.
  4. Python dot-notation resolution (`.`, `..`, module packages).
  5. Filename match with directory ancestor disambiguation.
  6. Strict non-speculation retention (`is_resolved=False`, `confidence="UNRESOLVED"`).
- **Serialization**: Plain text relationship tree and structured JSON (`--json`).

---

## 4. Known Limitations & Architecture Constraints

1. **Scanner Ignore Rules**: Uses static list of 8 directory names; does not yet parse arbitrary `.gitignore` glob patterns.
2. **Build System Aliases**: Resolver does not parse `tsconfig.json` path mappings (e.g. `@/lib/*`) or CMake include directories (`-I`).
3. **Sequential Execution**: Connector currently iterates through files in a single thread; multi-processing (`ProcessPoolExecutor`) will be needed to scale to 200,000+ files.

---

## 5. Architectural Decisions Awaiting Resolution for Future Phases

1. **Unresolved External Nodes**: In Phase 4 (Graph Representation), should third-party libraries (e.g. `react`, `express`, `numpy`) be modeled as dedicated `EXTERNAL` graph nodes with `confidence="UNRESOLVED"`, or stored only as metadata on file nodes?
2. **Path Alias Support**: Should a light `tsconfig.json` reader be introduced in Phase 4 to resolve `@/...` aliases prior to graph edge construction?
3. **Initial Graph Storage Backend**: Should Phase 4 implement the in-memory graph store first, or directly implement SQLite in WAL mode?
