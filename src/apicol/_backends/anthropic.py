"""Backend Anthropic : SDK natif + traduction OpenAI<->Anthropic.

La traduction est faite UNIQUEMENT à la frontière de ce module :
- _openai_to_anthropic : kwargs OpenAI -> kwargs anthropic.messages.create
- _anthropic_to_openai : anthropic.Message -> dict format OpenAI

Le reste de la lib parle OpenAI partout.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

import anthropic

from apicol._backends import reject_chat_stream, resolve_model
from apicol._config import Config
from apicol._errors import BackendError, NotSupportedError

logger = logging.getLogger("apicol")

_DEFAULT_MAX_TOKENS = 4096

_REASONING_BUDGET = {"low": 1024, "medium": 4096, "high": 16384}

_STOP_REASON_MAP = {
    "end_turn": "stop",
    "max_tokens": "length",
    "stop_sequence": "stop",
    "tool_use": "tool_calls",
}


def _is_opus_4_7(model: str) -> bool:
    """Détecte les modèles Opus 4.7 qui exigent le mode thinking adaptive."""
    return "opus-4-7" in (model or "").lower()


def _openai_to_anthropic(
    messages: list[dict[str, Any]],
    *,
    model: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    extra_body: dict[str, Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Traduit des kwargs OpenAI en kwargs anthropic.messages.create.

    Raises:
        NotSupportedError: Si tool calls ou role='tool' détecté.
    """
    if tools:
        raise NotSupportedError("tools n'est pas encore supporté (cf. roadmap v0.3).")
    if any(m.get("role") == "tool" for m in messages):
        raise NotSupportedError("Les messages role='tool' ne sont pas encore supportés.")

    system_parts: list[str] = []
    out_messages: list[dict[str, Any]] = []
    for msg in messages:
        if msg["role"] == "system":
            content = msg["content"]
            if isinstance(content, list):
                system_parts.append("".join(b["text"] for b in content if b.get("type") == "text"))
            else:
                system_parts.append(str(content))
        else:
            out_messages.append({"role": msg["role"], "content": msg["content"]})

    payload: dict[str, Any] = {"model": model, "messages": out_messages}

    if system_parts:
        payload["system"] = "\n\n".join(system_parts)

    if max_tokens is None:
        logger.warning(
            "max_tokens non précisé, default à %d (Anthropic requiert ce champ)",
            _DEFAULT_MAX_TOKENS,
        )
        payload["max_tokens"] = _DEFAULT_MAX_TOKENS
    else:
        payload["max_tokens"] = max_tokens

    if temperature is not None:
        payload["temperature"] = temperature

    if reasoning_effort and reasoning_effort != "none":
        if _is_opus_4_7(model):
            payload["thinking"] = {"type": "adaptive"}
            logger.debug(
                "Mapping reasoning_effort=%s -> adaptive (Opus 4.7)",
                reasoning_effort,
            )
        else:
            budget = _REASONING_BUDGET[reasoning_effort]
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
            logger.debug(
                "Mapping reasoning_effort=%s -> budget_tokens=%d",
                reasoning_effort,
                budget,
            )

    if extra_body:
        payload.update(extra_body)

    return payload


def _anthropic_to_openai(response: Any) -> dict[str, Any]:
    """Reformate une anthropic.Message en dict format OpenAI."""
    text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    content = "".join(text_parts)

    input_tokens = getattr(response.usage, "input_tokens", 0)
    output_tokens = getattr(response.usage, "output_tokens", 0)

    return {
        "id": response.id,
        "model": response.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": _STOP_REASON_MAP.get(response.stop_reason, "stop"),
            }
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }


def _text_delta_chunk(model: str, text: str) -> dict[str, Any]:
    return {
        "model": model,
        "choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}],
    }


def _final_chunk(model: str, stop_reason: str | None, usage: Any) -> dict[str, Any]:
    mapped = _STOP_REASON_MAP.get(stop_reason or "", "stop")
    chunk: dict[str, Any] = {
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": mapped}],
    }
    if usage is not None:
        it = getattr(usage, "input_tokens", 0)
        ot = getattr(usage, "output_tokens", 0)
        chunk["usage"] = {"prompt_tokens": it, "completion_tokens": ot, "total_tokens": it + ot}
    return chunk


def complete(messages: list[dict[str, Any]], config: Config, **kwargs: Any) -> dict[str, Any]:
    """Appel synchrone au backend Anthropic."""
    reject_chat_stream(kwargs)
    model = resolve_model(config, kwargs)
    client = anthropic.Anthropic(api_key=config.api_key, base_url=config.base_url)
    payload = _openai_to_anthropic(messages, model=model, **kwargs)
    try:
        response = client.messages.create(**payload)
    except anthropic.APIError as e:
        raise BackendError(f"Anthropic API error: {e}") from e
    return _anthropic_to_openai(response)


async def acomplete(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> dict[str, Any]:
    """Pendant async de complete()."""
    reject_chat_stream(kwargs)
    model = resolve_model(config, kwargs)
    client = anthropic.AsyncAnthropic(api_key=config.api_key, base_url=config.base_url)
    payload = _openai_to_anthropic(messages, model=model, **kwargs)
    try:
        response = await client.messages.create(**payload)
    except anthropic.APIError as e:
        raise BackendError(f"Anthropic API error: {e}") from e
    return _anthropic_to_openai(response)


def stream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> Iterator[dict[str, Any]]:
    """Streaming synchrone Anthropic : events -> chunks format OpenAI (texte seulement)."""
    model = resolve_model(config, kwargs)
    payload = _openai_to_anthropic(messages, model=model, **kwargs)
    client = anthropic.Anthropic(api_key=config.api_key, base_url=config.base_url)
    try:
        with client.messages.stream(**payload) as s:
            for text in s.text_stream:
                yield _text_delta_chunk(model, text)
            final = s.get_final_message()
        yield _final_chunk(model, final.stop_reason, final.usage)
    except anthropic.APIError as e:
        raise BackendError(f"Anthropic API error: {e}") from e


async def astream(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> AsyncIterator[dict[str, Any]]:
    """Pendant async de stream()."""
    model = resolve_model(config, kwargs)
    payload = _openai_to_anthropic(messages, model=model, **kwargs)
    client = anthropic.AsyncAnthropic(api_key=config.api_key, base_url=config.base_url)
    try:
        async with client.messages.stream(**payload) as s:
            async for text in s.text_stream:
                yield _text_delta_chunk(model, text)
            final = await s.get_final_message()
        yield _final_chunk(model, final.stop_reason, final.usage)
    except anthropic.APIError as e:
        raise BackendError(f"Anthropic API error: {e}") from e
