# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Instructions pour Claude Code travaillant sur ce repo.

## État actuel du repo

**Phase de design — aucun code Python n'existe encore.** `src/apicol/` est vide. La « Structure cible » plus bas décrit ce qu'il **faudra** créer, pas ce qui existe. Tout ce qui est livré pour l'instant est documentaire :

- `README.md` (vue produit), `ARCHITECTURE.md` (décisions D1–D10), `SPEC.md` (contrat d'API v0.1)
- `docs/prd/` : `BACKLOG.md` + PRD-001 (deux niveaux), PRD-002 (séparation `claude -p`), PRD-003 (multi-backend `Client`)

Avant tout travail non-trivial, vérifier que la décision est déjà tranchée dans un PRD. Si elle ne l'est pas, **rédiger un PRD avant de coder** plutôt que d'improviser.

## Hiérarchie des sources de vérité

Ordre de précédence en cas de divergence entre documents :

1. **PRDs (`docs/prd/PRD-NNN-*.md`)** — décisions structurantes votées, irrévocables sans nouveau PRD
2. **`SPEC.md`** — contrat d'API publique (signatures, comportements observables)
3. **`ARCHITECTURE.md`** — comment on implémente la SPEC (décisions D1–D10)
4. **`README.md`** — vue produit pour utilisateur final
5. Ce `CLAUDE.md` — règles opérationnelles pour l'agent

Si tu trouves une contradiction, **flag-la** (Règle 7 globale) au lieu de moyenner. Ne pas modifier silencieusement la SPEC depuis le code — c'est l'inverse : le code se conforme à la SPEC.

## Contexte projet en 30 secondes

`apicol` est une couche d'abstraction Python qui route les appels LLM vers trois familles de backends :

1. **API Anthropic native** (SDK `anthropic`) — pour le caching, le thinking complet, les citations
2. **LiteLLM** — pour tout le reste (OpenAI, Gemini, Ollama, vLLM, LM Studio, OpenRouter)
3. **`claude -p` subprocess** — usage dev local uniquement, fonction séparée

La sélection se fait par `APICOL_TYPE`. Surface API en format OpenAI (lingua franca).

## Principes directeurs (à respecter sans demander)

1. **Ne pas réinventer ce que LiteLLM fait déjà.** Quand un backend tombe dans le périmètre LiteLLM, on délègue, on ne réimplémente pas.
2. **Le chemin Anthropic natif doit rester natif.** Pas de traduction OpenAI→Anthropic→OpenAI inutile. Le SDK `anthropic` parle Anthropic, on traduit uniquement à la frontière de `chat()`.
3. **`claude -p` n'est jamais routé depuis `chat()` ou `Client`.** Fonction séparée, top-level, marquée « dev only » dans le docstring. Cette frontière est sémantique, pas technique — elle existe pour la lisibilité du code applicatif et la conformité TOS.
4. **Format OpenAI en surface, point.** Pas d'API alternative qui exposerait Anthropic en surface. Si l'utilisateur veut Anthropic natif, il appelle `client.anthropic_native()` (niveau 2).
5. **Sync ET async, en miroir strict.** Toute classe / fonction publique a un pendant async : `Client` / `AsyncClient`, `chat` / `achat`, `anthropic_client` / `anthropic_async_client`. Pas d'exception.
6. **Zéro magie sur les env vars.** Lecture stricte des 4 variables documentées, validation explicite, erreurs claires. Pas de fallback caché vers `ANTHROPIC_API_KEY` ou `OPENAI_API_KEY`.
7. **`Client` est immutable.** Dataclass `frozen=True`. Pour changer la config, on crée un nouveau client. Pas de setter, pas de `client.set_model(...)`. Cette rigidité est volontaire.
8. **Les fonctions globales sont des wrappers.** Elles construisent un `Client` implicite à la demande (avec cache lazy invalidé par hash des env vars). Toute la logique métier vit dans `Client` / `AsyncClient` — ne pas dupliquer dans les wrappers.

## Stack

- Python 3.10+ (pour `match`/`case` et union types modernes)
- `anthropic` SDK officiel (sync + async)
- `litellm` (SDK Python, pas le proxy)
- `pytest` + `pytest-asyncio` pour les tests
- `ruff` (lint + format) + `mypy --strict` pour la qualité
- Pas de `requests`, pas de `httpx` direct (les SDKs gèrent)

## Structure cible

```
apicol/
├── README.md
├── CLAUDE.md
├── ARCHITECTURE.md
├── SPEC.md
├── CHANGELOG.md
├── pyproject.toml
├── docs/prd/
│   ├── BACKLOG.md
│   ├── PRD-001-architecture-deux-niveaux.md
│   ├── PRD-002-separation-claude-cli.md
│   └── PRD-003-multi-backend-simultane.md
├── src/
│   └── apicol/
│       ├── __init__.py        # expose Client, AsyncClient, chat, achat, anthropic_client, anthropic_async_client, claude_cli_chat, claude_cli_achat
│       ├── _config.py         # Config (dataclass frozen) + load_from_env()
│       ├── _client.py         # Client, AsyncClient + cache lazy du client implicite
│       ├── _errors.py         # ConfigError, BackendUnavailableError, etc.
│       ├── _route.py          # pick_backend(config) -> Callable
│       └── _backends/
│           ├── __init__.py
│           ├── anthropic.py   # SDK anthropic, traduction OpenAI↔Anthropic à la frontière
│           ├── litellm.py     # délégation à litellm.completion / acompletion
│           └── claude_cli.py  # subprocess wrapper, fonction publique séparée
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_client.py            # Client, AsyncClient, immutabilité, multi-instance
    ├── test_v01_backcompat.py    # fonctions globales = wrappers, behavior unchanged
    ├── test_route.py
    ├── test_anthropic_backend.py
    ├── test_litellm_backend.py
    └── test_claude_cli_backend.py
```

## Conventions de code

- **Noms publics : sans underscore.** `chat`, `achat`, `anthropic_client`. Pas de `Chat()` ni de classes inutiles — fonctions tant que possible.
- **Noms internes : avec underscore en préfixe.** `_config.py`, `_route.py`. L'utilisateur ne doit jamais importer depuis ces modules.
- **Pas de `from X import *`.** Imports explicites partout.
- **Imports SDK : utiliser le module, pas le symbole nu.** Dans les backends, écrire `import anthropic` puis `anthropic.Anthropic(...)` ; **jamais** `from anthropic import Anthropic` puis `Anthropic(...)`. Idem pour `litellm`. Raison : les fixtures de test patchent `anthropic.Anthropic` / `litellm.completion` sur le module ; un import du symbole nu lie un alias local que `mocker.patch` ne peut pas intercepter — le test appellerait silencieusement le vrai SDK.
- **Type hints obligatoires** sur les signatures publiques, fortement encouragés ailleurs.
- **Docstrings** sur toute fonction publique, format Google (compatible Sphinx/MkDocs si on documente un jour).
- **Erreurs custom** dans `_errors.py`, jamais de `raise Exception(...)` brut.
- **Pas de logging configuré dans la lib.** On utilise `logging.getLogger("apicol")` mais on ne configure pas de handler — c'est l'application qui décide.

## Workflow de dev

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Tests
pytest -xvs                          # tous les tests
pytest tests/test_route.py           # un module
pytest -k "test_anthropic"           # par pattern

# Qualité
ruff format src tests
ruff check src tests --fix
mypy --strict src

# Tout d'un coup
make check                           # à créer : format + lint + types + tests
```

## Tests : convention

- **Tests unitaires** : mocker les SDKs (`anthropic.Anthropic`, `litellm.completion`). Pas d'appel réseau dans les tests par défaut.
- **Tests d'intégration** : marqués `@pytest.mark.integration`, skippés par défaut. Activés via `pytest -m integration` avec des vraies clés en env.
- **Tests claude_cli** : marqués `@pytest.mark.requires_claude_cli`, skippés si `which claude` échoue.

## Pièges à éviter

1. **Ne pas mocker `os.environ` directement.** Utiliser `monkeypatch.setenv` dans pytest pour l'isolation.
2. **Le format messages OpenAI a des subtilités** : `content` peut être string OU liste de blocks (`{type: "text", text: "..."}`). La traduction vers Anthropic doit gérer les deux.
3. **Le rôle `system`** : OpenAI le met dans `messages`, Anthropic le passe en kwarg `system` séparé. Traduction nécessaire à la frontière du backend Anthropic.
4. **Le rôle `tool`** : encodage différent OpenAI vs Anthropic. Pour v0.1 on peut **explicitement ne pas supporter** les tools et lever `NotImplementedError`. Mieux qu'un faux support.
5. **Le streaming** : différent partout. Pour v0.1 on supporte sync/async non-streaming uniquement. Streaming reporté à v0.2.
6. **`claude -p` est un CLI agentique, pas une API.** Il peut décider d'appeler des tools, de lire des fichiers, de lancer du code. Le wrapper doit utiliser les flags `--no-tools` (ou équivalent actuel) et `-p` pour mode prompt direct sans interaction. Vérifier la doc actuelle de `claude --help` avant d'implémenter.

## Conformité TOS — important

Le backend `claude_cli_chat()` est exposé pour que **toi, développeur, puisses scripter ton propre claude -p localement**. Il **n'est pas** destiné à servir une charge applicative routée selon coût/dispo. Cette frontière a deux conséquences dans le code :

- `claude_cli_chat()` n'est **jamais** atteignable depuis `chat()`, même en passant `api_type="claude_cli"` (cette valeur doit être rejetée par `_config.py` avec un message explicite).
- Le docstring de `claude_cli_chat()` mentionne explicitement « dev only — pas pour une charge programmatique routée ; voir les TOS Anthropic ».

Ne pas dégrader cette frontière sans PRD explicite qui justifie le risque.

## Quand demander à l'humain

- Avant d'ajouter une dépendance qui n'est pas dans `pyproject.toml`
- Avant de modifier la liste des env vars publiques
- Avant de toucher au routage `_route.py` (créer un PRD)
- Si un test d'intégration échoue à cause d'un changement de comportement d'un SDK upstream

## Quand NE PAS demander

- Refactor interne d'un backend sans changer la surface publique
- Ajout de tests unitaires
- Correction de bugs sans changement de comportement documenté
- Format / lint / typing
