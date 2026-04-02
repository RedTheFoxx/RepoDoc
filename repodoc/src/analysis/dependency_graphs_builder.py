"""
Build dependency graph from repo: parse -> save -> leaf nodes.
"""

import logging
import os
from typing import Any, Dict, List

from src.config import Config
from src.utils import file_manager
from src.analysis.ast_parser import DependencyParser
from src.analysis.topo_sort import build_graph_from_components, get_leaf_nodes
from src.graph.builder import build_graph_from_analysis as build_kg_from_analysis

logger = logging.getLogger(__name__)


class DependencyGraphBuilder:
    """Build and save dependency graph; return components and leaf nodes."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def build_dependency_graph(
        self,
        build_kg: bool = False,
        kg_output_path: str | None = None,
    ) -> tuple[Dict[str, Any], List[str]]:
        file_manager.ensure_directory(self.config.dependency_graph_dir)
        repo_name = os.path.basename(os.path.normpath(self.config.repo_path))
        sanitized = "".join(c if c.isalnum() else "_" for c in repo_name)
        dependency_graph_path = os.path.join(
            self.config.dependency_graph_dir,
            f"{sanitized}_dependency_graph.json",
        )

        parser = DependencyParser(self.config.repo_path)
        components = parser.parse_repository()
        parser.save_dependency_graph(dependency_graph_path)

        if build_kg and kg_output_path:
            kg = build_kg_from_analysis(components)
            kg_dir = os.path.dirname(kg_output_path)
            if kg_dir:
                file_manager.ensure_directory(kg_dir)
            kg.save(kg_output_path)
            logger.debug(
                "Knowledge graph saved: %s (%d nodes, %d edges)",
                kg_output_path,
                kg.node_count(),
                kg.edge_count(),
            )

        graph = build_graph_from_components(components)
        leaf_nodes = get_leaf_nodes(graph, components)

        available_types = {c.component_type for c in components.values()}
        valid_types = {"class", "interface", "struct"}
        if not available_types.intersection(valid_types):
            valid_types.add("function")

        keep_leaf_nodes = []
        for ln in leaf_nodes:
            if not isinstance(ln, str) or not ln.strip():
                continue
            if any(
                k in ln.lower() for k in ("error", "exception", "failed", "invalid")  # noqa: RUF001
            ):
                continue
            if ln in components and components[ln].component_type in valid_types:
                keep_leaf_nodes.append(ln)
            elif ln not in components:
                logger.warning("Leaf node %s not found in components", ln)

        return components, keep_leaf_nodes
