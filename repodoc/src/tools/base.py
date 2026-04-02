from abc import ABC, abstractmethod
from typing import Any


class ToolResult:
    """Result of tool execution"""

    def __init__(self, success: bool, output: Any = None, error: str | None = None):
        self.success = success
        self.output = output
        self.error = error

    def __repr__(self):
        if self.success:
            return f"ToolResult(success=True, output={self.output})"
        return f"ToolResult(success=False, error={self.error})"


class BaseTool(ABC):
    """Base class for all Tools"""

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        pass

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
        }
