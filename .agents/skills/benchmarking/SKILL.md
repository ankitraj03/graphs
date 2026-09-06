---
name: benchmarking
description: >-
  Standard performance benchmarking methodology and measurement protocol for the `graphs` engine.
  Defines metrics for files/second, CPU utilization, memory ceiling, parsing throughput,
  database writes, cold vs warm cache, and incremental scans. Enforces empirical measurement.
---

# Benchmarking Methodology & Metrics

This skill defines the empirical performance measurement protocol for the `graphs` system.

> **Cardinal Rule**: Never claim that one implementation, language, or optimization is faster without verifiable, reproducible benchmark measurements.

---

## 1. Core Metrics & Definitions

Every benchmark report must measure and report the following standard metrics:

| Metric | Unit | Measurement Method | Target Baseline (200k Files) |
| :--- | :--- | :--- | :--- |
| **Discovery Throughput** | Files / second | Wall-clock time for `os.scandir` directory discovery | > 50,000 files/sec |
| **Parsing Throughput** | Files / second, MB / sec | Wall-clock time for AST generation and symbol extraction | > 1,000 files/sec (multi-core) |
| **Graph Construction Rate** | Nodes / sec, Edges / sec | Rate of node/edge deduplication and in-memory indexing | > 100,000 entities/sec |
| **Database Write Rate** | Rows / sec | SQLite `executemany` batched transactions to disk | > 80,000 rows/sec |
| **End-to-End Scan Rate** | Files / second | Total elapsed time: discovery through database commit | > 500 files/sec (cold) |
| **Peak Memory (RSS)** | Megabytes (MB) | Max resident set size via OS / `memray` | < 500 MB bounded |
| **CPU Utilization** | % across cores | Core saturation efficiency across $N$ CPU cores | > 85% multi-core scaling |
| **Incremental Scan Time** | Seconds | Scan time when 0% to 1% of files are modified | < 2.0 seconds |

---

## 2. Benchmark Workloads & Datasets

To ensure consistency, benchmarks must be executed against standardized datasets:

1. **Synthetic Scale Corpus**:
   - `micro-1k`: 1,000 files, 50 packages (rapid regression).
   - `mid-20k`: 20,000 files, 500 packages (standard feature PR gate).
   - `macro-200k`: 200,000 files, 2,000 packages (system limit test).
2. **Real-World Reference Repositories**:
   - **Python**: CPython repository (`github.com/python/cpython`).
   - **Polyglot**: A mixed Python/C++ codebase (e.g. PyTorch or TensorFlow subsets).
3. **Reproducible Generation**:
   - Use deterministic PRNG seeds when generating synthetic repository topologies.

---

## 3. Experimental Protocol & Controls

To eliminate measurement noise:

### 1. Cold vs Warm Cache Isolation
- **Cold Cache**:
  - Clear OS filesystem buffers prior to test (on Linux: `echo 3 > /proc/sys/vm/drop_caches`; on Windows: restart process / drop standby list).
  - Simulates the user's initial repository scan.
- **Warm Cache**:
  - Run one unmeasured discovery pass to ensure filesystem metadata is cached in OS kernel memory.
  - Measures purely compute and internal I/O pipeline throughput.

### 2. Multi-Run Statistical Rigor
- Never report a single run.
- Execute a minimum of **1 warmup run** followed by **5 measured runs**.
- Report:
  - **Mean**
  - **Median**
  - **Min / Max**
  - **Standard Deviation ($\sigma$)**

### 3. Hardware & Environment Metadata
Every benchmark log must capture:
```yaml
environment:
  os: "Windows 11 / Ubuntu 22.04"
  cpu: "AMD Ryzen 9 5950X (16 cores, 32 threads)"
  ram: "64 GB DDR4"
  storage: "Samsung 980 Pro NVMe SSD (PCIe 4.0)"
  python_version: "3.12.2"
```

---

## 4. Benchmark Harness Implementation

A dedicated benchmark script (`tools/benchmark.py`) automates measurement:

```python
import time
import os
import psutil
from dataclasses import dataclass
from pathlib import Path

@dataclass
class BenchmarkResult:
    dataset_name: str
    total_files: int
    elapsed_seconds: float
    files_per_second: float
    peak_rss_mb: float
    cpu_percent_avg: float

def run_benchmark(dataset_path: Path, dataset_name: str) -> BenchmarkResult:
    process = psutil.Process(os.getpid())
    start_rss = process.memory_info().rss / (1024 * 1024)
    
    start_time = time.perf_counter()
    # Execute scan pipeline
    total_files = execute_scan(dataset_path)
    elapsed = time.perf_counter() - start_time

    peak_rss = (process.memory_info().rss / (1024 * 1024)) - start_rss
    throughput = total_files / elapsed if elapsed > 0 else 0.0

    return BenchmarkResult(
        dataset_name=dataset_name,
        total_files=total_files,
        elapsed_seconds=elapsed,
        files_per_second=throughput,
        peak_rss_mb=peak_rss,
        cpu_percent_avg=psutil.cpu_percent(interval=None),
    )
```

---

## 5. Incremental Scan Benchmarking

Incremental scans must be evaluated across distinct delta conditions:

1. **Null Delta (0% changed)**:
   - Re-run scan immediately on untouched 200,000-file repository.
   - Measures pure `mtime`/size fast-check overhead (Target: < 2 seconds).
2. **Low Delta (0.1% changed / ~200 files)**:
   - Modify 200 leaf files.
   - Measures selective invalidation and partial graph re-commit.
3. **High Delta (10% changed / 20,000 files)**:
   - Modify 20,000 files.
   - Measures worker scheduling under partial load.

---

## 6. C++ Rewrite Evaluation Gate

If a Python component is suspected of being a performance bottleneck, follow this strict evaluation protocol before considering any C++ rewrite:

```text
Identified Bottleneck
         │
         ▼
[ Step 1: Profiling ] ────> Collect flamegraph (py-spy / memray).
         │                  Does this function consume > 50% of total run time?
         │                  NO  ──> Do not rewrite. Bottleneck is elsewhere.
         ▼ YES
[ Step 2: Algorithmic Optimization ] ──> Can complexity be reduced?
         │                               (e.g., O(N^2) to O(N log N), hash sets, slots)
         │                               Benchmark again. If resolved, STOP.
         ▼
[ Step 3: Concurrency / Batching ] ───> Can workload be chunked across ProcessPool?
         │                               Benchmark again. If resolved, STOP.
         ▼
[ Step 4: Formal Rewrite Gate ]
         - Prototype C++ implementation behind the exact same Protocol interface.
         - Benchmark Python vs C++ side-by-side using identical datasets and hardware.
         - C++ implementation must demonstrate at least a 3x speedup on that component
           to justify the build complexity, cross-compilation, and FFI boundary costs.
```

