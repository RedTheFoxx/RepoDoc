"""
Topological sorting utilities for dependency graphs with cycle handling.
"""

import logging
from collections import deque
from typing import Any, Dict, List, Set

from src.analysis.models.core import Node

logger = logging.getLogger(__name__)

# Keywords used to filter out error-related leaf nodes
ERROR_KEYWORDS = ("error", "exception", "failed", "invalid")


def detect_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Detect cycles using Tarjan's algorithm (strongly connected components)."""
    index_counter = [0]
    index: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    onstack: Set[str] = set()
    stack: List[str] = []
    result: List[List[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        onstack.add(node)
        for successor in graph.get(node, set()):
            if successor not in index:
                strongconnect(successor)
                lowlink[node] = min(lowlink[node], lowlink[successor])
            elif successor in onstack:
                lowlink[node] = min(lowlink[node], index[successor])
        if lowlink[node] == index[node]:
            scc = []
            while True:
                successor = stack.pop()
                onstack.discard(successor)
                scc.append(successor)
                if successor == node:
                    break
            if len(scc) > 1:
                result.append(scc)

    for node in graph:
        if node not in index:
            strongconnect(node)
    return result


def resolve_cycles(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """Resolve cycles by breaking one edge per cycle."""
    cycles = detect_cycles(graph)
    if not cycles:
        return graph
    new_graph = {node: deps.copy() for node, deps in graph.items()}
    for cycle in cycles:
        for j in range(len(cycle) - 1):
            current, next_node = cycle[j], cycle[j + 1]
            if next_node in new_graph.get(current, set()):
                new_graph[current].discard(next_node)
                break
    return new_graph


def topological_sort(graph: Dict[str, Set[str]]) -> List[str]:
    """Topological sort (dependencies first)."""
    acyclic = resolve_cycles(graph)
    in_degree = {node: 0 for node in acyclic}
    for node, deps in acyclic.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[dep] += 1
    queue = deque(n for n, d in in_degree.items() if d == 0)
    result = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent, deps in acyclic.items():
            if node in deps:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
    if len(result) != len(acyclic):
        return list(acyclic.keys())
    return result[::-1]


def dependency_first_dfs(graph: Dict[str, Set[str]]) -> List[str]:
    """DFS with dependencies visited first."""
    acyclic = resolve_cycles(graph)
    has_incoming = {node: False for node in acyclic}
    for node, deps in acyclic.items():
        for dep in deps:
            has_incoming[dep] = True
    roots = [n for n in acyclic if not has_incoming.get(n, False)]
    if not roots:
        roots = list(acyclic.keys())[:1]
    visited: Set[str] = set()
    result: List[str] = []

    def dfs(n: str) -> None:
        if n in visited:
            return
        visited.add(n)
        for dep in sorted(acyclic.get(n, set())):
            dfs(dep)
        result.append(n)

    for root in sorted(roots):
        dfs(root)
    for node in sorted(acyclic.keys()):
        if node not in visited:
            dfs(node)
    return result


def build_graph_from_components(components: Dict[str, Any]) -> Dict[str, Set[str]]:
    """Build adjacency graph from components (A -> B if A depends on B)."""
    graph: Dict[str, Set[str]] = {}
    for comp_id, component in components.items():
        graph.setdefault(comp_id, set())
        for dep_id in getattr(component, "depends_on", []):
            if dep_id in components:
                graph[comp_id].add(dep_id)
    return graph


def get_leaf_nodes(
    graph: Dict[str, Set[str]], components: Dict[str, Node]
) -> List[str]:
    """Leaf nodes: no other node depends on them. Filter by valid types."""
    acyclic = resolve_cycles(graph)
    leaf_nodes = set(acyclic.keys())

    def concise_node(ln: Set[str]) -> List[str]:
        concise = set()
        for n in ln:
            concise.add(n.replace(".__init__", "") if n.endswith("__init__") else n)
        available_types = {c.component_type for c in components.values()}
        valid = {"class", "interface", "struct"}
        if not available_types.intersection(valid):
            valid.add("function")
        keep = []
        for n in concise:
            if not isinstance(n, str) or not n.strip():
                continue
            if any(k in n.lower() for k in ERROR_KEYWORDS):
                continue
            if n in components and components[n].component_type in valid:
                keep.append(n)
        return keep

    out = concise_node(leaf_nodes)
    if len(out) >= 400:
        for node, deps in acyclic.items():
            for dep in deps:
                leaf_nodes.discard(dep)
        out = concise_node(leaf_nodes)
    if not leaf_nodes:
        return []
    return out
