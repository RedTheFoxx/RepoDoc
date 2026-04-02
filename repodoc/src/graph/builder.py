"""
Build HeterogeneousGraph from analysis output: CodeNodes from Node, calls from depends_on.
"""

from typing import Dict

from src.analysis.models.core import Node
from src.graph.graph import HeterogeneousGraph
from src.graph.models import REL_CALLS, CodeNode


def build_graph_from_analysis(components: Dict[str, Node]) -> HeterogeneousGraph:
    """
    Populate a heterogeneous graph with CodeNodes and calls edges from parser components.

    Each Node becomes a CodeNode; each depends_on entry becomes a calls edge (weight 1.0)
    when the callee exists in components.
    """
    graph = HeterogeneousGraph()
    for nid, node in components.items():
        code_node = CodeNode(
            id=node.id,
            type=node.component_type,
            file_path=node.file_path,
            source_code=node.source_code,
            name=node.name,
            relative_path=node.relative_path,
            start_line=node.start_line,
            end_line=node.end_line,
            docstring=node.docstring or "",
        )
        graph.add_code_node(code_node)
    for nid, node in components.items():
        for callee_id in node.depends_on:
            if callee_id in components:
                graph.add_edge(nid, callee_id, REL_CALLS, 1.0)
    return graph
