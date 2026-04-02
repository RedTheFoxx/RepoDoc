from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic
from pydantic import BaseModel


class SkillMetadata(BaseModel):
    """Skill metadata definition"""

    name: str
    description: str
    version: str = "1.0.0"
    tags: list[str] = []
    tools_required: list[str] = []
    context_needed: list[str] = []


class SkillResult(BaseModel):
    """Skill execution result"""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = {}


T = TypeVar("T")


class BaseSkill(ABC, Generic[T]):
    """Base class for all Skills"""

    def __init__(self, metadata: SkillMetadata):
        self.metadata = metadata
        self._tools: dict[str, Any] = {}
        self._context: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, input_data: T) -> SkillResult:
        """Execute skill logic"""
        pass

    def register_tool(self, name: str, tool: Any) -> None:
        """Register available tool"""
        self._tools[name] = tool

    def load_context(self, context: dict[str, Any]) -> None:
        """Load context for skill execution"""
        self._context.update(context)

    @property
    def available_tools(self) -> dict[str, Any]:
        """Return available tools"""
        return self._tools.copy()
