from __future__ import annotations

from langchain_openai import ChatOpenAI

from backend.llm.config import LLMConfig


def build_chat_model(config: LLMConfig, temperature: float = 0.2) -> ChatOpenAI:
    """Build a LangChain ChatOpenAI instance from an LLMConfig."""
    if not config.is_configured:
        raise RuntimeError("LLM is not configured.")
    if not config.remote_enabled:
        raise RuntimeError("LLM remote is disabled.")
    model_kwargs: dict = {}
    if config.response_format == "json_object":
        model_kwargs["response_format"] = {"type": "json_object"}
    if config.disable_thinking:
        model_kwargs["thinking"] = {"type": "disabled"}
    return ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout_seconds,
        streaming=True,
        model_kwargs=model_kwargs,
    )
