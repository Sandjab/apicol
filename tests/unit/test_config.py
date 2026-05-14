"""Tests pour Config + load_from_env."""

from __future__ import annotations

import dataclasses

import pytest

from apicol._config import Config, load_from_env
from apicol._errors import ConfigError


class TestConfigConstruction:
    def test_minimal_anthropic(self) -> None:
        cfg = Config(backend="anthropic", api_key="sk-ant-x", model="claude-opus-4-7")
        assert cfg.backend == "anthropic"
        assert cfg.api_key == "sk-ant-x"
        assert cfg.model == "claude-opus-4-7"
        assert cfg.base_url is None

    def test_minimal_litellm(self) -> None:
        cfg = Config(backend="litellm", api_key="sk-x", model="openai/gpt-5")
        assert cfg.backend == "litellm"

    def test_litellm_local_no_key_required(self) -> None:
        cfg = Config(
            backend="litellm",
            api_key=None,
            model="ollama/qwen3:32b",
            base_url="http://localhost:11434",
        )
        assert cfg.api_key is None
        assert cfg.base_url == "http://localhost:11434"

    def test_is_frozen(self) -> None:
        cfg = Config(backend="anthropic", api_key="x", model="claude-opus-4-7")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.backend = "litellm"  # type: ignore[misc]


class TestConfigValidation:
    def test_invalid_backend_raises(self) -> None:
        with pytest.raises(ConfigError, match="backend"):
            Config(backend="openai", api_key="x", model="gpt-5")  # type: ignore[arg-type]

    def test_claude_cli_backend_rejected_with_explicit_message(self) -> None:
        with pytest.raises(ConfigError, match="claude_cli_chat"):
            Config(backend="claude_cli", api_key=None, model=None)  # type: ignore[arg-type]

    def test_anthropic_requires_api_key(self) -> None:
        with pytest.raises(ConfigError, match="api_key"):
            Config(backend="anthropic", api_key=None, model="claude-opus-4-7")

    def test_litellm_remote_requires_api_key_or_base_url(self) -> None:
        with pytest.raises(ConfigError, match="api_key"):
            Config(backend="litellm", api_key=None, model="openai/gpt-5")


class TestLoadFromEnv:
    def test_loads_anthropic_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_KEY", "sk-ant-test")
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        monkeypatch.delenv("APICOL_URL", raising=False)

        cfg = load_from_env()

        assert cfg.backend == "anthropic"
        assert cfg.api_key == "sk-ant-test"
        assert cfg.model == "claude-opus-4-7"
        assert cfg.base_url is None

    def test_loads_url_when_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APICOL_TYPE", "litellm")
        monkeypatch.setenv("APICOL_KEY", "ollama")
        monkeypatch.setenv("APICOL_MODEL", "ollama/qwen3:32b")
        monkeypatch.setenv("APICOL_URL", "http://localhost:11434")

        cfg = load_from_env()

        assert cfg.base_url == "http://localhost:11434"

    def test_missing_type_raises(self, clean_env: None) -> None:
        with pytest.raises(ConfigError, match="APICOL_TYPE"):
            load_from_env()

    def test_claude_cli_type_rejected(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "claude_cli")
        with pytest.raises(ConfigError, match="claude_cli_chat"):
            load_from_env()

    def test_no_silent_fallback_to_anthropic_api_key(
        self, monkeypatch: pytest.MonkeyPatch, clean_env: None
    ) -> None:
        monkeypatch.setenv("APICOL_TYPE", "anthropic")
        monkeypatch.setenv("APICOL_MODEL", "claude-opus-4-7")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-be-read")
        with pytest.raises(ConfigError, match=r"api_key|APICOL_KEY"):
            load_from_env()
