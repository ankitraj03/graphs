"""Exception hierarchy for the tokenizer package.

Adheres to the GraphsError domain hierarchy defined in AGENTS.md.
"""

from __future__ import annotations


class GraphsError(Exception):
    """Base exception for all errors originating from the graphs system."""


class TokenizerError(GraphsError):
    """Base exception for tokenizer and lexical analysis errors."""


class LexerScanError(TokenizerError):
    """Raised when lexical scanning fails to tokenize a file or stream."""


class FileNotFoundTokenizerError(TokenizerError):
    """Raised when a specified file cannot be found for tokenization."""


class UnsupportedLanguageError(TokenizerError):
    """Raised when a file extension or language is not supported by the tokenizer."""
