"""Single-file test entry point for the tokenizer.

Prompts the user for a single source-code file path, analyzes its dependencies
using FileTokenizer, and prints the results in a clean, readable format.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Cleanly resolve and add project root to sys.path if run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tokenizer import (
    FileNotFoundTokenizerError,
    FileTokenizer,
    UnsupportedLanguageError,
)


def main() -> None:
    """Prompt user for a file path and display its extracted dependencies."""
    raw_path = input("Enter file path: ").strip()
    if not raw_path:
        print("\nError: No file path provided.")
        return

    # Strip surrounding quotes commonly added when copying paths
    clean_path = raw_path.strip("\"'")

    tokenizer = FileTokenizer(project_root=PROJECT_ROOT)

    try:
        dependencies = tokenizer.get_dependencies(clean_path)
    except FileNotFoundTokenizerError:
        print(f"\nError: File not found: {clean_path}")
        return
    except UnsupportedLanguageError:
        print("\nError: Unsupported file type.")
        return
    except Exception as err:
        print(f"\nError: Could not process file: {err}")
        return

    print("\nDependencies:")
    if dependencies:
        for dep in dependencies:
            print(f"- {dep}")
    else:
        print("- No dependencies found.")


if __name__ == "__main__":
    main()
