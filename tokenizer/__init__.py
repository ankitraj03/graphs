"""Single-file tokenizer package for extracting connecting keywords and dependencies.

Exposes a class-based architecture where methods operate on one file at a time
and return arrays (lists) of dependency tokens, target files/modules, and connecting keywords.
"""

from __future__ import annotations

from tokenizer.base import BaseTokenizer
from tokenizer.cpp_tokenizer import CppTokenizer
from tokenizer.exceptions import (
    FileNotFoundTokenizerError,
    GraphsError,
    LexerScanError,
    TokenizerError,
    UnsupportedLanguageError,
)
from tokenizer.file_tokenizer import FileTokenizer
from tokenizer.javascript_tokenizer import JavaScriptTokenizer
from tokenizer.models import DependencyToken, SourceLocation, Token
from tokenizer.python_tokenizer import PythonTokenizer

__all__ = [
    "BaseTokenizer",
    "FileTokenizer",
    "PythonTokenizer",
    "CppTokenizer",
    "JavaScriptTokenizer",
    "DependencyToken",
    "SourceLocation",
    "Token",
    "GraphsError",
    "TokenizerError",
    "LexerScanError",
    "FileNotFoundTokenizerError",
    "UnsupportedLanguageError",
]
