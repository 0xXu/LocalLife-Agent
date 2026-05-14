from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI

from backend.llm.config import LLMConfig

# --- MiMo reasoning_content compatibility ---
# MiMo API returns reasoning_content in responses and requires it to be
# passed back in subsequent assistant messages during multi-turn tool calling.
#
# Two-sided fix:
# 1. CAPTURE: Override _stream/_astream to extract reasoning_content from
#    raw streaming chunk dicts before _convert_delta_to_message_chunk drops it.
# 2. RE-INJECTION: Monkey-patch _convert_message_to_dict to include
#    reasoning_content when converting AIMessage back to API format.

import langchain_openai.chat_models.base as _openai_base

_orig_convert = _openai_base._convert_message_to_dict


def _patched_convert_message_to_dict(message: BaseMessage, **kwargs: Any) -> dict:
    msg_dict = _orig_convert(message, **kwargs)
    if isinstance(message, AIMessage) and "reasoning_content" in message.additional_kwargs:
        msg_dict["reasoning_content"] = message.additional_kwargs["reasoning_content"]
    return msg_dict


_openai_base._convert_message_to_dict = _patched_convert_message_to_dict


def _inject_reasoning(
    chunk: ChatGenerationChunk, accumulated: str
) -> ChatGenerationChunk:
    """Inject accumulated reasoning_content into a ChatGenerationChunk's additional_kwargs."""
    if accumulated and chunk.message and isinstance(chunk.message, AIMessageChunk):
        chunk.message.additional_kwargs["reasoning_content"] = accumulated
    return chunk


class MiMoChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass that captures reasoning_content from MiMo API responses."""

    def _create_chat_result(self, response: Any, generation_info: dict | None = None):
        result = super()._create_chat_result(response, generation_info)
        # Extract reasoning_content from raw response choices
        choices = []
        if hasattr(response, "get"):
            choices = response.get("choices", [])
        elif hasattr(response, "choices"):
            for c in response.choices:
                msg = getattr(c, "message", None)
                if msg and hasattr(msg, "reasoning_content"):
                    choices.append({"message": {"reasoning_content": msg.reasoning_content}})

        for choice in choices:
            if isinstance(choice, dict):
                rc = choice.get("message", {}).get("reasoning_content")
                if rc and result.generations:
                    for gen in result.generations:
                        if hasattr(gen, "message") and isinstance(gen.message, AIMessage):
                            gen.message.additional_kwargs["reasoning_content"] = rc
        return result

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        *,
        stream_usage: bool | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Override _stream to capture reasoning_content from raw streaming chunks.

        The parent _stream calls _convert_chunk_to_generation_chunk which delegates
        to _convert_delta_to_message_chunk — both drop non-standard fields like
        reasoning_content. We replicate the parent loop but extract reasoning_content
        from the raw chunk dict (chunk_dict["choices"][0]["delta"]["reasoning_content"])
        BEFORE conversion, accumulate it across chunks, and inject it into each
        yielded ChatGenerationChunk so the final merged AIMessage carries the full text.
        """
        self._ensure_sync_client_available()
        kwargs["stream"] = True
        stream_usage_v = self._should_stream_usage(stream_usage, **kwargs)
        if stream_usage_v:
            kwargs["stream_options"] = {"include_usage": stream_usage_v}
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        default_chunk_class = AIMessageChunk
        base_generation_info: dict = {}

        response = self.client.create(**payload)
        accumulated = ""
        with response:
            is_first_chunk = True
            for chunk in response:
                if not isinstance(chunk, dict):
                    chunk_dict = chunk.model_dump()
                else:
                    chunk_dict = chunk
                # Extract reasoning_content from raw delta BEFORE conversion drops it
                if chunk_dict.get("choices"):
                    delta = chunk_dict["choices"][0].get("delta", {})
                    rc = delta.get("reasoning_content")
                    if rc:
                        accumulated += rc
                generation_chunk = self._convert_chunk_to_generation_chunk(
                    chunk_dict,
                    default_chunk_class,
                    base_generation_info if is_first_chunk else {},
                )
                if generation_chunk is None:
                    continue
                default_chunk_class = generation_chunk.message.__class__
                if accumulated:
                    _inject_reasoning(generation_chunk, accumulated)
                logprobs = (generation_chunk.generation_info or {}).get("logprobs")
                if run_manager:
                    run_manager.on_llm_new_token(
                        generation_chunk.text,
                        chunk=generation_chunk,
                        logprobs=logprobs,
                    )
                is_first_chunk = False
                yield generation_chunk

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        *,
        stream_usage: bool | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Async version of _stream with reasoning_content capture."""
        kwargs["stream"] = True
        stream_usage_v = self._should_stream_usage(stream_usage, **kwargs)
        if stream_usage_v:
            kwargs["stream_options"] = {"include_usage": stream_usage_v}
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        default_chunk_class = AIMessageChunk
        base_generation_info: dict = {}

        response = await self.async_client.create(**payload)
        accumulated = ""
        async with response:
            is_first_chunk = True
            async for chunk in response:
                if not isinstance(chunk, dict):
                    chunk_dict = chunk.model_dump()
                else:
                    chunk_dict = chunk
                if chunk_dict.get("choices"):
                    delta = chunk_dict["choices"][0].get("delta", {})
                    rc = delta.get("reasoning_content")
                    if rc:
                        accumulated += rc
                generation_chunk = self._convert_chunk_to_generation_chunk(
                    chunk_dict,
                    default_chunk_class,
                    base_generation_info if is_first_chunk else {},
                )
                if generation_chunk is None:
                    continue
                default_chunk_class = generation_chunk.message.__class__
                if accumulated:
                    _inject_reasoning(generation_chunk, accumulated)
                logprobs = (generation_chunk.generation_info or {}).get("logprobs")
                if run_manager:
                    await run_manager.on_llm_new_token(
                        generation_chunk.text,
                        chunk=generation_chunk,
                        logprobs=logprobs,
                    )
                is_first_chunk = False
                yield generation_chunk


def build_chat_model(config: LLMConfig, temperature: float = 0.2) -> ChatOpenAI:
    """Build a LangChain ChatOpenAI instance from an LLMConfig."""
    if not config.is_configured:
        raise RuntimeError("LLM is not configured.")
    if not config.remote_enabled:
        raise RuntimeError("LLM remote is disabled.")
    return ChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout_seconds,
        streaming=True,
    )


def build_mimo_chat_model(config: LLMConfig, temperature: float = 0.2) -> MiMoChatOpenAI:
    """Build a MiMo-compatible ChatOpenAI that handles reasoning_content."""
    if not config.is_configured:
        raise RuntimeError("LLM is not configured.")
    if not config.remote_enabled:
        raise RuntimeError("LLM remote is disabled.")
    return MiMoChatOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        temperature=temperature,
        max_tokens=config.max_tokens,
        timeout=config.timeout_seconds,
        streaming=True,
    )
