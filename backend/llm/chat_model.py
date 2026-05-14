from __future__ import annotations

from langchain_openai import ChatOpenAI

from backend.llm.config import LLMConfig


def build_chat_model(config: LLMConfig, temperature: float = 0.3) -> ChatOpenAI:
    """Build a LangChain ChatOpenAI from our LLMConfig.

    Uses OpenAI-compatible endpoint. Supports native function calling.
    """
    if not config.is_configured or not config.remote_enabled:
        raise RuntimeError("LLM is not configured or remote is disabled.")
    return ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout_seconds,
        streaming=True,
    )
