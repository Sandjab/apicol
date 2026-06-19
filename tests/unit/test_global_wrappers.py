"""Tests pour la surface publique apicol.* (wrappers globaux + garde-fous TOS)."""

from __future__ import annotations

import anthropic
import pytest
import pytest_mock

import apicol
from apicol._errors import BackendUnavailableError, ConfigError


class TestPublicSurface:
    def test_top_level_exports(self) -> None:
        expected = {
            "Client",
            "AsyncClient",
            "chat",
            "achat",
            "anthropic_client",
            "anthropic_async_client",
            "claude_cli_chat",
            "claude_cli_achat",
            "ApicolError",
            "ConfigError",
            "BackendUnavailableError",
            "BackendError",
            "NotSupportedError",
            "__version__",
        }
        for name in expected:
            assert hasattr(apicol, name), f"apicol.{name} manquant"

    def test_version_is_str(self) -> None:
        assert isinstance(apicol.__version__, str)
        assert apicol.__version__

    def test_apicol_error_is_root(self) -> None:
        for sub in (
            apicol.ConfigError,
            apicol.BackendUnavailableError,
            apicol.BackendError,
            apicol.NotSupportedError,
        ):
            assert issubclass(sub, apicol.ApicolError)


class TestTOSBoundaryByModule:
    """Garantie que claude_cli_chat/achat sont importés depuis _backends,
    pas depuis _client ou _route. C'est la frontière TOS testée."""

    def test_claude_cli_chat_module(self) -> None:
        assert apicol.claude_cli_chat.__module__ == "apicol._backends.claude_cli"

    def test_claude_cli_achat_module(self) -> None:
        assert apicol.claude_cli_achat.__module__ == "apicol._backends.claude_cli"


class TestChatWrapper:
    def test_chat_uses_implicit_client(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None, mock_anthropic_sdk
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-sonnet-4-6")
        result = apicol.chat([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hello"

    def test_chat_raises_config_error_without_env(self, clean_env: None) -> None:
        with pytest.raises(ConfigError):
            apicol.chat([{"role": "user", "content": "Hi"}])


class TestAchatWrapper:
    @pytest.mark.asyncio
    async def test_achat_uses_implicit_async_client(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None, mock_anthropic_sdk
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-sonnet-4-6")
        result = await apicol.achat([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "hello"


class TestAnthropicClientWrapper:
    def test_anthropic_client_returns_anthropic_anthropic(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        native = apicol.anthropic_client()
        assert isinstance(native, anthropic.Anthropic)

    def test_anthropic_async_client_returns_async(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        native = apicol.anthropic_async_client()
        assert isinstance(native, anthropic.AsyncAnthropic)

    def test_anthropic_client_unavailable_for_litellm(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "litellm")
        monkeypatch.setenv("APICOL_KEY", "sk-x")
        monkeypatch.setenv("APICOL_MODEL", "openai/gpt-5")
        with pytest.raises(BackendUnavailableError):
            apicol.anthropic_client()


class TestStreamWrapper:
    def test_global_stream_uses_implicit_client(
        self, mocker: pytest_mock.MockerFixture, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "k")
        monkeypatch.setenv("APICOL_MODEL", "claude-sonnet-4-6")
        fake = mocker.MagicMock(
            return_value=iter(
                [{"choices": [{"index": 0, "delta": {"content": "z"}, "finish_reason": None}]}]
            )
        )
        mocker.patch(
            "apicol._client.Client.stream",
            lambda self, messages, **kw: fake(messages, **kw),
        )
        out = list(apicol.stream([{"role": "user", "content": "x"}]))
        assert out[0]["choices"][0]["delta"]["content"] == "z"

    def test_stream_astream_in_all(self) -> None:
        assert "stream" in apicol.__all__
        assert "astream" in apicol.__all__
