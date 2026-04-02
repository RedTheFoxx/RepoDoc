"""Go AST analyzer using tree-sitter."""

import logging
import os
import traceback
from typing import List, Optional
from pathlib import Path

from tree_sitter import Parser, Language
import tree_sitter_go

from src.analysis.models.core import Node, CallRelationship


logger = logging.getLogger(__name__)


class GoASTAnalyzer:
    """Analyzer for Go source code using tree-sitter."""

    SUPPORTED_EXTENSIONS = [".go"]

    def __init__(self, file_path: str, content: str, repo_path: str = None):
        self.file_path = Path(file_path)
        self.content = content
        self.repo_path = repo_path or ""
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []

        self.top_level_nodes = {}
        self.seen_relationships = set()

        self.current_package = "main"
        self.current_struct = None

        try:
            language_capsule = tree_sitter_go.language()
            self.go_language = Language(language_capsule)
            self.parser = Parser(self.go_language)
        except Exception as e:
            logger.error(f"Failed to initialize Go parser: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.parser = None
            self.go_language = None

    def _add_relationship(self, relationship: CallRelationship) -> bool:
        rel_key = (relationship.caller, relationship.callee, relationship.call_line)
        if rel_key not in self.seen_relationships:
            self.seen_relationships.add(rel_key)
            self.call_relationships.append(relationship)
            return True
        return False

    def analyze(self) -> None:
        if self.parser is None:
            logger.warning(f"Skipping {self.file_path} - parser initialization failed")
            return

        try:
            tree = self.parser.parse(bytes(self.content, "utf8"))
            root_node = tree.root_node
            logger.debug(f"Parsed AST with root node type: {root_node.type}")

            self._extract_package(root_node)
            self._extract_functions_and_methods(root_node)
            self._extract_calls(root_node)

            logger.debug(
                f"Analysis complete: {len(self.nodes)} nodes, {len(self.call_relationships)} relationships"
            )

        except Exception as e:
            logger.error(
                f"Error analyzing Go file {self.file_path}: {e}", exc_info=True
            )

    def _extract_package(self, root_node) -> None:
        """Extract package name from the AST."""
        for child in root_node.children:
            if child.type == "package_clause":
                for pkg_child in child.children:
                    if pkg_child.type == "package_identifier":
                        self.current_package = self._get_node_text(pkg_child)
                        break
                break

    def _get_module_path(self) -> str:
        if self.repo_path:
            try:
                rel_path = os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                rel_path = str(self.file_path)
        else:
            rel_path = str(self.file_path)

        if rel_path.endswith(".go"):
            rel_path = rel_path[:-3]

        return rel_path.replace("/", ".").replace("\\", ".")

    def _get_relative_path(self) -> str:
        if self.repo_path:
            try:
                return os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                return str(self.file_path)
        else:
            return str(self.file_path)

    def _get_node_text(self, node) -> str:
        """Extract text content from a node."""
        return self.content.encode("utf8")[node.start_byte : node.end_byte].decode(
            "utf8"
        )

    def _extract_functions_and_methods(self, root_node) -> None:
        """Extract function and method declarations."""
        self._visit_node(root_node)

    def _visit_node(self, node) -> None:
        """Recursively visit nodes to find functions and methods."""
        if node.type in ("function_declaration", "method_declaration"):
            self._extract_function_or_method(node)
        elif node.type == "struct_type":
            self._extract_struct(node)

        for child in node.children:
            self._visit_node(child)

    def _extract_function_or_method(self, node) -> None:
        """Extract a function or method declaration."""
        name = None
        params = []
        is_method = False
        receiver = None

        for child in node.children:
            if child.type == "identifier":
                name = self._get_node_text(child)
            elif child.type == "parameter_list":
                params = self._extract_params(child)
            elif child.type == "parameter_declaration":
                params.append(self._get_node_text(child))
            elif child.type == "receiver":
                receiver = self._extract_receiver(child)
                is_method = True

        if not name:
            return

        docstring = self._extract_docstring(node)
        component_id = self._get_component_id(name, receiver)

        relative_path = self._get_relative_path()
        module_path = self._get_module_path()

        node_obj = Node(
            id=component_id,
            name=name,
            component_type="function" if not is_method else "method",
            file_path=relative_path,
            relative_path=module_path,
            docstring=docstring,
            source_code=self._get_node_text(node),
            depends_on=set(),
        )

        if receiver:
            node_obj.receiver = receiver

        self.nodes.append(node_obj)
        self.top_level_nodes[component_id] = node_obj

    def _extract_receiver(self, node) -> str:
        """Extract receiver type from method receiver."""
        for child in node.children:
            if child.type in ("identifier", "pointer"):
                return self._get_node_text(child)
        return ""

    def _extract_struct(self, node) -> None:
        """Extract struct declaration."""
        name = None

        for child in node.children:
            if child.type == "type_identifier":
                name = self._get_node_text(child)
                break
            elif child.type == "field_declaration":
                for fc in child.children:
                    if fc.type == "field_identifier":
                        name = self._get_node_text(fc)
                        break

        if not name:
            return

        docstring = self._extract_docstring(node)
        component_id = self._get_component_id(name)
        relative_path = self._get_relative_path()
        module_path = self._get_module_path()

        node_obj = Node(
            id=component_id,
            name=name,
            component_type="struct",
            file_path=relative_path,
            relative_path=module_path,
            docstring=docstring,
            source_code=self._get_node_text(node),
            depends_on=set(),
        )

        self.nodes.append(node_obj)
        self.top_level_nodes[component_id] = node_obj
        self.current_struct = name

    def _extract_params(self, node) -> List[str]:
        """Extract function parameters."""
        params = []
        for child in node.children:
            if child.type == "parameter_declaration":
                param_text = ""
                for pc in child.children:
                    if pc.type in ("identifier", "type_identifier", "pointer"):
                        if param_text:
                            param_text += " "
                        param_text += self._get_node_text(pc)
                if param_text:
                    params.append(param_text)
        return params

    def _extract_docstring(self, node) -> str:
        """Extract docstring from comments before a node."""
        # Note: tree-sitter doesn't provide prevSibling, so we skip docstring extraction
        return ""

    def _get_component_id(self, name: str, receiver: str = None) -> str:
        """Get unique component ID."""
        module_path = self._get_module_path()

        if receiver:
            return f"{module_path}.{receiver}.{name}"
        return f"{module_path}.{name}"

    def _extract_calls(self, root_node) -> None:
        """Extract function call relationships."""
        self._find_calls(root_node)

    def _find_calls(self, node) -> None:
        """Recursively find all call expressions."""
        if node.type == "call_expression":
            self._extract_call(node)
        elif node.type == "selector_expression":
            self._extract_selector_call(node)

        for child in node.children:
            self._find_calls(child)

    def _extract_call(self, node) -> None:
        """Extract a function call."""
        func_name = None
        line = node.start_point[0] + 1

        if node.children:
            first_child = node.children[0]
            if first_child.type == "identifier":
                func_name = self._get_node_text(first_child)
            elif first_child.type == "selector_expression":
                # Handle pkg.Function() style calls
                func_name = self._get_node_text(first_child)
            elif first_child.type == "qualified_identifier":
                func_name = self._get_node_text(first_child)

        if not func_name:
            return

        # Find the caller (current function/method)
        caller_id = self._find_current_function(node)

        if caller_id:
            relationship = CallRelationship(
                caller=caller_id,
                callee=func_name,
                call_line=line,
                is_resolved=False,
            )
            self._add_relationship(relationship)

    def _extract_selector_call(self, node) -> None:
        """Extract a selector expression call (e.g., obj.Method())."""
        if len(node.children) < 2:
            return

        # Get the method name (last child that's a field_identifier)
        field_identifier = None
        for child in reversed(node.children):
            if child.type == "field_identifier":
                field_identifier = self._get_node_text(child)
                break

        if not field_identifier:
            return

        line = node.start_point[0] + 1
        caller_id = self._find_current_function(node)

        if caller_id:
            # Try to construct full callee
            receiver_text = ""
            for child in node.children:
                if child.type not in ("field_identifier",):
                    receiver_text = self._get_node_text(child)
                    break

            full_callee = (
                f"{receiver_text}.{field_identifier}"
                if receiver_text
                else field_identifier
            )

            relationship = CallRelationship(
                caller=caller_id,
                callee=full_callee,
                call_line=line,
                is_resolved=False,
            )
            self._add_relationship(relationship)

    def _find_current_function(self, node) -> str:
        """Find the current function/method containing this node."""
        # Walk up the tree to find the enclosing function
        parent = node.parent
        while parent:
            if parent.type in ("function_declaration", "method_declaration"):
                # Find the function name
                for child in parent.children:
                    if child.type == "identifier":
                        func_name = self._get_node_text(child)
                        # Check for receiver
                        receiver = None
                        for c in parent.children:
                            if c.type == "receiver":
                                receiver = self._extract_receiver(c)
                        return self._get_component_id(func_name, receiver)
            parent = parent.parent
        return None


def analyze_go_file(
    file_path: str, content: str, repo_path: str = None
) -> tuple[List[Node], List[CallRelationship]]:
    """Analyze a Go source file and return nodes and call relationships."""
    analyzer = GoASTAnalyzer(file_path, content, repo_path)
    analyzer.analyze()
    logger.info(
        f"Found {len(analyzer.nodes)} top-level nodes, {len(analyzer.call_relationships)} calls"
    )
    return analyzer.nodes, analyzer.call_relationships
