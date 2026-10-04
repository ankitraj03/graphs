"""Top-level package for Graph Builder Phase 3 & 4: Connector and Graph Designer."""

from __future__ import annotations

from connector.connector import Connector
from connector.exceptions import (
    ConnectorError,
    GraphDesignerExecutionError,
    NotADirectoryRepositoryError,
    RepositoryNotFoundError,
    ScannerExecutionError,
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

__all__ = [
    "Connector",
    "ConnectorError",
    "FileRelationship",
    "GraphDesignerAdapter",
    "GraphDesignerExecutionError",
    "GraphResult",
    "NotADirectoryRepositoryError",
    "ReferenceResolver",
    "RelationshipMap",
    "RepositoryNotFoundError",
    "ResolvedConnection",
    "ResolvedReference",
    "ScannerAdapter",
    "ScannerExecutionError",
    "map_kind_to_relationship_type",
]
