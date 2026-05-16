"""Tests pour Client, AsyncClient, et cache implicite."""

from __future__ import annotations

import dataclasses

import anthropic
import pytest

from apicol._client import (
    AsyncClient,
    Client,
    _get_implicit_async_client,
    _get_implicit_sync_client,
)
from apicol._config import Config
from apicol._errors import BackendUnavailableError, ConfigError


class TestClientConstruction:
    def test_minimal_anthropic_client(self) -> None:
        client = Client(backend="anthropic", api_key="sk-x", model="claude-opus-4-7")
        assert client.config.backend == "anthropic"
        assert client.config.model == "claude-opus-4-7"

    def test_client_is_frozen(self) -> None:
        client = Client(backend="anthropic", api_key="x", model="claude-opus-4-7")
        with pytest.raises(dataclasses.FrozenInstanceError):
            client.config = Config(backend="litellm", api_key="y", model="z")

    def test_client_rejects_claude_cli(self) -> None:
        with pytest.raises(ConfigError, match="claude_cli_chat"):
            Client(backend="claude_cli", api_key=None, model=None)


class TestClientChat:
    def test_dispatch_to_anthropic_backend(self, mock_anthropic_sdk) -> None:
        client = Client(backend="anthropic", api_key="x", model="claude-sonnet-4-6")
        result = client.chat([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hello"

    def test_dispatch_to_litellm_backend(self, mock_litellm) -> None:
        client = Client(backend="litellm", api_key="x", model="openai/gpt-5")
        result = client.chat([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hello"

    def test_chat_kwargs_override_model(self, mock_anthropic_sdk) -> None:
        client = Client(backend="anthropic", api_key="x", model="claude-sonnet-4-6")
        client.chat([{"role": "user", "content": "Hi"}], model="claude-opus-4-7")
        call = mock_anthropic_sdk.sync.messages.create.call_args
        assert call.kwargs["model"] == "claude-opus-4-7"


class TestAnthropicNative:
    def test_returns_anthropic_client_when_backend_anthropic(self) -> None:
        client = Client(backend="anthropic", api_key="sk-x", model="claude-opus-4-7")
        native = client.anthropic_native()
        assert isinstance(native, anthropic.Anthropic)

    def test_raises_when_backend_litellm(self) -> None:
        client = Client(backend="litellm", api_key="x", model="openai/gpt-5")
        with pytest.raises(BackendUnavailableError, match="anthropic"):
            client.anthropic_native()


class TestAsyncClient:
    @pytest.mark.asyncio
    async def test_async_chat_dispatch(self, mock_anthropic_sdk) -> None:
        client = AsyncClient(backend="anthropic", api_key="x", model="claude-sonnet-4-6")
        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hello"

    def test_async_anthropic_native(self) -> None:
        client = AsyncClient(backend="anthropic", api_key="x", model="claude-opus-4-7")
        native = client.anthropic_native()
        assert isinstance(native, anthropic.AsyncAnthropic)

    def test_async_anthropic_native_raises_when_backend_litellm(self) -> None:
        client = AsyncClient(backend="litellm", api_key="x", model="openai/gpt-5")
        with pytest.raises(BackendUnavailableError, match="anthropic"):
            client.anthropic_native()


class TestImplicitClientCache:
    def test_same_env_returns_same_client(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        c1 = _get_implicit_sync_client()
        c2 = _get_implicit_sync_client()
        assert c1 is c2

    def test_changed_env_invalidates_cache(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-sonnet-4-6")
        c1 = _get_implicit_sync_client()
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        c2 = _get_implicit_sync_client()
        assert c1 is not c2

    def test_sync_and_async_caches_are_separate(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        sync_c = _get_implicit_sync_client()
        async_c = _get_implicit_async_client()
        assert sync_c is not async_c
        assert isinstance(sync_c, Client)
        assert isinstance(async_c, AsyncClient)

    def test_async_cache_same_env_returns_same_client(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        c1 = _get_implicit_async_client()
        c2 = _get_implicit_async_client()
        assert c1 is c2

    def test_async_cache_changed_env_invalidates(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-sonnet-4-6")
        c1 = _get_implicit_async_client()
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        c2 = _get_implicit_async_client()
        assert c1 is not c2


class TestMultiInstanceSimultaneous:
    def test_two_clients_independent(self, mock_anthropic_sdk, mock_litellm) -> None:
        claude = Client(backend="anthropic", api_key="x", model="claude-sonnet-4-6")
        gpt = Client(backend="litellm", api_key="y", model="openai/gpt-5")
        prompt = [{"role": "user", "content": "Hi"}]
        r1 = claude.chat(prompt)
        r2 = gpt.chat(prompt)
        assert r1["choices"][0]["message"]["content"] == "hello"
        assert r2["choices"][0]["message"]["content"] == "hello"

    def test_three_backends_coexist(
        self, mock_anthropic_sdk, mock_litellm, mock_openai_sdk
    ) -> None:
        claude = Client(backend="anthropic", api_key="x", model="claude-opus-4-7")
        gpt = Client(
            backend="openai-compatible",
            api_key="sk-or-x",
            model="anthropic/claude-haiku-4-5",
            base_url="https://openrouter.ai/api/v1",
        )
        gemini = Client(backend="litellm", api_key="y", model="gemini/gemini-2.5-pro")
        prompt = [{"role": "user", "content": "Hi"}]
        assert claude.chat(prompt)["choices"][0]["message"]["content"] == "hello"
        assert gpt.chat(prompt)["choices"][0]["message"]["content"] == "hello"
        assert gemini.chat(prompt)["choices"][0]["message"]["content"] == "hello"


class TestExtraHeaders:
    def test_extra_headers_stored_in_config(self) -> None:
        client = Client(
            backend="openai-compatible",
            api_key="sk-x",
            model="gpt-5",
            extra_headers={"X-Title": "apicol"},
        )
        assert client.config.extra_headers == {"X-Title": "apicol"}

    def test_extra_headers_propagated_to_openai_constructor(self, mock_openai_sdk) -> None:
        client = Client(
            backend="openai-compatible",
            api_key="sk-x",
            model="gpt-5",
            extra_headers={"X-Title": "apicol"},
        )
        client.chat([{"role": "user", "content": "Hi"}])
        ctor_kwargs = mock_openai_sdk.sync_ctor.call_args.kwargs
        assert ctor_kwargs["default_headers"] == {"X-Title": "apicol"}

    def test_default_extra_headers_is_none(self) -> None:
        client = Client(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        assert client.config.extra_headers is None
