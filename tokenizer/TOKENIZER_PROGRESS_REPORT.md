# Tokenizer Progress Report

## 1. Executive Summary

The `tokenizer/` directory contains a single-file dependency and lexical tokenizer written in Python (Python 3.12+ compliant, running on standard library `ast`, `tokenize`, `dataclasses`, and `re`). 

It is designed to operate strictly on **one file at a time**, returning structured arrays (Python `list`) of dependency tokens (`DependencyToken`), low-level lexical tokens (`Token`), unique dependency targets, and connecting keywords (e.g. `import`, `from`, `#include`, `require`). It supports three language families: **Python**, **C/C++**, and **JavaScript/TypeScript**.

All 25 automated unit and integration tests currently pass. Directory-level traversal was explicitly decoupled in commit `3e67df6` to enforce a clean separation of concerns. The tokenizer is ready to receive file paths from a scanner or orchestration pipeline, but no bridge currently connects it to the C++ `scanner/`.

```text
Input File Path / Code String
              │
              ▼
FileTokenizer (Language Dispatcher by Extension)
              │
   ┌──────────┼──────────┐
   ▼          ▼          ▼
Python       C++       JS/TS
Tokenizer  Tokenizer  Tokenizer
 (AST +      (Regex)   (Regex)
Fallback)
   │          │          │
   └──────────┬──────────┘
              ▼
   list[DependencyToken] / list[Token] / list[str]
```

---

## 2. Current Architecture

The tokenizer implements a class-based hierarchy rooted in `BaseTokenizer`:

- **Contract (`BaseTokenizer`)**: Abstract base class requiring `tokenize()`, `tokenize_source()`, and `get_all_tokens()`. Provides default implementations for `get_dependencies()` and `get_connecting_keywords()`.
- **Facade (`FileTokenizer`)**: Unified entry point. Inspects file extensions and delegates to the appropriate language tokenizer.
- **Language Tokenizers**:
  - `PythonTokenizer`: Uses Python's standard `ast` module for syntax parsing. Employs a regex-based fallback scanner (`_extract_from_tokens_and_lines`) if AST parsing raises `SyntaxError`.
  - `CppTokenizer`: Uses regex to extract `#include <...>`, `#include "..."`, and C++20 `import ...;`.
  - `JavaScriptTokenizer`: Uses regex to extract ES6 `import`, CommonJS `require()`, ES6 `export ... from`, and dynamic `import()`.
- **Data Models (`models.py`)**: Memory-efficient data structures using `@dataclass(frozen=True, slots=True)` and string interning (`sys.intern`) for repeated keywords and kinds.

---

## 3. Implemented Features

| Feature | Classification | Description |
| :--- | :--- | :--- |
| Single-File Processing Contract | `IMPLEMENTED + TESTED` | Processes one file at a time; all methods return arrays (`list`). |
| Language Dispatch by Extension | `IMPLEMENTED + TESTED` | Maps `.py`, `.c`, `.cpp`, `.ts`, `.js`, etc., to the correct tokenizer. |
| Python AST Import Extraction | `IMPLEMENTED + TESTED` | Extracts `import x`, `import x.y as z`, `from a import b`. |
| Python Relative Import Resolution | `IMPLEMENTED + TESTED` | Resolves `from . import x`, `from ..dir import y` to local filesystem paths. |
| Python Dynamic Import Extraction | `IMPLEMENTED + TESTED` | Identifies `__import__('name')` and `importlib.import_module('name')`. |
| Python Syntax-Error Resilience | `IMPLEMENTED + TESTED` | Gracefully falls back to lexical/regex scanning when AST parsing fails. |
| C/C++ System & Local `#include` | `IMPLEMENTED + TESTED` | Differentiates `#include <sys>` from `#include "local.h"`. |
| C++20 Module Import Detection | `IMPLEMENTED + TESTED` | Extracts `import module_name;` and `import <header>;`. |
| JS/TS ES6 `import` Extraction | `IMPLEMENTED + TESTED` | Extracts named, default, and side-effect ES6 imports. |
| JS/TS CommonJS `require()` | `IMPLEMENTED + TESTED` | Extracts `require('target')` calls. |
| JS/TS `export ... from` Re-exports | `IMPLEMENTED + TESTED` | Extracts re-export targets and paths. |
| JS/TS Dynamic `import()` | `IMPLEMENTED + TESTED` | Extracts `import('target')` promise expressions. |
| JS/TS Local Path Resolution | `IMPLEMENTED + TESTED` | Resolves relative targets against `.ts`, `.tsx`, `.js`, and `/index.js`. |
| Evidence & Location Retention | `IMPLEMENTED + TESTED` | Captures start/end line and column, and verbatim source code snippet. |
| Memory Optimization | `IMPLEMENTED + TESTED` | `slots=True`, `frozen=True`, and `sys.intern` on frequent strings. |
| Low-Level Python Tokens | `IMPLEMENTED + TESTED` | `get_all_tokens` wraps `tokenize.tokenize` with standard Python token types. |
| Low-Level C++ / JS Tokens | `PARTIALLY IMPLEMENTED` | Implemented via regex; lacks C++ keyword categorization and multi-line comment support. |
| True AST Parsing for C++ / JS | `NOT IMPLEMENTED` | C++ and JS rely on regex patterns rather than full AST parsers (e.g. tree-sitter/Clang). |
| Scanner Pipeline Integration | `NOT IMPLEMENTED` | No orchestrator exists to pipe scanner results into `FileTokenizer`. |

---

## 4. Tokenization Flow

```text
1. FileTokenizer.tokenize(file_path)
   │
   ├── Resolve file path & check existence (raises FileNotFoundTokenizerError if missing)
   ├── Match file extension against SUPPORTED_EXTENSIONS
   │     └── Raise UnsupportedLanguageError if unmapped
   │
2. Delegate to Language Tokenizer (e.g., PythonTokenizer)
   │
   ├── Read source code (with encoding fallback / tokenize.open)
   │
   ├── Extraction Strategy:
   │     ├── Python:
   │     │     ├── Try ast.parse() -> walk AST -> collect DependencyToken
   │     │     └── If SyntaxError -> fallback line-by-line regex scanner
   │     ├── C++:
   │     │     └── Line-by-line regex matching INCLUDE_PATTERN and CPP20_IMPORT_PATTERN
   │     └── JS/TS:
   │           └── Line-by-line regex matching ES6 import, require(), export from, import()
   │
3. Local Dependency Resolution:
   │     └── If target is relative, resolve against project_root or current_file.parent
   │
4. Return list[DependencyToken]
```

---

## 5. Token Types

The tokenizer operates with two primary token models:

### 1. `DependencyToken`
Represents a cross-file or cross-module dependency relationship:
- `keyword` (`str`): Connecting keyword (`"import"`, `"from"`, `"#include"`, `"require"`, `"export"`, `"__import__"`).
- `target` (`str`): Referenced target identifier (e.g. `"os"`, `".config"`, `"iostream"`, `"react"`).
- `kind` (`str`): Classification (`"IMPORT"`, `"IMPORT_FROM"`, `"DYNAMIC_IMPORT"`, `"INCLUDE_SYSTEM"`, `"INCLUDE_LOCAL"`, `"MODULE_IMPORT"`, `"ES_IMPORT"`, `"CJS_REQUIRE"`, `"ES_EXPORT_FROM"`).
- `location` (`SourceLocation`): `file_path`, `start_line`, `start_column`, `end_line`, `end_column`.
- `snippet` (`str`): Verbatim source line(s) where the dependency occurred.
- `symbols` (`tuple[str, ...]`): Specific imported names/symbols (e.g. `("Node", "Edge")`).
- `is_relative` (`bool`): Whether the import uses relative navigation (`.`, `..`).
- `level` (`int`): Depth level for relative imports.
- `resolved_path` (`Path | None`): Concrete resolved local filesystem path, if resolvable.

### 2. `Token`
Represents low-level lexical tokens extracted by `get_all_tokens()`:
- `kind` (`str`): Lexical kind (`"NAME"`, `"NUMBER"`, `"STRING"`, `"OP"`, `"COMMENT"`, `"KEYWORD"`, `"PREPROCESSOR"`, `"PUNCTUATION"`, `"IDENTIFIER"`).
- `value` (`str`): Raw string text of the token.
- `location` (`SourceLocation`): File location coordinates.

---

## 6. Important Files / Classes

- [`base.py`](file:///d:/graphs/tokenizer/base.py): Abstract base class `BaseTokenizer` defining the method contracts and default helper implementations for `get_dependencies()` and `get_connecting_keywords()`.
- [`models.py`](file:///d:/graphs/tokenizer/models.py): Frozen, slotted dataclasses `SourceLocation`, `Token`, and `DependencyToken` with dictionary serialization.
- [`exceptions.py`](file:///d:/graphs/tokenizer/exceptions.py): Exception hierarchy rooted in `GraphsError`: `TokenizerError`, `LexerScanError`, `FileNotFoundTokenizerError`, `UnsupportedLanguageError`.
- [`file_tokenizer.py`](file:///d:/graphs/tokenizer/file_tokenizer.py): Facade class `FileTokenizer` providing language dispatch and unified single-file analysis.
- [`python_tokenizer.py`](file:///d:/graphs/tokenizer/python_tokenizer.py): Python AST and fallback regex dependency extractor and `tokenize.tokenize` lexer.
- [`cpp_tokenizer.py`](file:///d:/graphs/tokenizer/cpp_tokenizer.py): C/C++ regex-based include and module extractor.
- [`javascript_tokenizer.py`](file:///d:/graphs/tokenizer/javascript_tokenizer.py): JavaScript and TypeScript regex-based import, require, and export extractor.
- [`__init__.py`](file:///d:/graphs/tokenizer/__init__.py): Public package interface exposing all tokenizers, data models, and exceptions.

---

## 7. Input / Output Format

### Input
- **File Input**: File path as `pathlib.Path` or `str` passed to `tokenize(file_path)`.
- **String Input**: Source string passed to `tokenize_source(source, language=...)`.
- **Optional Context**: `project_root` passed to `FileTokenizer` constructor for resolving workspace-wide relative paths.

### Output
- **Dependency Tokens**: `list[DependencyToken]` — Rich objects containing symbol names, snippets, and exact line/column locations.
- **Dependency Target Names**: `list[str]` — Array of unique string target names returned by `get_dependencies()`.
- **Connecting Keywords**: `list[str]` — Array of unique connecting keywords returned by `get_connecting_keywords()`.
- **Lexical Tokens**: `list[Token]` — Array of low-level tokens returned by `get_all_tokens()`.
- **Serialization**: Each token object provides `.to_dict()` for clean JSON serialization.

---

## 8. Testing Performed

### Test 1 — Existing Project Test Suite (`run_tests.py`)
- **Suite**: 25 automated tests in `tests/test_tokenizer.py` and `tests/test_project_dependency_scan.py`.
- **Checks**: Python standard imports, relative imports, dynamic imports, AST syntax error fallback, C++ `#include`, C++20 modules, JS/TS imports/requires/exports, unified file dispatch, serialization, and edge cases.
- **Result**: Passed (25/25 tests in 0.576s).

### Test 2 — Basic Code (Test A)
- **Setup**: Source file containing variables, function definitions, for loops, if conditions, and mathematical operations (`basic.py`).
- **Result**: Passed. Extracted 60 lexical tokens (`NAME`, `OP`, `NUMBER`, `INDENT`, `DEDENT`, etc.) and 1 dependency token (`math`).

### Test 3 — Keywords (Test B)
- **Setup**: Tested connecting keywords across Python (`import`, `from`), C++ (`#include`, `import`), and JS (`import`, `require`, `export`, `import()`). Also tested JS lexical keywords (`const`, `function`, `class`).
- **Result**: Passed. All connecting and language-specific keywords correctly identified.

### Test 4 — Identifiers (Test C)
- **Setup**: Tested class, variable, and function identifiers (`class MyService { int count_value; void executeQuery(); };`).
- **Result**: Passed. Identifiers extracted across all three languages.

### Test 5 — Strings (Test D)
- **Setup**: Tested single-line, double-quote, triple-quote, Python f-strings, and JS template literals.
- **Result**: Passed. String tokens captured with delimiters and contents intact.

### Test 6 — Comments (Test E)
- **Setup**: Tested single-line comments (`//`, `#`) and multi-line comments (`/* ... */`).
- **Result**: Single-line comments passed and were excluded from dependency extraction. A bug was identified: multi-line comments spanning across line breaks are not recognized as a single comment in C++/JS `get_all_tokens()` because regex execution runs per-line.

### Test 7 — Operators and Punctuation (Test F)
- **Setup**: Tested arithmetic, indexing, type arrows, and brackets (`a = (b + c) * d[0] -> None`).
- **Result**: Passed. Lexical operators accurately parsed.

### Test 8 — Nested / Complex Realistic Code (Test G)
- **Setup**: Complex Python file (`complex.py`) containing stdlib imports, multi-symbol imports, relative imports, alias imports, class inheritance, and dynamic `__import__`.
- **Result**: Passed. All 7 dependencies extracted with accurate `kind`, `target`, `symbols`, and relative levels.

### Test 9 — Invalid / Edge Cases (Test H)
- **Setup**: Tested unparseable syntax error, empty file, nonexistent file, and unsupported file extension.
- **Result**:
  - Python syntax error: AST failed, fallback scanner cleanly extracted valid imports.
  - Empty file: Returned empty list `[]`.
  - Nonexistent file: Correctly raised `FileNotFoundTokenizerError`.
  - Unsupported extension: Correctly raised `UnsupportedLanguageError`.
  - C++ inline comments: Handled cleanly without polluting include targets.

---

## 9. Test Results Summary

| Test Case | Scenario / Target | Expected Result | Observed Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| Existing Suite | 25 Unit & Integration tests | All 25 pass | 25 passed in 0.576s | **PASS** |
| Test A | Basic code structure | Lexical + dep tokens | 60 lex tokens, 1 dep token | **PASS** |
| Test B | Connecting & lexical keywords | Identify connecting keywords | All keywords identified | **PASS** |
| Test C | Identifiers across languages | Extract identifier tokens | All identifiers extracted | **PASS** |
| Test D | Strings (double, single, f-str, `) | Captured as string tokens | All formats captured | **PASS** |
| Test E | Single-line & multi-line comments | Filtered from deps | Single-line OK; multi-line regex issue | **PARTIAL** |
| Test F | Operators & punctuation | Classified as OP / PUNCTUATION | All operators captured | **PASS** |
| Test G | Complex code with inheritance | 7 dependencies extracted | 7/7 dependencies extracted | **PASS** |
| Test H.1 | Python syntax error | Fallback regex activates | 3/3 imports recovered | **PASS** |
| Test H.2 | Empty file | Return empty list `[]` | Returned `[]` | **PASS** |
| Test H.3 | Nonexistent file | Raise `FileNotFoundTokenizerError` | Raised as expected | **PASS** |
| Test H.4 | Unsupported extension | Raise `UnsupportedLanguageError` | Raised as expected | **PASS** |

---

## 10. Current Limitations

1. **Regex-Based C++ and JS Tokenizers**: While Python uses full AST parsing with lexical fallback, C++ and JS depend solely on regular expressions. They do not build ASTs, meaning complex macro expansions, conditional compilation (`#ifdef`), or dynamic computed requires cannot be analyzed.
2. **Multi-line Comment Lexing Across Lines**: In `cpp_tokenizer.py` and `javascript_tokenizer.py`, `get_all_tokens()` splits the file by lines (`source.splitlines()`) and applies regex matching per line. A multi-line comment spanning multiple lines will fail to match the single-line regex.
3. **C++ Keyword Classification**: In `CppTokenizer.get_all_tokens()`, language keywords (such as `class`, `int`, `return`, `virtual`) are grouped under `IDENTIFIER` rather than `KEYWORD`.
4. **No External vs Internal Disambiguation**: The tokenizer does not query the environment or package manifests (e.g. `package.json`, `pyproject.toml`) to determine whether a target like `requests` or `vector` is a standard-library module, a third-party package, or a local file.
5. **No Direct Scanner Bridge**: There is no module or script that feeds discovered paths from `scanner/` into `FileTokenizer`.

---

## 11. Bugs / Issues Found

1. **Multi-line Comment Regex Split**: In `cpp_tokenizer.py` (lines 143–144) and `javascript_tokenizer.py` (lines 176–177), `get_all_tokens` runs `for line in source.splitlines(): for m in token_regex.finditer(line)`. Because `re.DOTALL` cannot cross line boundaries when fed individual lines, multi-line block comments (`/* ... */`) that span multiple lines are broken into punctuation and identifiers.
2. **Multi-line Comment Bypassing in C++ `tokenize_source`**: In `cpp_tokenizer.py` (line 63), the comment check only tests `if stripped.startswith("//") or stripped.startswith("/*"): continue`. If a multi-line comment starts on line 1 and ends on line 3, line 2 is not skipped. If line 2 contains `#include <fake.h>`, it would be falsely extracted.

---

## 12. Git Development History

The Git repository documents the following development milestones for the tokenizer:

- **2026-09-06 (`1b958c1`) — *tokenizer***: Initial implementation of `FileTokenizer`, `PythonTokenizer`, `CppTokenizer`, `JavaScriptTokenizer`, `models.py`, `exceptions.py`, `base.py`, and comprehensive test suites (`test_tokenizer.py`, `test_project_dependency_scan.py`).
- **2026-09-06 (`15c3013`) — *Add .gitignore and untrack pycache bytecode files***: Removed compiled `.pyc` files from version control and configured `.gitignore`.
- **2026-09-06 (`3e67df6`) — *Refactor tokenizer to single-file processing and remove scan_directory***: Decoupled directory scanning from tokenization by removing `scan_directory` from `FileTokenizer`, ensuring the tokenizer adheres to single-file processing.

---

## 13. Current Development Status

- **Status**: `IMPLEMENTED + TESTED` (Single-file tokenization and dependency extraction are solid and verified).
- **Python Tokenizer**: `WORKING` (Full AST parsing, relative imports, dynamic imports, syntax error recovery).
- **C++ Tokenizer**: `WORKING` (Regex-based include and C++20 module extraction).
- **JavaScript Tokenizer**: `WORKING` (Regex-based ES6 import/export and CommonJS require extraction).
- **Test Suite**: `WORKING` (25/25 unit tests passing).
- **Integration with Scanner**: `NOT IMPLEMENTED` (Bridge pipeline missing).

---

## 14. Recommended Next Steps

1. **Fix Multi-line Comment Processing**: Update `CppTokenizer` and `JavaScriptTokenizer` to tokenize over the entire source string or maintain a multi-line comment state machine across lines.
2. **Add C++ Keyword Dictionary**: Define a standard C++ keyword set in `CppTokenizer.get_all_tokens()` so keywords are categorized as `KEYWORD` rather than `IDENTIFIER`.
3. **Build the Integration / Orchestration Layer**: Create a pipeline component (`pipeline/` or `scanner/` orchestrator) that takes discovered paths from the scanner, batches them, and invokes `FileTokenizer.tokenize()` concurrently across worker processes (`ProcessPoolExecutor`).
4. **Symbol Table & Graph Store Integration**: Pipe `DependencyToken` arrays into the symbol resolution table and graph store as specified in `AGENTS.md`.
