"""Command-line interface for the Graph Builder integrated pipeline.

Orchestrates Scanner -> Tokenizer -> Connector -> Graph Designer,
rendering the final constructed graph model to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from connector.connector import Connector


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for running the complete Graph Builder pipeline."""
    parser = argparse.ArgumentParser(
        prog="connector",
        description="Graph Builder: Integrated Scanner, Tokenizer, Connector, and Graph Designer pipeline",
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
        help="Output constructed graph as JSON instead of formatted text.",
    )
    parser.add_argument(
        "--to-string",
        action="store_true",
        help="Output raw Graph Designer graph.toString() format.",
    )
    parser.add_argument(
        "--relationships",
        action="store_true",
        help="Output Phase 3 relationship map instead of Graph Designer graph.",
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
    parser.add_argument(
        "--graph-designer-bin",
        default=None,
        help="Optional path to custom graph designer executable.",
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

    connector = Connector(
        scanner_bin=args.scanner_bin,
        graph_designer_bin=args.graph_designer_bin,
    )

    fmt = "json" if args.json else ("to-string" if args.to_string else "text")

    try:
        rel_map = connector.connect(
            target_path,
            build_graph=True,
            graph_output_format=fmt,
        )
    except FileNotFoundError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except NotADirectoryError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"Error executing Graph Builder pipeline: {err}", file=sys.stderr)
        return 1

    if args.relationships:
        if args.json:
            print(json.dumps(rel_map.to_dict(relative_to_root=True), indent=2))
        else:
            print(rel_map.format_text(show_unresolved=args.unresolved))
    elif args.json:
        if rel_map.graph_result and rel_map.graph_result.json_data:
            print(json.dumps(rel_map.graph_result.json_data, indent=2))
        else:
            print(json.dumps(rel_map.to_dict(relative_to_root=True), indent=2))
    else:
        print(rel_map.render_graph(output_format=fmt))

    return 0


if __name__ == "__main__":
    sys.exit(main())
