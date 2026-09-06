"""Integration test case for scanning multi-file project dependencies.

Validates the complete workflow:
1. Class-based architecture with array return types.
2. Scanning individual code files to retrieve dependent files/modules.
3. Tokenizing connecting keywords (import, from, require, #include).
4. Relative dependency resolution across directories.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tokenizer import (
    BaseTokenizer,
    DependencyToken,
    FileTokenizer,
    PythonTokenizer,
)


class TestProjectDependencyScan(unittest.TestCase):
    """End-to-end integration test scanning an interconnected project directory."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name).resolve()

        # Build a realistic sample project structure
        # repo_root/
        # ├── app/
        # │   ├── __init__.py
        # │   ├── main.py
        # │   ├── config.py
        # │   ├── utils/
        # │   │   ├── __init__.py
        # │   │   └── helpers.py
        # │   └── services/
        # │       ├── __init__.py
        # │       └── auth.py
        # ├── native/
        # │   └── engine.cpp
        # └── frontend/
        #     └── app.ts

        (self.repo_root / "app" / "utils").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "app" / "services").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "native").mkdir(parents=True, exist_ok=True)
        (self.repo_root / "frontend").mkdir(parents=True, exist_ok=True)

        # 1. config.py
        self.config_file = self.repo_root / "app" / "config.py"
        self.config_file.write_text(
            "import os\n"
            "import json\n"
            "from pathlib import Path\n"
            "CONFIG_PATH = Path('/etc/config.json')\n",
            encoding="utf-8",
        )

        # 2. helpers.py
        self.helpers_file = self.repo_root / "app" / "utils" / "helpers.py"
        self.helpers_file.write_text(
            "import math\n"
            "def add(a, b):\n"
            "    return a + b\n",
            encoding="utf-8",
        )

        # 3. auth.py (imports ..config and .helpers)
        self.auth_file = self.repo_root / "app" / "services" / "auth.py"
        self.auth_file.write_text(
            "import hashlib\n"
            "from ..config import CONFIG_PATH\n"
            "from ..utils.helpers import add\n",
            encoding="utf-8",
        )

        # 4. main.py (entrypoint importing config and services)
        self.main_file = self.repo_root / "app" / "main.py"
        self.main_file.write_text(
            "import sys\n"
            "from .config import CONFIG_PATH\n"
            "from .services.auth import add\n"
            "from .utils import helpers\n",
            encoding="utf-8",
        )

        # 5. engine.cpp
        self.cpp_file = self.repo_root / "native" / "engine.cpp"
        self.cpp_file.write_text(
            "#include <iostream>\n"
            "#include <vector>\n"
            '#include "engine.h"\n',
            encoding="utf-8",
        )

        # 6. app.ts
        self.ts_file = self.repo_root / "frontend" / "app.ts"
        self.ts_file.write_text(
            "import { useState } from 'react';\n"
            "const axios = require('axios');\n"
            "import '../styles/main.css';\n",
            encoding="utf-8",
        )

        self.tokenizer = FileTokenizer(project_root=self.repo_root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_class_architecture_and_array_output(self) -> None:
        """Verify class-based architecture contract: subclass of BaseTokenizer and returns arrays."""
        self.assertIsInstance(self.tokenizer, BaseTokenizer)

        # Verify method returns an array (list in Python)
        dependencies = self.tokenizer.get_dependencies(self.main_file)
        self.assertIsInstance(dependencies, list, "Output must be returned as an array")

        keywords = self.tokenizer.get_connecting_keywords(self.main_file)
        self.assertIsInstance(keywords, list, "Output must be returned as an array")

        tokens = self.tokenizer.tokenize(self.main_file)
        self.assertIsInstance(tokens, list, "Output must be returned as an array")

    def test_scan_code_file_dependencies(self) -> None:
        """Verify scanning a file returns all other files/modules it is dependent on."""
        deps = self.tokenizer.get_dependencies(self.main_file)

        self.assertIn("sys", deps)
        self.assertIn(".config", deps)
        self.assertIn(".services.auth", deps)
        self.assertIn(".utils", deps)
        self.assertEqual(len(deps), 4)

    def test_retrieve_connecting_keywords(self) -> None:
        """Verify retrieval of all keywords that connect this file to other files."""
        keywords = self.tokenizer.get_connecting_keywords(self.main_file)

        # Connecting keywords present in main.py: 'import', 'from'
        self.assertIn("import", keywords)
        self.assertIn("from", keywords)

    def test_dependency_token_metadata(self) -> None:
        """Verify tokenized items contain exact line/column locations, keywords, and targets."""
        tokens = self.tokenizer.tokenize(self.main_file)

        for tok in tokens:
            self.assertIsInstance(tok, DependencyToken)
            self.assertIn(tok.keyword, ("import", "from"))
            self.assertGreater(tok.location.start_line, 0)
            self.assertTrue(len(tok.snippet) > 0)

    def test_relative_dependency_resolution(self) -> None:
        """Verify that relative imports are accurately resolved to neighboring file paths."""
        tokens = self.tokenizer.tokenize(self.auth_file)

        # auth.py imports '..config'
        config_dep = next(t for t in tokens if t.target == "..config")
        self.assertTrue(config_dep.is_relative)
        self.assertEqual(config_dep.level, 2)
        self.assertIsNotNone(config_dep.resolved_path)
        self.assertEqual(config_dep.resolved_path, self.config_file)

    def test_cpp_file_scanning(self) -> None:
        """Verify scanning C++ code retrieves #include dependencies."""
        deps = self.tokenizer.get_dependencies(self.cpp_file)
        self.assertIn("iostream", deps)
        self.assertIn("vector", deps)
        self.assertIn("engine.h", deps)

        keywords = self.tokenizer.get_connecting_keywords(self.cpp_file)
        self.assertIn("#include", keywords)

    def test_typescript_file_scanning(self) -> None:
        """Verify scanning JS/TS code retrieves import/require dependencies."""
        deps = self.tokenizer.get_dependencies(self.ts_file)
        self.assertIn("react", deps)
        self.assertIn("axios", deps)
        self.assertIn("../styles/main.css", deps)

        keywords = self.tokenizer.get_connecting_keywords(self.ts_file)
        self.assertIn("import", keywords)
        self.assertIn("require", keywords)

    def test_tokenize_individual_project_files(self) -> None:
        """Verify scanning individual project files one by one produces dependency tokens and no directory scanning exists."""
        self.assertFalse(hasattr(self.tokenizer, "scan_directory"))

        files = [self.main_file, self.config_file, self.auth_file, self.cpp_file, self.ts_file]
        for f in files:
            deps = self.tokenizer.tokenize(f)
            self.assertIsInstance(deps, list)
            self.assertTrue(len(deps) > 0)


if __name__ == "__main__":
    unittest.main()
