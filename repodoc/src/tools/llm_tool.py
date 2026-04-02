from src.config import Config
from src.llm import call_llm_async, TokenUsage
from src.tools.base import BaseTool, ToolResult


class LLMTool(BaseTool):
    name = "llm_caller"
    description = "Call LLM for code generation or analysis"

    def __init__(self, config: Config):
        self.config = config
        self._token_usage_history: list[TokenUsage] = []

    def get_token_usage_history(self) -> list[TokenUsage]:
        return self._token_usage_history

    async def execute(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        **kwargs,
    ) -> ToolResult:
        try:
            result, token_usage = await call_llm_async(
                prompt=prompt,
                config=self.config,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self._token_usage_history.append(token_usage)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
