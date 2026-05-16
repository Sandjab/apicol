"""Backend openai-compatible : SDK OpenAI vers tout endpoint /v1/chat/completions.

Couvre OpenAI, Mistral La Plateforme, Ollama, vLLM, LM Studio, OpenRouter,
Groq, DeepSeek, Together AI, Fireworks, Anyscale, et tout proxy qui expose
une interface OpenAI-compatible.

Le SDK OpenAI parle déjà OpenAI : pas de traduction de format. La réponse
ChatCompletion (Pydantic) est convertie en dict via .model_dump() pour
respecter le contrat de retour `dict[str, Any]` partagé par tous les
backends.

extra_headers est appliqué au niveau de la connexion (default_headers du
SDK), pas par appel — utile notamment pour OpenRouter (HTTP-Referer,
X-Title) ou un gateway custom.
"""

from __future__ import annotations

from typing import Any

import openai

from apicol._config import Config
from apicol._errors import BackendError


def _build_client_kwargs(config: Config) -> dict[str, Any]:
    """Prépare les kwargs du constructeur openai.OpenAI / openai.AsyncOpenAI."""
    client_kwargs: dict[str, Any] = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    if config.extra_headers:
        client_kwargs["default_headers"] = config.extra_headers
    return client_kwargs


def _build_call_kwargs(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> dict[str, Any]:
    """Prépare les kwargs de chat.completions.create."""
    model = kwargs.pop("model", None) or config.model
    if not model:
        raise BackendError("model requis : ni dans Config ni dans kwargs.")

    call_kwargs: dict[str, Any] = {"model": model, "messages": messages}
    call_kwargs.update(kwargs)
    return call_kwargs


def complete(messages: list[dict[str, Any]], config: Config, **kwargs: Any) -> dict[str, Any]:
    """Appel synchrone via le SDK OpenAI."""
    client = openai.OpenAI(**_build_client_kwargs(config))
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    try:
        response = client.chat.completions.create(**call_kwargs)
    except openai.APIError as e:
        raise BackendError(f"OpenAI-compatible API error: {e}") from e
    result: dict[str, Any] = response.model_dump()
    return result


async def acomplete(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> dict[str, Any]:
    """Pendant async de complete()."""
    client = openai.AsyncOpenAI(**_build_client_kwargs(config))
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    try:
        response = await client.chat.completions.create(**call_kwargs)
    except openai.APIError as e:
        raise BackendError(f"OpenAI-compatible API error: {e}") from e
    result: dict[str, Any] = response.model_dump()
    return result
