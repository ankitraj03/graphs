"""Integration tests for Graph Builder: Scanner + Tokenizer + Connector + Graph Designer.

Verifies end-to-end integration satisfying all Phase 4 contract requirements:
- Test 1: Empty repository (0 nodes, 0 edges)
- Test 2: Isolated file (1 node, 0 edges)
- Test 3: Connected files (2 nodes, 1 edge)
- Test 4: Isolated + connected files (3 nodes, 1 edge)
- Test 5: Multiple relationships (3 nodes, 2 edges)
- Test 6: Multiple relationship types between same pair (2 nodes, 2 edges: INCLUDE & IMPORT)
- Test 7: Duplicate relationship deduplication (2 nodes, 1 edge)
- Test 8: Unresolved/external reference (1 internal node, 0 external nodes, 0 edges)
- Test 9: Cycle safety (A -> B -> C -> A)
- Test 10: Full end-to-end execution through Connector pipeline with Graph Designer
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from connector import Connector, RelationshipMap
from connector.graph_designer_adapter import GraphDesignerAdapter, GraphResult


class TestPhase4Integration(unittest.TestCase):
    """Test suite verifying Connector and Graph Designer end-to-end integration."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name).resolve()
        self.connector = Connector()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_1_empty_repository(self) -> None:
        """Test 1: Empty repository produces 0 nodes and 0 edges in Graph Designer."""
        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 0)
        self.assertIsNotNone(rel_map.graph_result)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 0)
        self.assertEqual(rel_map.graph_result.edge_count, 0)

    def test_2_isolated_file(self) -> None:
        """Test 2: A single file with no dependencies produces exactly 1 node and 0 edges."""
        (self.repo_root / "A.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 1)
        self.assertIsNotNone(rel_map.graph_result)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 1)
        self.assertEqual(rel_map.graph_result.edge_count, 0)

        # Verify node URI
        json_data = rel_map.graph_result.json_data
        self.assertIsNotNone(json_data)
        node_ids = [n["id"] for n in json_data["nodes"]]
        self.assertIn("file:A.cpp", node_ids)

    def test_3_connected_files(self) -> None:
        """Test 3: Two connected files produce 2 nodes and 1 directed edge."""
        (self.repo_root / "B.h").write_text("#pragma once\n", encoding="utf-8")
        (self.repo_root / "A.cpp").write_text('#include "B.h"\n', encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 2)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 2)
        self.assertEqual(rel_map.graph_result.edge_count, 1)

        edge = rel_map.graph_result.json_data["edges"][0]
        self.assertEqual(edge["source"], "file:A.cpp")
        self.assertEqual(edge["target"], "file:B.h")
        self.assertEqual(edge["type"], "INCLUDE")
        self.assertEqual(edge["metadata"]["kind"], "INCLUDE_LOCAL")

    def test_4_isolated_plus_connected(self) -> None:
        """Test 4: Isolated files are preserved as nodes alongside connected files.

        A.cpp -> B.h
        C.cpp (isolated)
        Expected: 3 nodes, 1 edge
        """
        (self.repo_root / "B.h").write_text("#pragma once\n", encoding="utf-8")
        (self.repo_root / "A.cpp").write_text('#include "B.h"\n', encoding="utf-8")
        (self.repo_root / "C.cpp").write_text("void standalone() {}\n", encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 3)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 3)
        self.assertEqual(rel_map.graph_result.edge_count, 1)

        node_ids = {n["id"] for n in rel_map.graph_result.json_data["nodes"]}
        self.assertEqual(node_ids, {"file:A.cpp", "file:B.h", "file:C.cpp"})

    def test_5_multiple_relationships(self) -> None:
        """Test 5: Multiple outgoing relationships from one source file (3 nodes, 2 edges)."""
        (self.repo_root / "user.h").write_text("#pragma once\n", encoding="utf-8")
        (self.repo_root / "database.h").write_text("#pragma once\n", encoding="utf-8")
        (self.repo_root / "main.cpp").write_text(
            '#include "user.h"\n#include "database.h"\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 3)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 3)
        self.assertEqual(rel_map.graph_result.edge_count, 2)

        edge_targets = {e["target"] for e in rel_map.graph_result.json_data["edges"]}
        self.assertEqual(edge_targets, {"file:user.h", "file:database.h"})

    def test_6_multiple_relationship_types(self) -> None:
        """Test 6: Distinct relationship types between same nodes are preserved.

        A -> B INCLUDE
        A -> B IMPORT
        Expected: 2 nodes, 2 distinct edges
        """
        (self.repo_root / "target.h").write_text("// header\n", encoding="utf-8")
        # In C++, #include "target.h" is INCLUDE_LOCAL, import target; is MODULE_IMPORT
        (self.repo_root / "source.cpp").write_text(
            '#include "target.h"\nimport target;\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 2)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 2)
        self.assertEqual(rel_map.graph_result.edge_count, 2)

        edge_types = {e["type"] for e in rel_map.graph_result.json_data["edges"]}
        self.assertEqual(edge_types, {"INCLUDE", "IMPORT"})

    def test_7_duplicate_relationship_deduplication(self) -> None:
        """Test 7: Duplicate identical (source, target, type) relationships are deduplicated."""
        (self.repo_root / "user.h").write_text("", encoding="utf-8")
        (self.repo_root / "main.cpp").write_text(
            '#include "user.h"\n#include "user.h"\n#include "user.h"\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 2)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 2)
        self.assertEqual(rel_map.graph_result.edge_count, 1)

    def test_8_unresolved_reference_handling(self) -> None:
        """Test 8: Unresolved references (e.g. iostream) do not create external nodes.

        A.cpp -> iostream
        Expected: 1 internal node, 0 external nodes, 0 edges.
        iostream recorded as unresolved metadata.
        """
        (self.repo_root / "A.cpp").write_text(
            '#include <iostream>\n#include "external_lib.h"\n',
            encoding="utf-8",
        )

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 1)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 1)
        self.assertEqual(rel_map.graph_result.edge_count, 0)

        # Nodes strictly contain only repository files
        node_ids = [n["id"] for n in rel_map.graph_result.json_data["nodes"]]
        self.assertEqual(node_ids, ["file:A.cpp"])

        # Unresolved references are retained in metadata
        src_path = (self.repo_root / "A.cpp").resolve()
        unres = rel_map.relationships[src_path].unresolved_references
        self.assertIn("iostream", unres)
        self.assertIn("external_lib.h", unres)

    def test_9_cycle_safety(self) -> None:
        """Test 9: Cyclical relationships (A -> B -> C -> A) are represented safely."""
        (self.repo_root / "pkg").mkdir()
        (self.repo_root / "pkg" / "a.py").write_text("from .b import B\nclass A: pass\n", encoding="utf-8")
        (self.repo_root / "pkg" / "b.py").write_text("from .c import C\nclass B: pass\n", encoding="utf-8")
        (self.repo_root / "pkg" / "c.py").write_text("from .a import A\nclass C: pass\n", encoding="utf-8")

        rel_map = self.connector.connect(self.repo_root, build_graph=True)

        self.assertEqual(rel_map.total_files_scanned, 3)
        assert rel_map.graph_result is not None
        self.assertEqual(rel_map.graph_result.node_count, 3)
        self.assertEqual(rel_map.graph_result.edge_count, 3)

    def test_10_render_formats(self) -> None:
        """Test 10: Formatted text output and raw graph.toString() rendering."""
        (self.repo_root / "b.h").write_text("", encoding="utf-8")
        (self.repo_root / "a.cpp").write_text('#include "b.h"\n', encoding="utf-8")

        # 1. Standard banner format
        rel_map_banner = self.connector.connect(self.repo_root, build_graph=True, graph_output_format="text")
        text_banner = rel_map_banner.render_graph()
        self.assertIn("GRAPH BUILDER", text_banner)
        self.assertIn("Graph contains 2 nodes and 1 edges", text_banner)
        self.assertIn("--INCLUDE-->", text_banner)

        # 2. Raw graph.toString() format
        rel_map_raw = self.connector.connect(self.repo_root, build_graph=True, graph_output_format="to-string")
        text_raw = rel_map_raw.render_graph(output_format="to-string")
        self.assertIn("Graph (2 nodes, 1 edges):", text_raw)


if __name__ == "__main__":
    unittest.main()
