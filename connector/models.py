"""Data models for file relationships, resolved references, and graph integration.

Adheres to AGENTS.md standards:
- @dataclass(frozen=True, slots=True) for minimal memory overhead
- Strict typing throughout
- Clean dictionary serialization
- Multi-type connection preservation (source, target, relationship_type, metadata)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from connector.graph_designer_adapter import GraphResult

# Mapping from granular Tokenizer kinds to Graph Designer RelationshipType enum strings
KIND_TO_RELATIONSHIP_TYPE: dict[str, str] = {
    "INCLUDE_LOCAL": "INCLUDE",
    "INCLUDE_SYSTEM": "INCLUDE",
    "IMPORT": "IMPORT",
    "IMPORT_FROM": "IMPORT",
    "MODULE_IMPORT": "IMPORT",
    "ES_IMPORT": "IMPORT",
    "CJS_REQUIRE": "IMPORT",
    "ES_EXPORT_FROM": "IMPORT",
    "DYNAMIC_IMPORT": "IMPORT",
}


def map_kind_to_relationship_type(kind: str) -> str:
    """Map a granular Tokenizer kind string to a Graph Designer RelationshipType string.

    Rules:
    - INCLUDE_LOCAL, INCLUDE_SYSTEM -> INCLUDE
    - IMPORT, IMPORT_FROM, MODULE_IMPORT, ES_IMPORT, CJS_REQUIRE, ES_EXPORT_FROM, DYNAMIC_IMPORT -> IMPORT
    - All other kinds -> REFERENCE
    """
    return KIND_TO_RELATIONSHIP_TYPE.get(kind, "REFERENCE")


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
class ResolvedConnection:
    """Represents a typed, directed connection between two files with metadata."""

    source_file: Path
    target_file: Path
    relationship_type: str  # "INCLUDE", "IMPORT", "REFERENCE"
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self, repo_root: Path | None = None) -> dict[str, Any]:
        """Serialize resolved connection to dictionary."""
        def format_path(p: Path) -> str:
            if repo_root and p.is_relative_to(repo_root):
                return p.relative_to(repo_root).as_posix()
            return p.as_posix()

        return {
            "source_file": format_path(self.source_file),
            "target_file": format_path(self.target_file),
            "relationship_type": self.relationship_type,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class FileRelationship:
    """Represents all outgoing connections and references from a single source file.

    Preserves relationship tuples as (source_file, target_file, relationship_type, metadata)
    supporting multiple distinct relationship types between the same pair of files.
    """

    source_file: Path
    connected_files: tuple[Path, ...] = field(default_factory=tuple)
    unresolved_references: tuple[str, ...] = field(default_factory=tuple)
    connections: tuple[ResolvedConnection, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.connections and not self.connected_files:
            seen: set[Path] = set()
            targets: list[Path] = []
            for conn in self.connections:
                if conn.target_file not in seen:
                    seen.add(conn.target_file)
                    targets.append(conn.target_file)
            object.__setattr__(self, "connected_files", tuple(targets))

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
            "connections": [c.to_dict(repo_root) for c in self.connections],
        }


@dataclass(frozen=True, slots=True)
class RelationshipMap:
    """Complete repository-wide file-to-file relationship graph and metadata."""

    repo_root: Path
    total_files_scanned: int
    relationships: dict[Path, FileRelationship]
    all_files: tuple[Path, ...] = field(default_factory=tuple)
    graph_result: Any | None = field(default=None)

    def to_dict(self, relative_to_root: bool = True) -> dict[str, list[str]]:
        """Return a clean map of source_file -> [connected_file, ...] for backward compatibility."""
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

    def to_graph_designer_payload(self) -> dict[str, Any]:
        """Produce the exact JSON payload consumed by Graph Designer executable.

        CRITICAL: All scanned repository files are included as nodes, guaranteeing that
        files with zero connections exist as independent nodes in the graph.
        """
        # 1. Complete list of scanned files as repository-relative paths
        file_list = self.all_files if self.all_files else tuple(self.relationships.keys())
        nodes: list[str] = []
        for p in file_list:
            rel = (
                p.relative_to(self.repo_root).as_posix()
                if p.is_relative_to(self.repo_root)
                else p.as_posix()
            )
            nodes.append(rel)

        # 2. Resolved connections as (source, target, type, metadata)
        relationships: list[dict[str, Any]] = []
        for rel in self.relationships.values():
            src_rel = (
                rel.source_file.relative_to(self.repo_root).as_posix()
                if rel.source_file.is_relative_to(self.repo_root)
                else rel.source_file.as_posix()
            )
            for conn in rel.connections:
                tgt_rel = (
                    conn.target_file.relative_to(self.repo_root).as_posix()
                    if conn.target_file.is_relative_to(self.repo_root)
                    else conn.target_file.as_posix()
                )
                relationships.append({
                    "source": src_rel,
                    "target": tgt_rel,
                    "type": conn.relationship_type,
                    "metadata": dict(conn.metadata),
                })

        return {
            "nodes": nodes,
            "relationships": relationships,
        }

    def render_graph(self, output_format: str = "text") -> str:
        """Return the Graph Designer rendered output if available, or fallback to format_text()."""
        if self.graph_result and hasattr(self.graph_result, "rendered_text"):
            return self.graph_result.rendered_text  # type: ignore[no-any-return]
        return self.format_text()

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
