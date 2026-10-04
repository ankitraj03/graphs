"""Reference resolver for matching dependency tokens against repository files.

Builds O(1) indexed representations of discovered repository files and resolves
import/include targets using exact, relative, language-inferred, and include-path rules.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Sequence

from connector.models import ResolvedReference
from tokenizer.models import DependencyToken

# Supported extension variations by language family
LANG_EXTENSIONS: tuple[str, ...] = (
    ".h",
    ".hpp",
    ".hxx",
    ".cpp",
    ".c",
    ".cc",
    ".cxx",
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)


class ReferenceResolver:
    """Resolves dependency targets to actual scanned repository files."""

    def __init__(self, repo_root: Path, repo_files: Sequence[Path]) -> None:
        self.repo_root = repo_root.resolve()
        # Set of absolute canonical paths for O(1) existence checks
        self._exact_paths: set[Path] = {p.resolve() for p in repo_files}

        # Index by normalized relative path string (forward slashes, lowercase)
        self._by_rel_path: dict[str, Path] = {}
        # Index by lowercase filename (e.g. "user.h" -> [Path, ...])
        self._by_filename: dict[str, list[Path]] = defaultdict(list)
        # Index by lowercase stem (e.g. "user" -> [Path, ...])
        self._by_stem: dict[str, list[Path]] = defaultdict(list)

        for p in self._exact_paths:
            if p.is_relative_to(self.repo_root):
                rel_str = p.relative_to(self.repo_root).as_posix().lower()
                self._by_rel_path[rel_str] = p

            self._by_filename[p.name.lower()].append(p)
            self._by_stem[p.stem.lower()].append(p)

    def resolve(self, source_file: Path, token: DependencyToken) -> ResolvedReference:
        """Resolve a single DependencyToken originating from source_file against the repository.

        Returns a ResolvedReference with is_resolved=True and resolved_path if found in repo,
        or is_resolved=False and resolved_path=None if external or missing.
        """
        raw_target = token.target.strip()
        src_path = source_file.resolve()
        src_dir = src_path.parent

        # 1. Direct Tokenizer Pre-Resolved Path Check
        if token.resolved_path:
            cand = token.resolved_path.resolve()
            if cand in self._exact_paths and cand != src_path:
                return ResolvedReference(
                    raw_target=raw_target,
                    resolved_path=cand,
                    is_resolved=True,
                    confidence="DIRECT",
                    keyword=token.keyword,
                    kind=token.kind,
                )

        # Clean target string (strip quotes, angle brackets)
        clean_target = raw_target.strip("\"'<>")

        # 2. Direct Relative Path Lookup (relative to source_file's directory)
        candidate = (src_dir / clean_target).resolve()
        if candidate in self._exact_paths and candidate != src_path:
            return ResolvedReference(
                raw_target=raw_target,
                resolved_path=candidate,
                is_resolved=True,
                confidence="DIRECT",
                keyword=token.keyword,
                kind=token.kind,
            )

        # Check candidate with extensions (e.g. require('./utils') -> utils.js/ts)
        resolved_ext = self._probe_extensions(candidate, src_path)
        if resolved_ext:
            return ResolvedReference(
                raw_target=raw_target,
                resolved_path=resolved_ext,
                is_resolved=True,
                confidence="INFERRED",
                keyword=token.keyword,
                kind=token.kind,
            )

        # 3. Direct Repository-Root Relative Lookup
        root_cand = (self.repo_root / clean_target).resolve()
        if root_cand in self._exact_paths and root_cand != src_path:
            return ResolvedReference(
                raw_target=raw_target,
                resolved_path=root_cand,
                is_resolved=True,
                confidence="DIRECT",
                keyword=token.keyword,
                kind=token.kind,
            )

        resolved_root_ext = self._probe_extensions(root_cand, src_path)
        if resolved_root_ext:
            return ResolvedReference(
                raw_target=raw_target,
                resolved_path=resolved_root_ext,
                is_resolved=True,
                confidence="INFERRED",
                keyword=token.keyword,
                kind=token.kind,
            )

        # 4. Python Module Dot-Notation Lookup
        if token.keyword in ("import", "from", "__import__", "importlib.import_module") or "." in clean_target:
            py_resolved = self._resolve_python_dot_target(src_dir, clean_target, token.level, src_path)
            if py_resolved:
                return ResolvedReference(
                    raw_target=raw_target,
                    resolved_path=py_resolved,
                    is_resolved=True,
                    confidence="INFERRED",
                    keyword=token.keyword,
                    kind=token.kind,
                )

        # 5. Filename / Basename Lookup (e.g. C/C++ #include "user.h" in another folder)
        target_name = Path(clean_target).name.lower()
        if target_name in self._by_filename:
            matches = [m for m in self._by_filename[target_name] if m != src_path]
            if len(matches) == 1:
                return ResolvedReference(
                    raw_target=raw_target,
                    resolved_path=matches[0],
                    is_resolved=True,
                    confidence="INFERRED",
                    keyword=token.keyword,
                    kind=token.kind,
                )
            elif len(matches) > 1:
                # Disambiguate by matching relative path suffix or shared ancestor
                best = self._disambiguate_matches(src_path, clean_target, matches)
                if best:
                    return ResolvedReference(
                        raw_target=raw_target,
                        resolved_path=best,
                        is_resolved=True,
                        confidence="INFERRED",
                        keyword=token.keyword,
                        kind=token.kind,
                    )

        # 6. Unresolved / External Reference (stdlib, external package, or missing file)
        return ResolvedReference(
            raw_target=raw_target,
            resolved_path=None,
            is_resolved=False,
            confidence="UNRESOLVED",
            keyword=token.keyword,
            kind=token.kind,
        )

    def _probe_extensions(self, base_path: Path, src_path: Path) -> Path | None:
        """Probe common extensions and index files for a path lacking an extension."""
        for ext in LANG_EXTENSIONS:
            cand = base_path.with_suffix(ext)
            if cand in self._exact_paths and cand != src_path:
                return cand

        # Index files for JS/TS/Python packages
        for index_name in ("index.ts", "index.tsx", "index.js", "index.jsx", "__init__.py"):
            cand = base_path / index_name
            if cand in self._exact_paths and cand != src_path:
                return cand

        return None

    def _resolve_python_dot_target(
        self, src_dir: Path, target: str, level: int, src_path: Path
    ) -> Path | None:
        """Resolve Python dot-separated module paths (e.g. 'app.services.auth' or '..config')."""
        if level > 0 or target.startswith("."):
            eff_level = level if level > 0 else (len(target) - len(target.lstrip(".")))
            base_dir = src_dir
            for _ in range(max(0, eff_level - 1)):
                base_dir = base_dir.parent

            mod_part = target.lstrip(".")
            if not mod_part:
                init_file = (base_dir / "__init__.py").resolve()
                return init_file if init_file in self._exact_paths and init_file != src_path else None

            parts = [p for p in mod_part.split(".") if p]
            candidate = base_dir.joinpath(*parts).resolve()
            return self._probe_extensions(candidate, src_path)

        # Root-relative module path (e.g. 'app.models.user')
        parts = [p for p in target.split(".") if p]
        if parts:
            cand = self.repo_root.joinpath(*parts).resolve()
            resolved = self._probe_extensions(cand, src_path)
            if resolved:
                return resolved

            # Also check stem index for the final component
            last_part = parts[-1].lower()
            if last_part in self._by_stem:
                for match in self._by_stem[last_part]:
                    if match != src_path and match.suffix == ".py":
                        return match

        return None

    def _disambiguate_matches(
        self, src_path: Path, clean_target: str, matches: list[Path]
    ) -> Path | None:
        """Pick the best matching file when multiple files share the same filename."""
        norm_target = clean_target.replace("\\", "/").lower()

        # 1. Match relative suffix
        for m in matches:
            m_rel = m.relative_to(self.repo_root).as_posix().lower()
            if m_rel.endswith(norm_target):
                return m

        # 2. Pick candidate sharing the deepest directory prefix with src_path
        src_parts = src_path.parts
        best_match: Path | None = None
        max_common = -1

        for m in matches:
            m_parts = m.parts
            common = 0
            for sp, mp in zip(src_parts, m_parts, strict=False):
                if sp == mp:
                    common += 1
                else:
                    break
            if common > max_common:
                max_common = common
                best_match = m

        return best_match if best_match else matches[0]
