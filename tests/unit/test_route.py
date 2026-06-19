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
        complete, acomplete, _stream, _astream = pick_backend(cfg)
        assert complete is anthropic_backend.complete
        assert acomplete is anthropic_backend.acomplete

    def test_litellm_returns_litellm_callables(self) -> None:
        cfg = Config(backend="litellm", api_key="x", model="openai/gpt-5")
        complete, acomplete, _stream, _astream = pick_backend(cfg)
        assert complete is litellm_backend.complete
        assert acomplete is litellm_backend.acomplete

    def test_openai_compatible_returns_openai_compatible_callables(self) -> None:
        cfg = Config(backend="openai-compatible", api_key="sk-x", model="gpt-5")
        complete, acomplete, _stream, _astream = pick_backend(cfg)
        assert complete is openai_compatible_backend.complete
        assert acomplete is openai_compatible_backend.acomplete

    def test_pick_backend_rejects_claude_cli_via_config(self) -> None:
        with pytest.raises(ConfigError):
            Config(backend="claude_cli", api_key=None, model=None)

    def test_pick_backend_returns_four_callables(self) -> None:
        from apicol._config import Config
        from apicol._route import pick_backend

        cfg = Config(backend="anthropic", api_key="k", model="claude-sonnet-4-6")
        result = pick_backend(cfg)
        assert len(result) == 4
        complete, acomplete, stream, astream = result
        assert all(callable(x) for x in (complete, acomplete, stream, astream))
