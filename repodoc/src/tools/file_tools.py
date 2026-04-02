import os
from src.tools.base import BaseTool, ToolResult


class FileReaderTool(BaseTool):
    name = "file_reader"
    description = "Read file content from the repository"

    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        try:
            if not os.path.exists(file_path):
                return ToolResult(success=False, error=f"File not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class FileWriterTool(BaseTool):
    name = "file_writer"
    description = "Write content to a file in the repository"

    async def execute(self, file_path: str, content: str, **kwargs) -> ToolResult:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output=f"Written to {file_path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
