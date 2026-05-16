"""Tests unitaires pour le backend openai-compatible."""

from __future__ import annotations

from unittest.mock import MagicMock

import openai
import pytest
import pytest_mock

from apicol._backends import openai_compatible as backend
from apicol._config import Config
from apicol._errors import BackendError


class TestComplete:
    def test_pass_through_messages_and_model(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        messages = [{"role": "user", "content": "Hi"}]
        result = backend.complete(messages, cfg)
        call = mock_openai_sdk.sync_client.chat.completions.create.call_args
        assert call.kwargs["messages"] == messages
        assert call.kwargs["model"] == "gpt-5"
        assert result["choices"][0]["message"]["content"] == "hello"

    def test_propagates_api_key_to_constructor(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-secret", model="gpt-5")
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        ctor_kwargs = mock_openai_sdk.sync_ctor.call_args.kwargs
        assert ctor_kwargs["api_key"] == "sk-secret"

    def test_propagates_base_url_to_constructor(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(
            backend="openai-compatible",
            api_key="ollama",
            model="qwen3:32b",
            base_url="http://localhost:11434/v1",
        )
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        ctor_kwargs = mock_openai_sdk.sync_ctor.call_args.kwargs
        assert ctor_kwargs["base_url"] == "http://localhost:11434/v1"

    def test_no_base_url_omits_constructor_kwarg(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        ctor_kwargs = mock_openai_sdk.sync_ctor.call_args.kwargs
        assert "base_url" not in ctor_kwargs

    def test_propagates_extra_headers_as_default_headers(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(
            backend="openai-compatible",
            api_key="sk-or-x",
            model="anthropic/claude-haiku-4-5",
            base_url="https://openrouter.ai/api/v1",
            extra_headers={"HTTP-Referer": "https://example.com", "X-Title": "apicol"},
        )
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        ctor_kwargs = mock_openai_sdk.sync_ctor.call_args.kwargs
        assert ctor_kwargs["default_headers"] == {
            "HTTP-Referer": "https://example.com",
            "X-Title": "apicol",
        }

    def test_no_extra_headers_omits_default_headers(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        ctor_kwargs = mock_openai_sdk.sync_ctor.call_args.kwargs
        assert "default_headers" not in ctor_kwargs

    def test_kwargs_passed_through_to_create(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        backend.complete(
            [{"role": "user", "content": "Hi"}],
            cfg,
            temperature=0.7,
            max_tokens=100,
            reasoning_effort="medium",
        )
        call = mock_openai_sdk.sync_client.chat.completions.create.call_args
        assert call.kwargs["temperature"] == 0.7
        assert call.kwargs["max_tokens"] == 100
        assert call.kwargs["reasoning_effort"] == "medium"

    def test_chat_kwarg_overrides_config_model(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        backend.complete(
            [{"role": "user", "content": "Hi"}],
            cfg,
            model="gpt-5-mini",
        )
        call = mock_openai_sdk.sync_client.chat.completions.create.call_args
        assert call.kwargs["model"] == "gpt-5-mini"

    def test_raises_backend_error_when_no_model(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(
            backend="openai-compatible",
            api_key="sk-x",
            model=None,
            base_url="http://localhost:11434/v1",
        )
        with pytest.raises(BackendError, match="model requis"):
            backend.complete([{"role": "user", "content": "Hi"}], cfg)

    def test_wraps_openai_api_error(self, mocker: pytest_mock.MockerFixture) -> None:
        sync_client = MagicMock()
        sync_client.chat.completions.create.side_effect = openai.APIError(
            message="boom", request=MagicMock(), body=None
        )
        mocker.patch("openai.OpenAI", return_value=sync_client)
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        with pytest.raises(BackendError) as exc_info:
            backend.complete([{"role": "user", "content": "Hi"}], cfg)
        assert isinstance(exc_info.value.__cause__, openai.APIError)


class TestAcomplete:
    @pytest.mark.asyncio
    async def test_acomplete_pass_through(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        result = await backend.acomplete([{"role": "user", "content": "Hi"}], cfg)
        assert result["choices"][0]["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_acomplete_propagates_extra_headers(self, mock_openai_sdk: MagicMock) -> None:
        cfg = Config(
            backend="openai-compatible",
            api_key="sk-or-x",
            model="anthropic/claude-haiku-4-5",
            base_url="https://openrouter.ai/api/v1",
            extra_headers={"X-Title": "apicol"},
        )
        await backend.acomplete([{"role": "user", "content": "Hi"}], cfg)
        ctor_kwargs = mock_openai_sdk.async_ctor.call_args.kwargs
        assert ctor_kwargs["default_headers"] == {"X-Title": "apicol"}

    @pytest.mark.asyncio
    async def test_acomplete_wraps_api_error(self, mocker: pytest_mock.MockerFixture) -> None:
        async_client = MagicMock()

        async def _raise(**_kwargs: object) -> object:
            raise openai.APIError(message="boom", request=MagicMock(), body=None)

        async_client.chat.completions.create.side_effect = _raise
        mocker.patch("openai.AsyncOpenAI", return_value=async_client)
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        with pytest.raises(BackendError) as exc_info:
            await backend.acomplete([{"role": "user", "content": "Hi"}], cfg)
        assert isinstance(exc_info.value.__cause__, openai.APIError)
