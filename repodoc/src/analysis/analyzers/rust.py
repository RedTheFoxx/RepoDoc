"""Rust AST analyzer using tree-sitter."""

import logging
import os
import traceback
from typing import List, Optional
from pathlib import Path

from tree_sitter import Parser, Language
import tree_sitter_rust

from src.analysis.models.core import Node, CallRelationship


logger = logging.getLogger(__name__)


class RustASTAnalyzer:
    """Analyzer for Rust source code using tree-sitter."""

    SUPPORTED_EXTENSIONS = [".rs"]

    def __init__(self, file_path: str, content: str, repo_path: str = None):
        self.file_path = Path(file_path)
        self.content = content
        self.repo_path = repo_path or ""
        self.nodes: List[Node] = []
        self.call_relationships: List[CallRelationship] = []

        self.top_level_nodes = {}
        self.seen_relationships = set()

        self.current_impl = None
        self.current_trait = None

        try:
            language_capsule = tree_sitter_rust.language()
            self.rust_language = Language(language_capsule)
            self.parser = Parser(self.rust_language)
        except Exception as e:
            logger.error(f"Failed to initialize Rust parser: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.parser = None
            self.rust_language = None

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

            self._extract_items(root_node)
            self._extract_calls(root_node)

            logger.debug(
                f"Analysis complete: {len(self.nodes)} nodes, {len(self.call_relationships)} relationships"
            )

        except Exception as e:
            logger.error(
                f"Error analyzing Rust file {self.file_path}: {e}", exc_info=True
            )

    def _get_module_path(self) -> str:
        if self.repo_path:
            try:
                rel_path = os.path.relpath(str(self.file_path), self.repo_path)
            except ValueError:
                rel_path = str(self.file_path)
        else:
            rel_path = str(self.file_path)

        if rel_path.endswith(".rs"):
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

    def _extract_items(self, root_node) -> None:
        """Extract top-level items (functions, structs, impls, traits, etc.)."""
        self._visit_item(root_node)

    def _visit_item(self, node) -> None:
        """Recursively visit nodes to find items."""
        if node.type == "function_item":
            self._extract_function(node)
        elif node.type == "struct_item":
            self._extract_struct(node)
        elif node.type == "impl_item":
            self._extract_impl(node)
        elif node.type == "trait_item":
            self._extract_trait(node)
        elif node.type == "enum_item":
            self._extract_enum(node)

        for child in node.children:
            self._visit_item(child)

    def _extract_function(self, node) -> None:
        """Extract a function declaration."""
        name = None
        params = []

        for child in node.children:
            if child.type == "identifier":
                name = self._get_node_text(child)
            elif child.type == "parameters":
                params = self._extract_params(child)

        if not name:
            return

        docstring = self._extract_docstring(node)
        component_id = self._get_component_id(name)
        relative_path = self._get_relative_path()
        module_path = self._get_module_path()

        node_obj = Node(
            id=component_id,
            name=name,
            component_type="function",
            file_path=relative_path,
            relative_path=module_path,
            docstring=docstring,
            source_code=self._get_node_text(node),
            depends_on=set(),
        )

        self.nodes.append(node_obj)
        self.top_level_nodes[component_id] = node_obj

    def _extract_struct(self, node) -> None:
        """Extract a struct declaration."""
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

    def _extract_impl(self, node) -> None:
        """Extract an impl block."""
        impl_type = None

        for child in node.children:
            if child.type == "type_identifier":
                impl_type = self._get_node_text(child)
                break

        if not impl_type:
            return

        # Save current impl context
        old_impl = self.current_impl
        self.current_impl = impl_type

        # Extract methods within impl
        for child in node.children:
            if child.type == "declaration_list":
                for decl in child.children:
                    if decl.type == "function_item":
                        self._extract_impl_method(decl, impl_type)

        self.current_impl = old_impl

    def _extract_impl_method(self, node, impl_type: str) -> None:
        """Extract a method within an impl block."""
        name = None
        params = []

        for child in node.children:
            if child.type == "identifier":
                name = self._get_node_text(child)
            elif child.type == "parameters":
                params = self._extract_params(child)

        if not name:
            return

        docstring = self._extract_docstring(node)
        component_id = self._get_component_id(name, impl_type)
        relative_path = self._get_relative_path()
        module_path = self._get_module_path()

        node_obj = Node(
            id=component_id,
            name=name,
            component_type="method",
            file_path=relative_path,
            relative_path=module_path,
            docstring=docstring,
            source_code=self._get_node_text(node),
            depends_on=set(),
            receiver=impl_type,
        )

        self.nodes.append(node_obj)
        self.top_level_nodes[component_id] = node_obj

    def _extract_trait(self, node) -> None:
        """Extract a trait declaration."""
        name = None

        for child in node.children:
            if child.type == "type_identifier":
                name = self._get_node_text(child)
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
            component_type="trait",
            file_path=relative_path,
            relative_path=module_path,
            docstring=docstring,
            source_code=self._get_node_text(node),
            depends_on=set(),
        )

        self.nodes.append(node_obj)
        self.top_level_nodes[component_id] = node_obj
        self.current_trait = name

    def _extract_enum(self, node) -> None:
        """Extract an enum declaration."""
        name = None

        for child in node.children:
            if child.type == "type_identifier":
                name = self._get_node_text(child)
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
            component_type="enum",
            file_path=relative_path,
            relative_path=module_path,
            docstring=docstring,
            source_code=self._get_node_text(node),
            depends_on=set(),
        )

        self.nodes.append(node_obj)
        self.top_level_nodes[component_id] = node_obj

    def _extract_params(self, node) -> List[str]:
        """Extract function parameters."""
        params = []
        for child in node.children:
            if child.type == "parameter":
                param_text = ""
                for pc in child.children:
                    if pc.type in (
                        "identifier",
                        "type_identifier",
                        "mutable_specifier",
                        "reference_expression",
                    ):
                        if param_text:
                            param_text += " "
                        param_text += self._get_node_text(pc)
                if param_text:
                    params.append(param_text)
            elif child.type == "self_parameter":
                params.append("self")
        return params

    def _extract_docstring(self, node) -> str:
        """Extract docstring from comments before a node."""
        # Note: tree-sitter doesn't provide prevSibling, so we skip docstring extraction
        return ""

    def _get_component_id(self, name: str, impl_type: str = None) -> str:
        """Get unique component ID."""
        module_path = self._get_module_path()

        if impl_type:
            return f"{module_path}.{impl_type}::{name}"
        return f"{module_path}::{name}"

    def _extract_calls(self, root_node) -> None:
        """Extract function call relationships."""
        self._find_calls(root_node)

    def _find_calls(self, node) -> None:
        """Recursively find all call expressions."""
        if node.type in ("call_expression", "method_call_expression"):
            self._extract_call(node)

        for child in node.children:
            self._find_calls(child)

    def _extract_call(self, node) -> None:
        """Extract a function call."""
        func_name = None
        line = node.start_point[0] + 1

        if node.type == "call_expression":
            # Regular function call: func(args)
            if node.children:
                first_child = node.children[0]
                if first_child.type == "identifier":
                    func_name = self._get_node_text(first_child)
                elif first_child.type == "field_expression":
                    # Handle obj.func() style calls
                    func_name = self._get_node_text(first_child)
                elif first_child.type == "scoped_identifier":
                    func_name = self._get_node_text(first_child)
        elif node.type == "method_call_expression":
            # Method call: obj.method(args)
            for child in node.children:
                if child.type == "field_identifier":
                    func_name = self._get_node_text(child)
                    break

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

    def _find_current_function(self, node) -> str:
        """Find the current function/method containing this node."""
        parent = node.parent
        while parent:
            if parent.type == "function_item":
                # Find the function name
                for child in parent.children:
                    if child.type == "identifier":
                        func_name = self._get_node_text(child)
                        return self._get_component_id(func_name)
            elif parent.type == "impl_item":
                # Find the impl type and look for method
                impl_type = None
                for child in parent.children:
                    if child.type == "type_identifier":
                        impl_type = self._get_node_text(child)
                        break
                if impl_type:
                    # Look for the method in declaration_list
                    for child in parent.children:
                        if child.type == "declaration_list":
                            for decl in child.children:
                                if decl.type == "function_item":
                                    for dc in decl.children:
                                        if dc.type == "identifier":
                                            method_name = self._get_node_text(dc)
                                            return self._get_component_id(
                                                method_name, impl_type
                                            )
            parent = parent.parent
        return None


def analyze_rust_file(
    file_path: str, content: str, repo_path: str = None
) -> tuple[List[Node], List[CallRelationship]]:
    """Analyze a Rust source file and return nodes and call relationships."""
    analyzer = RustASTAnalyzer(file_path, content, repo_path)
    analyzer.analyze()
    logger.info(
        f"Found {len(analyzer.nodes)} top-level nodes, {len(analyzer.call_relationships)} calls"
    )
    return analyzer.nodes, analyzer.call_relationships
