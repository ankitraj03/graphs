"""Exceptions for the Relationship Ranker component.

Strictly independent of previous pipeline phases.
Adheres to clean domain hierarchy rules.
"""

from __future__ import annotations


class RankerError(Exception):
    """Base exception for all errors originating from the Relationship Ranker."""


class NodeNotFoundError(RankerError, KeyError):
    """Raised when the specified target node does not exist in the graph."""


class InvalidGraphError(RankerError, ValueError):
    """Raised when an invalid operation is performed on the graph model."""


class ConfigurationError(RankerError, ValueError):
    """Raised when an invalid configuration value is supplied to the ranker."""
