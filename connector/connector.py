"""Core orchestration component linking Scanner and Tokenizer.

Implements the Graph Builder Phase 3 Connector pipeline:
1. Receives repository path
2. Validates path
3. Calls Scanner to get the repository file list
4. Passes each relevant file to Tokenizer
5. Receives tokenized references
6. Resolves references against the repository file index
7. Builds the file-to-file relationship map
8. Produces deterministic, structured output
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from connector.exceptions import NotADirectoryRepositoryError, RepositoryNotFoundError
from connector.models import FileRelationship, RelationshipMap, ResolvedReference
from connector.resolver import ReferenceResolver
from connector.scanner_adapter import ScannerAdapter
from tokenizer import FileTokenizer, TokenizerError

logger = logging.getLogger(__name__)



class Connector:
    """Orchestrates file discovery, tokenization, and cross-file relationship resolution."""

    def __init__(
        self,
        scanner_bin: Path | str | None = None,
        tokenizer: FileTokenizer | None = None,
    ) -> None:
        self.scanner_adapter = ScannerAdapter(scanner_bin=scanner_bin)
        self.tokenizer = tokenizer

    def connect(self, repo_path: Path | str) -> RelationshipMap:
        """Execute the full Connector pipeline against a target repository.

        Args:
            repo_path: Path to the repository root directory.

        Returns:
            RelationshipMap containing all resolved file-to-file connections.
        """
        # 1. Receive & validate repository path
        root = Path(repo_path).resolve()
        if not root.exists():
            raise RepositoryNotFoundError(f"Repository path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryRepositoryError(f"Repository path is not a directory: {root}")


        # 2. Call Scanner -> Receive repository file list
        files = self.scanner_adapter.scan(root)

        if not files:
            return RelationshipMap(
                repo_root=root,
                total_files_scanned=0,
                relationships={},
            )

        # 3. Initialize Resolver index
        resolver = ReferenceResolver(repo_root=root, repo_files=files)

        # 4. Initialize Tokenizer (scoped to the repository root for relative resolutions)
        active_tokenizer = self.tokenizer or FileTokenizer(project_root=root)

        relationships: dict[Path, FileRelationship] = {}

        # 5. Iterate through each scanned file
        for source_file in files:
            connected: list[Path] = []
            seen_connected: set[Path] = set()
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
                    # Deduplicate connected files (Section 12, Test 6)
                    if resolved.resolved_path not in seen_connected:
                        seen_connected.add(resolved.resolved_path)
                        connected.append(resolved.resolved_path)
                else:
                    if resolved.raw_target not in seen_unresolved:
                        seen_unresolved.add(resolved.raw_target)
                        unresolved.append(resolved.raw_target)

            # 8. Store file relationship
            relationships[source_file] = FileRelationship(
                source_file=source_file,
                connected_files=tuple(connected),
                unresolved_references=tuple(unresolved),
            )

        # 9. Return RelationshipMap
        return RelationshipMap(
            repo_root=root,
            total_files_scanned=len(files),
            relationships=relationships,
        )
