from typing import TYPE_CHECKING

from src.agents.base import Agent
from src.config import Config
from src.skills import SkillRegistry
from src.tools.file_tools import FileReaderTool, FileWriterTool
from src.tools.graph_tool import GraphStoreTool

if TYPE_CHECKING:
    from src.graph.graph import HeterogeneousGraph


def create_agent(
    name: str, config: Config, graph: "HeterogeneousGraph" = None
) -> Agent:
    agent = Agent(name)

    agent.register_tool("file_reader", FileReaderTool())
    agent.register_tool("file_writer", FileWriterTool())

    if config:
        from src.tools.llm_tool import LLMTool

        agent.register_tool("llm_caller", LLMTool(config))

    if graph:
        agent.register_tool("graph_store", GraphStoreTool(graph))

    for skill_name in SkillRegistry.list_skills():
        agent.register_skill(skill_name)

    return agent
