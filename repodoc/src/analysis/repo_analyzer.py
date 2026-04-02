"""
Repository structure analysis: file tree with include/exclude patterns.
"""

import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analysis.utils.patterns import (
    DEFAULT_IGNORE_PATTERNS,
    DEFAULT_INCLUDE_PATTERNS,
)


class RepoAnalyzer:
    def __init__(
        self,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> None:
        self.include_patterns = (
            include_patterns
            if include_patterns is not None
            else DEFAULT_INCLUDE_PATTERNS
        )
        self.exclude_patterns = (
            list(DEFAULT_IGNORE_PATTERNS) + exclude_patterns
            if exclude_patterns is not None
            else list(DEFAULT_IGNORE_PATTERNS)
        )

    def analyze_repository_structure(self, repo_dir: str) -> Dict[str, Any]:
        file_tree = self._build_file_tree(repo_dir)
        if file_tree is None:
            file_tree = {"type": "directory", "name": ".", "path": ".", "children": []}
        return {
            "file_tree": file_tree,
            "summary": {
                "total_files": self._count_files(file_tree),
                "total_size_kb": self._calculate_size(file_tree),
            },
        }

    def _build_file_tree(self, repo_dir: str) -> Optional[Dict[str, Any]]:
        # Resolve to absolute path to handle relative paths correctly
        repo_dir = str(Path(repo_dir).resolve())

        def build_tree(path: Path, base_path: Path) -> Optional[Dict[str, Any]]:
            relative_path = path.relative_to(base_path)
            relative_path_str = str(relative_path)

            if path.is_symlink():
                return None
            try:
                if not path.resolve().is_relative_to(base_path.resolve()):
                    return None
            except AttributeError:
                if not str(path.resolve()).startswith(str(base_path.resolve())):
                    return None

            if self._should_exclude_path(relative_path_str, path.name):
                return None

            if path.is_file():
                if not self._should_include_file(relative_path_str, path.name):
                    return None
                return {
                    "type": "file",
                    "name": path.name,
                    "path": relative_path_str,
                    "extension": path.suffix,
                    "_size_bytes": path.stat().st_size,
                }

            if path.is_dir():
                children = []
                try:
                    for child in sorted(path.iterdir()):
                        child_tree = build_tree(child, base_path)
                        if child_tree is not None:
                            children.append(child_tree)
                except PermissionError:
                    pass
                if children or str(relative_path) == ".":
                    return {
                        "type": "directory",
                        "name": path.name,
                        "path": relative_path_str,
                        "children": children,
                    }
                return None

            return None

        return build_tree(Path(repo_dir), Path(repo_dir))

    def _should_exclude_path(self, path: str, filename: str) -> bool:
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(filename, pattern):
                return True
            if pattern.endswith("/") and path.startswith(pattern.rstrip("/")):
                return True
            if path.startswith(pattern + "/") or path == pattern:
                return True
            if pattern in path.split("/"):
                return True
        return False

    def _should_include_file(self, path: str, filename: str) -> bool:
        if not self.include_patterns:
            return True
        for pattern in self.include_patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(filename, pattern):
                return True
        return False

    def _count_files(self, tree: Dict[str, Any]) -> int:
        if tree.get("type") == "file":
            return 1
        return sum(self._count_files(c) for c in tree.get("children", []))

    def _calculate_size(self, tree: Dict[str, Any]) -> float:
        if tree.get("type") == "file":
            return tree.get("_size_bytes", 0) / 1024
        return sum(self._calculate_size(c) for c in tree.get("children", []))
