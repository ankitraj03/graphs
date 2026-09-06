"""Python-specific lexer and dependency tokenizer.

Combines lexical tokenization with AST validation to identify connecting keywords,
imported modules, relative imports, dynamic imports, and exact source locations.
Includes a fallback token-level scanner for resilience when files contain syntax errors.
"""

from __future__ import annotations

import ast
import io
import logging
import re
import tokenize
from pathlib import Path

from tokenizer.base import BaseTokenizer
from tokenizer.exceptions import FileNotFoundTokenizerError, LexerScanError
from tokenizer.models import DependencyToken, SourceLocation, Token

logger = logging.getLogger(__name__)

# Fallback regex patterns for malformed or unparseable source files
FALLBACK_IMPORT_REGEX = re.compile(
    r"^\s*import\s+(?P<modules>[a-zA-Z0-9_\.,\s]+?)(?:\s+as\s+[a-zA-Z0-9_]+)?\s*$",
    re.MULTILINE,
)
FALLBACK_FROM_REGEX = re.compile(
    r"^\s*from\s+(?P<module>[\.\w]+)\s+import\s+(?P<symbols>[a-zA-Z0-9_\.,\s\*]+)",
    re.MULTILINE,
)


class PythonTokenizer(BaseTokenizer):
    """Lexer-tokenizer for Python source files (.py, .pyi)."""

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else None

    def tokenize(self, file_path: Path | str) -> list[DependencyToken]:
        """Scan a Python file and return an array of dependency tokens."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundTokenizerError(f"File not found: {path}")

        try:
            with tokenize.open(path) as f:
                source = f.read()
        except Exception as err:
            logger.warning("Failed to read file %s: %s", path, err)
            raise LexerScanError(f"Could not read Python file '{path}': {err}") from err

        return self.tokenize_source(source, file_path=path)

    def tokenize_source(
        self, source: str, file_path: Path | str | None = None
    ) -> list[DependencyToken]:
        """Tokenize Python source code string and return an array of dependency tokens."""
        resolved_path = Path(file_path).resolve() if file_path else Path("unknown.py")
        source_lines = source.splitlines(keepends=True)

        # Attempt AST-based extraction first (syntactically robust)
        try:
            tree = ast.parse(source, filename=str(resolved_path))
            return self._extract_from_ast(tree, source_lines, resolved_path)
        except SyntaxError as err:
            logger.info(
                "Syntax error parsing AST for %s (%s). Falling back to lexical scan.",
                resolved_path,
                err,
            )
            return self._extract_from_tokens_and_lines(source, source_lines, resolved_path)

    def get_all_tokens(self, file_path: Path | str) -> list[Token]:
        """Tokenize a Python file into an array of all low-level lexical tokens."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundTokenizerError(f"File not found: {path}")

        with tokenize.open(path) as f:
            source = f.read()

        tokens: list[Token] = []
        try:
            tok_gen = tokenize.tokenize(io.BytesIO(source.encode("utf-8")).readline)
            while True:
                try:
                    tok = next(tok_gen)
                except (tokenize.TokenError, StopIteration):
                    break
                tok_name = tokenize.tok_name.get(tok.type, str(tok.type))
                location = SourceLocation(
                    file_path=path,
                    start_line=tok.start[0],
                    start_column=tok.start[1],
                    end_line=tok.end[0],
                    end_column=tok.end[1],
                )
                tokens.append(Token(kind=tok_name, value=tok.string, location=location))
        except Exception as err:
            logger.warning("Error tokenizing %s: %s", path, err)
        return tokens

    def _extract_from_ast(
        self, tree: ast.AST, source_lines: list[str], file_path: Path
    ) -> list[DependencyToken]:
        """Extract dependency tokens from Python AST."""
        dependencies: list[DependencyToken] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                snippet = self._get_snippet(source_lines, node.lineno, getattr(node, "end_lineno", node.lineno))
                location = SourceLocation(
                    file_path=file_path,
                    start_line=node.lineno,
                    start_column=node.col_offset,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    end_column=getattr(node, "end_col_offset", node.col_offset),
                )
                for alias in node.names:
                    dependencies.append(
                        DependencyToken(
                            keyword="import",
                            target=alias.name,
                            kind="IMPORT",
                            location=location,
                            snippet=snippet,
                            symbols=(alias.asname,) if alias.asname else (),
                            is_relative=False,
                            level=0,
                            resolved_path=self._resolve_module_path(alias.name, file_path, 0),
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                snippet = self._get_snippet(source_lines, node.lineno, getattr(node, "end_lineno", node.lineno))
                location = SourceLocation(
                    file_path=file_path,
                    start_line=node.lineno,
                    start_column=node.col_offset,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    end_column=getattr(node, "end_col_offset", node.col_offset),
                )
                level = node.level or 0
                is_relative = level > 0
                prefix = "." * level if is_relative else ""
                base_module = node.module or ""
                full_target = prefix + base_module if prefix or base_module else "."
                symbols = tuple(alias.name for alias in node.names)

                resolved = self._resolve_module_path(base_module, file_path, level)
                dependencies.append(
                    DependencyToken(
                        keyword="from",
                        target=full_target,
                        kind="IMPORT_FROM",
                        location=location,
                        snippet=snippet,
                        symbols=symbols,
                        is_relative=is_relative,
                        level=level,
                        resolved_path=resolved,
                    )
                )

            elif isinstance(node, ast.Call):
                func_name = self._get_call_func_name(node.func)
                if func_name in ("__import__", "importlib.import_module", "import_module"):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        target = node.args[0].value
                        snippet = self._get_snippet(
                            source_lines, node.lineno, getattr(node, "end_lineno", node.lineno)
                        )
                        location = SourceLocation(
                            file_path=file_path,
                            start_line=node.lineno,
                            start_column=node.col_offset,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            end_column=getattr(node, "end_col_offset", node.col_offset),
                        )
                        dependencies.append(
                            DependencyToken(
                                keyword=func_name,
                                target=target,
                                kind="DYNAMIC_IMPORT",
                                location=location,
                                snippet=snippet,
                                is_relative=target.startswith("."),
                                level=1 if target.startswith(".") else 0,
                                resolved_path=self._resolve_module_path(
                                    target.lstrip("."),
                                    file_path,
                                    1 if target.startswith(".") else 0,
                                ),
                            )
                        )

        return dependencies

    def _extract_from_tokens_and_lines(
        self, source: str, source_lines: list[str], file_path: Path
    ) -> list[DependencyToken]:
        """Fallback scanner using line-by-line regex and lexical tokens when AST parsing fails."""
        dependencies: list[DependencyToken] = []
        seen_targets: set[str] = set()

        for line_idx, raw_line in enumerate(source_lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # Match 'from <module> import <symbols>'
            m_from = FALLBACK_FROM_REGEX.search(line)
            if m_from:
                module_part = m_from.group("module")
                symbols_part = m_from.group("symbols")
                symbols = tuple(s.strip().split()[0] for s in symbols_part.split(",") if s.strip())

                level = len(module_part) - len(module_part.lstrip("."))
                is_rel = level > 0

                location = SourceLocation(
                    file_path=file_path,
                    start_line=line_idx,
                    start_column=raw_line.find("from"),
                    end_line=line_idx,
                    end_column=len(raw_line.rstrip("\r\n")),
                )
                dependencies.append(
                    DependencyToken(
                        keyword="from",
                        target=module_part,
                        kind="IMPORT_FROM",
                        location=location,
                        snippet=line,
                        symbols=symbols,
                        is_relative=is_rel,
                        level=level,
                        resolved_path=self._resolve_module_path(module_part.lstrip("."), file_path, level),
                    )
                )
                seen_targets.add(module_part)
                continue

            # Match 'import <modules>'
            m_import = FALLBACK_IMPORT_REGEX.search(line)
            if m_import:
                modules_part = m_import.group("modules")
                for mod_entry in modules_part.split(","):
                    mod_entry = mod_entry.strip()
                    if not mod_entry:
                        continue
                    mod_name = mod_entry.split()[0]  # strip 'as alias'
                    location = SourceLocation(
                        file_path=file_path,
                        start_line=line_idx,
                        start_column=raw_line.find("import"),
                        end_line=line_idx,
                        end_column=len(raw_line.rstrip("\r\n")),
                    )
                    dependencies.append(
                        DependencyToken(
                            keyword="import",
                            target=mod_name,
                            kind="IMPORT",
                            location=location,
                            snippet=line,
                            is_relative=False,
                            level=0,
                            resolved_path=self._resolve_module_path(mod_name, file_path, 0),
                        )
                    )
                    seen_targets.add(mod_name)

        return dependencies

    def _get_snippet(self, source_lines: list[str], start_line: int, end_line: int) -> str:
        """Extract lines of code as a trimmed snippet string."""
        if not source_lines or start_line <= 0:
            return ""
        start_idx = max(0, start_line - 1)
        end_idx = min(len(source_lines), end_line)
        return "".join(source_lines[start_idx:end_idx]).strip()

    def _get_call_func_name(self, node: ast.AST) -> str:
        """Extract function name string from ast.Call func."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            val = self._get_call_func_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return ""

    def _resolve_module_path(self, module_name: str, current_file: Path, level: int) -> Path | None:
        """Attempt to resolve a module name to an actual local file path."""
        if level > 0:
            base_dir = current_file.parent
            for _ in range(level - 1):
                base_dir = base_dir.parent

            rel_parts = [p for p in module_name.split(".") if p] if module_name else []
            if not rel_parts:
                init_file = base_dir / "__init__.py"
                return init_file if init_file.is_file() else None

            target_path = base_dir.joinpath(*rel_parts)
            if target_path.name:
                py_file = target_path.with_suffix(".py")
                if py_file.is_file():
                    return py_file
            init_file = target_path / "__init__.py"
            if init_file.is_file():
                return init_file
            return target_path.with_suffix(".py") if target_path.name else None

        if self.project_root:
            parts = [p for p in module_name.split(".") if p]
            if not parts:
                return None
            target = self.project_root.joinpath(*parts)
            if target.name:
                py_file = target.with_suffix(".py")
                if py_file.is_file():
                    return py_file
            init_file = target / "__init__.py"
            if init_file.is_file():
                return init_file

        return None
