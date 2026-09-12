"""Direct source code input entry point for the tokenizer.

Prompts the user to paste or enter complete source code (and optional language hint),
tokenizes the code directly via FileTokenizer.tokenize_source(), and displays
the extracted dependencies in a clean, readable format.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Cleanly resolve and add project root to sys.path if run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tokenizer import (
    FileTokenizer,
    UnsupportedLanguageError,
)


def main() -> None:
    """Prompt user for language and code content, then extract and display dependencies."""
    # 1. Ask for language (optional, defaults to python)
    raw_lang = input("Enter language [python/cpp/javascript] (default: python): ").strip()
    language = raw_lang.lower() if raw_lang else "python"

    # Normalize common aliases
    if language in ("py", "python3"):
        language = "python"
    elif language in ("c", "c++", "cxx"):
        language = "cpp"
    elif language in ("js", "ts", "typescript"):
        language = "javascript"

    # 2. Read whole source code
    print("Enter/paste your code below. Type 'END' on an empty line or press Ctrl+Z (Windows) / Ctrl+D (Unix) to finish:")
    lines: list[str] = []
    while True:
        try:
            line = sys.stdin.readline()
            if not line:  # EOF
                break
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    code = "".join(lines)
    if not code.strip():
        print("\nError: No code provided.")
        return

    tokenizer = FileTokenizer(project_root=PROJECT_ROOT)

    try:
        dep_tokens = tokenizer.tokenize_source(code, language=language)
    except UnsupportedLanguageError:
        print(f"\nError: Unsupported language '{language}'. Supported: python, cpp, javascript")
        return
    except Exception as err:
        print(f"\nError: Could not process source code: {err}")
        return

    # Extract unique targets preserving order
    seen: set[str] = set()
    dependencies: list[str] = []
    for tok in dep_tokens:
        if tok.target not in seen:
            seen.add(tok.target)
            dependencies.append(tok.target)

    print("\nDependencies:")
    if dependencies:
        for dep in dependencies:
            print(f"- {dep}")
    else:
        print("- No dependencies found.")


if __name__ == "__main__":
    main()
