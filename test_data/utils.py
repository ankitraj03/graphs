"""Utility helper module for relative import resolution testing."""

from __future__ import annotations

import re
from typing import Final

DEFAULT_NAME: Final[str] = "graphs_test_module"


def helper_function() -> str:
    """Return a test string."""
    return f"helper from {DEFAULT_NAME}"
