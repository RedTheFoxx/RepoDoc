"""
Heterogeneous knowledge graph for RepoDoc: code, doc, and concept nodes with typed edges.

Public API: CodeNode, DocNode, ConceptNode, HeterogeneousGraph, relation constants.
"""

from src.graph.builder import build_graph_from_analysis
from src.graph.graph import HeterogeneousGraph
from src.graph.models import (
    REL_CALLS,
    REL_DESCRIBES,
    REL_IMPLEMENTS,
    REL_SEMANTIC_IMPACT,
    RELATION_TYPES,
    CodeNode,
    ConceptNode,
    DocNode,
)

__all__ = [
    "build_graph_from_analysis",
    "CodeNode",
    "ConceptNode",
    "DocNode",
    "HeterogeneousGraph",
    "REL_CALLS",
    "REL_DESCRIBES",
    "REL_IMPLEMENTS",
    "REL_SEMANTIC_IMPACT",
    "RELATION_TYPES",
]
