"""LLM calls (OpenAI-compatible API). Used by clustering and doc generation."""

import logging
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from src.config import Config

logger = logging.getLogger(__name__)


class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def call_llm(
    prompt: str,
    config: "Config",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    system: str | None = None,
    response_format: dict | None = None,
    extra_body: dict | None = None,
) -> tuple[str, TokenUsage]:
    """
    Call LLM with the given prompt (OpenAI-compatible chat API).

    Args:
        prompt: User message content.
        config: RepoDoc config with llm_base_url, llm_api_key, main_model, cluster_model.
        model: Model name override (default: config.main_model).
        temperature: Sampling temperature.
        max_tokens: Max response tokens.
        system: Optional system message. Format instructions are followed more
            reliably when placed here.
        response_format: Optional response_format dict (e.g. {"type": "json_object"})
            to force a structured/JSON output.
        extra_body: Optional params forwarded to the API (e.g. reasoning_effort,
            chat_template_kwargs) for provider-specific controls like Ollama thinking.

    Returns:
        Tuple of (assistant message content, token usage dict).
    """
    from openai import OpenAI
    from openai import APIError

    if model is None:
        model = config.main_model
    client = OpenAI(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
    )

    # Truncate prompt if too long (keep under 60K chars for safety)
    if len(prompt) > 60000:
        logger.warning(f"Prompt too long ({len(prompt)} chars), truncating to 60K")
        prompt = prompt[:60000]

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if extra_body is not None:
        kwargs["extra_body"] = extra_body

    try:
        response = client.chat.completions.create(**kwargs)
    except APIError as e:
        logger.error(f"API Error: {e}")
        # Fallback: drop format constraints (some providers reject them) and shrink
        # max_tokens to fit stricter limits.
        fallback_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("response_format", "extra_body")
        }
        if max_tokens > 4096:
            logger.info("Retrying with smaller max_tokens and no format constraints...")
            fallback_kwargs["max_tokens"] = 4096
            response = client.chat.completions.create(**fallback_kwargs)
        else:
            raise
    usage = response.usage
    token_usage: TokenUsage = {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }
    return response.choices[0].message.content or "", token_usage


async def call_llm_async(
    prompt: str,
    config: "Config",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    system: str | None = None,
    response_format: dict | None = None,
    extra_body: dict | None = None,
) -> tuple[str, TokenUsage]:
    """
    Async version of call_llm with OpenAI-compatible async chat API.

    Args:
        prompt: User message content.
        config: RepoDoc config with llm_base_url, llm_api_key, main_model, cluster_model.
        model: Model name override (default: config.main_model).
        temperature: Sampling temperature.
        max_tokens: Max response tokens.
        system: Optional system message for more reliable format adherence.
        response_format: Optional response_format dict (e.g. {"type": "json_object"}).
        extra_body: Optional provider-specific params (e.g. reasoning_effort,
            chat_template_kwargs for Ollama thinking control).

    Returns:
        Tuple of (assistant message content, token usage dict).
    """
    from openai import AsyncOpenAI
    from openai import APIError

    if model is None:
        model = config.main_model
    client = AsyncOpenAI(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key,
    )

    if len(prompt) > 60000:
        logger.warning(f"Prompt too long ({len(prompt)} chars), truncating to 60K")
        prompt = prompt[:60000]

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if extra_body is not None:
        kwargs["extra_body"] = extra_body

    try:
        response = await client.chat.completions.create(**kwargs)
    except APIError as e:
        logger.error(f"API Error: {e}")
        fallback_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ("response_format", "extra_body")
        }
        if max_tokens > 4096:
            logger.info("Retrying with smaller max_tokens and no format constraints...")
            fallback_kwargs["max_tokens"] = 4096
            response = await client.chat.completions.create(**fallback_kwargs)
        else:
            raise
    finally:
        await client.close()

    usage = response.usage
    token_usage: TokenUsage = {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }
    return response.choices[0].message.content or "", token_usage
