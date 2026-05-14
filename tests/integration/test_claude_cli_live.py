"""Smoke tests live `claude -p` (skippés si binaire absent)."""

from __future__ import annotations

import pytest

import apicol


@pytest.mark.integration
@pytest.mark.requires_claude_cli
class TestClaudeCliLive:
    def test_claude_cli_chat(self) -> None:
        response = apicol.claude_cli_chat(
            messages=[{"role": "user", "content": "Réponds 'pong' uniquement."}],
            timeout=60,
        )
        assert response["choices"][0]["message"]["content"]
        assert response["usage"] is None

    @pytest.mark.asyncio
    async def test_claude_cli_achat(self) -> None:
        response = await apicol.claude_cli_achat(
            messages=[{"role": "user", "content": "Réponds 'pong' uniquement."}],
            timeout=60,
        )
        assert response["choices"][0]["message"]["content"]
