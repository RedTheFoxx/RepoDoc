# Documentation Writer Skill

Generates high-quality documentation from code analysis results.

## Capabilities

- Generate markdown documentation from code analysis
- Create API documentation with parameter descriptions
- Produce architecture diagrams from dependency graphs
- Support multiple output formats

## Usage

```python
from repodoc.skills.doc_writer import DocWriterSkill

skill = DocWriterSkill()
result = await skill.execute({"analysis_result": {...}, "template": "api"})
```
