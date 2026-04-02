from src.skills.base import BaseSkill, SkillMetadata, SkillResult
from src.skills.doc_writer.prompts import (
    format_doc_prompt,
    format_overview_prompt,
    format_architecture_diagram_prompt,
    format_module_prompt,
    format_sub_module_prompt,
)


class DocWriterSkill(BaseSkill[dict]):
    """Skill for generating documentation from code analysis"""

    def __init__(self):
        super().__init__(
            SkillMetadata(
                name="doc_writer",
                description="Generates documentation from code analysis",
                tools_required=["llm_caller", "file_writer"],
                context_needed=[
                    "code_entities",
                    "dependency_graph",
                    "module_structure",
                ],
            )
        )

    async def execute(self, input_data: dict) -> SkillResult:
        """Generate documentation based on input data"""
        doc_type = input_data.get("type", "component")
        config = self._context.get("config")

        if not config:
            return SkillResult(success=False, error="Config not found in context")

        llm_tool = self._tools.get("llm_caller")
        if not llm_tool:
            return SkillResult(success=False, error="LLM tool not available")

        try:
            if doc_type == "overview":
                return await self._generate_overview(input_data, llm_tool)
            elif doc_type == "component":
                return await self._generate_component_doc(input_data, llm_tool)
            elif doc_type == "module":
                return await self._generate_module_doc(input_data, llm_tool)
            elif doc_type == "sub_module":
                return await self._generate_sub_module_doc(input_data, llm_tool)
            elif doc_type == "architecture_diagram":
                return await self._generate_architecture_diagram(input_data, llm_tool)
            else:
                return SkillResult(
                    success=False, error=f"Unknown documentation type: {doc_type}"
                )
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _generate_overview(self, input_data: dict, llm_tool) -> SkillResult:
        """Generate repository overview documentation"""
        repo_name = input_data.get("repo_name", "Repository")
        component_count = input_data.get("component_count", 0)
        module_structure = input_data.get("module_structure", {})
        code_statistics = input_data.get("code_statistics", {})

        modules_summary = "\n".join(
            [
                f"- {name}: {len(info.get('components', []))} components"
                for name, info in module_structure.items()
            ]
        )

        available_modules = list(module_structure.keys()) if module_structure else []

        system_prompt, user_prompt = format_overview_prompt(
            repo_name=repo_name,
            component_count=component_count,
            module_structure=module_structure,
            code_statistics=code_statistics,
            modules_summary=modules_summary,
            available_modules=available_modules,
        )

        result = await llm_tool.execute(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            temperature=0.3,
            max_tokens=8192,
        )

        if not result.success:
            return SkillResult(success=False, error=result.error)

        output_content = result.output
        output_path = input_data.get("output_path", "docs/README.md")

        file_tool = self._tools.get("file_writer")
        if file_tool:
            await file_tool.execute(file_path=output_path, content=output_content)

        return SkillResult(
            success=True,
            output={
                "type": "overview",
                "content": output_content,
                "path": output_path,
            },
            metadata={"skill": "doc_writer", "doc_type": "overview"},
        )

    async def _generate_component_doc(self, input_data: dict, llm_tool) -> SkillResult:
        """Generate documentation for a single component"""
        component = input_data.get("component", {})

        system_prompt, user_prompt = format_doc_prompt(
            component_name=component.get("name", "Unknown"),
            component_type=component.get("component_type", "unknown"),
            file_path=component.get("file_path", ""),
            docstring=component.get("docstring", ""),
            source_code=component.get("source_code", ""),
            dependencies=list(component.get("depends_on", set())),
            module_context=input_data.get("module_context", ""),
        )

        result = await llm_tool.execute(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            temperature=0.3,
            max_tokens=8192,
        )

        if not result.success:
            return SkillResult(success=False, error=result.error)

        output_content = result.output
        output_path = input_data.get(
            "output_path", f"docs/{component.get('relative_path', 'component')}.md"
        )

        file_tool = self._tools.get("file_writer")
        if file_tool:
            await file_tool.execute(file_path=output_path, content=output_content)

        return SkillResult(
            success=True,
            output={
                "type": "component",
                "content": output_content,
                "path": output_path,
                "component_name": component.get("name"),
            },
            metadata={"skill": "doc_writer", "doc_type": "component"},
        )

    async def _generate_module_doc(self, input_data: dict, llm_tool) -> SkillResult:
        """Generate documentation for a module"""
        module_name = input_data.get("module_name", "Module")
        module_path = input_data.get("module_path", "")
        components = input_data.get("components", [])
        sub_modules = input_data.get("sub_modules", [])
        children = input_data.get("children", {})
        children_docs = input_data.get("children_docs", {})
        component_docs = input_data.get("component_docs", {})
        available_root_modules = input_data.get("available_root_modules", [])
        available_components = input_data.get("available_components", [])

        system_prompt, user_prompt = format_module_prompt(
            module_name=module_name,
            module_path=module_path,
            components=components,
            sub_modules=sub_modules,
            children=children,
            children_docs=children_docs,
            component_docs=component_docs,
            available_root_modules=available_root_modules,
            available_components=available_components,
        )

        result = await llm_tool.execute(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            temperature=0.3,
            max_tokens=8192,
        )

        if not result.success:
            return SkillResult(success=False, error=result.error)

        output_content = result.output
        output_path = input_data.get("output_path", f"docs/modules/{module_name}.md")

        file_tool = self._tools.get("file_writer")
        if file_tool:
            await file_tool.execute(file_path=output_path, content=output_content)

        return SkillResult(
            success=True,
            output={
                "type": "module",
                "content": output_content,
                "path": output_path,
                "module_name": module_name,
            },
            metadata={"skill": "doc_writer", "doc_type": "module"},
        )

    async def _generate_sub_module_doc(self, input_data: dict, llm_tool) -> SkillResult:
        """Generate documentation for sub-modules (recursive)"""
        sub_modules = input_data.get("sub_modules", [])
        parent_module = input_data.get("parent_module", "")

        is_complex = len(sub_modules) > 1

        if not is_complex:
            return SkillResult(
                success=True,
                output={"type": "sub_module", "skipped": True, "reason": "Not complex"},
                metadata={"skill": "doc_writer", "doc_type": "sub_module"},
            )

        sub_docs = []
        for sub in sub_modules:
            sub_name = sub.get("name", "sub_module")
            sub_components = sub.get("components", [])

            prompt = f"""Generate detailed documentation for sub-module: {sub_name}

Parent Module: {parent_module}
Sub-module Name: {sub_name}
Components:
{chr(10).join([f"- {c.get('name', 'Unknown')}: {c.get('docstring', 'No docs')}" for c in sub_components])}

Include:
1. Sub-module overview
2. Component details
3. Relationships with other sub-modules
4. Mermaid diagram if helpful"""

            result = await llm_tool.execute(
                prompt=prompt,
                temperature=0.3,
                max_tokens=8192,
            )

            if result.success:
                output_path = input_data.get("output_path", f"docs/{sub_name}.md")
                file_tool = self._tools.get("file_writer")
                if file_tool:
                    await file_tool.execute(
                        file_path=output_path, content=result.output
                    )
                sub_docs.append({"name": sub_name, "path": output_path})

        return SkillResult(
            success=True,
            output={
                "type": "sub_module",
                "generated": sub_docs,
                "count": len(sub_docs),
            },
            metadata={"skill": "doc_writer", "doc_type": "sub_module"},
        )

    async def _generate_architecture_diagram(
        self, input_data: dict, llm_tool
    ) -> SkillResult:
        """Generate Mermaid architecture diagram"""
        module_name = input_data.get("module_name", "Module")
        components = input_data.get("components", [])
        dependencies = input_data.get("dependencies", {})

        system_prompt, user_prompt = format_architecture_diagram_prompt(
            module_name=module_name,
            components=[c.get("name", "") for c in components],
            dependencies=dependencies,
        )

        result = await llm_tool.execute(
            prompt=f"{system_prompt}\n\n{user_prompt}",
            temperature=0.2,
            max_tokens=2048,
        )

        if not result.success:
            return SkillResult(success=False, error=result.error)

        return SkillResult(
            success=True,
            output={
                "type": "architecture_diagram",
                "diagram": result.output,
                "module_name": module_name,
            },
            metadata={"skill": "doc_writer", "doc_type": "architecture_diagram"},
        )
