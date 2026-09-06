---
name: python-performance
description: >-
  Performance engineering guidelines for scaling Python in the `graphs` repository analysis system
  to 200,000+ files. Covers low-level filesystem I/O, memory optimization, concurrency selection
  (multiprocessing vs threading vs asyncio), batching, caching, database throughput, and profiling.
---

# Python Performance Engineering

This skill defines the performance strategies, memory optimization techniques, and concurrency architectures required for the `graphs` engine to process very large repositories (200,000+ files) efficiently in Python.

---

## 1. Cardinal Performance Rules

1. **Profile Before Optimizing**: Never guess where bottlenecks are. Profile with `cProfile`, `py-spy`, or `memray` before writing complex optimization code.
2. **Classify Workload Characteristics**: Always distinguish whether an operation is **I/O-bound** (directory walking, reading file contents, database flush) or **CPU-bound** (AST parsing, lexical analysis, symbol resolution, cycle detection).
3. **Never Assume C++ or Multiprocessing is Automatically Faster**: Multiprocessing carries substantial inter-process communication (IPC) and serialization costs. C++ extensions introduce FFI overhead and build complexity. Optimize algorithms and data structures first.
4. **Stream Everything**: Never hold all 200,000 file representations, ASTs, or graph nodes in memory at once.

---

## 2. Filesystem I/O & Traversal (200,000+ Files)

### `os.scandir` vs `pathlib.Path.iterdir()` vs `os.walk`

- **The Problem with naive `pathlib` / `os.walk`**: Calling `.stat()` or `.is_file()` on thousands of `Path` objects triggers a distinct OS system call for each entry, causing severe latency on large directory trees (especially over Windows NTFS or network mounts).
- **The Solution: `os.scandir()`**:
  - `os.scandir()` yields `os.DirEntry` objects.
  - On Windows and modern POSIX systems, `DirEntry` caches file attributes (file type, size, modification time) directly from the directory stream without performing additional `stat()` calls.
  - Traversal with `os.scandir` is 2x to 10x faster than traditional recursion.
- **Implementation Rule**: Use `os.scandir` in the core scanner discovery loop; only convert to `pathlib.Path` lazily when passing to higher-level domain components.

```python
import os
from collections.abc import Iterator

def fast_walk(directory: str) -> Iterator[os.DirEntry[str]]:
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if not is_ignored_dir(entry.name):
                            yield from fast_walk(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        yield entry
                except OSError:
                    continue
    except OSError:
        return
```

---

## 3. Memory Optimization & Allocation Reduction

When handling 200,000+ files producing millions of nodes and edges, object overhead is the primary memory driver.

### 1. `__slots__` Everywhere
Standard Python objects contain a `__dict__` requiring ~150-300 bytes per instance. Using `slots=True` in dataclasses drops per-instance overhead to ~48-64 bytes:
```python
@dataclass(frozen=True, slots=True)
class EdgeRecord:
    source_id: str
    target_id: str
    kind: str
    evidence: str
```

### 2. String Interning (`sys.intern`)
In large codebases, strings such as relationship kinds (`"IMPORTS"`, `"CALLS"`, `"CONTAINS"`), node kinds (`"FUNCTION"`, `"CLASS"`), common package prefixes, and file extensions are duplicated millions of times.
- Use `sys.intern(s)` on all repeated identifier strings:
```python
import sys

KIND_IMPORTS = sys.intern("IMPORTS")
KIND_CALLS = sys.intern("CALLS")

def make_interned_kind(kind: str) -> str:
    return sys.intern(kind)
```
Interning guarantees a single shared string object in memory and allows pointer equality (`is`) comparison instead of string content comparison.

### 3. Avoid Full AST Retention
Parse an individual file, extract its symbols, definitions, and edges, and immediately release the AST for garbage collection. Never store AST node objects in the persistent graph.

### 4. Garbage Collection Tuning
When creating and destroying millions of transient objects in batch jobs, Python's cyclical garbage collector (`gc`) can trigger frequent, expensive traversals of generation 2.
- For high-throughput worker processes, tune GC thresholds or temporarily disable GC during pure compute passes:
```python
import gc

# Disable during intensive batch parsing, manually collect between batches
gc.disable()
try:
    process_chunk(chunk)
finally:
    gc.enable()
    gc.collect(generation=1)
```

---

## 4. Concurrency Model Selection

| Workload Type | Concurrency Mechanism | Why | Pitfalls to Avoid |
| :--- | :--- | :--- | :--- |
| **Filesystem Walk & Stat** | Single-threaded or I/O ThreadPool | Metadata is cached by OS kernel; single-thread scanning avoids disk head thrashing on HDDs and lock contention on NVMe. | Spawning thousands of threads causes OS context-switch overhead. |
| **File Content Reading** | Batched ThreadPool | I/O-bound reading releases the GIL during read syscalls. | Reading too many huge files simultaneously causes RAM spikes. |
| **AST Parsing & Extraction** | `ProcessPoolExecutor` (Multiprocessing) | CPU-bound. Multiprocessing bypasses Python's Global Interpreter Lock (GIL). | IPC overhead: never pass individual files across processes. |
| **Asyncio** | Not Recommended for Local FS | Standard OS file read/write operations are blocking in POSIX/Windows; `asyncio` file wrappers simply offload to threadpools with overhead. | Using `asyncio` for local file I/O adds overhead without true non-blocking OS benefits. |

---

## 5. IPC, Batching & Queues

When distributing work across worker processes via `concurrent.futures.ProcessPoolExecutor` or `multiprocessing`:

1. **Chunking is Essential**: Passing individual file paths or individual parse results across IPC boundaries incurs severe pickling/unpickling overhead.
2. **Optimal Batch Sizing**:
   - Send batches of **500 to 2,000 files** per task payload to worker processes.
   - Return aggregated analysis results (lists of nodes and edges) in single batch payloads.
3. **Shared Memory / Read-Only Config**:
   - Configuration should be initialized once per worker on process start (using worker initializers) rather than re-pickled with every task.

```python
from concurrent.futures import ProcessPoolExecutor

def analyze_batch(file_paths: list[str]) -> list[FileAnalysisResult]:
    results: list[FileAnalysisResult] = []
    for path in file_paths:
        results.append(analyze_single_file(path))
    return results

def run_pipeline(all_paths: list[str], max_workers: int = 8, batch_size: int = 1000) -> None:
    chunks = [all_paths[i:i + batch_size] for i in range(0, len(all_paths), batch_size)]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for batch_result in executor.map(analyze_batch, chunks):
            persist_results(batch_result)
```

---

## 6. Incremental Scanning & Hashing

Do not re-parse 200,000 files on every run:

1. **Fast-Check First (mtime + size)**:
   - Record `(file_path, st_mtime_ns, st_size)` in an SQLite state cache.
   - If both `mtime` and `size` match the previous scan, the file has not changed. Skip reading and parsing completely.
2. **Content Hash (Fallback for precision)**:
   - When `mtime` or `size` differs, or when running in strict mode, compute a cryptographic or fast non-cryptographic content hash.
   - Use streaming chunks (e.g. 64 KB buffers) with `hashlib.blake2b` or `hashlib.sha256` so large files do not load entirely into memory.
3. **Incremental Graph Merging**:
   - For modified files: remove previous edges originating from the file, parse the new version, and insert the new edges.
   - For deleted files: cascade delete all nodes and edges defined in that file.

---

## 7. High-Throughput Database Writes (SQLite / Disk Storage)

When writing millions of edges and nodes into disk storage:

1. **Enable Write-Ahead Logging (WAL)**:
   ```sql
   PRAGMA journal_mode = WAL;
   PRAGMA synchronous = NORMAL;
   PRAGMA cache_size = -64000; -- 64MB cache
   PRAGMA temp_store = MEMORY;
   ```
2. **Batch Transactions**:
   - Individual `INSERT` statements commit each row separately, limiting throughput to ~100 writes/second.
   - Use `connection.executemany(...)` wrapped in an explicit transaction (`BEGIN TRANSACTION ... COMMIT`) with batch sizes of **10,000 to 50,000 rows**.
   - Batch writes achieve **100,000+ inserts per second** in SQLite.
3. **Index Management**:
   - Drop or defer index creation (e.g. indices on `source_id`, `target_id`) during initial bulk ingestion; build indices after all edges are inserted.

---

## 8. Profiling & Diagnostic Methodology

Before recommending any native C++ rewrite, gather empirical telemetry:

- **CPU Profiling**: Run `py-spy` for non-intrusive sampling:
  ```bash
  py-spy record -o profile.svg -- python -m graphs scan /path/to/repo
  ```
- **Deterministic Profiling**: Use `cProfile` with `pstats` to identify hot call sites.
- **Memory Profiling**: Use `memray` to trace peak heap usage, memory leaks, and high-frequency allocation sites:
  ```bash
  memray run -m graphs scan /path/to/repo
  memray flamegraph memray-*.bin
  ```
- **Line Profiling**: Apply `@line_profiler.profile` to isolated hot functions (e.g. AST visitor traversal).
- **Rule for Native Rewrite**: Only propose a C++ rewrite if a single CPU-bound function accounts for >50% of runtime and cannot be improved algorithmically or via multiprocessing in Python.

