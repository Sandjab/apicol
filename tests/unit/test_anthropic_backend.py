"""Tests unitaires pour le backend Anthropic."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import anthropic
import pytest
import pytest_mock

from apicol._backends import anthropic as backend
from apicol._config import Config
from apicol._errors import BackendError, NotSupportedError


@pytest.fixture
def basic_config() -> Config:
    return Config(backend="anthropic", api_key="sk-ant-test", model="claude-sonnet-4-6")


class TestOpenaiToAnthropic:
    def test_simple_user_message(self) -> None:
        messages = [{"role": "user", "content": "Hello"}]
        payload = backend._openai_to_anthropic(messages, model="claude-sonnet-4-6")
        assert payload["messages"] == [{"role": "user", "content": "Hello"}]
        assert "system" not in payload or payload["system"] in (None, "")

    def test_system_message_extracted_to_kwarg(self) -> None:
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
        ]
        payload = backend._openai_to_anthropic(messages, model="claude-sonnet-4-6")
        assert payload["system"] == "You are helpful"
        assert payload["messages"] == [{"role": "user", "content": "Hi"}]

    def test_multiple_system_messages_concatenated(self) -> None:
        messages = [
            {"role": "system", "content": "A"},
            {"role": "system", "content": "B"},
            {"role": "user", "content": "Hi"},
        ]
        payload = backend._openai_to_anthropic(messages, model="claude-sonnet-4-6")
        assert payload["system"] == "A\n\nB"

    def test_content_blocks_preserved(self) -> None:
        messages = [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}]
        payload = backend._openai_to_anthropic(messages, model="claude-sonnet-4-6")
        assert payload["messages"][0]["content"] == [{"type": "text", "text": "Hello"}]

    def test_system_message_with_content_blocks(self) -> None:
        messages = [
            {"role": "system", "content": [{"type": "text", "text": "Sys block"}]},
            {"role": "user", "content": "Hi"},
        ]
        payload = backend._openai_to_anthropic(messages, model="claude-sonnet-4-6")
        assert payload["system"] == "Sys block"

    def test_explicit_max_tokens_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        with caplog.at_level(logging.WARNING, logger="apicol"):
            payload = backend._openai_to_anthropic(
                messages, model="claude-sonnet-4-6", max_tokens=512
            )
        assert payload["max_tokens"] == 512
        assert not any("max_tokens" in r.message for r in caplog.records)

    def test_temperature_propagated(self) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        payload = backend._openai_to_anthropic(messages, model="claude-sonnet-4-6", temperature=0.3)
        assert payload["temperature"] == 0.3

    def test_extra_body_merged_into_payload(self) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        payload = backend._openai_to_anthropic(
            messages,
            model="claude-sonnet-4-6",
            extra_body={"metadata": {"user_id": "abc"}},
        )
        assert payload["metadata"] == {"user_id": "abc"}

    def test_default_max_tokens_4096_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        with caplog.at_level(logging.WARNING, logger="apicol"):
            payload = backend._openai_to_anthropic(messages, model="claude-sonnet-4-6")
        assert payload["max_tokens"] == 4096
        assert any("max_tokens" in r.message for r in caplog.records)

    def test_role_tool_raises_not_supported(self) -> None:
        messages = [{"role": "tool", "content": "result", "tool_call_id": "x"}]
        with pytest.raises(NotSupportedError, match="tool"):
            backend._openai_to_anthropic(messages, model="claude-sonnet-4-6")

    def test_chat_stream_kwarg_raises_not_supported(self) -> None:
        from apicol._config import Config

        cfg = Config(backend="anthropic", api_key="k", model="claude-sonnet-4-6")
        with pytest.raises(NotSupportedError, match="stream"):
            backend.complete([{"role": "user", "content": "hi"}], cfg, stream=True)

    def test_tools_kwarg_raises_not_supported(self) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        with pytest.raises(NotSupportedError, match="tools"):
            backend._openai_to_anthropic(messages, model="claude-sonnet-4-6", tools=[{"name": "x"}])


class TestReasoningEffortMapping:
    @pytest.mark.parametrize(
        "effort,expected_budget",
        [("low", 1024), ("medium", 4096), ("high", 16384)],
    )
    def test_sonnet_uses_budget_tokens(self, effort: str, expected_budget: int) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        payload = backend._openai_to_anthropic(
            messages, model="claude-sonnet-4-6", reasoning_effort=effort
        )
        assert payload["thinking"] == {
            "type": "enabled",
            "budget_tokens": expected_budget,
        }

    @pytest.mark.parametrize("effort", ["low", "medium", "high"])
    def test_opus_4_7_uses_adaptive_mode(self, effort: str) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        payload = backend._openai_to_anthropic(
            messages, model="claude-opus-4-7", reasoning_effort=effort
        )
        assert payload["thinking"] == {"type": "adaptive"}

    @pytest.mark.parametrize("effort", [None, "none"])
    def test_no_thinking_when_none(self, effort: str | None) -> None:
        messages = [{"role": "user", "content": "Hi"}]
        payload = backend._openai_to_anthropic(
            messages, model="claude-sonnet-4-6", reasoning_effort=effort
        )
        assert "thinking" not in payload


class TestAnthropicToOpenai:
    def test_basic_response(self) -> None:
        resp = MagicMock()
        resp.id = "msg_123"
        resp.model = "claude-sonnet-4-6"
        resp.content = [MagicMock(type="text", text="hello world")]
        resp.usage = MagicMock(input_tokens=10, output_tokens=5)
        resp.stop_reason = "end_turn"

        result = backend._anthropic_to_openai(resp)
        assert result["id"] == "msg_123"
        assert result["choices"][0]["message"]["content"] == "hello world"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15

    @pytest.mark.parametrize(
        "stop,expected",
        [
            ("end_turn", "stop"),
            ("max_tokens", "length"),
            ("stop_sequence", "stop"),
            ("tool_use", "tool_calls"),
        ],
    )
    def test_stop_reason_mapping(self, stop: str, expected: str) -> None:
        resp = MagicMock()
        resp.id = "x"
        resp.model = "claude"
        resp.content = [MagicMock(type="text", text="x")]
        resp.usage = MagicMock(input_tokens=1, output_tokens=1)
        resp.stop_reason = stop

        result = backend._anthropic_to_openai(resp)
        assert result["choices"][0]["finish_reason"] == expected


class TestComplete:
    def test_complete_returns_openai_dict(
        self, basic_config: Config, mock_anthropic_sdk: MagicMock
    ) -> None:
        result = backend.complete([{"role": "user", "content": "Hi"}], basic_config)
        assert result["choices"][0]["message"]["content"] == "hello"
        mock_anthropic_sdk.sync.messages.create.assert_called_once()

    def test_complete_passes_api_key_and_base_url(self, mock_anthropic_sdk: MagicMock) -> None:
        cfg = Config(
            backend="anthropic",
            api_key="sk-x",
            model="claude-sonnet-4-6",
            base_url="https://api.example.com",
        )
        backend.complete([{"role": "user", "content": "Hi"}], cfg)
        anthropic.Anthropic.assert_called_once_with(  # type: ignore[attr-defined]
            api_key="sk-x", base_url="https://api.example.com"
        )

    def test_complete_wraps_api_error(
        self, basic_config: Config, mocker: pytest_mock.MockerFixture
    ) -> None:
        sync_client = mocker.MagicMock()
        api_error = anthropic.APIError("boom", request=mocker.MagicMock(), body=None)
        sync_client.messages.create.side_effect = api_error
        mocker.patch("anthropic.Anthropic", return_value=sync_client)
        with pytest.raises(BackendError) as exc_info:
            backend.complete([{"role": "user", "content": "Hi"}], basic_config)
        assert isinstance(exc_info.value.__cause__, anthropic.APIError)

    def test_complete_without_model_raises_backend_error(
        self, mock_anthropic_sdk: MagicMock
    ) -> None:
        cfg = Config(backend="anthropic", api_key="sk-x", model=None)
        with pytest.raises(BackendError, match="model requis"):
            backend.complete([{"role": "user", "content": "Hi"}], cfg)


class TestAcomplete:
    @pytest.mark.asyncio
    async def test_acomplete_returns_openai_dict(
        self, basic_config: Config, mock_anthropic_sdk: MagicMock
    ) -> None:
        result = await backend.acomplete([{"role": "user", "content": "Hi"}], basic_config)
        assert result["choices"][0]["message"]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_acomplete_without_model_raises_backend_error(
        self, mock_anthropic_sdk: MagicMock
    ) -> None:
        cfg = Config(backend="anthropic", api_key="sk-x", model=None)
        with pytest.raises(BackendError, match="model requis"):
            await backend.acomplete([{"role": "user", "content": "Hi"}], cfg)

    @pytest.mark.asyncio
    async def test_acomplete_wraps_api_error(
        self, basic_config: Config, mocker: pytest_mock.MockerFixture
    ) -> None:
        async_client = mocker.MagicMock()
        api_error = anthropic.APIError("boom", request=mocker.MagicMock(), body=None)

        async def _raise(**kwargs: object) -> None:
            raise api_error

        async_client.messages.create.side_effect = _raise
        mocker.patch("anthropic.AsyncAnthropic", return_value=async_client)
        with pytest.raises(BackendError) as exc_info:
            await backend.acomplete([{"role": "user", "content": "Hi"}], basic_config)
        assert isinstance(exc_info.value.__cause__, anthropic.APIError)
