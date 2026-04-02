"""LLM calls (OpenAI-compatible API). Used by clustering and doc generation."""

import logging
from typing import TYPE_CHECKING, TypedDict

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
) -> tuple[str, TokenUsage]:
    """
    Call LLM with the given prompt (OpenAI-compatible chat API).

    Args:
        prompt: User message content.
        config: RepoDoc config with llm_base_url, llm_api_key, main_model, cluster_model.
        model: Model name override (default: config.main_model).
        temperature: Sampling temperature.
        max_tokens: Max response tokens.

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

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except APIError as e:
        logger.error(f"API Error: {e}")
        # Fallback to a smaller max_tokens if API error
        if max_tokens > 4096:
            logger.info("Retrying with smaller max_tokens...")
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=4096,
            )
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
) -> tuple[str, TokenUsage]:
    """
    Async version of call_llm with OpenAI-compatible async chat API.

    Args:
        prompt: User message content.
        config: RepoDoc config with llm_base_url, llm_api_key, main_model, cluster_model.
        model: Model name override (default: config.main_model).
        temperature: Sampling temperature.
        max_tokens: Max response tokens.

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

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except APIError as e:
        logger.error(f"API Error: {e}")
        if max_tokens > 4096:
            logger.info("Retrying with smaller max_tokens...")
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=4096,
            )
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
