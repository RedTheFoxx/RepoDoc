from src.tools.base import BaseTool
from src.tools.file_tools import FileReaderTool, FileWriterTool
from src.tools.llm_tool import LLMTool
from src.tools.graph_tool import GraphStoreTool


class ToolRegistry:
    _tools: dict[str, type[BaseTool]] = {}

    @classmethod
    def register(cls, name: str, tool_class: type[BaseTool]) -> None:
        cls._tools[name] = tool_class

    @classmethod
    def get(cls, name: str) -> type[BaseTool] | None:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> list[str]:
        return list(cls._tools.keys())


ToolRegistry.register("file_reader", FileReaderTool)
ToolRegistry.register("file_writer", FileWriterTool)
ToolRegistry.register("llm_caller", LLMTool)
ToolRegistry.register("graph_store", GraphStoreTool)
