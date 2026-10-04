# Graph Builder — Phase 3: Connector

The **Connector** is the orchestration and relationship-resolution engine of the `graphs` static-analysis pipeline. It serves as the bridge between filesystem discovery (**Scanner**, Phase 1) and single-file lexical/syntactic dependency extraction (**Tokenizer**, Phase 2), producing a deterministic, verified repository file-relationship map.

---

## 1. Overall System Architecture

The pipeline strictly decouples responsibilities: the Scanner discovers files, the Tokenizer extracts syntactic dependency tokens per file, and the Connector resolves those references into actual repository connections without inventing spurious links.

```text
Repository Path
      │
      ▼
  Connector (Input Validation)
      │
      ▼
   Scanner (scanner.exe / Python fallback)
      │
      ▼
Discovered File List [file1, file2, ...]
      │
      ▼
  Connector (Build O(1) Path/Stem/Filename Index)
      │
      ▼
 For each file ──► Tokenizer (FileTokenizer)
                         │
                         ▼
                   Dependency Tokens [include "user.h", import os, ...]
                         │
                         ▼
  Connector (Resolve References against Repository Index)
      │
      ├── Match exact relative / root-relative / stemmed file paths
      ├── Retain unresolved references (confidence="UNRESOLVED")
      └── Deduplicate redundant links
      │
      ▼
File Relationship Map
      │
      ├── Text Output:  main.cpp -> [user.h, database.h]
      └── JSON Output:  {"main.cpp": ["user.h", "database.h"]}
```

---

## 2. Core Responsibilities

- **Orchestration**: Directs the end-to-end workflow from repository discovery to tokenization without duplicating Scanner or Tokenizer logic.
- **Reference Resolution**: Maps imported module names, C/C++ `#include` headers, and JS/TS imports to verified file paths in the target repository.
- **Non-Speculation**: Enforces strict evidence attribution per `AGENTS.md`. External libraries (e.g. `iostream`, `react`, `sys`) and missing files are classified as `UNRESOLVED` rather than linked to arbitrary files.
- **Deduplication**: Repeated references from a source file to the same target are deduplicated into unique connections.
- **Resilience**: Catches per-file tokenization and traversal errors gracefully, allowing the rest of the repository scan to proceed.

---

## 3. Input & Output Formats

### Input
- **Repository Root Path**: Absolute or relative directory path supplied as a CLI argument or via interactive prompt.
- **Optional CLI Flags**:
  - `--json`: Output relationships as structured JSON.
  - `--unresolved`: Display unresolved/external references.
  - `--scanner-bin <path>`: Explicitly provide path to a custom native scanner executable.

### Output
#### Human-Readable Text (Default)
```text
========================================
FILE RELATIONSHIPS
========================================

main.cpp
  -> user.h
  -> database.h

user.cpp
  -> user.h

user.h
  -> No linked files
```

#### JSON Output (`--json`)
```json
{
  "main.cpp": [
    "database.h",
    "user.h"
  ],
  "user.cpp": [
    "user.h"
  ],
  "user.h": []
}
```

---

## 4. Component Interactions

### Scanner Interaction (`ScannerAdapter`)
- Queries the native C++ executable (`scanner/scanner.exe`) if present.
- Seamlessly falls back to an `os.scandir`-based Python traversal matching the exact directory pruning rules (`.git`, `node_modules`, `build`, `dist`, `bin`, `obj`, `__pycache__`) and 16 supported file extensions (`.py`, `.cpp`, `.ts`, `.h`, etc.).
- Normalizes discovered paths to canonical absolute `pathlib.Path` objects.

### Tokenizer Interaction (`FileTokenizer`)
- Instantiates `FileTokenizer(project_root=root)` to process one file at a time.
- Employs AST-based parsing with lexical fallback for Python, and regex pattern extraction for C/C++ and JS/TS.
- Receives rich `DependencyToken` objects containing `target`, `keyword`, `kind`, and `location`.

### Reference Resolution (`ReferenceResolver`)
Builds four multi-level indexes over the scanned file set for fast $O(1)$ lookups:
1. **Canonical Exact Paths**: `set[Path]` for instant resolution of pre-resolved paths.
2. **Normalized Relative Paths**: `dict[str, Path]` for repository-relative paths.
3. **Filename Index**: `dict[str, list[Path]]` for `#include "header.h"` lookups.
4. **Stem Index**: `dict[str, list[Path]]` for Python dot-notation module matching.

Resolution follows a 6-tier pipeline:
1. *Pre-resolved path validation* (if already resolved by language tokenizer).
2. *Local directory-relative lookup* (relative to source file's directory, probing language extensions).
3. *Repository root-relative lookup*.
4. *Python dot-notation package resolution* (including relative `.`/`..` levels).
5. *Basename lookup with disambiguation* (matching relative path suffix or deepest common directory ancestor).
6. *Unresolved retention* (`is_resolved=False`, `confidence="UNRESOLVED"`).

---

## 5. How to Build & Run

### Building the Native Launcher (`connector.exe`)
A C++ CLI wrapper (`main.cpp`) compiles to a native `connector.exe` that invokes the Python orchestration module:

```cmd
cd connector
build.bat
```
`build.bat` automatically detects `g++` (MinGW) or `cl.exe` (MSVC) and copies the resulting binary to both `connector/connector.exe` and the project root `connector.exe`.

### Running the Connector

#### Option 1: Native CLI Executable
```cmd
.\connector.exe "D:\graphs\test_data"
.\connector.exe "D:\graphs\test_data" --json
.\connector.exe "D:\graphs\test_data" --unresolved
```

#### Option 2: Python Module Invocation
```cmd
python -m connector "D:\graphs\test_data"
python -m connector "D:\graphs\test_data" --json
python -m connector "D:\graphs\test_data" --unresolved
```

#### Option 3: Python Library API
```python
from pathlib import Path
from connector import Connector

connector = Connector()
rel_map = connector.connect(Path("D:/graphs/test_data"))

# Access structured data models
for src, rel in rel_map.relationships.items():
    print(f"{src.name} connects to {[t.name for t in rel.connected_files]}")

# Export dictionary representation
clean_dict = rel_map.to_dict(relative_to_root=True)
```

---

## 6. Current Limitations

1. **Static Name-Based Ambiguity**: If multiple files in different subdirectories share the identical filename (e.g. `src/a/types.h` and `src/b/types.h`) and an include uses `#include "types.h"`, the resolver uses common directory ancestor heuristics rather than compiler include paths (`-I`).
2. **No Build System Analysis**: The connector does not parse `CMakeLists.txt`, `Makefile`, or `tsconfig.json` path aliases (`@/components/*`).
3. **Single-Threaded Orchestration**: Iterates over files sequentially. Concurrency (multiprocessing pool) is slated for Phase 4 / scaling phase.