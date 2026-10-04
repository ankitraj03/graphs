"""Graph Designer adapter for building and rendering in-memory graphs.

Follows the same subprocess integration pattern as ScannerAdapter:
invokes the native C++ graph_designer.exe passing JSON payload over stdin
and retrieving the rendered graph representation and metrics.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from connector.exceptions import GraphDesignerExecutionError

logger = logging.getLogger(__name__)

# Default locations for graph_designer.exe
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH_DESIGNER_BINS: tuple[Path, ...] = (
    PROJECT_ROOT / "graph-designer" / "graph_designer.exe",
    PROJECT_ROOT / "graph_designer.exe",
)


@dataclass(frozen=True, slots=True)
class GraphResult:
    """Represents the constructed graph metrics and rendered visualization from Graph Designer."""

    node_count: int
    edge_count: int
    rendered_text: str
    json_data: dict[str, Any] | None = None


class GraphDesignerAdapter:
    """Adapter invoking the native C++ Graph Designer binary via stdin/stdout."""

    def __init__(self, bin_path: Path | str | None = None) -> None:
        if bin_path:
            self.bin_path = Path(bin_path).resolve()
        else:
            self.bin_path = None
            for cand in DEFAULT_GRAPH_DESIGNER_BINS:
                if cand.is_file():
                    self.bin_path = cand
                    break

    def build_graph(
        self,
        payload: dict[str, Any],
        output_format: str = "text",
    ) -> GraphResult:
        """Send nodes and relationships JSON payload to Graph Designer executable.

        Args:
            payload: Dictionary containing 'nodes' and 'relationships'.
            output_format: 'text' (human-readable banner), 'to-string' (raw graph.toString()),
                           or 'json' (structured JSON).

        Returns:
            GraphResult containing node count, edge count, and rendered output.

        Raises:
            GraphDesignerExecutionError: If the binary is missing or execution fails.
        """
        if not self.bin_path or not self.bin_path.is_file():
            raise GraphDesignerExecutionError(
                f"Graph Designer binary not found. Expected at {DEFAULT_GRAPH_DESIGNER_BINS[0]}"
            )

        json_bytes = json.dumps(payload).encode("utf-8")

        # First obtain exact graph metrics via --json
        cmd_json = [str(self.bin_path), "--json"]
        try:
            proc_json = subprocess.run(
                cmd_json,
                input=json_bytes,
                capture_output=True,
                check=False,
            )
        except OSError as err:
            raise GraphDesignerExecutionError(
                f"Failed to execute Graph Designer at {self.bin_path}: {err}"
            ) from err

        if proc_json.returncode != 0:
            err_msg = proc_json.stderr.decode("utf-8", errors="replace").strip()
            raise GraphDesignerExecutionError(
                f"Graph Designer exited with code {proc_json.returncode}: {err_msg}"
            )

        try:
            json_data = json.loads(proc_json.stdout.decode("utf-8", errors="replace"))
            node_count = int(json_data.get("node_count", 0))
            edge_count = int(json_data.get("edge_count", 0))
        except (ValueError, KeyError) as err:
            raise GraphDesignerExecutionError(
                f"Invalid JSON returned by Graph Designer: {err}"
            ) from err

        if output_format == "json":
            rendered_text = proc_json.stdout.decode("utf-8", errors="replace")
            return GraphResult(
                node_count=node_count,
                edge_count=edge_count,
                rendered_text=rendered_text,
                json_data=json_data,
            )

        # Obtain human-readable text output
        flag = "--to-string" if output_format == "to-string" else ""
        cmd_text = [str(self.bin_path)]
        if flag:
            cmd_text.append(flag)

        try:
            proc_text = subprocess.run(
                cmd_text,
                input=json_bytes,
                capture_output=True,
                check=False,
            )
        except OSError as err:
            raise GraphDesignerExecutionError(
                f"Failed to execute Graph Designer text rendering: {err}"
            ) from err

        if proc_text.returncode != 0:
            err_msg = proc_text.stderr.decode("utf-8", errors="replace").strip()
            raise GraphDesignerExecutionError(
                f"Graph Designer text rendering exited with code {proc_text.returncode}: {err_msg}"
            )

        rendered_text = proc_text.stdout.decode("utf-8", errors="replace")

        return GraphResult(
            node_count=node_count,
            edge_count=edge_count,
            rendered_text=rendered_text,
            json_data=json_data,
        )
