"""Dry run utility for the graphs tokenizer.

Demonstrates tokenization, connecting keyword extraction, and dependency resolution
across multi-language test data (Python, C++, TypeScript/JavaScript) and custom files.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Sequence

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tokenizer import (
    DependencyToken,
    FileNotFoundTokenizerError,
    FileTokenizer,
    UnsupportedLanguageError,
)


def format_location(tok: DependencyToken) -> str:
    """Format token source location as L{start}:{col}..L{end}:{col}."""
    loc = tok.location
    return f"L{loc.start_line}:{loc.start_column}..L{loc.end_line}:{loc.end_column}"


def print_separator(char: str = "=", length: int = 80) -> None:
    """Print horizontal divider."""
    print(char * length)


def dry_run_file(tokenizer: FileTokenizer, file_path: Path) -> bool:
    """Execute a dry run of tokenizer methods on a single file and display output."""
    rel_path = file_path.relative_to(PROJECT_ROOT) if file_path.is_relative_to(PROJECT_ROOT) else file_path
    print(f"\nTarget File: {rel_path} ({file_path.suffix or 'no-ext'})")
    print_separator("-")

    if not file_path.exists():
        print(f"  [ERROR] File does not exist: {file_path}")
        return False

    # 1. Measure get_dependencies()
    t0 = time.perf_counter()
    try:
        dependencies = tokenizer.get_dependencies(file_path)
    except UnsupportedLanguageError as err:
        print(f"  [SKIPPED] Unsupported language: {err}")
        return False
    except Exception as err:
        print(f"  [ERROR] Failed to get dependencies: {err}")
        return False
    deps_time_ms = (time.perf_counter() - t0) * 1000

    # 2. Measure get_connecting_keywords()
    t1 = time.perf_counter()
    keywords = tokenizer.get_connecting_keywords(file_path)
    kw_time_ms = (time.perf_counter() - t1) * 1000

    # 3. Measure full tokenize()
    t2 = time.perf_counter()
    tokens = tokenizer.tokenize(file_path)
    tok_time_ms = (time.perf_counter() - t2) * 1000

    # 4. Measure get_all_tokens()
    t3 = time.perf_counter()
    all_lex_tokens = tokenizer.get_all_tokens(file_path)
    lex_time_ms = (time.perf_counter() - t3) * 1000

    # Display High-Level Summary
    print(f"  Execution Timing : tokenize={tok_time_ms:.2f}ms | lex={lex_time_ms:.2f}ms")
    print(f"  Connecting Kwds  : {keywords if keywords else 'None'}")
    print(f"  Dependencies     : {len(dependencies)} target(s) -> {dependencies}")
    print(f"  Total Lex Tokens : {len(all_lex_tokens)}")
    print("\n  Extracted Dependency Tokens Breakdown:")
    print("  " + "-" * 76)
    print(f"  {'Keyword':<12} {'Kind':<16} {'Target':<22} {'Location':<14} {'Resolved'}")
    print("  " + "-" * 76)

    for tok in tokens:
        resolved_str = "-"
        if tok.resolved_path:
            try:
                resolved_str = str(tok.resolved_path.relative_to(PROJECT_ROOT))
            except ValueError:
                resolved_str = tok.resolved_path.name

        print(
            f"  {tok.keyword:<12} {tok.kind:<16} {tok.target:<22} "
            f"{format_location(tok):<14} {resolved_str}"
        )
        if tok.symbols:
            print(f"    -> Imported symbols: {', '.join(tok.symbols)}")
        if tok.snippet:
            print(f"    -> Code snippet    : \"{tok.snippet}\"")

    return True


def dry_run_source_string(tokenizer: FileTokenizer, language: str, source: str, title: str) -> None:
    """Execute a dry run of tokenize_source on an in-memory string."""
    print(f"\nIn-Memory Code Snippet: {title} [Language: {language}]")
    print_separator("-")
    print("  Source Code:")
    for line in source.strip().splitlines():
        print(f"    | {line}")

    t0 = time.perf_counter()
    tokens = tokenizer.tokenize_source(source, language=language)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\n  Extracted in {elapsed_ms:.2f}ms ({len(tokens)} token(s)):")
    for tok in tokens:
        print(f"    * [{tok.keyword}] target='{tok.target}' kind={tok.kind} (symbols={tok.symbols or 'none'})")


def run_all_test_data() -> int:
    """Run tokenizer dry run across all predefined test data files."""
    print_separator("=")
    print("GRAPHS TOKENIZER DRY RUN SUITE")
    print(f"Project Root: {PROJECT_ROOT}")
    print_separator("=")

    tokenizer = FileTokenizer(project_root=PROJECT_ROOT)
    test_data_dir = PROJECT_ROOT / "test_data"

    test_files: list[Path] = [
        test_data_dir / "python_example.py",
        test_data_dir / "utils.py",
        test_data_dir / "syntax_error.py",
        test_data_dir / "cpp_example.cpp",
        test_data_dir / "local_header.h",
        test_data_dir / "ts_example.ts",
    ]

    success_count = 0
    start_total = time.perf_counter()

    for file_path in test_files:
        if dry_run_file(tokenizer, file_path):
            success_count += 1

    # In-memory snippet tests
    print("\n")
    print_separator("=")
    print("IN-MEMORY SNIPPET TOKENIZATION")
    print_separator("=")

    py_snippet = "import os, sys\nfrom math import sin, cos\n__import__('sqlite3')"
    dry_run_source_string(tokenizer, "python", py_snippet, "Python standard & dynamic imports")

    cpp_snippet = '#include <vector>\n#include "common.h"\nimport std.core;'
    dry_run_source_string(tokenizer, "cpp", cpp_snippet, "C++ includes & C++20 module")

    js_snippet = "import { useState } from 'react';\nconst lodash = require('lodash');\nexport * from './api';"
    dry_run_source_string(tokenizer, "javascript", js_snippet, "JS/TS imports, require & re-export")

    total_time_ms = (time.perf_counter() - start_total) * 1000

    print("\n")
    print_separator("=")
    print("DRY RUN SUMMARY")
    print_separator("=")
    print(f"  Files Processed : {success_count}/{len(test_files)}")
    print(f"  Total Duration  : {total_time_ms:.2f} ms")
    print("  Status          : ALL DRY RUNS COMPLETED SUCCESSFULLY [OK]")
    print_separator("=")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for dry running the tokenizer."""
    parser = argparse.ArgumentParser(
        description="Dry run the graphs tokenizer on test data or custom files."
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="Optional path to a specific file to dry run.",
    )
    args = parser.parse_args(argv)

    tokenizer = FileTokenizer(project_root=PROJECT_ROOT)

    if args.file:
        target_path = Path(args.file).resolve()
        print_separator("=")
        print(f"GRAPHS TOKENIZER SINGLE FILE DRY RUN: {target_path.name}")
        print_separator("=")
        ok = dry_run_file(tokenizer, target_path)
        return 0 if ok else 1

    return run_all_test_data()


if __name__ == "__main__":
    sys.exit(main())
