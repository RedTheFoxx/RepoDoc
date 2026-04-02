from typing import Any

from src.skills import SkillRegistry
from src.skills.base import BaseSkill, SkillResult
from src.tools.base import BaseTool


class Agent:
    def __init__(self, name: str):
        self.name = name
        self.skills: dict[str, BaseSkill] = {}
        self.tools: dict[str, BaseTool] = {}

    def register_skill(self, skill_name: str) -> None:
        skill_class = SkillRegistry.get(skill_name)
        if skill_class is None:
            raise ValueError(f"Skill not found: {skill_name}")
        skill = skill_class()
        self.skills[skill_name] = skill
        self._attach_tools_to_skill(skill)

    def register_tool(self, name: str, tool: BaseTool) -> None:
        self.tools[name] = tool
        for skill in self.skills.values():
            skill.register_tool(name, tool)

    def _attach_tools_to_skill(self, skill: BaseSkill) -> None:
        for tool_name in skill.metadata.tools_required:
            if tool_name in self.tools:
                skill.register_tool(tool_name, self.tools[tool_name])

    async def execute(self, task: dict[str, Any]) -> SkillResult:
        task_type = task.get("type")
        skill = self._select_skill(task_type)
        if skill is None:
            return SkillResult(
                success=False, error=f"No skill available for task type: {task_type}"
            )
        context = self._prepare_context(task)
        skill.load_context(context)
        return await skill.execute(task.get("input", {}))

    def _select_skill(self, task_type: str) -> BaseSkill | None:
        mapping = {
            "analyze": "code_analysis",
            "write_doc": "doc_writer",
            "query_graph": "graph_query",
        }
        skill_name = mapping.get(task_type)
        if skill_name:
            return self.skills.get(skill_name)
        if self.skills:
            return next(iter(self.skills.values()))
        return None

    def _prepare_context(self, task: dict[str, Any]) -> dict[str, Any]:
        return {
            "repo_path": task.get("repo_path"),
            "config": task.get("config"),
            "graph": task.get("graph"),
        }
