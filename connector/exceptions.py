"""Exception hierarchy for the connector package.

Adheres to the GraphsError domain hierarchy defined in AGENTS.md.
"""

from __future__ import annotations

from tokenizer.exceptions import GraphsError


class ConnectorError(GraphsError):
    """Base exception for all errors originating from the Connector component."""


class RepositoryNotFoundError(ConnectorError, FileNotFoundError):
    """Raised when the specified repository root path does not exist."""


class NotADirectoryRepositoryError(ConnectorError, NotADirectoryError):
    """Raised when the specified repository path exists but is not a directory."""


class ScannerExecutionError(ConnectorError, RuntimeError):
    """Raised when the underlying scanner process fails to execute or returns an error."""
