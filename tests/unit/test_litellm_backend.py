"""Tests unitaires pour le backend LiteLLM."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import litellm
import pytest
import pytest_mock

from apicol._backends import litellm as backend
from apicol._config import Config
from apicol._errors import BackendError


class TestDetectProviderEnvVar:
    @pytest.mark.parametrize(
        "model,expected",
        [
            ("openai/gpt-5", "OPENAI_API_KEY"),
            ("gemini/gemini-2.5-pro", "GEMINI_API_KEY"),
            ("anthropic/claude-3", "ANTHROPIC_API_KEY"),
            ("ollama/qwen3:32b", "OLLAMA_API_KEY"),
            ("openrouter/anthropic/claude-3.5", "OPENROUTER_API_KEY"),
            ("lm_studio/llama3", "LM_STUDIO_API_KEY"),
        ],
    )
    def test_known_providers(self, model: str, expected: str) -> None:
        assert backend._detect_provider_env_var(model) == expected

    def test_unknown_provider_falls_back_to_uppercase(self) -> None:
        assert backend._detect_provider_env_var("foobar/x") == "FOOBAR_API_KEY"

    def test_no_slash_returns_none(self) -> None:
        assert backend._detect_provider_env_var("gpt-5") is None


class TestComplete:
    def test_pass_through_messages(self, mock_litellm: MagicMock) -> None:
        cfg = Config(backend="litellm", api_key="sk-x", model="openai/gpt-5")
        messages = [{"role": "user", "content": "Hi"}]
        result = backend.complete(messages, cfg)
        call = mock_litellm.sync_call.call_args
        assert call.kwargs["messages"] == messages
        assert call.kwargs["model"] == "openai/gpt-5"
        assert result["choices"][0]["message"]["content"] == "hello"

    def test_injects_provider_env_var(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = Config(backend="litellm", api_key="injected-key", model="openai/gpt-5")
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        assert os.environ.get("OPENAI_API_KEY") == "injected-key"

    def test_does_not_overwrite_existing_provider_env_var(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "preset-key")
        cfg = Config(backend="litellm", api_key="injected-key", model="openai/gpt-5")
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        assert os.environ.get("OPENAI_API_KEY") == "preset-key"

    def test_injects_api_base(self, mock_litellm: MagicMock) -> None:
        cfg = Config(
            backend="litellm",
            api_key="ollama",
            model="ollama/qwen3:32b",
            base_url="http://localhost:11434",
        )
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        call = mock_litellm.sync_call.call_args
        assert call.kwargs["api_base"] == "http://localhost:11434"

    def test_wraps_litellm_exception(self, mocker: pytest_mock.MockerFixture) -> None:
        mocker.patch(
            "litellm.completion",
            side_effect=litellm.exceptions.APIError(
                status_code=500,
                message="boom",
                llm_provider="openai",
                model="gpt-5",
            ),
        )
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        with pytest.raises(BackendError) as exc_info:
            backend.complete([{"role": "user", "content": "Hi"}], cfg)
        assert isinstance(exc_info.value.__cause__, litellm.exceptions.APIError)

    def test_raises_backend_error_when_no_model(self, mock_litellm: MagicMock) -> None:
        # Config sans model + pas de model= dans kwargs -> BackendError
        cfg = Config(backend="litellm", api_key="x", model=None, base_url="http://x")
        with pytest.raises(BackendError, match="model requis"):
            backend.complete([{"role": "user", "content": "Hi"}], cfg)

    def test_no_api_key_skips_env_injection(
        self, mock_litellm: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        cfg = Config(
            backend="litellm",
            api_key=None,
            model="ollama/qwen3:32b",
            base_url="http://localhost:11434",
        )
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        assert os.environ.get("OLLAMA_API_KEY") is None

    def test_extra_body_merged_into_call_kwargs(self, mock_litellm: MagicMock) -> None:
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        backend.complete(
            [{"role": "user", "content": "Hi"}],
            cfg,
            extra_body={"safety_settings": "off"},
        )
        call = mock_litellm.sync_call.call_args
        assert call.kwargs.get("safety_settings") == "off"

    def test_wraps_bad_request_error(self, mocker: pytest_mock.MockerFixture) -> None:
        mocker.patch(
            "litellm.completion",
            side_effect=litellm.exceptions.BadRequestError(
                message="bad", model="gpt-5", llm_provider="openai"
            ),
        )
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        with pytest.raises(BackendError) as exc_info:
            backend.complete([{"role": "user", "content": "Hi"}], cfg)
        assert isinstance(exc_info.value.__cause__, litellm.exceptions.BadRequestError)


class TestAcomplete:
    @pytest.mark.asyncio
    async def test_acomplete_pass_through(self, mock_litellm: MagicMock) -> None:
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        result = await backend.acomplete([{"role": "user", "content": "Hi"}], cfg)
        assert result["choices"][0]["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_acomplete_wraps_api_error(self, mocker: pytest_mock.MockerFixture) -> None:
        async def _raise(**_kwargs: object) -> dict[str, object]:
            raise litellm.exceptions.APIError(
                status_code=500, message="boom", llm_provider="openai", model="gpt-5"
            )

        mocker.patch("litellm.acompletion", side_effect=_raise)
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        with pytest.raises(BackendError) as exc_info:
            await backend.acomplete([{"role": "user", "content": "Hi"}], cfg)
        assert isinstance(exc_info.value.__cause__, litellm.exceptions.APIError)

    @pytest.mark.asyncio
    async def test_acomplete_wraps_bad_request_error(
        self, mocker: pytest_mock.MockerFixture
    ) -> None:
        async def _raise(**_kwargs: object) -> dict[str, object]:
            raise litellm.exceptions.BadRequestError(
                message="bad", model="gpt-5", llm_provider="openai"
            )

        mocker.patch("litellm.acompletion", side_effect=_raise)
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        with pytest.raises(BackendError) as exc_info:
            await backend.acomplete([{"role": "user", "content": "Hi"}], cfg)
        assert isinstance(exc_info.value.__cause__, litellm.exceptions.BadRequestError)
