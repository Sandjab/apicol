"""Backends apicol + utilitaires partagés entre backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apicol._errors import BackendError

if TYPE_CHECKING:
    from apicol._config import Config


def resolve_model(config: Config, kwargs: dict[str, Any]) -> str:
    """Résout le modèle effectif (kwargs prioritaire sur Config) et le retire de kwargs.

    Raises:
        BackendError: Si aucun modèle n'est défini, ni dans Config ni dans kwargs.
    """
    model = kwargs.pop("model", None) or config.model
    if not model:
        raise BackendError("model requis : ni dans Config ni dans kwargs.")
    return model
