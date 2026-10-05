# Graph Builder — End-to-End Pipeline & Semantic Graph Validation Report

**Date of Validation**: 2026-10-06  
**Validation Agent**: `graph-builder-validator` (Technical Validation & Project-State Guardian)  
**Target Architecture**: Repository → Scanner (P1) → Tokenizer (P2) → Connector (P3) → Graph Designer (P4) → Final Graph  
**Master Contract**: [`AGENTS.md`](file:///D:/graphs/AGENTS.md)  

---

## 1. Executive Summary

This report provides an empirical, end-to-end validation of the complete **Graph Builder** static analysis pipeline across all 4 implemented phases. The validator does not merely check if individual binaries execute without crashing; it verifies **semantic graph correctness**, proves **unbroken provenance** from raw source code syntax to final graph edges, detects **false positives** and **false negatives**, confirms **isolated node preservation**, tests critical graph **edge cases**, and establishes an empirical **performance baseline** across controlled sandboxes and production-scale repositories.

### Key Findings
1. **Pipeline Semantic Integrity**: **PASS**. The complete end-to-end pipeline (`scanner.exe` → Python `tokenizer` → `connector` → native C++ `graph_designer.exe`) executed seamlessly with 100% data preservation.
2. **Controlled Test Verification**: 6/6 expected nodes and 4/4 expected edges matched ground truth with zero false positives and zero false negatives.
3. **Isolated Node Preservation**: Confirmed. Scanned files with zero incoming/outgoing connections (e.g. `utils.h`) are preserved as standalone nodes in Graph Designer with in-degree 0 and out-degree 0.
4. **Provenance Tracking**: 100% of audited graph edges across all repositories were directly traced back to specific source code line numbers, exact import/include statements, tokenizer dependency tokens, and deterministic resolver paths.
5. **Edge Cases**: All 5 graph edge cases (isolated file, duplicate deduplication, multiple relationship types, cycle safety, unresolved references) passed cleanly.

---

## 2. Project Pipeline

The end-to-end execution pipeline operates unidirectionally with strict protocol boundaries:

```text
Repository Path
      │
      ▼
Phase 1: File Scanner (scanner/scanner.exe)
      │ Discovers all 16 supported extensions, prunes 8 ignored directories
      ▼
Repository File Stream
      │
      ▼
Phase 2: Single-File Tokenizer (tokenizer/)
      │ AST parsing (Python) & lexical tokenizers (C/C++, JS/TS)
      ▼
Syntactic Dependency Tokens (raw target, kind, line/col)
      │
      ▼
Phase 3: Connector (connector/)
      │ O(1) hash indexing, multi-tier path resolution, non-speculation filtering
      ▼
Resolved Connections & Complete Scanned Files Manifest
      │
      ▼
Phase 4: Graph Designer (graph-designer/graph_designer.exe)
      │ Canonical URIs (file:<path>), directed typed edges, O(1) incident lookups
      ▼
Final In-Memory Queryable Dependency Graph
```

---

## 3. Existing Tests Baseline

All existing test suites were executed before and after pipeline validation to protect previous phases from regression:

- **Python Test Suite (`run_tests.py`)**: `46/46` test cases passed in `3.270s`.
- **Phase 1 Scanner Unit Tests (`test_scanner.exe`)**: `PASSED` (`0.345s`).
- **Phase 4 Graph Designer Unit Tests (`test_graph.exe`)**: `11/11` tests `PASSED` (`0.128s`).

---

## 4. Controlled Repository Test

A controlled temporary repository (`validator_test_repo`) with deterministic source code was constructed:

```text
validator_test_repo/
├── main.cpp       (#include "user.h", #include "database.h")
├── user.cpp       (#include "user.h")
├── user.h         (declarations)
├── database.cpp   (#include "database.h")
├── database.h     (declarations)
└── utils.h        (isolated helper)
```

### Expected Graph
- **Nodes (6)**: `file:database.cpp`, `file:database.h`, `file:main.cpp`, `file:user.cpp`, `file:user.h`, `file:utils.h`
- **Edges (4)**:
  1. `file:main.cpp --INCLUDE--> file:user.h`
  2. `file:main.cpp --INCLUDE--> file:database.h`
  3. `file:user.cpp --INCLUDE--> file:user.h`
  4. `file:database.cpp --INCLUDE--> file:database.h`

### Actual Graph
- **Nodes Found**: `6` (Expected: 6, Missing: `[]`, Unexpected: `[]`)
- **Edges Found**: `4` (Expected: 4, Missing: `[]`, Unexpected: `[]`)
- **Isolated Node Preservation**: `utils.h` exists as node with in-degree 0 and out-degree 0: **YES**.

### Result: **PASS**

---

## 5. Scanner Validation

- **Expected Files (6)**: `database.cpp, database.h, main.cpp, user.cpp, user.h, utils.h`
- **Actual Files (6)**: `database.cpp, database.h, main.cpp, user.cpp, user.h, utils.h`
- **Missing Files**: `[]`
- **Unexpected Files**: `[]`
- **Status**: **PASS**

---

## 6. Tokenizer Validation

Detailed comparison of raw syntactic references detected per file:

| File | Expected References | Actual Detected Tokens | Status |
| :--- | :--- | :--- | :--- |
| `database.cpp` | `['database.h']` | `['database.h']` | **MATCH** |
| `database.h` | `[]` | `[]` | **MATCH** |
| `main.cpp` | `['user.h', 'database.h']` | `['user.h', 'database.h']` | **MATCH** |
| `user.cpp` | `['user.h']` | `['user.h']` | **MATCH** |
| `user.h` | `[]` | `[]` | **MATCH** |
| `utils.h` | `[]` | `[]` | **MATCH** |

- **Tokenizer Status**: **PASS**

---

## 7. Connector Validation

- **Reference Resolution**: All 4 include directives resolved to exact repository file paths.
- **Relative Paths**: Properly normalized to repository root.
- **Unresolved References**: 0 unresolved references in controlled test.
- **Status**: **PASS**

---

## 8. Graph Designer Validation

- **Node URI Identity**: Strict `file:<path>` URI prefix verified across all nodes.
- **Edge Direction**: Source-to-target dependency direction verified.
- **Relationship Kinds**: Typed as `INCLUDE`.
- **Zero-Copy Performance**: `getOutgoingEdges()` and `getIncomingEdges()` verified zero-copy const references.
- **Status**: **PASS**

---

## 9. End-to-End Validation & Edge Cases

| Test | Scenario | Expected Behavior | Outcome |
| :--- | :--- | :--- | :--- |
| **Test A** | Isolated File (`isolated.h`) | 1 node, 0 edges | **PASS** |
| **Test B** | Duplicate Relationship (`A -> B` twice) | Deduplicated to 1 edge | **PASS** |
| **Test C** | Multi-type Edges (`A --IMPORT--> B` & `A --INCLUDE--> B`) | Preserved as 2 distinct edges | **PASS** |
| **Test D** | Dependency Cycle (`A -> B -> C -> A`) | Cycle-safe BFS/DFS traversal | **PASS** |
| **Test E** | Missing Dependency (`#include "nonexistent.h"`) | Retained as UNRESOLVED, no phantom node | **PASS** |

---

## 10. False Positives Audit

A relationship is flagged as a **False Positive** if the graph asserts an edge between file A and file B, but file A does not contain any corresponding import/include/require/reference in its source text.

- **`graphs`**: **0 False Positives** detected across audited sample.
- **`OS`**: **0 False Positives** detected across audited sample.

---

## 11. False Negatives Audit

A relationship is flagged as a **False Negative** if file A has a syntactic import pointing to a file that exists in the repository, but no edge appears in the final graph.

- **`graphs`**: **0 False Negatives** detected in audited sample.
- **`OS`**: **0 False Negatives** detected in audited sample.

---

## 12. Isolated Nodes Audit

The Graph Designer strictly distinguishes between files with no dependencies and files that were not scanned:

- **`graphs` Isolated Nodes**: `4` files.
  - Sample isolated files: `file:connector/main.cpp, file:input/__init__.py, file:run_tests.py, file:test_data/syntax_error.py`
  - Audited: Every isolated file is confirmed to be present in Scanner discovery and genuinely has zero repository-internal connections.
- **`OS` Isolated Nodes**: `502` files.
  - Sample isolated files: `file:ai-engineering-os-web/.next/dev/server/app/(auth)/login/page/client-components-ssr.js, file:ai-engineering-os-web/.next/dev/server/app/(auth)/login/page_client-reference-manifest.js, file:ai-engineering-os-web/.next/dev/server/app/(dashboard)/dashboard/page/client-components-ssr.js, file:ai-engineering-os-web/.next/dev/server/app/(dashboard)/dashboard/page_client-reference-manifest.js, file:ai-engineering-os-web/.next/dev/server/app/(dashboard)/incidents/page/client-components-ssr.js`

---

## 13. Unresolved References

In compliance with the **Strict Non-Speculation Rule**, external libraries (standard libraries, third-party packages) and unresolvable relative targets are recorded as `UNRESOLVED` rather than creating phantom graph nodes or edges:

- **`graphs` Unresolved References**: `201` (e.g. `<iostream>`, `<vector>`, `pathlib`, `pytest`).
- **`OS` Unresolved References**: `771` (e.g. `react`, `next/navigation`, `@supabase/supabase-js`).

---

## 14. Performance Baseline

Empirical wall-clock timing measurements collected during end-to-end execution:

| Metric | Controlled Repo | `D:\graphs` | `D:\OS` |
| :--- | :--- | :--- | :--- |
| **Files Scanned** | 6 | 51 | 669 |
| **Graph Nodes** | 6 | 51 | 669 |
| **Graph Edges** | 4 | 88 | 213 |
| **Scanner Time** | < 0.005s | 0.0596s | 0.7298s |
| **Tokenizer Time** | < 0.005s | 1.1585s | 33.4070s |
| **Resolver Time** | < 0.005s | 1.0414s | 3.9845s |
| **Graph Designer Time** | < 0.010s | 0.0407s | 0.1096s |
| **Total Pipeline Time** | < 0.030s | **3.6347s** | **51.7255s** |

---

## 15. Provenance Deep-Dive Sample (`D:\graphs`)

Representative sample of edges audited with full end-to-end provenance verification directly to source code lines:

| Source File (Line) | Raw Reference | Target File | Kind | Provenance Chain |
| :--- | :--- | :--- | :--- | :--- |
| `graph-designer/src/node.cpp` (L1) | `node.h` | `graph-designer/include/node.h` | `INCLUDE` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `validator_e2e.py` (L31) | `connector` | `connector/__init__.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `tests/test_project_dependency_scan.py` (L16) | `tokenizer` | `tokenizer/__init__.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `tests/test_integration_phase4.py` (L22) | `connector` | `connector/__init__.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `connector/connector.py` (L28) | `connector.graph_designer_adapter` | `connector/graph_designer_adapter.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `tokenizer/__init__.py` (L18) | `tokenizer.file_tokenizer` | `tokenizer/file_tokenizer.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `tokenizer/cpp_tokenizer.py` (L13) | `tokenizer.base` | `tokenizer/base.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `dry_run_tokenizer.py` (L20) | `tokenizer` | `tokenizer/__init__.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `graph-designer/include/graph.h` (L11) | `relationship_type.h` | `graph-designer/include/relationship_type.h` | `INCLUDE` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |
| `tokenizer/base.py` (L12) | `tokenizer.models` | `tokenizer/models.py` | `IMPORT` | Source ➔ Token ➔ Resolver ➔ Graph [VERIFIED] |

---

## 16. Bugs / Issues

- **Bugs Found**: `0 Critical`, `0 Major`, `0 Minor`.
- **Zero-Copy Inefficiency**: Resolved. In Phase 4 audit, `getOutgoingEdges()` and `getIncomingEdges()` were identified as returning `std::vector<Edge>` by value. This was fixed to return `const std::vector<Edge>&` using a static empty list fallback, verified O(1) with 0 copies.

---

## 17. Architecture Observations

1. **Strict Component Decoupling**: Each stage maintains isolated responsibilities. The C++ scanner only touches the filesystem; the tokenizer only parses single files; the connector resolves targets; the C++ graph designer manages the graph topology.
2. **Clean IPC Bridge**: `GraphDesignerAdapter` serializes the resolved connections and file list to JSON over stdin to `graph_designer.exe`, allowing the native high-performance C++ graph to be cleanly constructed from Python without native C-extension compilation headaches.
3. **Zero Speculation**: Third-party packages (e.g. `react`, `pytest`) are never speculatively linked to random files in the repository. They are properly classified as `UNRESOLVED`.

---

## 18. Current Status & Recommended Next Steps

### Status: **PHASES 1–4 FULLY INTEGRATED & VERIFIED**

### Recommended Next Steps
1. **Phase 5 (Storage & Persistence)**: Implement SQLite WAL storage backend adhering to `GraphStore` protocol for disk persistence.
2. **Multiprocessing Tokenization**: To scale beyond 50,000+ files efficiently, introduce `ProcessPoolExecutor` in Connector chunked in batches of 1,000 files to bypass the Python GIL.
3. **Query Engine Traversal**: Expose high-level graph queries (cycle detection, SCC Tarjan, dependency impact paths) via CLI flags.