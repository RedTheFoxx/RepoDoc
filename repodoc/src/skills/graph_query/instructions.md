# Graph Query Skill

Queries the heterogeneous knowledge graph to retrieve code-doc-concept relationships for context assembly.

## Capabilities

- Query nodes by type (file, class, function, concept)
- Find relationships between code entities
- Retrieve context for specific targets
- Support complex graph traversal patterns

## Usage

```python
from repodoc.skills.graph_query import GraphQuerySkill

skill = GraphQuerySkill()
result = await skill.execute({"query": {"type": "function", "name": "main"}})
```
