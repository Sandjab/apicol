"""apicol — Couche d'abstraction multi-backend pour appels LLM.

Surface publique :
- Client, AsyncClient (configurations immutables multi-instance)
- chat, achat (fonctions globales utilisant un Client implicite)
- anthropic_client, anthropic_async_client (échappatoire native Anthropic)
- claude_cli_chat, claude_cli_achat (subprocess `claude -p`, dev only)
- Erreurs : ApicolError, ConfigError, BackendUnavailableError,
  BackendError, NotSupportedError

Voir README.md pour les exemples, SPEC.md pour le contrat d'API.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import anthropic

from apicol._backends.claude_cli import acomplete as claude_cli_achat
from apicol._backends.claude_cli import complete as claude_cli_chat
from apicol._client import (
    AsyncClient,
    Client,
    _get_implicit_async_client,
    _get_implicit_sync_client,
)
from apicol._errors import (
    ApicolError,
    BackendError,
    BackendUnavailableError,
    ConfigError,
    NotSupportedError,
)

try:
    __version__ = version("apicol")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"


def chat(messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Appel synchrone à un LLM via le backend configuré par env vars.

    Utilise un Client implicite construit depuis APICOL_TYPE/KEY/MODEL/URL,
    avec cache module-level invalidé par hash des env vars.

    Args:
        messages: Format OpenAI (role, content).
        **kwargs: Voir SPEC.md (temperature, max_tokens, reasoning_effort,
            extra_body, model, base_url).

    Returns:
        Dict format OpenAI : {id, model, choices, usage}.

    Raises:
        ConfigError: env vars manquantes/invalides.
        NotSupportedError: Feature v0.1 hors scope (tools, streaming).
        BackendError: Erreur upstream wrappée (cf. __cause__).
    """
    return _get_implicit_sync_client().chat(messages, **kwargs)


async def achat(messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Pendant async de chat(). Mêmes paramètres et erreurs."""
    return await _get_implicit_async_client().chat(messages, **kwargs)


def stream(messages: list[dict[str, Any]], **kwargs: Any) -> Iterator[dict[str, Any]]:
    """Streaming synchrone via le backend configuré par env vars.

    Yield des dicts au format OpenAI chunk. Voir Client.stream pour la sémantique
    (le générateur lève à l'itération, erreurs SDK wrappées en BackendError).
    """
    return _get_implicit_sync_client().stream(messages, **kwargs)


def astream(messages: list[dict[str, Any]], **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
    """Pendant async de stream(). À consommer avec `async for`."""
    return _get_implicit_async_client().stream(messages, **kwargs)


def anthropic_client() -> anthropic.Anthropic:
    """Échappatoire native : retourne un anthropic.Anthropic préconfiguré.

    Construit un Client implicite depuis les env vars puis appelle
    .anthropic_native() dessus. Équivalent à
    `apicol.Client(...).anthropic_native()`.

    Raises:
        BackendUnavailableError: Si APICOL_TYPE != 'anthropic'.
        ConfigError: env vars manquantes/invalides.
    """
    return _get_implicit_sync_client().anthropic_native()


def anthropic_async_client() -> anthropic.AsyncAnthropic:
    """Pendant async de anthropic_client()."""
    return _get_implicit_async_client().anthropic_native()


__all__ = [
    "ApicolError",
    "AsyncClient",
    "BackendError",
    "BackendUnavailableError",
    "Client",
    "ConfigError",
    "NotSupportedError",
    "__version__",
    "achat",
    "anthropic_async_client",
    "anthropic_client",
    "astream",
    "chat",
    "claude_cli_achat",
    "claude_cli_chat",
    "stream",
]
