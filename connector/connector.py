"""Core orchestration component linking Scanner, Tokenizer, and Graph Designer.

Implements the complete Graph Builder pipeline:
1. Receives repository path
2. Validates path
3. Calls Scanner to get the repository file list (ALL files)
4. Passes each relevant file to Tokenizer
5. Receives tokenized references
6. Resolves references against repository file index (internal only)
7. Maps granular kinds to Graph Designer RelationshipType enum
8. Preserves original tokenizer kinds in metadata
9. Sends complete nodes list + resolved relationships to Graph Designer
10. Graph Designer builds the in-memory graph (isolated + connected files)
11. Renders deterministic output
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from connector.exceptions import (
    GraphDesignerExecutionError,
    NotADirectoryRepositoryError,
    RepositoryNotFoundError,
)
from connector.graph_designer_adapter import GraphDesignerAdapter, GraphResult
from connector.models import (
    FileRelationship,
    RelationshipMap,
    ResolvedConnection,
    ResolvedReference,
    map_kind_to_relationship_type,
)
from connector.resolver import ReferenceResolver
from connector.scanner_adapter import ScannerAdapter
from tokenizer import FileTokenizer, TokenizerError

logger = logging.getLogger(__name__)


class Connector:
    """Orchestrates file discovery, tokenization, cross-file resolution, and Graph Designer assembly."""

    def __init__(
        self,
        scanner_bin: Path | str | None = None,
        tokenizer: FileTokenizer | None = None,
        graph_designer_bin: Path | str | None = None,
    ) -> None:
        self.scanner_adapter = ScannerAdapter(scanner_bin=scanner_bin)
        self.tokenizer = tokenizer
        self.graph_designer_adapter = GraphDesignerAdapter(bin_path=graph_designer_bin)

    def connect(
        self,
        repo_path: Path | str,
        build_graph: bool = True,
        graph_output_format: str = "text",
    ) -> RelationshipMap:
        """Execute the full Connector pipeline against a target repository.

        Args:
            repo_path: Path to the repository root directory.
            build_graph: Whether to send the resolved relationships to Graph Designer.
            graph_output_format: Output format for Graph Designer ('text', 'to-string', 'json').

        Returns:
            RelationshipMap containing all resolved file-to-file connections and GraphResult.
        """
        # 1. Receive & validate repository path
        root = Path(repo_path).resolve()
        if not root.exists():
            raise RepositoryNotFoundError(f"Repository path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryRepositoryError(f"Repository path is not a directory: {root}")

        # 2. Call Scanner -> Receive repository file list (ALL files discovered)
        files = self.scanner_adapter.scan(root)

        if not files:
            empty_map = RelationshipMap(
                repo_root=root,
                total_files_scanned=0,
                relationships={},
                all_files=(),
            )
            if build_graph and self.graph_designer_adapter.bin_path:
                try:
                    res = self.graph_designer_adapter.build_graph(
                        payload={"nodes": [], "relationships": []},
                        output_format=graph_output_format,
                    )
                    object.__setattr__(empty_map, "graph_result", res)
                except Exception as err:
                    logger.warning("Graph Designer execution on empty repository: %s", err)
            return empty_map

        # 3. Initialize Resolver index
        resolver = ReferenceResolver(repo_root=root, repo_files=files)

        # 4. Initialize Tokenizer (scoped to the repository root for relative resolutions)
        active_tokenizer = self.tokenizer or FileTokenizer(project_root=root)

        relationships: dict[Path, FileRelationship] = {}

        # 5. Iterate through each scanned file
        for source_file in files:
            connections: list[ResolvedConnection] = []
            seen_conn_keys: set[tuple[Path, str]] = set()
            connected_targets: list[Path] = []
            seen_targets: set[Path] = set()
            unresolved: list[str] = []
            seen_unresolved: set[str] = set()

            try:
                # 6. Send file to Tokenizer & receive dependency tokens
                dep_tokens = active_tokenizer.tokenize(source_file)
            except TokenizerError as err:
                logger.warning("Tokenizer error on %s: %s", source_file, err)
                dep_tokens = []
            except Exception as err:
                logger.warning("Failed to tokenize %s: %s", source_file, err)
                dep_tokens = []

            # 7. Resolve references against repository file index
            for tok in dep_tokens:
                resolved: ResolvedReference = resolver.resolve(source_file, tok)

                if resolved.is_resolved and resolved.resolved_path:
                    # Disallow self-edges
                    if resolved.resolved_path == source_file.resolve():
                        continue

                    # Map granular tokenizer kind -> Graph Designer RelationshipType
                    rel_type = map_kind_to_relationship_type(resolved.kind)
                    metadata: dict[str, str] = {"kind": resolved.kind}
                    if resolved.keyword:
                        metadata["keyword"] = resolved.keyword

                    # Preserve distinct relationship types between same pair of files (A -> B INCLUDE, A -> B IMPORT)
                    conn_key = (resolved.resolved_path, rel_type)
                    if conn_key not in seen_conn_keys:
                        seen_conn_keys.add(conn_key)
                        connections.append(
                            ResolvedConnection(
                                source_file=source_file,
                                target_file=resolved.resolved_path,
                                relationship_type=rel_type,
                                metadata=metadata,
                            )
                        )

                    if resolved.resolved_path not in seen_targets:
                        seen_targets.add(resolved.resolved_path)
                        connected_targets.append(resolved.resolved_path)
                else:
                    # Unresolved reference: keep in metadata, DO NOT create graph node or edge
                    if resolved.raw_target not in seen_unresolved:
                        seen_unresolved.add(resolved.raw_target)
                        unresolved.append(resolved.raw_target)

            # 8. Store file relationship (even for files with 0 outgoing connections)
            relationships[source_file] = FileRelationship(
                source_file=source_file,
                connected_files=tuple(connected_targets),
                unresolved_references=tuple(unresolved),
                connections=tuple(connections),
            )

        # 9. Create complete RelationshipMap with all scanned files
        rel_map = RelationshipMap(
            repo_root=root,
            total_files_scanned=len(files),
            relationships=relationships,
            all_files=tuple(files),
        )

        # 10. Feed Connector Output Into Graph Designer
        if build_graph and self.graph_designer_adapter.bin_path:
            try:
                payload = rel_map.to_graph_designer_payload()
                graph_result = self.graph_designer_adapter.build_graph(
                    payload=payload,
                    output_format=graph_output_format,
                )
                object.__setattr__(rel_map, "graph_result", graph_result)
            except Exception as err:
                logger.warning("Graph Designer execution error: %s", err)

        return rel_map
