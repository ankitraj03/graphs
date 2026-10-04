"""Unit and integration tests for Graph Builder Phase 3: Connector.

Tests all required scenarios:
- Test 1: Basic relationships (one file includes another)
- Test 2: Multiple references (one file references multiple files)
- Test 3: No references (file has no repository references)
- Test 4: Nested directories (src/main.cpp -> include/user.h)
- Test 5: Unresolved references (missing.h, external library)
- Test 6: Duplicate references (repeated includes deduplicated)
- Test 7: Empty repository (graceful handling)
- Test 8: Invalid repository path (graceful error handling)
- End-to-end Section 11 validation on connector_test repository
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from connector import Connector, FileRelationship, RelationshipMap
from connector.resolver import ReferenceResolver
from connector.scanner_adapter import ScannerAdapter


class TestConnectorPipeline(unittest.TestCase):
    """Test suite verifying the complete Connector orchestration pipeline."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name).resolve()
        self.connector = Connector()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_section_11_specification_example(self) -> None:
        """Verify the exact project structure from Graph Builder Phase 3 Specification."""
        # project/
        # ├── main.cpp
        # ├── user.cpp
        # ├── user.h
        # ├── database.cpp
        # ├── database.h
        # └── utils.h

        (self.repo_root / "main.cpp").write_text(
            '#include "user.h"\n#include "database.h"\n\nint main() { return 0; }\n',
            encoding="utf-8",
        )
        (self.repo_root / "user.cpp").write_text(
            '#include "user.h"\n',
            encoding="utf-8",
        )
        (self.repo_root / "user.h").write_text(
            '#pragma once\nclass User {};\n',
            encoding="utf-8",
        )
        (self.repo_root / "database.cpp").write_text(
            '#include "database.h"\n',
            encoding="utf-8",
        )
        (self.repo_root / "database.h").write_text(
            '#pragma once\nclass Database {};\n',
            encoding="utf-8",
        )
        (self.repo_root / "utils.h").write_text(
            '#pragma once\n// standalone utility\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root)
        self.assertIsInstance(rel_map, RelationshipMap)
        self.assertEqual(rel_map.total_files_scanned, 6)

        dict_map = rel_map.to_dict(relative_to_root=True)

        # main.cpp → [user.h, database.h]
        self.assertEqual(sorted(dict_map["main.cpp"]), ["database.h", "user.h"])
        # user.cpp → [user.h]
        self.assertEqual(dict_map["user.cpp"], ["user.h"])
        # database.cpp → [database.h]
        self.assertEqual(dict_map["database.cpp"], ["database.h"])
        # user.h → []
        self.assertEqual(dict_map["user.h"], [])
        # database.h → []
        self.assertEqual(dict_map["database.h"], [])
        # utils.h → []
        self.assertEqual(dict_map["utils.h"], [])

    def test_case_1_basic_relationships(self) -> None:
        """Test 1: One file includes another."""
        (self.repo_root / "b.h").write_text("// b header\n", encoding="utf-8")
        (self.repo_root / "a.cpp").write_text('#include "b.h"\n', encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        self.assertEqual(dict_map["a.cpp"], ["b.h"])
        self.assertEqual(dict_map["b.h"], [])

    def test_case_2_multiple_references(self) -> None:
        """Test 2: One file references multiple files."""
        (self.repo_root / "h1.h").write_text("", encoding="utf-8")
        (self.repo_root / "h2.h").write_text("", encoding="utf-8")
        (self.repo_root / "h3.h").write_text("", encoding="utf-8")
        (self.repo_root / "multi.cpp").write_text(
            '#include "h1.h"\n#include "h2.h"\n#include "h3.h"\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        self.assertEqual(sorted(dict_map["multi.cpp"]), ["h1.h", "h2.h", "h3.h"])

    def test_case_3_no_references(self) -> None:
        """Test 3: A file has no repository references (file.cpp -> [])."""
        (self.repo_root / "standalone.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        self.assertEqual(dict_map["standalone.cpp"], [])

    def test_case_4_nested_directories(self) -> None:
        """Test 4: Nested directories (src/main.cpp -> include/user.h)."""
        (self.repo_root / "src").mkdir()
        (self.repo_root / "include").mkdir()

        (self.repo_root / "include" / "user.h").write_text("struct User{};\n", encoding="utf-8")
        (self.repo_root / "src" / "main.cpp").write_text('#include "user.h"\n', encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        # src/main.cpp includes user.h which resides in include/user.h
        self.assertEqual(dict_map["src/main.cpp"], ["include/user.h"])
        self.assertEqual(dict_map["include/user.h"], [])

    def test_case_5_unresolved_reference(self) -> None:
        """Test 5: #include 'missing.h' is not incorrectly linked to another file."""
        (self.repo_root / "file.cpp").write_text(
            '#include "missing.h"\n#include <iostream>\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        # Must not invent any connections
        self.assertEqual(dict_map["file.cpp"], [])

        # Unresolved reference should be retained
        src_file = (self.repo_root / "file.cpp").resolve()
        rel = rel_map.relationships[src_file]
        self.assertIn("missing.h", rel.unresolved_references)

    def test_case_6_duplicate_references(self) -> None:
        """Test 6: Repeated references to the same file are deduplicated."""
        (self.repo_root / "user.h").write_text("", encoding="utf-8")
        (self.repo_root / "main.cpp").write_text(
            '#include "user.h"\n#include "user.h"\n#include "user.h"\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        # Exactly one occurrence
        self.assertEqual(dict_map["main.cpp"], ["user.h"])

    def test_case_7_empty_repository(self) -> None:
        """Test 7: Empty repository handled gracefully without errors."""
        rel_map = self.connector.connect(self.repo_root)

        self.assertEqual(rel_map.total_files_scanned, 0)
        self.assertEqual(rel_map.relationships, {})
        self.assertEqual(rel_map.to_dict(), {})
        self.assertIn("No files found", rel_map.format_text())

    def test_case_8_invalid_repository_path(self) -> None:
        """Test 8: Invalid or nonexistent path raises appropriate exceptions."""
        nonexistent = self.repo_root / "ghost_folder_xyz"
        with self.assertRaises(FileNotFoundError):
            self.connector.connect(nonexistent)

        # File instead of directory
        dummy_file = self.repo_root / "file.txt"
        dummy_file.write_text("not a dir", encoding="utf-8")
        with self.assertRaises(NotADirectoryError):
            self.connector.connect(dummy_file)

    def test_python_multi_file_connections(self) -> None:
        """Verify Python module and relative import connections."""
        (self.repo_root / "app").mkdir()
        (self.repo_root / "app" / "__init__.py").write_text("", encoding="utf-8")
        (self.repo_root / "app" / "config.py").write_text("PORT = 8080\n", encoding="utf-8")
        (self.repo_root / "app" / "main.py").write_text(
            "import os\nfrom .config import PORT\nfrom . import __init__\n",
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        self.assertIn("app/config.py", dict_map["app/main.py"])

    def test_javascript_typescript_connections(self) -> None:
        """Verify TypeScript and JavaScript import connections."""
        (self.repo_root / "src").mkdir()
        (self.repo_root / "src" / "button.tsx").write_text("export const Button = () => null;\n", encoding="utf-8")
        (self.repo_root / "src" / "index.ts").write_text("import { Button } from './button';\n", encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root)
        dict_map = rel_map.to_dict(relative_to_root=True)

        self.assertEqual(dict_map["src/index.ts"], ["src/button.tsx"])


if __name__ == "__main__":
    unittest.main()
