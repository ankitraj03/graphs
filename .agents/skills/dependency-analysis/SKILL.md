---
name: dependency-analysis
description: >-
  Language-independent dependency analysis framework for the `graphs` repository engine.
  Combines multi-source evidence from imports, includes, AST relations, calls, inheritance,
  and type usage. Enforces evidence attribution, symbol resolution, and architectural rule validation.
---

# Dependency Analysis Framework

This skill defines the language-independent principles and algorithms for analyzing, resolving, attributing, and validating dependencies across software repositories in the `graphs` system.

---

## 1. Core Principles

1. **Evidence-Based Attribution**: Every dependency edge must carry its causal evidence and provenance. Never record a dependency without noting *why* it exists.
   ```text
   Module A.py ──[IMPORTS]──> Module B.py
       evidence: "from b import helper"
       source_location: "A.py:12:1-12:28"
       kind: "import_statement"
   ```
2. **Never Invent Relationships**: If a symbolic target cannot be unambiguously resolved to a concrete declaration or definition, record the edge as an `UNRESOLVED` reference. Do not guess.
3. **Multi-Source Evidence Aggregation**: A dependency between two modules may be supported by multiple independent syntactic facts (e.g. an import, an inheritance clause, and five function calls). The dependency model aggregates these into a unified, weighted relationship while preserving individual evidence records.

---

## 2. Evidence Taxonomy

Dependencies are synthesized from distinct categories of evidence:

| Evidence Kind | Origin Construct | Semantic Category | Example |
| :--- | :--- | :--- | :--- |
| `import_statement` | `import X`, `from X import Y` | Module Loading | `A.py` loads `B.py` |
| `include_directive` | `#include "types.h"` | Physical Inclusion | `service.cpp` includes `types.h` |
| `inheritance_specifier`| `class Dog(Animal):`, `: public Base` | Structural Derivation | Class `Dog` extends `Animal` |
| `implementation_specifier`| `class Repo(Protocol):` | Interface Contract | `SQLRepo` implements `Repo` |
| `call_expression` | `service.execute()`, `calculate()` | Behavioral Invocation | Function `run` invokes `execute` |
| `type_annotation` | `x: Logger`, `def get() -> User:` | Type System Reference | Parameter/Return type reference |
| `containment` | Filesystem or scope nesting | Structural Ownership | Package `core` contains `models` |
| `variable_reference` | Reading/writing a global or constant | Data Access | Function reads `CONFIG_MAP` |

---

## 3. Dependency Classification

Dependencies are categorized into distinct operational layers:

```text
┌────────────────────────────────────────────────────────┐
│               BEHAVIORAL DEPENDENCIES                  │
│       (Function Calls, Method Invocations)            │
├────────────────────────────────────────────────────────┤
│               STRUCTURAL DEPENDENCIES                  │
│    (Inheritance, Interface Implementation, Aggregation)│
├────────────────────────────────────────────────────────┤
│                 TYPE DEPENDENCIES                      │
│        (Parameter Types, Return Types, Generics)       │
├────────────────────────────────────────────────────────┤
│                SYNTACTIC DEPENDENCIES                  │
│             (Imports, Module References)               │
├────────────────────────────────────────────────────────┤
│                PHYSICAL DEPENDENCIES                   │
│        (Filesystem Containment, C/C++ Includes)        │
└────────────────────────────────────────────────────────┘
```

- **Physical / Packaging**: Required to compile or package the files (e.g. `#include`, module files within a package directory).
- **Syntactic**: Declared module-level links (e.g. Python `import`, Java `import`).
- **Type**: Dependencies that exist solely in the type system (e.g. annotations guarded by `if TYPE_CHECKING:` in Python or forward declarations in C++).
- **Structural**: Deep semantic coupling through object inheritance or protocol compliance.
- **Behavioral**: Execution-time coupling via function and method calls.

---

## 4. Multi-Pass Resolution Architecture

Dependency extraction requires a two-phase architecture to separate local syntactic parsing from global symbol resolution:

### Phase 1: Local Extraction (Parallel per File)
- The language-specific analyzer parses the file into an AST.
- Emits local definitions (symbols declared in the file) with their stable local IDs.
- Emits raw references (unresolved imported names, called functions, type annotations) with source locations and evidence.
- No global repository knowledge is required during Phase 1.

### Phase 2: Global Symbol Resolution (Aggregator)
- Builds a repository-wide **Symbol Definition Index** mapping fully qualified names to stable node IDs.
- Iterates over raw references and resolves them against the symbol table:
  1. Check local file scope.
  2. Check imported symbols within the file.
  3. Check enclosing package / namespace scope.
  4. Check global repository exports.
  5. If unresolved, mark as external or unresolved dependency:
     ```python
     if target_node_id in symbol_table:
         emit_edge(source_id, target_node_id, confidence="RESOLVED")
     else:
         emit_edge(source_id, f"external:{raw_target}", confidence="UNRESOLVED")
     ```

---

## 5. Architectural Rule Validation & Cycle Detection

The dependency graph serves as the source of truth for architectural analysis:

### 1. Circular Dependency Detection
- Execute Tarjan's or Kosaraju's algorithm on the module/package subgraph.
- Any strongly connected component with $>1$ node represents an architectural cycle.
- Output the exact cycle trace:
  ```text
  Cycle detected (Length 3):
    graphs.scanner.pipeline
      --[IMPORTS]--> graphs.analyzers.registry
      --[IMPORTS]--> graphs.analyzers.python
      --[IMPORTS]--> graphs.scanner.pipeline
  ```

### 2. Layering & Boundary Rules
- Define boundary policy matrices (e.g., Domain must not depend on Infrastructure):
  ```yaml
  rules:
    - from: "graphs.core.*"
      deny:
        - "graphs.scanner.*"
        - "graphs.storage.*"
        - "graphs.analyzers.*"
      rationale: "Core domain models must remain pure and free of I/O dependencies."
  ```
- The dependency engine traverses edges and flags rule violations with precise file and line evidence.

### 3. Impact Analysis & Blast Radius
- Given a proposed change to Node $N$:
  - Perform reverse BFS traversal along incoming dependency edges (`CALLS`, `USES`, `IMPORTS`, `INHERITS`).
  - The reachable set of nodes represents the exact **blast radius** of the change.

