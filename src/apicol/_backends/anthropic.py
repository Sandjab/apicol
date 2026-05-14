"""Backend Anthropic : SDK natif + traduction OpenAI<->Anthropic.

La traduction est faite UNIQUEMENT à la frontière de ce module :
- _openai_to_anthropic : kwargs OpenAI -> kwargs anthropic.messages.create
- _anthropic_to_openai : anthropic.Message -> dict format OpenAI

Le reste de la lib parle OpenAI partout.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic

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
    stream: bool = False,
    tools: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Traduit des kwargs OpenAI en kwargs anthropic.messages.create.

    Raises:
        NotSupportedError: Si streaming, tool calls, ou role='tool' détecté.
    """
    if stream:
        raise NotSupportedError("stream=True n'est pas supporté en v0.1.0 (cf. roadmap v0.2).")
    if tools:
        raise NotSupportedError("tools n'est pas supporté en v0.1.0 (cf. roadmap v0.3).")
    if any(m.get("role") == "tool" for m in messages):
        raise NotSupportedError("Les messages role='tool' ne sont pas supportés en v0.1.0.")

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


def complete(messages: list[dict[str, Any]], config: Config, **kwargs: Any) -> dict[str, Any]:
    """Appel synchrone au backend Anthropic."""
    model = kwargs.pop("model", None) or config.model
    if not model:
        raise BackendError("model requis : ni dans Config ni dans kwargs.")
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
    model = kwargs.pop("model", None) or config.model
    if not model:
        raise BackendError("model requis : ni dans Config ni dans kwargs.")
    client = anthropic.AsyncAnthropic(api_key=config.api_key, base_url=config.base_url)
    payload = _openai_to_anthropic(messages, model=model, **kwargs)
    try:
        response = await client.messages.create(**payload)
    except anthropic.APIError as e:
        raise BackendError(f"Anthropic API error: {e}") from e
    return _anthropic_to_openai(response)
