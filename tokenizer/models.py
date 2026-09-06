"""Data models for tokens, source locations, and dependency relationships.

Follows the AGENTS.md requirements:
- @dataclass(frozen=True, slots=True) for minimal memory overhead
- sys.intern() on frequent repeated strings
- Full source location attribution and evidence snippet retention
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Represents a precise location within a source code file."""

    file_path: Path
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize source location to a dictionary."""
        return {
            "file_path": str(self.file_path),
            "start_line": self.start_line,
            "start_column": self.start_column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }


@dataclass(frozen=True, slots=True)
class Token:
    """Represents an individual lexical token extracted by the lexer."""

    kind: str
    value: str
    location: SourceLocation

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", sys.intern(self.kind))

    def to_dict(self) -> dict[str, Any]:
        """Serialize token to a dictionary."""
        return {
            "kind": self.kind,
            "value": self.value,
            "location": self.location.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class DependencyToken:
    """Represents a dependency relationship linking this file to another module or file.

    Contains the connecting keyword (e.g. 'import', 'from', '#include', 'require'),
    the dependency target identifier, any specific imported symbols, the exact location,
    and the evidence snippet.
    """

    keyword: str
    target: str
    kind: str
    location: SourceLocation
    snippet: str
    symbols: tuple[str, ...] = field(default_factory=tuple)
    is_relative: bool = False
    level: int = 0
    resolved_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "keyword", sys.intern(self.keyword))
        object.__setattr__(self, "kind", sys.intern(self.kind))

    def to_dict(self) -> dict[str, Any]:
        """Serialize dependency token to a dictionary."""
        return {
            "keyword": self.keyword,
            "target": self.target,
            "kind": self.kind,
            "symbols": list(self.symbols),
            "is_relative": self.is_relative,
            "level": self.level,
            "snippet": self.snippet,
            "resolved_path": str(self.resolved_path) if self.resolved_path else None,
            "location": self.location.to_dict(),
        }
