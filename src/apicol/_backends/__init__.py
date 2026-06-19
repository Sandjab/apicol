"""Backends apicol + utilitaires partagés entre backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apicol._errors import BackendError, NotSupportedError

if TYPE_CHECKING:
    from apicol._config import Config


def reject_chat_stream(kwargs: dict[str, Any]) -> None:
    """Interdit stream=True sur le chemin chat()/complete().

    Le streaming passe par stream()/astream(), pas par un kwarg de chat().

    Raises:
        NotSupportedError: Si kwargs contient stream truthy.
    """
    if kwargs.get("stream"):
        raise NotSupportedError(
            "stream=True n'est pas supporté sur chat() ; utiliser stream()/astream()."
        )


def resolve_model(config: Config, kwargs: dict[str, Any]) -> str:
    """Résout le modèle effectif (kwargs prioritaire sur Config) et le retire de kwargs.

    Raises:
        BackendError: Si aucun modèle n'est défini, ni dans Config ni dans kwargs.
    """
    model = kwargs.pop("model", None) or config.model
    if not model:
        raise BackendError("model requis : ni dans Config ni dans kwargs.")
    return model
