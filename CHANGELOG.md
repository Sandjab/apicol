# CHANGELOG.md

Toutes les modifications notables de ce projet sont documentées ici.

Le format est inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et le projet adhère au [Versioning Sémantique](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-14

### Added

- Surface publique v0.1 : `Client`, `AsyncClient`, `chat`, `achat`,
  `anthropic_client`, `anthropic_async_client`, `claude_cli_chat`,
  `claude_cli_achat`.
- Backend Anthropic natif avec traduction OpenAI↔Anthropic à la frontière,
  mapping `reasoning_effort` selon modèle (Sonnet→budget_tokens,
  Opus 4.7→adaptive).
- Backend LiteLLM en pass-through pour 100+ providers (OpenAI, Gemini,
  Ollama, vLLM, LM Studio, OpenRouter, ...).
- Backend `claude_cli` séparé (dev only, `claude -p` en subprocess).
- Hiérarchie d'erreurs typées : `ApicolError`, `ConfigError`,
  `BackendUnavailableError`, `BackendError`, `NotSupportedError`.
- Multi-backend simultané via objets `Client` immutables.
- Configuration via 4 variables d'env : `APICOL_TYPE`, `APICOL_KEY`,
  `APICOL_MODEL`, `APICOL_URL`.
- Tests : unit + property-based (Hypothesis) + intégration smoke,
  coverage >=95%, matrix Python 3.10-3.13.
- CI : ruff format + check, mypy strict, pytest avec coverage gate.
- Release : Trusted Publisher OIDC vers TestPyPI puis PyPI avec manual
  approval gate.

### Documentation

- Nom du projet retenu : **apicol** (jeu de mots API + col, écho à `apikoltar` dans l'écosystème de l'auteur).
- Création du squelette documentaire : `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `SPEC.md`.
- Création du workflow PRD : `docs/prd/BACKLOG.md`.
- Création du PRD-001 : Architecture à deux niveaux pour la couche d'abstraction multi-backend.
- Création du PRD-002 : Séparation lexicale du backend `claude -p` (conformité TOS).
- Création du PRD-003 : Multi-backend simultané via objet `Client`.
- Mise à jour de `ARCHITECTURE.md` : ajout de la décision D10 (réification de la configuration en `Client`), amendement du diagramme et du flux de dispatch.
- Mise à jour de `SPEC.md` : ajout des sections `Client` et `AsyncClient`, positionnement des fonctions globales comme wrappers de commodité.
- Mise à jour de `README.md` : sections **Installation** complètes (PyPI, Git, editable, dépendance d'un projet tiers via `pyproject.toml` / `requirements.txt` / `uv`) et **Usage** complet (mode env vars, mode Client, async, échappatoire native, `claude_cli_chat`).

### Conventions de nommage

- Variables d'environnement : `APICOL_TYPE`, `APICOL_KEY`, `APICOL_MODEL`, `APICOL_URL` (forme courte sans redondance API+API).
- Dossier des PRD : `docs/prd/` (renommé depuis `prd-meta-workflow/` pour s'aligner sur les conventions Python usuelles).

---

_Convention : chaque release listera les sections `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security` selon ce qui s'applique._
