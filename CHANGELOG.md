# CHANGELOG.md

Toutes les modifications notables de ce projet sont documentées ici.

Le format est inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et le projet adhère au [Versioning Sémantique](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Test property `test_config_parsing` : `VALID_BACKENDS` n'incluait pas
  `openai-compatible` (backend ajouté en v0.2.0). Le test considérait à tort
  ce backend valide comme invalide et n'échouait que lorsqu'Hypothesis tirait
  exactement cette valeur — faux négatif intermittent en CI. Constante et
  docstring corrigées.

### Documentation

- Resynchronisation de `CLAUDE.md` avec l'état réel v0.2.0 (le document
  décrivait encore une « phase de design, aucun code ») : état d'avancement,
  quatre backends dont `openai-compatible`, SDK `openai` dans la stack,
  structure réelle du code et des tests, reste à faire.
- Harmonisation de la cible roadmap du streaming v0.2 → v0.3 (devenue
  obsolète après la sortie de v0.2.0) dans `SPEC.md`, `README.md`,
  `docs/prd/BACKLOG.md` et les messages d'erreur du backend Anthropic.
- `README.md` : versions d'installation v0.1.0 → v0.2.0.

## [0.2.0] - 2026-05-16

### Added

- Backend `openai-compatible` (PRD-004) : SDK OpenAI officiel vers tout
  endpoint qui expose `/v1/chat/completions` (OpenAI, Mistral, Ollama, vLLM,
  LM Studio, OpenRouter, Groq, DeepSeek, Together AI, Fireworks, Anyscale,
  proxy custom). Disponible via `APICOL_TYPE=openai-compatible` ou
  `Client(backend="openai-compatible", ...)`.
- Nouveau kwarg `extra_headers: dict[str, str] | None` sur `Client` et
  `AsyncClient` pour attacher des headers HTTP à la connexion (utile pour
  OpenRouter : `HTTP-Referer`, `X-Title` ; ou tout gateway custom).
  Honoré par les backends `openai-compatible` et `anthropic`, ignoré
  silencieusement par `litellm`.
- Dépendance directe `openai>=1.50` (était transitive via `litellm`).
- Tests unitaires `test_openai_compatible_backend.py` (13 cas), extension
  des suites existantes (`test_config.py`, `test_route.py`, `test_client.py`)
  pour le nouveau backend et pour `extra_headers`. 161 tests passent (5
  intégration live skippés).

### Changed

- Positionnement du backend `litellm` : désormais réservé aux providers
  qui ne parlent pas OpenAI nativement (Gemini natif Google AI Studio /
  Vertex AI, Bedrock, Azure OpenAI, Cohere, Replicate, HuggingFace
  Inference). Les endpoints OpenAI-compatibles (Ollama, vLLM, OpenRouter…)
  passent désormais par `openai-compatible` recommandé.
- SPEC.md : nouveau tableau de règle de décision (« quel backend
  choisir »), mapping `APICOL_KEY` documenté pour `openai-compatible`,
  table de mapping LiteLLM provider → env var explicitée, colonne
  `openai-compatible` dans le tableau de compatibilité.
- ARCHITECTURE.md : nouvelle décision D11 (backend `openai-compatible`
  distinct de LiteLLM), diagramme étendu à trois backends.
- README.md : section « Pourquoi cette lib » étendue (3 apports au lieu
  de 2), tableau de décision, exemples Ollama et OpenRouter via
  `openai-compatible`, badges et statut v0.2.0.

### Documentation

- PRD-004 (Backend `openai-compatible` à côté de LiteLLM) : motivation,
  options évaluées (A retenue : ajouter à côté de LiteLLM ; B rejetée :
  remplacer LiteLLM ; C rejetée : statu quo ; D rejetée : fallback
  automatique), plan d'implémentation et métriques de succès.

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
