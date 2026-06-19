"""Hiérarchie d'exceptions typées d'apicol.

Toutes les erreurs publiques dérivent d'ApicolError pour permettre un
catch-all côté utilisateur via `except apicol.ApicolError`.

Les erreurs SDK upstream (anthropic.APIError, litellm.exceptions.*) sont
toujours wrappées et leur cause préservée dans __cause__.
"""

from __future__ import annotations


class ApicolError(Exception):
    """Racine de toutes les erreurs apicol.

    Permet `except apicol.ApicolError` côté applicatif.
    """


class ConfigError(ApicolError):
    """Configuration invalide : env vars manquantes ou incohérentes,
    valeurs hors domaine, tentative de routage vers claude_cli."""


class BackendUnavailableError(ApicolError):
    """Le backend demandé n'est pas disponible : binaire absent du PATH,
    SDK non installé, ou méthode appelée sur un mauvais backend
    (ex. anthropic_native sur un Client litellm)."""


class BackendError(ApicolError):
    """Erreur remontée par le SDK ou processus sous-jacent.

    L'erreur d'origine est toujours préservée dans __cause__ pour debug.
    """


class NotSupportedError(ApicolError):
    """Feature volontairement non supportée à ce stade (ex. tool calls).

    Levée tôt avant l'appel SDK, avec un message clair pointant vers la
    roadmap (v0.3 tool calls).
    """
