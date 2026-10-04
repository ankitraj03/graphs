"""Scanner adapter for invoking and consuming file discovery results.

Calls the native C++ scanner executable (scanner.exe) if available, or uses a
zero-dependency fallback implementation adhering to identical pruning and extension rules.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Sequence

from connector.exceptions import (
    NotADirectoryRepositoryError,
    RepositoryNotFoundError,
    ScannerExecutionError,
)

logger = logging.getLogger(__name__)


# Default locations for scanner.exe
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCANNER_BIN = PROJECT_ROOT / "scanner" / "scanner.exe"

# Hardcoded rules matching scanner/file_scanner.cpp
IGNORED_DIRECTORIES: frozenset[str] = frozenset({
    ".git",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    "bin",
    "obj",
    "__pycache__",
})

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".py",
    ".pyi",
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".hxx",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
})


class ScannerAdapter:
    """Invokes the scanner component to retrieve all relevant repository files."""

    def __init__(self, scanner_bin: Path | str | None = None) -> None:
        if scanner_bin:
            self.scanner_bin = Path(scanner_bin).resolve()
        elif DEFAULT_SCANNER_BIN.is_file():
            self.scanner_bin = DEFAULT_SCANNER_BIN
        else:
            self.scanner_bin = None

    def scan(self, repo_path: Path | str) -> list[Path]:
        """Scan a repository path and return a sorted list of discovered source file Paths.

        Raises:
            FileNotFoundError: If repo_path does not exist.
            NotADirectoryError: If repo_path is not a directory.
            RuntimeError: If scanner fails to execute.
        """
        path = Path(repo_path).resolve()

        if not path.exists():
            raise RepositoryNotFoundError(f"Repository path does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryRepositoryError(f"Repository path is not a directory: {path}")

        # Prefer native scanner executable if present
        if self.scanner_bin and self.scanner_bin.is_file():
            try:
                return self._scan_with_executable(path)
            except Exception as err:
                logger.warning(
                    "Native scanner failed (%s). Falling back to direct filesystem traversal.",
                    err,
                )
                return self._scan_fallback(path)

        return self._scan_fallback(path)

    def _scan_with_executable(self, repo_path: Path) -> list[Path]:
        """Run scanner.exe and parse stdout paths."""
        cmd = [str(self.scanner_bin), str(repo_path)]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if proc.returncode != 0 and not proc.stdout:
            raise ScannerExecutionError(
                f"Scanner binary exited with code {proc.returncode}: {proc.stderr.strip()}"
            )


        files: list[Path] = []
        in_file_section = False

        for raw_line in proc.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if "Found files:" in line:
                in_file_section = True
                continue

            if "Total files:" in line:
                break

            if in_file_section:
                file_path = Path(line).resolve()
                if file_path.is_file():
                    files.append(file_path)

        files.sort()
        return files

    def _scan_fallback(self, repo_path: Path) -> list[Path]:
        """Fallback traversal matching scanner/file_scanner.cpp logic identically."""
        discovered: list[Path] = []

        def _traverse(current_dir: Path) -> None:
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name.lower() not in IGNORED_DIRECTORIES:
                                    _traverse(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                ext = Path(entry.name).suffix.lower()
                                if ext in SUPPORTED_EXTENSIONS:
                                    discovered.append(Path(entry.path).resolve())
                        except (PermissionError, FileNotFoundError, OSError):
                            continue
            except (PermissionError, FileNotFoundError, OSError):
                return

        _traverse(repo_path)
        discovered.sort()
        return discovered
