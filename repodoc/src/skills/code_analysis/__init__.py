from src.skills.base import BaseSkill, SkillMetadata, SkillResult

CONCEPT_EXTRACTION_PROMPT = """Extract business concepts and semantic information from the following code component.

Component Name: {component_name}
Component Type: {component_type}
Docstring: {docstring}
Source Code:
{source_code}

Please extract:
1. Business concepts (what business domain concepts does this code represent?)
2. Design patterns used (if any)
3. Key responsibilities
4. Dependencies on external systems or services

Return a JSON-like structure with these fields."""


class CodeAnalysisSkill(BaseSkill[dict]):
    """Skill for analyzing code structure and extracting semantics"""

    def __init__(self):
        super().__init__(
            SkillMetadata(
                name="code_analysis",
                description="Analyzes code structure, extracts semantic information",
                tools_required=["file_reader", "graph_store", "llm_caller"],
                context_needed=["file_tree", "dependencies"],
            )
        )

    async def execute(self, input_data: dict) -> SkillResult:
        """Analyze code and extract semantics"""
        analysis_type = input_data.get("type", "concepts")

        try:
            if analysis_type == "concepts":
                return await self._extract_concepts(input_data)
            elif analysis_type == "dependencies":
                return await self._analyze_dependencies(input_data)
            elif analysis_type == "full":
                return await self._full_analysis(input_data)
            else:
                return SkillResult(
                    success=False, error=f"Unknown analysis type: {analysis_type}"
                )
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _extract_concepts(self, input_data: dict) -> SkillResult:
        """Extract business concepts from code using LLM"""
        component = input_data.get("component", {})

        llm_tool = self._tools.get("llm_caller")
        if not llm_tool:
            return SkillResult(success=False, error="LLM tool not available")

        prompt = CONCEPT_EXTRACTION_PROMPT.format(
            component_name=component.get("name", "Unknown"),
            component_type=component.get("component_type", "unknown"),
            docstring=component.get("docstring", "None"),
            source_code=component.get("source_code", "")[:2000],
        )

        result = await llm_tool.execute(
            prompt=prompt,
            temperature=0.2,
            max_tokens=1024,
        )

        if not result.success:
            return SkillResult(success=False, error=result.error)

        graph_tool = self._tools.get("graph_store")
        if graph_tool:
            concept_node = {
                "id": f"concept:{component.get('name')}",
                "type": "concept",
                "concept": result.output,
                "context": component.get("file_path"),
                "confidence": 0.8,
            }
            await graph_tool.execute(
                operation="add_node",
                node_type="concept",
                node_data=concept_node,
            )

        return SkillResult(
            success=True,
            output={
                "type": "concepts",
                "component": component.get("name"),
                "concepts": result.output,
            },
            metadata={"skill": "code_analysis", "analysis_type": "concepts"},
        )

    async def _analyze_dependencies(self, input_data: dict) -> SkillResult:
        """Analyze component dependencies"""
        component = input_data.get("component", {})
        depends_on = component.get("depends_on", set())

        direct_deps = list(depends_on)[:10]

        return SkillResult(
            success=True,
            output={
                "type": "dependencies",
                "component": component.get("name"),
                "direct_dependencies": direct_deps,
                "dependency_count": len(depends_on),
            },
            metadata={"skill": "code_analysis", "analysis_type": "dependencies"},
        )

    async def _full_analysis(self, input_data: dict) -> SkillResult:
        """Perform full analysis: concepts + dependencies"""
        component = input_data.get("component", {})

        concepts_result = await self._extract_concepts(input_data)
        deps_result = await self._analyze_dependencies(input_data)

        return SkillResult(
            success=True,
            output={
                "type": "full",
                "component": component.get("name"),
                "concepts": (
                    concepts_result.output.get("concepts")
                    if concepts_result.success
                    else None
                ),
                "dependencies": (
                    deps_result.output.get("direct_dependencies")
                    if deps_result.success
                    else None
                ),
            },
            metadata={"skill": "code_analysis", "analysis_type": "full"},
        )
