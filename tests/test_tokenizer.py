"""Comprehensive unit test suite for the tokenizer package.

Tests class-based architecture, array return types, connecting keyword extraction,
syntax error tolerance, and multi-language support.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tokenizer import (
    CppTokenizer,
    DependencyToken,
    FileNotFoundTokenizerError,
    FileTokenizer,
    JavaScriptTokenizer,
    PythonTokenizer,
    SourceLocation,
    Token,
    UnsupportedLanguageError,
)


class TestPythonTokenizer(unittest.TestCase):
    """Test Python-specific tokenization and dependency extraction."""

    def setUp(self) -> None:
        self.tokenizer = PythonTokenizer()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_standard_imports(self) -> None:
        code = """
import os
import sys, math
import collections as col
from pathlib import Path
from os.path import join, split as sp
"""
        results = self.tokenizer.tokenize_source(code)
        self.assertIsInstance(results, list)

        targets = [dep.target for dep in results]
        self.assertIn("os", targets)
        self.assertIn("sys", targets)
        self.assertIn("math", targets)
        self.assertIn("collections", targets)
        self.assertIn("pathlib", targets)
        self.assertIn("os.path", targets)

        # Verify connecting keywords
        keywords = {dep.keyword for dep in results}
        self.assertIn("import", keywords)
        self.assertIn("from", keywords)

    def test_relative_imports(self) -> None:
        code = """
from . import sibling
from .models import Node, Edge
from ..utils import helper
"""
        results = self.tokenizer.tokenize_source(code)
        self.assertIsInstance(results, list)

        rel_deps = [dep for dep in results if dep.is_relative]
        self.assertEqual(len(rel_deps), 3)

        targets = [dep.target for dep in rel_deps]
        self.assertIn(".", targets)
        self.assertIn(".models", targets)
        self.assertIn("..utils", targets)

        # Check level
        models_dep = next(d for d in rel_deps if d.target == ".models")
        self.assertEqual(models_dep.level, 1)
        self.assertEqual(models_dep.symbols, ("Node", "Edge"))

        utils_dep = next(d for d in rel_deps if d.target == "..utils")
        self.assertEqual(utils_dep.level, 2)
        self.assertEqual(utils_dep.symbols, ("helper",))

    def test_dynamic_imports(self) -> None:
        code = """
import os
mod1 = __import__('json')
mod2 = importlib.import_module('csv')
"""
        results = self.tokenizer.tokenize_source(code)
        targets = [dep.target for dep in results]
        self.assertIn("os", targets)
        self.assertIn("json", targets)
        self.assertIn("csv", targets)

        dynamic_deps = [dep for dep in results if dep.kind == "DYNAMIC_IMPORT"]
        self.assertEqual(len(dynamic_deps), 2)

    def test_syntax_error_fallback(self) -> None:
        """Verify fallback lexical scanning when code has syntax errors."""
        broken_code = """
import os
from sys import argv
def broken_function(
    # Unclosed parentheses causing AST SyntaxError
import math
from pathlib import Path
"""
        results = self.tokenizer.tokenize_source(broken_code)
        self.assertIsInstance(results, list)
        targets = [dep.target for dep in results]
        self.assertIn("os", targets)
        self.assertIn("sys", targets)
        self.assertIn("math", targets)
        self.assertIn("pathlib", targets)

    def test_file_scanning(self) -> None:
        test_file = self.root / "sample.py"
        test_file.write_text("import json\nfrom datetime import datetime\n", encoding="utf-8")

        results = self.tokenizer.tokenize(test_file)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].target, "json")
        self.assertEqual(results[0].keyword, "import")
        self.assertEqual(results[1].target, "datetime")
        self.assertEqual(results[1].keyword, "from")

        deps = self.tokenizer.get_dependencies(test_file)
        self.assertIsInstance(deps, list)
        self.assertEqual(deps, ["json", "datetime"])

        keywords = self.tokenizer.get_connecting_keywords(test_file)
        self.assertIsInstance(keywords, list)
        self.assertEqual(keywords, ["import", "from"])

    def test_get_all_tokens(self) -> None:
        test_file = self.root / "tokens.py"
        test_file.write_text("x = 42\nimport os\n", encoding="utf-8")

        tokens = self.tokenizer.get_all_tokens(test_file)
        self.assertIsInstance(tokens, list)
        self.assertGreater(len(tokens), 0)
        token_values = [t.value for t in tokens]
        self.assertIn("import", token_values)
        self.assertIn("os", token_values)


class TestCppTokenizer(unittest.TestCase):
    """Test C/C++ dependency tokenization."""

    def setUp(self) -> None:
        self.tokenizer = CppTokenizer()

    def test_cpp_includes(self) -> None:
        code = """
#include <iostream>
#include <vector>
#include "my_header.h"
#include "../utils/helper.hpp"
// #include <commented_out.h>
"""
        results = self.tokenizer.tokenize_source(code)
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 4)

        targets = [dep.target for dep in results]
        self.assertIn("iostream", targets)
        self.assertIn("vector", targets)
        self.assertIn("my_header.h", targets)
        self.assertIn("../utils/helper.hpp", targets)
        self.assertNotIn("commented_out.h", targets)


class TestJavaScriptTokenizer(unittest.TestCase):
    """Test JavaScript and TypeScript dependency tokenization."""

    def setUp(self) -> None:
        self.tokenizer = JavaScriptTokenizer()

    def test_js_imports_and_requires(self) -> None:
        code = """
import React, { useState } from 'react';
import './styles.css';
const express = require('express');
export { helper } from './utils';
const dynamicMod = import('./dynamic');
// import fake from 'fake';
"""
        results = self.tokenizer.tokenize_source(code)
        self.assertIsInstance(results, list)
        targets = [dep.target for dep in results]

        self.assertIn("react", targets)
        self.assertIn("./styles.css", targets)
        self.assertIn("express", targets)
        self.assertIn("./utils", targets)
        self.assertIn("./dynamic", targets)
        self.assertNotIn("fake", targets)


class TestUnifiedFileTokenizer(unittest.TestCase):
    """Test the unified FileTokenizer facade class."""

    def setUp(self) -> None:
        self.tokenizer = FileTokenizer()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_dispatch_by_extension(self) -> None:
        py_file = self.root / "test.py"
        py_file.write_text("import sqlite3\n", encoding="utf-8")

        cpp_file = self.root / "test.cpp"
        cpp_file.write_text('#include "header.h"\n', encoding="utf-8")

        js_file = self.root / "test.js"
        js_file.write_text("const fs = require('fs');\n", encoding="utf-8")

        py_deps = self.tokenizer.get_dependencies(py_file)
        self.assertIsInstance(py_deps, list)
        self.assertEqual(py_deps, ["sqlite3"])

        cpp_deps = self.tokenizer.get_dependencies(cpp_file)
        self.assertIsInstance(cpp_deps, list)
        self.assertEqual(cpp_deps, ["header.h"])

        js_deps = self.tokenizer.get_dependencies(js_file)
        self.assertIsInstance(js_deps, list)
        self.assertEqual(js_deps, ["fs"])

    def test_file_not_found(self) -> None:
        non_existent = self.root / "ghost.py"
        with self.assertRaises(FileNotFoundTokenizerError):
            self.tokenizer.tokenize(non_existent)

    def test_unsupported_language(self) -> None:
        unknown_file = self.root / "readme.unknown"
        unknown_file.write_text("Some text", encoding="utf-8")
        with self.assertRaises(UnsupportedLanguageError):
            self.tokenizer.tokenize(unknown_file)

    def test_single_file_tokenization_only(self) -> None:
        """Verify FileTokenizer processes individual files and does not expose directory scanning."""
        self.assertFalse(hasattr(self.tokenizer, "scan_directory"))

        py_file = self.root / "a.py"
        py_file.write_text("import os\n", encoding="utf-8")
        deps = self.tokenizer.tokenize(py_file)
        self.assertIsInstance(deps, list)
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].target, "os")

    def test_serialization(self) -> None:
        py_file = self.root / "serial.py"
        py_file.write_text("import math\n", encoding="utf-8")

        deps = self.tokenizer.tokenize(py_file)
        self.assertEqual(len(deps), 1)
        data = deps[0].to_dict()

        self.assertEqual(data["keyword"], "import")
        self.assertEqual(data["target"], "math")
        self.assertEqual(data["kind"], "IMPORT")
        self.assertIn("location", data)
        self.assertEqual(data["location"]["start_line"], 1)

    def test_empty_file(self) -> None:
        empty_py = self.root / "empty.py"
        empty_py.write_text("", encoding="utf-8")
        deps = self.tokenizer.tokenize(empty_py)
        self.assertIsInstance(deps, list)
        self.assertEqual(len(deps), 0)

    def test_relative_path_resolution(self) -> None:
        # Create helper.py and main.py in same directory
        helper_py = self.root / "helper.py"
        helper_py.write_text("def run(): pass\n", encoding="utf-8")

        main_py = self.root / "main.py"
        main_py.write_text("from .helper import run\n", encoding="utf-8")

        deps = self.tokenizer.tokenize(main_py)
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].target, ".helper")
        self.assertIsNotNone(deps[0].resolved_path)
        self.assertEqual(deps[0].resolved_path, helper_py.resolve())

    def test_cpp_modules(self) -> None:
        cpp_tokenizer = CppTokenizer()
        code = "import std.core;\nimport <iostream>;"
        results = cpp_tokenizer.tokenize_source(code)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].target, "std.core")
        self.assertEqual(results[0].kind, "MODULE_IMPORT")

    def test_js_export_all(self) -> None:
        js_tokenizer = JavaScriptTokenizer()
        code = "export * from './components';\nexport { Button } from './button';"
        results = js_tokenizer.tokenize_source(code)
        self.assertEqual(len(results), 2)
        targets = [d.target for d in results]
        self.assertIn("./components", targets)
        self.assertIn("./button", targets)


if __name__ == "__main__":
    unittest.main()

