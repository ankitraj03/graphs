"""Top-level package for Graph Builder Phase 3: Connector."""

from __future__ import annotations

from connector.connector import Connector
from connector.exceptions import (
    ConnectorError,
    NotADirectoryRepositoryError,
    RepositoryNotFoundError,
    ScannerExecutionError,
)
from connector.models import FileRelationship, RelationshipMap, ResolvedReference
from connector.resolver import ReferenceResolver
from connector.scanner_adapter import ScannerAdapter

__all__ = [
    "Connector",
    "ConnectorError",
    "FileRelationship",
    "NotADirectoryRepositoryError",
    "RelationshipMap",
    "RepositoryNotFoundError",
    "ResolvedReference",
    "ReferenceResolver",
    "ScannerAdapter",
    "ScannerExecutionError",
]

