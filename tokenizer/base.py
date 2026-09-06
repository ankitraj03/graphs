"""Base tokenizer interface and abstract class.

Defines the class-based architecture contract where methods return output
in the form of arrays (lists in Python) as required by the system specification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from tokenizer.models import DependencyToken, Token


class BaseTokenizer(ABC):
    """Abstract base class for language-specific and unified tokenizers."""

    @abstractmethod
    def tokenize(self, file_path: Path | str) -> list[DependencyToken]:
        """Scan a code file and return an array of dependency tokens connecting this file to other files."""

    @abstractmethod
    def tokenize_source(
        self, source: str, file_path: Path | str | None = None
    ) -> list[DependencyToken]:
        """Tokenize source string and return an array of dependency tokens connecting to other files."""

    @abstractmethod
    def get_all_tokens(self, file_path: Path | str) -> list[Token]:
        """Tokenize a file and return an array of all lexical tokens (keywords, identifiers, etc.)."""

    def get_dependencies(self, file_path: Path | str) -> list[str]:
        """Scan a code file and return an array of all unique dependency target names or paths."""
        tokens = self.tokenize(file_path)
        seen: set[str] = set()
        result: list[str] = []
        for tok in tokens:
            if tok.target not in seen:
                seen.add(tok.target)
                result.append(tok.target)
        return result

    def get_connecting_keywords(self, file_path: Path | str) -> list[str]:
        """Scan a code file and return an array of unique connecting keywords found (e.g. 'import', 'from')."""
        tokens = self.tokenize(file_path)
        seen: set[str] = set()
        result: list[str] = []
        for tok in tokens:
            if tok.keyword not in seen:
                seen.add(tok.keyword)
                result.append(tok.keyword)
        return result
