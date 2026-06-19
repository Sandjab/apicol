"""Dispatch backend -> couple (sync_callable, async_callable).

Le routeur ne peut PAS retourner les callables de claude_cli — ces
fonctions sont importées directement dans __init__.py, jamais via _route.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

from apicol._backends import anthropic as anthropic_backend
from apicol._backends import litellm as litellm_backend
from apicol._backends import openai_compatible as openai_compatible_backend
from apicol._config import Config
from apicol._errors import ConfigError

SyncCallable = Callable[..., dict[str, Any]]
AsyncCallable = Callable[..., Awaitable[dict[str, Any]]]
StreamCallable = Callable[..., Iterator[dict[str, Any]]]
AStreamCallable = Callable[..., AsyncIterator[dict[str, Any]]]


def pick_backend(
    config: Config,
) -> tuple[SyncCallable, AsyncCallable, StreamCallable, AStreamCallable]:
    """Retourne (complete, acomplete, stream, astream) pour un Config validé."""
    match config.backend:
        case "anthropic":
            return (
                anthropic_backend.complete,
                anthropic_backend.acomplete,
                anthropic_backend.stream,
                anthropic_backend.astream,
            )
        case "openai-compatible":
            return (
                openai_compatible_backend.complete,
                openai_compatible_backend.acomplete,
                openai_compatible_backend.stream,
                openai_compatible_backend.astream,
            )
        case "litellm":
            return (
                litellm_backend.complete,
                litellm_backend.acomplete,
                litellm_backend.stream,
                litellm_backend.astream,
            )
        case _:  # pragma: no cover
            raise ConfigError(
                f"_route ne peut pas dispatcher backend={config.backend!r}. "
                "Cette erreur signale un bug d'invariant : Config aurait dû "
                "rejeter ce backend en amont."
            )
