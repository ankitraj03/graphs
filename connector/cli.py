"""Command-line interface for the Graph Builder Connector.

Provides formatted terminal output and JSON output matching Graph Builder Phase 3 specification.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from connector.connector import Connector


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for running Connector against a target repository."""
    parser = argparse.ArgumentParser(
        prog="connector",
        description="Graph Builder Phase 3: Orchestration and Relationship Connector",
    )
    parser.add_argument(
        "repository_path",
        nargs="?",
        default=None,
        help="Path to the repository to analyze.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output relationship map as JSON instead of plain text.",
    )
    parser.add_argument(
        "--unresolved",
        action="store_true",
        help="Display unresolved/external references in output.",
    )
    parser.add_argument(
        "--scanner-bin",
        default=None,
        help="Optional path to custom scanner executable.",
    )

    args = parser.parse_args(argv)

    path_str = args.repository_path
    if not path_str:
        try:
            path_str = input("Enter repository path: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            return 1

    if not path_str:
        print("Error: No repository path provided.", file=sys.stderr)
        return 1

    # Strip surrounding quotes if pasted
    path_str = path_str.strip("\"'")
    target_path = Path(path_str)

    connector = Connector(scanner_bin=args.scanner_bin)

    try:
        rel_map = connector.connect(target_path)
    except FileNotFoundError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except NotADirectoryError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Error executing Connector: {err}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(rel_map.to_dict(relative_to_root=True), indent=2))
    else:
        print(rel_map.format_text(show_unresolved=args.unresolved))

    return 0


if __name__ == "__main__":
    sys.exit(main())
