"""Tests pour le dispatch backend -> callables."""

from __future__ import annotations

import pytest

from apicol._backends import anthropic as anthropic_backend
from apicol._backends import litellm as litellm_backend
from apicol._backends import openai_compatible as openai_compatible_backend
from apicol._config import Config
from apicol._errors import ConfigError
from apicol._route import pick_backend


class TestPickBackend:
    def test_anthropic_returns_anthropic_callables(self) -> None:
        cfg = Config(backend="anthropic", api_key="x", model="claude-opus-4-7")
        sync_cb, async_cb = pick_backend(cfg)
        assert sync_cb is anthropic_backend.complete
        assert async_cb is anthropic_backend.acomplete

    def test_litellm_returns_litellm_callables(self) -> None:
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        sync_cb, async_cb = pick_backend(cfg)
        assert sync_cb is litellm_backend.complete
        assert async_cb is litellm_backend.acomplete

    def test_openai_compatible_returns_openai_compatible_callables(self) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        sync_cb, async_cb = pick_backend(cfg)
        assert sync_cb is openai_compatible_backend.complete
        assert async_cb is openai_compatible_backend.acomplete

    def test_pick_backend_rejects_claude_cli_via_config(self) -> None:
        with pytest.raises(ConfigError):
            Config(backend="claude_cli", api_key=None, model=None)
