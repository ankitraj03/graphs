"""Unified file tokenizer and dependency scanner.

Detects the target language of a code file and delegates to the appropriate
language-specific tokenizer. Exposes a class-based architecture where all
methods return arrays (lists in Python) of dependency tokens and targets.
"""

from __future__ import annotations

import logging
from pathlib import Path

from tokenizer.base import BaseTokenizer
from tokenizer.cpp_tokenizer import CppTokenizer
from tokenizer.exceptions import FileNotFoundTokenizerError, UnsupportedLanguageError
from tokenizer.javascript_tokenizer import JavaScriptTokenizer
from tokenizer.models import DependencyToken, Token
from tokenizer.python_tokenizer import PythonTokenizer

logger = logging.getLogger(__name__)


class FileTokenizer(BaseTokenizer):
    """Main entry point for scanning code files to extract connecting keywords and dependencies.

    Uses a class-based architecture where methods return outputs as arrays.
    Automatically detects language by file extension or explicit hint.
    """

    SUPPORTED_EXTENSIONS: dict[str, str] = {
        ".py": "python",
        ".pyi": "python",
        ".c": "cpp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "javascript",
        ".tsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
    }

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root).resolve() if project_root else None
        self._python_tokenizer = PythonTokenizer(project_root=self.project_root)
        self._cpp_tokenizer = CppTokenizer(project_root=self.project_root)
        self._js_tokenizer = JavaScriptTokenizer(project_root=self.project_root)

    def _get_tokenizer_for_path(self, path: Path) -> BaseTokenizer:
        """Resolve the appropriate BaseTokenizer instance for a given file path."""
        ext = path.suffix.lower()
        lang = self.SUPPORTED_EXTENSIONS.get(ext)

        if lang == "python":
            return self._python_tokenizer
        if lang == "cpp":
            return self._cpp_tokenizer
        if lang == "javascript":
            return self._js_tokenizer

        raise UnsupportedLanguageError(
            f"Unsupported file extension '{ext}' for file '{path}'. "
            f"Supported extensions: {sorted(self.SUPPORTED_EXTENSIONS.keys())}"
        )

    def tokenize(self, file_path: Path | str) -> list[DependencyToken]:
        """Scan a code file and return an array of dependency tokens connecting this file to other files."""
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundTokenizerError(f"File not found: {path}")

        tokenizer = self._get_tokenizer_for_path(path)
        return tokenizer.tokenize(path)

    def tokenize_source(
        self,
        source: str,
        file_path: Path | str | None = None,
        language: str | None = None,
    ) -> list[DependencyToken]:
        """Tokenize a source string and return an array of dependency tokens."""
        if language:
            lang = language.lower()
            if lang in ("py", "python"):
                return self._python_tokenizer.tokenize_source(source, file_path)
            if lang in ("c", "cpp", "c++"):
                return self._cpp_tokenizer.tokenize_source(source, file_path)
            if lang in ("js", "javascript", "ts", "typescript"):
                return self._js_tokenizer.tokenize_source(source, file_path)
            raise UnsupportedLanguageError(f"Unsupported language: '{language}'")

        if file_path:
            path = Path(file_path)
            tokenizer = self._get_tokenizer_for_path(path)
            return tokenizer.tokenize_source(source, file_path=path)

        # Default fallback to Python
        return self._python_tokenizer.tokenize_source(source, file_path=None)

    def get_all_tokens(self, file_path: Path | str) -> list[Token]:
        """Return an array of all lexical tokens (keywords, identifiers, etc.) in the file."""
        path = Path(file_path).resolve()
        tokenizer = self._get_tokenizer_for_path(path)
        return tokenizer.get_all_tokens(path)

    def scan_directory(
        self,
        directory_path: Path | str,
        recursive: bool = True,
        extensions: tuple[str, ...] | None = None,
    ) -> dict[str, list[DependencyToken]]:
        """Scan all code files in a directory and return a dictionary mapping file paths to their dependency token arrays."""
        root = Path(directory_path).resolve()
        if not root.is_dir():
            raise FileNotFoundTokenizerError(f"Directory not found: {root}")

        allowed_exts = set(extensions) if extensions else set(self.SUPPORTED_EXTENSIONS.keys())
        results: dict[str, list[DependencyToken]] = {}

        pattern = "**/*" if recursive else "*"
        for p in root.glob(pattern):
            if p.is_file() and p.suffix.lower() in allowed_exts:
                # Ignore hidden directories like .git
                if any(part.startswith(".") for part in p.parts):
                    continue
                try:
                    deps = self.tokenize(p)
                    results[str(p)] = deps
                except Exception as err:
                    logger.warning("Error tokenizing %s: %s", p, err)

        return results
