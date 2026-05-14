"""Smoke tests live Anthropic (skippés sans ANTHROPIC_API_KEY)."""

from __future__ import annotations

import os

import pytest

import apicol


@pytest.mark.integration
@pytest.mark.anthropic_live
class TestAnthropicLive:
    def test_chat_minimal_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", os.environ["ANTHROPIC_API_KEY"])
        monkeypatch.setenv("APICOL_MODEL", "claude-haiku-4-5-20251001")
        response = apicol.chat(
            messages=[{"role": "user", "content": "Réponds 'pong' uniquement."}],
            max_tokens=20,
        )
        assert "choices" in response
        assert response["choices"][0]["message"]["role"] == "assistant"
        assert response["choices"][0]["message"]["content"]
        assert response["usage"]["prompt_tokens"] > 0
        assert response["usage"]["completion_tokens"] > 0

    @pytest.mark.asyncio
    async def test_achat_minimal_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", os.environ["ANTHROPIC_API_KEY"])
        monkeypatch.setenv("APICOL_MODEL", "claude-haiku-4-5-20251001")
        response = await apicol.achat(
            messages=[{"role": "user", "content": "Réponds 'pong' uniquement."}],
            max_tokens=20,
        )
        assert response["choices"][0]["message"]["content"]

    def test_anthropic_native_escape_hatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", os.environ["ANTHROPIC_API_KEY"])
        monkeypatch.setenv("APICOL_MODEL", "claude-haiku-4-5-20251001")
        native = apicol.anthropic_client()
        response = native.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": "ping"}],
        )
        assert response.content[0].text
