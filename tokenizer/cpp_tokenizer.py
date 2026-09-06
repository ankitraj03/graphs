"""C/C++ lexer and dependency tokenizer.

Extracts #include directives (<header> and "header.h") and C++20 module import statements.
Attributed with source locations, connecting keywords, and snippets.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from tokenizer.base import BaseTokenizer
from tokenizer.exceptions import FileNotFoundTokenizerError, LexerScanError
from tokenizer.models import DependencyToken, SourceLocation, Token

logger = logging.getLogger(__name__)

# Pattern for #include <...> or #include "..."
INCLUDE_PATTERN = re.compile(
    r'^\s*#\s*include\s+(?:<(?P<sys_header>[^>]+)>|"(?P<local_header>[^"]+)")',
    re.MULTILINE,
)

# Pattern for C++20 module imports: import <header>; or import module_name;
CPP20_IMPORT_PATTERN = re.compile(
    r'^\s*import\s+(?:<(?P<import_header>[^>]+)>|(?P<import_module>[a-zA-Z0-9_\.]+))\s*;',
    re.MULTILINE,
)


class CppTokenizer(BaseTokenizer):
    """Lexer-tokenizer for C and C++ source/header files (.c, .cpp, .cc, .cxx, .h, .hpp, .hxx)."""

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else None

    def tokenize(self, file_path: Path | str) -> list[DependencyToken]:
        """Scan a C/C++ file and return an array of dependency tokens."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundTokenizerError(f"File not found: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as err:
            raise LexerScanError(f"Could not read C/C++ file '{path}': {err}") from err

        return self.tokenize_source(source, file_path=path)

    def tokenize_source(
        self, source: str, file_path: Path | str | None = None
    ) -> list[DependencyToken]:
        """Tokenize C/C++ source code string and return an array of dependency tokens."""
        resolved_path = Path(file_path).resolve() if file_path else Path("unknown.cpp")
        dependencies: list[DependencyToken] = []
        source_lines = source.splitlines(keepends=True)

        for line_num, line in enumerate(source_lines, start=1):
            stripped = line.strip()
            # Skip full single-line comments
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # Match #include
            inc_match = INCLUDE_PATTERN.match(line)
            if inc_match:
                sys_header = inc_match.group("sys_header")
                local_header = inc_match.group("local_header")
                target = sys_header if sys_header is not None else (local_header or "")
                is_system = sys_header is not None

                # Resolve relative path for local headers
                resolved: Path | None = None
                if not is_system and resolved_path.parent:
                    candidate = resolved_path.parent / target
                    resolved = candidate if candidate.is_file() else candidate

                location = SourceLocation(
                    file_path=resolved_path,
                    start_line=line_num,
                    start_column=line.find("#"),
                    end_line=line_num,
                    end_column=len(line.rstrip("\r\n")),
                )

                dependencies.append(
                    DependencyToken(
                        keyword="#include",
                        target=target,
                        kind="INCLUDE_SYSTEM" if is_system else "INCLUDE_LOCAL",
                        location=location,
                        snippet=line.strip(),
                        is_relative=not is_system,
                        level=0,
                        resolved_path=resolved,
                    )
                )
                continue

            # Match C++20 import
            import_match = CPP20_IMPORT_PATTERN.match(line)
            if import_match:
                hdr = import_match.group("import_header")
                mod = import_match.group("import_module")
                target = hdr if hdr is not None else (mod or "")

                location = SourceLocation(
                    file_path=resolved_path,
                    start_line=line_num,
                    start_column=line.find("import"),
                    end_line=line_num,
                    end_column=len(line.rstrip("\r\n")),
                )

                dependencies.append(
                    DependencyToken(
                        keyword="import",
                        target=target,
                        kind="MODULE_IMPORT",
                        location=location,
                        snippet=line.strip(),
                        is_relative=False,
                        level=0,
                    )
                )

        return dependencies

    def get_all_tokens(self, file_path: Path | str) -> list[Token]:
        """Return basic tokens extracted from C/C++ file."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundTokenizerError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()

        tokens: list[Token] = []
        token_regex = re.compile(r'#\w+|[a-zA-Z_]\w*|<[^>]+>|"[^"]*"|//[^\n]*|/\*.*?\*/|[^\s\w]', re.DOTALL)

        for line_num, line in enumerate(source.splitlines(), start=1):
            for m in token_regex.finditer(line):
                val = m.group(0)
                if val.startswith("//") or val.startswith("/*"):
                    kind = "COMMENT"
                elif val.startswith("#"):
                    kind = "PREPROCESSOR"
                elif val.startswith('"') or (val.startswith("<") and val.endswith(">")):
                    kind = "HEADER_OR_STRING"
                elif val[0].isalpha() or val[0] == "_":
                    kind = "IDENTIFIER"
                else:
                    kind = "PUNCTUATION"

                tokens.append(
                    Token(
                        kind=kind,
                        value=val,
                        location=SourceLocation(
                            file_path=path,
                            start_line=line_num,
                            start_column=m.start(),
                            end_line=line_num,
                            end_column=m.end(),
                        ),
                    )
                )

        return tokens
