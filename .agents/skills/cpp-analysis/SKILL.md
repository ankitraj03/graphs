---
name: cpp-analysis
description: >-
  Static analysis methodology for C++ target code analyzed by the `graphs` repository engine.
  Analyzes C++ as a TARGET LANGUAGE (not implementation language). Extracts translation units,
  includes, namespaces, classes, structs, functions, templates, inheritance, and calls.
---

# C++ Target Code Analysis

This skill defines the methodology for analyzing C and C++ code when scanned as a **target language** in repositories analyzed by `graphs`. 

> **Important**: C++ is the language being inspected, not the implementation language of the scanner. The analyzer itself operates as a pluggable component within the `graphs` architecture (e.g. `CPlusPlusAnalyzer` implementing the `LanguageAnalyzer` protocol).

---

## 1. Analysis Goals & Target Artifacts

When analyzing C++ repositories, the analyzer must extract and model:

| Entity Kind | Typical File Extensions / AST Constructs | Description |
| :--- | :--- | :--- |
| **Translation Unit** | `.cpp`, `.cc`, `.cxx`, `.c` | Primary compilation units |
| **Header** | `.h`, `.hpp`, `.hxx`, `.hh`, `.inl` | Declarations, inline definitions, templates |
| **Include** | `#include <header>`, `#include "file.h"` | Physical file dependency directives |
| **Namespace** | `namespace foo { ... }`, `namespace a::b` | Scope boundaries, including anonymous and inline |
| **Class / Struct** | `class Foo`, `struct Bar` | User-defined aggregate types and access specifications |
| **Function / Method** | Free functions, class methods, constructors | Signatures, parameters, return types, const/noexcept qualifiers |
| **Template** | `template <typename T> class Vector` | Generic declarations and specializations |
| **Macro** | `#define MAX_BUFFER 1024` | Preprocessor symbols (where relevant to architecture) |

---

## 2. Extraction Taxonomy & AST Strategy

Parsing C++ without running a full compiler requires balancing parsing speed against semantic completeness.

### Parsing Options
1. **Tree-Sitter C++ Parser**:
   - Fast, resilient to missing header inclusions, partial code, and syntax errors.
   - Ideal for initial scanning of massive codebases (100,000+ files) where full compiler setup is unavailable.
2. **`compile_commands.json` (Clang Compilation Database)**:
   - When present in the target repository, use it to obtain exact include paths (`-I`), system headers (`-isystem`), and macro defines (`-D`).
3. **Libclang / Clang AST**:
   - High-fidelity semantic analysis when exact compilation flags are available.

### Syntactic Entities Extracted
```text
C++ File (.cpp / .hpp)
  ├── #include Directives ──────> Physical File Dependency (INCLUDES)
  ├── Preprocessor Guards (#pragma once / #ifndef)
  └── Namespaces
       └── Classes / Structs
            ├── Base Classes ───> Inheritance Dependency (INHERITS)
            ├── Field Types ────> Type Dependency (USES)
            └── Methods
                 ├── Parameters ─> Type Dependency (USES)
                 └── Calls ──────> Call Dependency (CALLS)
```

---

## 3. Include Resolution & Evidence Tiers

Resolving `#include` directives to concrete files in the target repository is central to C++ dependency modeling:

### Include Categorization
- **Quoted Includes (`#include "local.h"`)**: Resolved first relative to the including file's directory, then searched against project include directories.
- **Angle-Bracket Includes (`#include <vector>`)**: System/standard headers or external third-party library includes; searched against standard/external include paths.

### Evidence Tiers for C++

#### Tier 1: Directly Observed (Syntactic Facts)
- `File INCLUDES Header` (Direct `#include` statement in source).
- `Class INHERITS BaseClass` (Explicit base class in class head: `class B : public A`).
- `Namespace CONTAINS Class` (Class declared within namespace block).
- `Class CONTAINS Method` (Method declared within class definition).
- `Function CALLS Function` (Syntactic call expression identified in AST).

#### Tier 2: Statically Inferred (Resolved Symbols)
- Resolving `#include "common/types.h"` to the target file `src/common/types.h` via project root paths.
- Forward declaration resolution: Linking a forward-declared `class Engine;` to its complete definition in `engine.hpp`.
- Namespace qualification resolution: Resolving unqualified call `init()` to `core::init()` using active `using namespace core;` directives.

#### Tier 3: Unresolved / Dynamic
- **Macro-Generated Identifiers**: Functions or classes generated via preprocessor token concatenation (`##`).
- **Template Metaprogramming**: Method calls on template type parameters `T::process()` prior to instantiation.
- **Virtual Dispatch**: Calls to virtual methods where the runtime dynamic type could be any subclass.
- **Rule**: Mark uncertain targets as `UNRESOLVED` or assign edge confidence tier. **Never invent speculative call edges.**

---

## 4. Source Location Integrity

- Capture exact source locations for all definitions:
  - File path
  - Start line and column
  - End line and column
- Differentiate between:
  - **Declaration Location**: E.g., method prototype in `.hpp`.
  - **Definition Location**: E.g., method implementation body in `.cpp`.
  - Model this with dual nodes or a `DEFINES` vs `DECLARES` edge.

---

## 5. Analyzer Protocol Integration

The C++ analyzer integrates into `graphs` using the standard Python protocol:

```python
from pathlib import Path
from typing import override
from graphs.core.protocols import LanguageAnalyzer
from graphs.core.models import FileAnalysisResult

class CPlusPlusAnalyzer(LanguageAnalyzer):
    CPP_EXTENSIONS = frozenset({".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx", ".hh", ".inl"})

    @property
    @override
    def language_id(self) -> str:
        return "cpp"

    @override
    def can_analyze(self, path: Path) -> bool:
        return path.suffix.lower() in self.CPP_EXTENSIONS

    @override
    def extract_dependencies(self, path: Path, content: str) -> FileAnalysisResult:
        # Implements AST-based parsing (Tree-sitter C++ or libclang)
        ...
```

