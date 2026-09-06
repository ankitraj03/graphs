---
name: python-project-scanning
description: >-
  Repository scanning architecture for processing 200,000+ files in the `graphs` system.
  Covers fast directory traversal, ignore filtering (.git, venv, build dirs), binary detection,
  symlink handling, streaming metadata collection, incremental change detection, and parallel pipelines.
---

# Python Project Scanning

This skill defines the architecture and operational procedures for scanning massive source code repositories (200,000+ files) in the `graphs` system without exhausting system memory.

---

## 1. Scanner Architecture & Principles

1. **Language-Agnostic Core**: The scanner's job is file discovery, filtering, metadata collection, and language classification. It must **not** contain language-specific parsing logic.
2. **Zero-Buffering Discovery**: Files must be yielded as a lazy stream (generators). Never collect 200,000 file paths into an in-memory list before beginning processing.
3. **Producer-Consumer Pipeline**:
   - **Producer (Discovery Thread)**: Fast filesystem traversal using `os.scandir()`. Batches paths into chunks of 1,000.
   - **Queue**: A bounded memory queue to enforce backpressure and prevent memory exhaustion if workers fall behind.
   - **Consumers (Worker Pool)**: Worker processes parse files, extract dependencies, and emit graph updates.
   - **Aggregator / Storage**: Streaming consumer that writes graph edges to the database in batch transactions.

```text
Repository
    │
    ▼
[ Fast Directory Walk (os.scandir) ]  <-- Ignores .git, .venv, build, binary
    │
    ▼ (Stream of 1,000-item chunks)
[ Bounded Ingestion Queue ]
    │
    ├──────────────┬──────────────┤
    ▼              ▼              ▼
[ Worker 1 ]  [ Worker 2 ]  [ Worker N ]  <-- Pluggable Language Analyzers
    │              │              │
    └──────────────┴──────────────┘
    │
    ▼ (Stream of Node/Edge batches)
[ Database / Graph Storage Writer ]
```

---

## 2. Directory Filtering & Ignore Policies

To scale to 200,000+ files, the scanner must prune unneeded directory trees at traversal time before descending into them.

### Default Ignored Directories
Always skip these directories during discovery:
- **VCS Metadata**: `.git`, `.hg`, `.svn`
- **Virtual Environments**: `.venv`, `venv`, `env`, `.env`, `virtualenv`, `conda-meta`
- **Build & Distribution Artifacts**: `build`, `dist`, `out`, `bin`, `obj`, `target`, `cmake-build-*`
- **Cache Directories**: `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`
- **Package Manager Caches**: `node_modules`, `bower_components`, `vendor`
- **IDE & Tooling**: `.idea`, `.vscode`, `.vs`, `.eclipse`

### Gitignore Integration
- Support `.gitignore` and `.ignore` hierarchical rules.
- Evaluate ignore patterns against directory paths before descending into child directories to avoid scanning entire ignored trees.

---

## 3. Binary File & Symlink Handling

### 1. Binary Detection Heuristics
Never pass binary files (executables, compiled objects, archives, media) to source code analyzers:
- **Extension Filtering**: Exclude known binary extensions (`.exe`, `.dll`, `.so`, `.dylib`, `.o`, `.a`, `.pyc`, `.zip`, `.tar`, `.gz`, `.png`, `.jpg`, `.pdf`, `.db`).
- **Null-Byte Check**: For unrecognized or extensionless files, read the first 1,024 bytes. If a null byte (`b'\x00'`) is present, classify as binary and skip.
- **Size Safeguard**: Skip files exceeding a configurable threshold (e.g. >10 MB) unless explicitly included.

### 2. Symlink Policies & Cycle Prevention
- By default, do **not** follow directory symlinks (`follow_symlinks=False`).
- If symlink following is explicitly enabled:
  - Track visited directories by `(st_dev, st_ino)` on POSIX systems or canonical realpaths on Windows (`Path.resolve()`).
  - Abort traversal of any directory path whose canonical target has already been visited to prevent infinite recursion cycles.

---

## 4. Metadata Collection & Streaming

Collect file metadata during traversal without redundant `stat()` calls:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    relative_path: str
    absolute_path: str
    size_bytes: int
    mtime_ns: int
    extension: str
```

- When using `os.scandir()`, extract `entry.stat().st_size` and `entry.stat().st_mtime_ns`.
- Windows paths: Support paths longer than 260 characters by prefixing with `\\?\` when needed.

---

## 5. Incremental Change Detection

Avoid scanning unchanged files on subsequent runs:

1. **State Manifest**: Persist a manifest table in SQLite storing previous scan state:
   ```sql
   CREATE TABLE file_scan_state (
       path TEXT PRIMARY KEY,
       size_bytes INTEGER NOT NULL,
       mtime_ns INTEGER NOT NULL,
       content_hash TEXT NOT NULL,
       last_scanned_timestamp REAL NOT NULL
   );
   ```
2. **Three-Way Change Classification**:
   - **UNCHANGED**: `path`, `size_bytes`, and `mtime_ns` match the manifest. Skip analysis completely.
   - **MODIFIED**: `path` matches, but `mtime_ns` or `size_bytes` differs. Compute content hash (BLAKE3 or SHA-256). If hash differs, queue for re-analysis and update manifest.
   - **ADDED**: `path` does not exist in manifest. Queue for analysis and insert into manifest.
   - **DELETED**: Any path in manifest not visited during discovery. Purge associated nodes/edges from graph and delete from manifest.

---

## 6. Resilient Error Handling

The scanner must never abort the entire scan due to an issue with a single file or directory:

- **Permission Denied (`PermissionError`)**: Log a warning with the affected path and continue traversing sibling entries.
- **File Not Found / Race Condition (`FileNotFoundError`)**: Transient files (e.g. temporary files deleted during scan) must be caught and ignored.
- **Decoding Errors**: Catch `UnicodeDecodeError` when reading file text. Attempt fallback decoding (UTF-8, Latin-1) or skip if non-text.
- **Path Length Errors**: Catch Windows `WinError 206` (path too long) and retry using extended-length syntax (`\\?\Path`).

---

## 7. Progress Reporting & Telemetry

Scanning 200,000 files can take from 15 seconds to several minutes depending on hardware.

- **Non-Blocking Telemetry**: Use an atomic counter or background reporter thread (e.g. update every 0.5 seconds).
- **Reported Metrics**:
  - Discovered files count.
  - Processed / analyzed files count.
  - Skipped (ignored/binary/unchanged) count.
  - Current throughput (files/sec).
  - Estimated Time of Arrival (ETA).
- **Avoid Terminal Lock Contention**: Never update progress bars on every individual file; update at throttled time intervals or chunk completions.

