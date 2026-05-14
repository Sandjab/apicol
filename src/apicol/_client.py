"""Client / AsyncClient + cache implicite pour les fonctions globales chat/achat.

Client immutable (frozen dataclass), résout son backend une fois à la
construction. _get_implicit_sync_client() et _get_implicit_async_client()
caches module-level keyés par tuple des env vars APICOL_*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import anthropic

from apicol._config import Config, load_from_env
from apicol._errors import BackendUnavailableError
from apicol._route import AsyncCallable, SyncCallable, pick_backend


@dataclass(frozen=True)
class Client:
    """Client synchrone immutable encapsulant une Config + un backend résolu."""

    config: Config = field(init=False)
    _sync_callable: SyncCallable = field(init=False, repr=False, compare=False)
    _async_callable: AsyncCallable = field(init=False, repr=False, compare=False)

    def __init__(
        self,
        backend: str,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        cfg = Config(
            backend=backend,  # type: ignore[arg-type]
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        sync_cb, async_cb = pick_backend(cfg)
        object.__setattr__(self, "config", cfg)
        object.__setattr__(self, "_sync_callable", sync_cb)
        object.__setattr__(self, "_async_callable", async_cb)

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Appel synchrone — dispatche vers le backend résolu."""
        return self._sync_callable(messages, self.config, **kwargs)

    def anthropic_native(self) -> anthropic.Anthropic:
        """Retourne un anthropic.Anthropic préconfiguré.

        Raises:
            BackendUnavailableError: Si backend != 'anthropic'.
        """
        if self.config.backend != "anthropic":
            raise BackendUnavailableError(
                f"anthropic_native() disponible uniquement sur backend='anthropic' "
                f"(actuel : {self.config.backend!r})."
            )
        return anthropic.Anthropic(api_key=self.config.api_key, base_url=self.config.base_url)


@dataclass(frozen=True)
class AsyncClient:
    """Pendant async de Client."""

    config: Config = field(init=False)
    _sync_callable: SyncCallable = field(init=False, repr=False, compare=False)
    _async_callable: AsyncCallable = field(init=False, repr=False, compare=False)

    def __init__(
        self,
        backend: str,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        cfg = Config(
            backend=backend,  # type: ignore[arg-type]
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        sync_cb, async_cb = pick_backend(cfg)
        object.__setattr__(self, "config", cfg)
        object.__setattr__(self, "_sync_callable", sync_cb)
        object.__setattr__(self, "_async_callable", async_cb)

    async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Appel asynchrone — dispatche vers le backend résolu."""
        return await self._async_callable(messages, self.config, **kwargs)

    def anthropic_native(self) -> anthropic.AsyncAnthropic:
        """Retourne un anthropic.AsyncAnthropic préconfiguré.

        Raises:
            BackendUnavailableError: Si backend != 'anthropic'.
        """
        if self.config.backend != "anthropic":
            raise BackendUnavailableError(
                f"anthropic_native() disponible uniquement sur backend='anthropic' "
                f"(actuel : {self.config.backend!r})."
            )
        return anthropic.AsyncAnthropic(api_key=self.config.api_key, base_url=self.config.base_url)


# Cache implicite pour les fonctions globales chat() / achat()
_IMPLICIT_SYNC_CACHE: dict[tuple[str | None, ...], Client] = {}
_IMPLICIT_ASYNC_CACHE: dict[tuple[str | None, ...], AsyncClient] = {}


def _config_to_cache_key(cfg: Config) -> tuple[str | None, ...]:
    return (cfg.backend, cfg.api_key, cfg.model, cfg.base_url)


def _get_implicit_sync_client() -> Client:
    """Retourne un Client implicite depuis env vars, avec cache invalidé par hash."""
    cfg = load_from_env()
    key = _config_to_cache_key(cfg)
    cached = _IMPLICIT_SYNC_CACHE.get(key)
    if cached is not None:
        return cached
    _IMPLICIT_SYNC_CACHE.clear()
    client = Client(
        backend=cfg.backend, api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url
    )
    _IMPLICIT_SYNC_CACHE[key] = client
    return client


def _get_implicit_async_client() -> AsyncClient:
    """Retourne un AsyncClient implicite depuis env vars, avec cache invalidé par hash."""
    cfg = load_from_env()
    key = _config_to_cache_key(cfg)
    cached = _IMPLICIT_ASYNC_CACHE.get(key)
    if cached is not None:
        return cached
    _IMPLICIT_ASYNC_CACHE.clear()
    client = AsyncClient(
        backend=cfg.backend, api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url
    )
    _IMPLICIT_ASYNC_CACHE[key] = client
    return client
