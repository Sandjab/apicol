"""PBT : fuzzing du parsing Config / load_from_env."""

from __future__ import annotations

import string

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apicol._config import Config, load_from_env
from apicol._errors import ConfigError

VALID_BACKENDS = ("anthropic", "litellm")

random_string = st.text(
    alphabet=string.ascii_letters + string.digits + "/-_.", min_size=0, max_size=40
)


@given(garbage=random_string)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_load_from_env_rejects_invalid_type(monkeypatch: pytest.MonkeyPatch, garbage: str) -> None:
    """Toute valeur de APICOL_TYPE ∉ {anthropic, litellm} doit lever ConfigError."""
    if garbage in VALID_BACKENDS:
        return
    monkeypatch.setenv("APICOL_TYPE", garbage)
    monkeypatch.setenv("APICOL_KEY", "x")
    monkeypatch.setenv("APICOL_MODEL", "y")
    with pytest.raises(ConfigError):
        load_from_env()


@given(model=random_string)
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_anthropic_always_requires_key_regardless_of_model(
    monkeypatch: pytest.MonkeyPatch, model: str
) -> None:
    """Backend anthropic sans api_key → ConfigError, peu importe le modèle."""
    monkeypatch.setenv("APICOL_TYPE", "anthropic")
    monkeypatch.delenv("APICOL_KEY", raising=False)
    monkeypatch.setenv("APICOL_MODEL", model or "claude-opus-4-7")
    with pytest.raises(ConfigError):
        load_from_env()


@given(
    backend=st.sampled_from(VALID_BACKENDS),
    api_key=st.text(min_size=1, max_size=30),
    model=st.text(min_size=1, max_size=30),
)
def test_config_is_immutable(backend: str, api_key: str, model: str) -> None:
    """Tout Config valide doit être frozen."""
    import dataclasses

    try:
        cfg = Config(backend=backend, api_key=api_key, model=model)  # type: ignore[arg-type]
    except ConfigError:
        return
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.api_key = "modified"  # type: ignore[misc]
