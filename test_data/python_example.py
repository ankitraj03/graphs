"""Sample Python module demonstrating imports and dependencies for tokenizer dry run."""

from __future__ import annotations

import os
import sys, math
import collections.abc as abc
from pathlib import Path
from .utils import helper_function
import importlib

dynamic_module = importlib.import_module("json")
legacy_mod = __import__("csv")


def process_data() -> None:
    """Sample dummy function."""
    print("Processing with", helper_function())
