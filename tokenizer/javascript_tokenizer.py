"""JavaScript and TypeScript lexer and dependency tokenizer.

Extracts ES6 import/export statements, CommonJS require() calls, and dynamic import() calls.
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

# ES6 Import: import ... from 'target' or import 'target'
IMPORT_FROM_PATTERN = re.compile(
    r"""(?:import\s+(?:(?:[\w*\s{},$]+)\s+from\s+)?|import\s+)['"](?P<target>[^'"]+)['"]"""
)

# CommonJS require: require('target')
REQUIRE_PATTERN = re.compile(
    r"""\brequire\s*\(\s*['"](?P<target>[^'"]+)['"]\s*\)"""
)

# ES6 Export from: export ... from 'target'
EXPORT_FROM_PATTERN = re.compile(
    r"""\bexport\s+(?:(?:[\w*\s{},$]+)\s+from\s+)['"](?P<target>[^'"]+)['"]"""
)

# Dynamic import: import('target')
DYNAMIC_IMPORT_PATTERN = re.compile(
    r"""\bimport\s*\(\s*['"](?P<target>[^'"]+)['"]\s*\)"""
)


class JavaScriptTokenizer(BaseTokenizer):
    """Lexer-tokenizer for JavaScript and TypeScript files (.js, .jsx, .ts, .tsx, .mjs, .cjs)."""

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else None

    def tokenize(self, file_path: Path | str) -> list[DependencyToken]:
        """Scan a JS/TS file and return an array of dependency tokens."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundTokenizerError(f"File not found: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
        except Exception as err:
            raise LexerScanError(f"Could not read JS/TS file '{path}': {err}") from err

        return self.tokenize_source(source, file_path=path)

    def tokenize_source(
        self, source: str, file_path: Path | str | None = None
    ) -> list[DependencyToken]:
        """Tokenize JS/TS source code string and return an array of dependency tokens."""
        resolved_path = Path(file_path).resolve() if file_path else Path("unknown.js")
        dependencies: list[DependencyToken] = []
        source_lines = source.splitlines(keepends=True)

        for line_num, line in enumerate(source_lines, start=1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue

            # 1. ES6 import
            for match in IMPORT_FROM_PATTERN.finditer(line):
                target = match.group("target")
                is_rel = target.startswith(".")
                dependencies.append(
                    DependencyToken(
                        keyword="import",
                        target=target,
                        kind="ES_IMPORT",
                        location=SourceLocation(
                            file_path=resolved_path,
                            start_line=line_num,
                            start_column=match.start(),
                            end_line=line_num,
                            end_column=match.end(),
                        ),
                        snippet=line.strip(),
                        is_relative=is_rel,
                        resolved_path=self._resolve_js_path(target, resolved_path) if is_rel else None,
                    )
                )

            # 2. CommonJS require()
            for match in REQUIRE_PATTERN.finditer(line):
                target = match.group("target")
                is_rel = target.startswith(".")
                dependencies.append(
                    DependencyToken(
                        keyword="require",
                        target=target,
                        kind="CJS_REQUIRE",
                        location=SourceLocation(
                            file_path=resolved_path,
                            start_line=line_num,
                            start_column=match.start(),
                            end_line=line_num,
                            end_column=match.end(),
                        ),
                        snippet=line.strip(),
                        is_relative=is_rel,
                        resolved_path=self._resolve_js_path(target, resolved_path) if is_rel else None,
                    )
                )

            # 3. Export ... from
            for match in EXPORT_FROM_PATTERN.finditer(line):
                target = match.group("target")
                is_rel = target.startswith(".")
                dependencies.append(
                    DependencyToken(
                        keyword="export",
                        target=target,
                        kind="ES_EXPORT_FROM",
                        location=SourceLocation(
                            file_path=resolved_path,
                            start_line=line_num,
                            start_column=match.start(),
                            end_line=line_num,
                            end_column=match.end(),
                        ),
                        snippet=line.strip(),
                        is_relative=is_rel,
                        resolved_path=self._resolve_js_path(target, resolved_path) if is_rel else None,
                    )
                )

            # 4. Dynamic import()
            for match in DYNAMIC_IMPORT_PATTERN.finditer(line):
                # Don't duplicate if already matched by general import
                target = match.group("target")
                is_rel = target.startswith(".")
                dependencies.append(
                    DependencyToken(
                        keyword="import()",
                        target=target,
                        kind="DYNAMIC_IMPORT",
                        location=SourceLocation(
                            file_path=resolved_path,
                            start_line=line_num,
                            start_column=match.start(),
                            end_line=line_num,
                            end_column=match.end(),
                        ),
                        snippet=line.strip(),
                        is_relative=is_rel,
                        resolved_path=self._resolve_js_path(target, resolved_path) if is_rel else None,
                    )
                )

        return dependencies

    def get_all_tokens(self, file_path: Path | str) -> list[Token]:
        """Return array of lexical tokens from JS/TS file."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundTokenizerError(f"File not found: {path}")

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()

        tokens: list[Token] = []
        token_regex = re.compile(r'[a-zA-Z_$][a-zA-Z0-9_$]*|`[^`]*`|"[^"]*"|\'[^\']*\'|//[^\n]*|/\*.*?\*/|[^\s\w]', re.DOTALL)

        for line_num, line in enumerate(source.splitlines(), start=1):
            for m in token_regex.finditer(line):
                val = m.group(0)
                if val.startswith("//") or val.startswith("/*"):
                    kind = "COMMENT"
                elif val.startswith('"') or val.startswith("'") or val.startswith("`"):
                    kind = "STRING"
                elif val in ("import", "from", "export", "require", "const", "let", "var", "function", "class", "default", "as"):
                    kind = "KEYWORD"
                elif val[0].isalpha() or val[0] in ("_", "$"):
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

    def _resolve_js_path(self, target: str, current_file: Path) -> Path | None:
        """Resolve a relative JS/TS path with common extensions (.js, .ts, /index.js)."""
        base_dir = current_file.parent
        target_path = (base_dir / target).resolve()

        if target_path.is_file():
            return target_path

        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            candidate = target_path.with_suffix(ext)
            if candidate.is_file():
                return candidate

        for index_file in ("index.ts", "index.tsx", "index.js", "index.jsx"):
            candidate = target_path / index_file
            if candidate.is_file():
                return candidate

        return target_path
