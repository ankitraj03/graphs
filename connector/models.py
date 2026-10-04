"""Data models for file relationships and resolved references.

Adheres to AGENTS.md standards:
- @dataclass(frozen=True, slots=True) for minimal memory overhead
- Strict typing throughout
- Clean dictionary serialization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ResolvedReference:
    """Represents a single reference resolved against the repository file list."""

    raw_target: str
    resolved_path: Path | None
    is_resolved: bool
    confidence: str  # "DIRECT", "INFERRED", "UNRESOLVED"
    keyword: str
    kind: str

    def to_dict(self, repo_root: Path | None = None) -> dict[str, Any]:
        """Serialize resolved reference to dictionary."""
        resolved_str: str | None = None
        if self.resolved_path:
            if repo_root and self.resolved_path.is_relative_to(repo_root):
                resolved_str = self.resolved_path.relative_to(repo_root).as_posix()
            else:
                resolved_str = self.resolved_path.as_posix()

        return {
            "raw_target": self.raw_target,
            "resolved_path": resolved_str,
            "is_resolved": self.is_resolved,
            "confidence": self.confidence,
            "keyword": self.keyword,
            "kind": self.kind,
        }


@dataclass(frozen=True, slots=True)
class FileRelationship:
    """Represents all outgoing connections and references from a single source file."""

    source_file: Path
    connected_files: tuple[Path, ...]
    unresolved_references: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self, repo_root: Path | None = None) -> dict[str, Any]:
        """Serialize file relationship to dictionary."""
        def format_path(p: Path) -> str:
            if repo_root and p.is_relative_to(repo_root):
                return p.relative_to(repo_root).as_posix()
            return p.as_posix()

        return {
            "source_file": format_path(self.source_file),
            "connected_files": [format_path(f) for f in self.connected_files],
            "unresolved_references": list(self.unresolved_references),
        }


@dataclass(frozen=True, slots=True)
class RelationshipMap:
    """Complete repository-wide file-to-file relationship graph."""

    repo_root: Path
    total_files_scanned: int
    relationships: dict[Path, FileRelationship]

    def to_dict(self, relative_to_root: bool = True) -> dict[str, list[str]]:
        """Return a clean map of source_file -> [connected_file, ...]."""
        result: dict[str, list[str]] = {}
        for src, rel in self.relationships.items():
            src_key = (
                src.relative_to(self.repo_root).as_posix()
                if relative_to_root and src.is_relative_to(self.repo_root)
                else src.as_posix()
            )
            targets = [
                (
                    tgt.relative_to(self.repo_root).as_posix()
                    if relative_to_root and tgt.is_relative_to(self.repo_root)
                    else tgt.as_posix()
                )
                for tgt in rel.connected_files
            ]
            result[src_key] = targets
        return result

    def format_text(self, show_unresolved: bool = False) -> str:
        """Produce human-readable terminal output matching Graph Builder Phase 3 specification."""
        lines: list[str] = [
            "========================================",
            "FILE RELATIONSHIPS",
            "========================================",
            "",
        ]

        if not self.relationships:
            lines.append("No files found in repository.")
            return "\n".join(lines)

        for src, rel in self.relationships.items():
            src_name = (
                src.relative_to(self.repo_root).as_posix()
                if src.is_relative_to(self.repo_root)
                else src.name
            )
            lines.append(src_name)

            if not rel.connected_files and not (show_unresolved and rel.unresolved_references):
                lines.append("  -> No linked files")
            else:
                for tgt in rel.connected_files:
                    tgt_name = (
                        tgt.relative_to(self.repo_root).as_posix()
                        if tgt.is_relative_to(self.repo_root)
                        else tgt.name
                    )
                    lines.append(f"  -> {tgt_name}")

                if show_unresolved:
                    for unres in rel.unresolved_references:
                        lines.append(f"  -> {unres} [UNRESOLVED]")

            lines.append("")

        return "\n".join(lines).rstrip()
