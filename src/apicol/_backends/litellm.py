"""Backend LiteLLM : pass-through pur + injection contrôlée d'env vars.

LiteLLM gère déjà 100+ providers. On ne traduit rien sur les messages.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import litellm

from apicol._backends import reject_chat_stream, resolve_model
from apicol._config import Config
from apicol._errors import BackendError

logger = logging.getLogger("apicol")

_PROVIDER_ENV_OVERRIDES: dict[str, str] = {
    "lm_studio": "LM_STUDIO_API_KEY",
}


def _detect_provider_env_var(model: str) -> str | None:
    """Déduit le nom d'env var à injecter pour un nom de modèle LiteLLM."""
    if "/" not in model:
        return None
    provider = model.split("/", 1)[0].lower()
    if provider in _PROVIDER_ENV_OVERRIDES:
        return _PROVIDER_ENV_OVERRIDES[provider]
    return f"{provider.upper()}_API_KEY"


def _build_call_kwargs(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> dict[str, Any]:
    """Prépare les kwargs LiteLLM + injecte env var + api_base."""
    model = resolve_model(config, kwargs)

    if config.api_key:
        env_var = _detect_provider_env_var(model)
        if env_var and not os.environ.get(env_var):
            os.environ[env_var] = config.api_key
            logger.debug("Injected APICOL_KEY into %s", env_var)

    call_kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if config.base_url:
        call_kwargs["api_base"] = config.base_url

    extra_body = kwargs.pop("extra_body", None)
    if extra_body:
        call_kwargs.update(extra_body)
    call_kwargs.update(kwargs)

    return call_kwargs


def complete(messages: list[dict[str, Any]], config: Config, **kwargs: Any) -> dict[str, Any]:
    """Appel synchrone via LiteLLM."""
    reject_chat_stream(kwargs)
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    try:
        result: dict[str, Any] = litellm.completion(**call_kwargs)
        return result
    except litellm.exceptions.APIError as e:
        raise BackendError(f"LiteLLM API error: {e}") from e
    except litellm.exceptions.BadRequestError as e:
        raise BackendError(f"LiteLLM bad request: {e}") from e


async def acomplete(
    messages: list[dict[str, Any]], config: Config, **kwargs: Any
) -> dict[str, Any]:
    """Pendant async de complete()."""
    reject_chat_stream(kwargs)
    call_kwargs = _build_call_kwargs(messages, config, **kwargs)
    try:
        result: dict[str, Any] = await litellm.acompletion(**call_kwargs)
        return result
    except litellm.exceptions.APIError as e:
        raise BackendError(f"LiteLLM API error: {e}") from e
    except litellm.exceptions.BadRequestError as e:
        raise BackendError(f"LiteLLM bad request: {e}") from e
