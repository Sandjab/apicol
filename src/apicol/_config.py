"""Configuration immutable apicol + parser env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from apicol._errors import ConfigError

Backend = Literal["anthropic", "openai-compatible", "litellm"]
_VALID_BACKENDS: tuple[str, ...] = ("anthropic", "openai-compatible", "litellm")

_ENV_TYPE = "APICOL_TYPE"
_ENV_KEY = "APICOL_KEY"
_ENV_MODEL = "APICOL_MODEL"
_ENV_URL = "APICOL_URL"


@dataclass(frozen=True)
class Config:
    """Configuration immutable d'un backend apicol.

    Args:
        backend: 'anthropic', 'openai-compatible' ou 'litellm'. Toute autre
            valeur lève ConfigError.
        api_key: Clé d'API. Requise sauf cas locaux (openai-compatible ou
            litellm avec base_url et endpoint qui n'exige pas de clé).
        model: Nom du modèle. Requis pour pouvoir appeler chat().
        base_url: Endpoint custom optionnel (vLLM, Ollama, OpenRouter, gateway).
        extra_headers: Headers HTTP attachés à la connexion (ex. HTTP-Referer
            et X-Title pour OpenRouter). Appliqué pour openai-compatible et
            anthropic ; ignoré silencieusement pour litellm (cf. SPEC).

    Raises:
        ConfigError: Si backend invalide, si claude_cli passé, ou si la
            combinaison de paramètres est incohérente.
    """

    backend: Backend
    api_key: str | None
    model: str | None
    base_url: str | None = None
    extra_headers: dict[str, str] | None = field(default=None)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.backend == "claude_cli":  # type: ignore[comparison-overlap]
            raise ConfigError(
                "Le backend 'claude_cli' n'est pas routable. "
                "Utiliser apicol.claude_cli_chat() ou apicol.claude_cli_achat() "
                "directement (voir SPEC.md § Backend dev only)."
            )
        if self.backend not in _VALID_BACKENDS:
            raise ConfigError(
                f"backend='{self.backend}' invalide. Valeurs acceptées : {_VALID_BACKENDS}."
            )
        if self.backend == "anthropic" and not self.api_key:
            raise ConfigError("backend='anthropic' requiert api_key (ou APICOL_KEY en env).")
        if self.backend == "litellm" and not self.api_key and not self.base_url:
            raise ConfigError(
                "backend='litellm' requiert api_key sauf si base_url est défini "
                "(ex. Ollama/LM Studio local)."
            )
        if self.backend == "openai-compatible" and not self.api_key and not self.base_url:
            raise ConfigError(
                "backend='openai-compatible' requiert api_key sauf si base_url est défini "
                "(ex. Ollama/vLLM/LM Studio local)."
            )


def load_from_env() -> Config:
    """Construit un Config à partir des variables d'environnement APICOL_*.

    Returns:
        Config validé.

    Raises:
        ConfigError: Si APICOL_TYPE manquant/invalide ou combinaison incohérente.
    """
    backend_raw = os.environ.get(_ENV_TYPE)
    if not backend_raw:
        raise ConfigError(f"{_ENV_TYPE} non défini. Valeurs acceptées : {_VALID_BACKENDS}.")
    api_key = os.environ.get(_ENV_KEY) or None
    model = os.environ.get(_ENV_MODEL) or None
    base_url = os.environ.get(_ENV_URL) or None

    return Config(
        backend=backend_raw,  # type: ignore[arg-type]
        api_key=api_key,
        model=model,
        base_url=base_url,
        extra_headers=None,
    )
