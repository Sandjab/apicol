"""Smoke tests live OpenAI via LiteLLM (skippés sans OPENAI_API_KEY)."""

from __future__ import annotations

import os

import pytest

import apicol


@pytest.mark.integration
@pytest.mark.openai_live
class TestLitellmLive:
    def test_openai_chat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APICOL_TYPE", "litellm")
        monkeypatch.setenv("APICOL_KEY", os.environ["OPENAI_API_KEY"])
        monkeypatch.setenv("APICOL_MODEL", "openai/gpt-4o-mini")
        response = apicol.chat(
            messages=[{"role": "user", "content": "Réponds 'pong' uniquement."}],
            max_tokens=20,
        )
        assert response["choices"][0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_openai_achat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APICOL_TYPE", "litellm")
        monkeypatch.setenv("APICOL_KEY", os.environ["OPENAI_API_KEY"])
        monkeypatch.setenv("APICOL_MODEL", "openai/gpt-4o-mini")
        response = await apicol.achat(
            messages=[{"role": "user", "content": "Réponds 'pong' uniquement."}],
            max_tokens=20,
        )
        assert response["choices"][0]["message"]["content"]
