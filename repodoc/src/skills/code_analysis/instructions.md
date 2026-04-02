# Code Analysis Skill

Analyzes code structure, extracts semantic information, and identifies business concepts from code patterns.

## Capabilities

- Parse source code files using AST analysis
- Extract function/class definitions and their relationships
- Identify dependencies between modules
- Build knowledge graph from code semantics

## Usage

```python
from repodoc.skills.code_analysis import CodeAnalysisSkill

skill = CodeAnalysisSkill()
result = await skill.execute({"target_path": "/path/to/code"})
```
