"""Alias entry point forwarding to code_input.py."""

from __future__ import annotations

import sys
from pathlib import Path

# Cleanly resolve and add project root to sys.path if run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from input.code_input import main

if __name__ == "__main__":
    main()
