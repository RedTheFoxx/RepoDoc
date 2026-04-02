"""Extract code components from specific git commits."""

import ast
import logging
import os
import subprocess
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GitCodeExtractor:
    """Extract code components from specific git commits."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = os.path.abspath(repo_path)

    def get_file_content_at_commit(self, file_path: str, commit: str) -> Optional[str]:
        """Get file content at specific commit.

        Args:
            file_path: Path to file (relative to repo root)
            commit: Git commit hash

        Returns:
            File content as string, or None if file doesn't exist at commit
        """
        try:
            # Make path relative if absolute
            if os.path.isabs(file_path):
                file_path = os.path.relpath(file_path, self.repo_path)

            result = subprocess.run(
                ["git", "show", f"{commit}:{file_path}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
            return None
        except Exception as e:
            logger.warning(f"Failed to get file content at {commit}: {e}")
            return None

    def extract_component_at_commit(
        self, file_path: str, component_name: str, commit: str
    ) -> Optional[dict[str, Any]]:
        """Extract a specific component's code at a given commit.

        Args:
            file_path: Path to the file containing the component
            component_name: Name of the component (class/function)
            commit: Git commit hash

        Returns:
            Dict with source_code, docstring, parameters, or None if not found
        """
        content = self.get_file_content_at_commit(file_path, commit)
        if not content:
            return None

        try:
            tree = ast.parse(content)
        except SyntaxError:
            logger.warning(f"Failed to parse {file_path} at {commit}")
            return None

        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == component_name:
                    # Get source code segment
                    source_code = ast.get_source_segment(content, node)
                    if source_code is None:
                        # Fallback: extract manually
                        lines = content.split("\n")
                        source_code = "\n".join(
                            lines[node.lineno - 1 : node.end_lineno]
                        )

                    # Get docstring
                    docstring = ast.get_docstring(node)

                    # Get parameters (only for functions)
                    params = []
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if hasattr(node, "args") and node.args:
                            for arg in node.args.args:
                                params.append(arg.arg)
                            if node.args.kwonlyargs:
                                for arg in node.args.kwonlyargs:
                                    params.append(arg.arg)

                    # Get return annotation (only for functions)
                    returns = None
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.returns:
                            returns = ast.unparse(node.returns)

                    # Get base classes for classes
                    base_classes = None
                    if isinstance(node, ast.ClassDef):
                        base_classes = []
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                base_classes.append(base.id)
                            elif isinstance(base, ast.Attribute):
                                base_classes.append(ast.unparse(base))

                    return {
                        "source_code": source_code or "",
                        "docstring": docstring or "",
                        "parameters": params,
                        "returns": returns,
                        "base_classes": base_classes,
                        "start_line": node.lineno,
                        "end_line": node.end_lineno,
                        "component_type": (
                            "class" if isinstance(node, ast.ClassDef) else "function"
                        ),
                    }

        return None

    def component_exists_at_commit(
        self, file_path: str, component_name: str, commit: str
    ) -> bool:
        """Check if a component exists at a specific commit.

        Args:
            file_path: Path to the file
            component_name: Name of the component
            commit: Git commit hash

        Returns:
            True if component exists, False otherwise
        """
        result = self.extract_component_at_commit(file_path, component_name, commit)
        return result is not None

    def get_changed_components(
        self, base_commit: str, current_commit: str, file_changes: dict[str, list]
    ) -> dict[str, dict[str, Any]]:
        """Get code for all changed components between two commits.

        Args:
            base_commit: Base commit (older)
            current_commit: Current commit (newer)
            file_changes: Dict mapping file_path to list of component changes

        Returns:
            Dict mapping component_id to new code info
        """
        results = {}

        for file_path, changes in file_changes.items():
            for change in changes:
                component_name = change.get("name")
                change_type = change.get("change_type")

                if change_type in ("new_component", "api_signature_changed"):
                    # Extract from current commit (new code)
                    code_info = self.extract_component_at_commit(
                        file_path, component_name, current_commit
                    )
                    if code_info:
                        component_id = f"{file_path}:{component_name}"
                        results[component_id] = {
                            "change_type": change_type,
                            "code": code_info,
                        }

                elif change_type == "removed_component":
                    # Mark as removed - extract from base commit for reference
                    code_info = self.extract_component_at_commit(
                        file_path, component_name, base_commit
                    )
                    component_id = f"{file_path}:{component_name}"
                    results[component_id] = {
                        "change_type": change_type,
                        "old_code": code_info,
                        "exists": False,
                    }

        return results
