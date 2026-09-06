---
name: python-static-analysis
description: >-
  Static analysis methodology for Python target code in the `graphs` repository analyzer.
  Extracts modules, imports, classes, functions, calls, inheritance, decorators, and type annotations
  using AST-based parsing while maintaining strict evidence tracking and relationship confidence.
---

# Python Static Analysis

This skill defines the static analysis methodology for parsing and analyzing Python code within target repositories scanned by `graphs`.

---

## 1. Analysis Principles

1. **AST Over Regex**: Never use regular expressions to parse Python code. Always use Python's built-in `ast` module (or modern concrete syntax tree tools) to obtain a deterministic syntax tree.
2. **Never Invent Relationships**: If a relationship cannot be proven from syntax or deterministic static inference, do NOT create speculative edges. Record it as unresolved or omit it.
3. **Preserve Precise Source Locations**: Every extracted symbol, definition, and reference must record its source file, `lineno`, `col_offset`, `end_lineno`, and `end_col_offset`.
4. **Resilience to Malformed Syntax**: Syntax errors, incompatible Python version syntax, or encoding errors in individual files must be captured cleanly as diagnostic events and must never crash the broader repository scan.

---

## 2. Extraction Taxonomy

The Python static analyzer must extract and classify the following syntactic entities:

| Entity Kind | AST Nodes | Extracted Metadata |
| :--- | :--- | :--- |
| **Package** | Directory containing `__init__.py` or namespace dir | Package name, canonical path, init file path |
| **Module** | `ast.Module` | Module name, docstring, file path, is_init flag |
| **Import** | `ast.Import`, `ast.ImportFrom` | Target module, imported names, aliases (`asname`), level (relative imports) |
| **Class** | `ast.ClassDef` | Name, docstring, bases (inheritance), decorators, keywords, location |
| **Function** | `ast.FunctionDef`, `ast.AsyncFunctionDef` (module-level) | Name, docstring, arguments, return type annotation, decorators, location |
| **Method** | `ast.FunctionDef`, `ast.AsyncFunctionDef` (class-level) | Method name, kind (instance, `@classmethod`, `@staticmethod`), location |
| **Decorator** | Expressions inside `.decorator_list` | Decorator name/expression, arguments |
| **Call** | `ast.Call` | Called function/expression, arguments, location |
| **Type Usage** | `ast.AnnAssign`, function annotations, `ast.TypeAlias` | Referenced type names, generic parameters |
| **Variable** | `ast.Assign`, `ast.AnnAssign` (module/class level) | Variable name, type annotation if present, is_constant flag |

---

## 3. Relationship Classification & Evidence

To maintain query integrity, every relationship edge emitted by the Python analyzer must carry an explicit **Evidence Tier**:

### Tier 1: Directly Observed (Syntactic Facts)
Directly stated in the AST with zero ambiguity:
- `Module CONTAINS Class` (Class is defined inside module scope).
- `Class CONTAINS Method` (Method is defined inside class body).
- `Module IMPORTS Module` (Explicit `import os`).
- `Class INHERITS Class` (Direct base class expression `class Child(Parent):`).
- `Function CALLS Function` (Syntactic call expression `foo()` within caller's body).
- `Function DEFINES Variable` (Assignment in function scope).

### Tier 2: Statically Inferred (Resolved via Context)
Derived through deterministic static resolution:
- **Import Resolution**: Resolving `from mypkg.utils import helper` to the specific file `mypkg/utils.py` using repository package roots and `sys.path` rules.
- **Type-Inferred Calls**: Resolving `obj.process()` to `Service.process()` when `obj` has an explicit type annotation `obj: Service`.
- **Method Resolution Order (MRO)**: Resolving inherited method dispatch across a static class hierarchy.

### Tier 3: Unresolved / Ambiguous (Flagged Explicitly)
Relationships that cannot be determined with complete certainty:
- **Dynamic Imports**: `importlib.import_module(variable_name)`, `__import__(name)`.
- **Dynamic Dispatches / Reflection**: `getattr(obj, func_name)()`.
- **Duck-Typed Calls**: Calling `x.save()` where `x` has no type annotation and multiple classes define `.save()`.
- **Conditional Imports**: Imports inside `if sys.version_info < (3, 10):` or `try ... except ImportError:`.
- **Rule**: If a target cannot be resolved to a definitive node, emit an `UnresolvedReference` node or tag the edge with `confidence="UNRESOLVED"`. Never arbitrarily link to a random matching name.

---

## 4. AST Visitor Architecture

Implement analysis using `ast.NodeVisitor` with structured scope management:

```python
import ast
from dataclasses import dataclass, field
from pathlib import Path
from graphs.core.models import Node, Edge, SourceLocation

@dataclass
class PythonAnalysisScope:
    module_id: str
    current_scope: list[str] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

class PythonASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path, module_id: str) -> None:
        self.file_path = file_path
        self.module_id = module_id
        self.scope = PythonAnalysisScope(module_id=module_id)
        self._scope_stack: list[str] = [module_id]

    def _current_scope_id(self) -> str:
        return "::".join(self._scope_stack)

    def _get_location(self, node: ast.AST) -> SourceLocation:
        return SourceLocation(
            file_path=self.file_path,
            start_line=getattr(node, "lineno", 0),
            start_column=getattr(node, "col_offset", 0),
            end_line=getattr(node, "end_lineno", getattr(node, "lineno", 0)),
            end_column=getattr(node, "end_col_offset", getattr(node, "col_offset", 0)),
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.scope.edges.append(
                Edge(
                    source=self.module_id,
                    target=alias.name,
                    kind="IMPORTS",
                    evidence=f"import {alias.name}",
                    location=self._get_location(node),
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module_name = "." * node.level + (node.module or "")
        for alias in node.names:
            target = f"{module_name}.{alias.name}" if module_name else alias.name
            self.scope.edges.append(
                Edge(
                    source=self.module_id,
                    target=target,
                    kind="IMPORTS",
                    evidence=f"from {module_name} import {alias.name}",
                    location=self._get_location(node),
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_id = f"{self._current_scope_id()}::{node.name}"
        class_node = Node(
            id=class_id,
            kind="CLASS",
            name=node.name,
            location=self._get_location(node),
        )
        self.scope.nodes.append(class_node)
        self.scope.edges.append(
            Edge(
                source=self._current_scope_id(),
                target=class_id,
                kind="CONTAINS",
                evidence="class_definition",
            )
        )

        # Extract inheritance
        for base in node.bases:
            base_name = ast.unparse(base)
            self.scope.edges.append(
                Edge(
                    source=class_id,
                    target=base_name,
                    kind="INHERITS",
                    evidence=f"base: {base_name}",
                    location=self._get_location(base),
                )
            )

        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node, is_async=True)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        is_method = len(self._scope_stack) > 1 and not self._scope_stack[-1].endswith(".py")
        func_id = f"{self._current_scope_id()}::{node.name}"
        kind = "METHOD" if is_method else "FUNCTION"

        self.scope.nodes.append(
            Node(
                id=func_id,
                kind=kind,
                name=node.name,
                location=self._get_location(node),
            )
        )
        self.scope.edges.append(
            Edge(
                source=self._current_scope_id(),
                target=func_id,
                kind="CONTAINS",
                evidence="function_definition",
            )
        )

        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        callee_name = ast.unparse(node.func)
        self.scope.edges.append(
            Edge(
                source=self._current_scope_id(),
                target=callee_name,
                kind="CALLS",
                evidence=f"call: {callee_name}",
                location=self._get_location(node),
            )
        )
        self.generic_visit(node)
```

---

## 5. Handling Python Complexities

1. **Relative Imports (`.` and `..`)**:
   - Compute relative package offsets using the current module's position relative to the repository package root.
   - If a relative import ascends beyond the package root, flag it as an unresolved external import.
2. **Type-Checking Guards (`if TYPE_CHECKING:`)**:
   - Parse blocks guarded by `TYPE_CHECKING`.
   - Distinguish runtime imports from type-only imports: tag type-only imports with `evidence="type_checking_import"`. This prevents false cycle alerts when cyclic imports are safe at runtime.
3. **`__all__` Exports**:
   - Inspect `__all__` assignments (e.g. `__all__ = ["Foo", "bar"]`).
   - Mark matching entities as `is_exported=True`.
4. **Encoding & Malformed Source**:
   - Use `tokenize.open(file_path)` or read binary with fallback decoding (UTF-8, then latin-1) to detect PEP 263 encoding declarations (`# -*- coding: ... -*-`).

