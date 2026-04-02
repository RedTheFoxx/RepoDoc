"""
Node and relation types for the heterogeneous knowledge graph.

Design: CodeNode (code entities), DocNode (document fragments), ConceptNode (business concepts)
with relation types calls, implements, describes, semantic_impact.
"""

from typing import Optional

from pydantic import BaseModel

# Relation type constants for graph edges (design: calls, implements, describes, semantic_impact).
REL_CALLS = "calls"
REL_IMPLEMENTS = "implements"
REL_DESCRIBES = "describes"
REL_SEMANTIC_IMPACT = "semantic_impact"

RELATION_TYPES = (REL_CALLS, REL_IMPLEMENTS, REL_DESCRIBES, REL_SEMANTIC_IMPACT)


class CodeNode(BaseModel):
    """Code entity: file, class, or function. Maps from analysis Node in Step 2."""

    id: str
    type: str  # e.g. "function", "class", "file"
    file_path: str
    source_code: Optional[str] = None
    name: Optional[str] = None
    relative_path: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    docstring: str = ""


class DocNode(BaseModel):
    """Document fragment: module doc, API doc, or architecture diagram."""

    id: str
    content: str
    format: str  # e.g. "markdown", "mermaid"
    version: int = 1
    file_path: Optional[str] = None


class ConceptNode(BaseModel):
    """Business concept extracted from comments, naming, or commit messages."""

    id: str
    concept: str
    context: str = ""
    confidence: float = 1.0  # 0.0 to 1.0
