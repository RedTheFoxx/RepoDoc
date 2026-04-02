"""Incremental documentation update algorithm.

This module provides semantic impact propagation for efficient documentation updates.
When a file changes, it identifies all affected components and only re-generates
documentation for those components and their dependents.
"""

import logging
from typing import Set, List, Dict, Any, Optional
from pathlib import Path

from src.graph import HeterogeneousGraph, REL_CALLS, REL_SEMANTIC_IMPACT

logger = logging.getLogger(__name__)


class IncrementalUpdater:
    """Handles incremental documentation updates based on semantic impact."""

    def __init__(self, graph: HeterogeneousGraph, config: Any):
        self.graph = graph
        self.config = config
        self._impact_cache: Dict[str, Set[str]] = {}

    def get_affected_components(
        self,
        changed_files: List[str],
    ) -> Set[str]:
        """Get all components affected by the given file changes.

        Args:
            changed_files: List of file paths that changed.

        Returns:
            Set of component names that need documentation updates.
        """
        affected: Set[str] = set()

        for file_path in changed_files:
            # Find components defined in this file
            components = self._find_components_in_file(file_path)
            affected.update(components)

            # Find components that depend on these (downstream)
            downstream = self._get_downstream_components(components)
            affected.update(downstream)

        logger.info(
            f"Affected components from {len(changed_files)} files: {len(affected)}"
        )
        return affected

    def _find_components_in_file(self, file_path: str) -> Set[str]:
        """Find all components defined in a file."""
        components: Set[str] = set()

        # Normalize path
        path = Path(file_path).as_posix()

        # Try exact match first
        for node_id, node_attrs in self.graph.nodes(data=True):
            node_data = node_attrs.get("data", {})
            source_file = node_data.get("file_path", "")
            if source_file and self._paths_match(source_file, path):
                components.add(node_id)

        # If no match, try matching by relative path (filename + parent dirs)
        if not components:
            components = self._find_components_by_relative_path(file_path)

        return components

    def _find_components_by_relative_path(self, file_path: str) -> Set[str]:
        """Find components by matching relative path within repo.

        This handles the case where the repo was copied to a different location.
        We compare the relative structure within the repo (e.g., src/requests/adapters.py).
        """
        components: Set[str] = set()

        try:
            current_path = Path(file_path)
            current_name = current_path.name
            current_parts = current_path.parts
            current_len = len(current_parts)

            # Find nodes where the file_path ends with the same relative structure
            for node_id, node_attrs in self.graph.nodes(data=True):
                node_data = node_attrs.get("data", {})
                source_file = node_data.get("file_path", "")

                if not source_file:
                    continue

                source_path = Path(source_file)
                source_name = source_path.name
                source_parts = source_path.parts
                source_len = len(source_parts)

                # Must have same filename
                if source_name != current_name:
                    continue

                # Compare from the end - find matching suffix
                # We need at least 2 matching parts (filename + at least 1 dir)
                min_match = 2
                match_count = 0

                src_idx = source_len - 1
                tgt_idx = current_len - 1

                while src_idx >= 0 and tgt_idx >= 0 and match_count < min_match:
                    if source_parts[src_idx] == current_parts[tgt_idx]:
                        match_count += 1
                    else:
                        break
                    src_idx -= 1
                    tgt_idx -= 1

                # If we matched at least filename + 1 directory, it's a match
                if match_count >= min_match:
                    components.add(node_id)

        except Exception as e:
            logger.debug(f"Error in relative path matching: {e}")

        return components

    def _paths_match(self, source: str, target: str) -> bool:
        """Check if two file paths match (handling relative/absolute)."""
        try:
            return Path(source).resolve() == Path(target).resolve()
        except Exception:
            return source == target

    def _get_downstream_components(self, components: Set[str]) -> Set[str]:
        """Get all components that depend on the given components.

        Uses semantic impact relationships to find downstream dependencies.
        """
        downstream: Set[str] = set()
        to_process = list(components)
        visited: Set[str] = set()

        while to_process:
            component = to_process.pop()
            if component in visited:
                continue
            visited.add(component)

            # Find components that this component impacts (semantic relationship)
            successors = self.graph.successors(component)
            for succ in successors:
                edge_data = self.graph.get_edge_data(component, succ)
                if edge_data and edge_data.get("relation_type") in (
                    REL_CALLS,
                    REL_SEMANTIC_IMPACT,
                ):
                    downstream.add(succ)
                    to_process.append(succ)

        return downstream

    def get_upstream_dependencies(self, component: str) -> Set[str]:
        """Get all components that this component depends on.

        Args:
            component: Component name.

        Returns:
            Set of component names this component depends on.
        """
        if component in self._impact_cache:
            return self._impact_cache[component]

        dependencies: Set[str] = set()
        to_process = [component]
        visited: Set[str] = set()

        while to_process:
            comp = to_process.pop()
            if comp in visited:
                continue
            visited.add(comp)

            predecessors = self.graph.predecessors(comp)
            for pred in predecessors:
                edge_data = self.graph.get_edge_data(pred, comp)
                if edge_data and edge_data.get("relation_type") in (
                    REL_CALLS,
                    REL_SEMANTIC_IMPACT,
                ):
                    dependencies.add(pred)
                    to_process.append(pred)

        self._impact_cache[component] = dependencies
        return dependencies

    def compute_impact_graph(
        self,
        changed_files: List[str],
        module_tree: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute a complete impact analysis for changed files.

        Args:
            changed_files: List of changed file paths
            module_tree: Optional module_tree to filter affected components.
                        If provided, only components in module_tree will be included.

        Returns a structured result with:
        - changed_files: Original list of changed files
        - changed_components: Direct changes (from changed files)
        - affected_components: All affected (changed + downstream), filtered by module_tree if provided
        - new_components: Components not in knowledge graph (newly detected)
        - not_in_module_tree: Components in knowledge graph but not in module_tree
        - impact_order: Processing order (topological)
        - total_affected: Count of affected components
        """
        changed_components = set()
        for f in changed_files:
            changed_components.update(self._find_components_in_file(f))

        all_affected = self.get_affected_components(changed_files)

        # Build set of components in module_tree
        module_tree_components: Set[str] = set()
        if module_tree:
            for mod_info in module_tree.values():
                module_tree_components.update(mod_info.get("components", []))

        # Build set of components in knowledge graph
        graph_components: Set[str] = set()
        for node_id in self.graph.nodes(data=True):
            if isinstance(node_id, tuple):
                nid, _ = node_id
                graph_components.add(nid)
            elif isinstance(node_id, str):
                graph_components.add(node_id)

        # Filter to only components in module_tree
        if module_tree:
            filtered_affected = all_affected & module_tree_components
            not_in_module_tree = all_affected - module_tree_components
        else:
            filtered_affected = all_affected
            not_in_module_tree = set()

        # Find new components (not in knowledge graph)
        new_components = changed_components - graph_components

        # Compute impact order (process dependencies first)
        impact_order = self._compute_topological_order(filtered_affected)

        return {
            "changed_files": changed_files,
            "changed_components": list(changed_components),
            "affected_components": list(filtered_affected),
            "new_components": list(new_components),
            "not_in_module_tree": list(not_in_module_tree),
            "impact_order": impact_order,
            "total_affected": len(filtered_affected),
        }

    def _compute_topological_order(self, components: Set[str]) -> List[str]:
        """Compute processing order respecting dependency graph."""
        # Simple topological sort based on dependencies
        order: List[str] = []
        remaining = set(components)
        visited: Set[str] = set()

        while remaining:
            # Find components with no unprocessed dependencies
            ready = []
            for comp in remaining:
                deps = self.get_upstream_dependencies(comp)
                if deps.issubset(visited):
                    ready.append(comp)

            if not ready:
                # Cycle or independent - just pick one
                ready = [remaining.pop()]
            else:
                for r in ready:
                    remaining.discard(r)

            order.extend(ready)
            visited.update(ready)

        return order


def create_incremental_updater(
    config: Any,
    graph_path: Optional[str] = None,
) -> IncrementalUpdater:
    """Create an IncrementalUpdater instance.

    Args:
        config: Configuration object.
        graph_path: Optional path to saved graph. If None, loads from config.

    Returns:
        Configured IncrementalUpdater instance.
    """
    if graph_path and Path(graph_path).exists():
        graph = HeterogeneousGraph.load(graph_path)
    else:
        # Build new graph from analysis
        from src.analysis import DependencyGraphBuilder
        from src.graph.builder import build_graph_from_analysis

        builder = DependencyGraphBuilder(config)
        components, _ = builder.build_dependency_graph()
        graph = build_graph_from_analysis(components)

    return IncrementalUpdater(graph, config)
