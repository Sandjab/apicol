# apicol

[![CI](https://github.com/Sandjab/apicol/actions/workflows/ci.yml/badge.svg)](https://github.com/Sandjab/apicol/actions/workflows/ci.yml)
[![Last commit](https://img.shields.io/github/last-commit/Sandjab/apicol)](https://github.com/Sandjab/apicol/commits/main)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.10-blue.svg)](https://www.python.org)
[![Version](https://img.shields.io/badge/Version-v0.1.0-green.svg)](https://github.com/Sandjab/apicol/releases/tag/v0.1.0)
[![Visitors](https://komarev.com/ghpvc/?username=sandjab-apicol&label=Visitors&color=0e75b6&style=flat)](https://github.com/Sandjab/apicol)

Couche d'abstraction Python pour appeler un LLM via plusieurs backends interchangeables. Une interface unifiée au format OpenAI pour parler à : **API Anthropic native** (avec caching, thinking, citations), **LiteLLM** (qui route vers OpenAI, Gemini, Mistral, Ollama, vLLM, LM Studio, OpenRouter et 100+ providers), et **Claude Code CLI** (`claude -p`, usage dev local uniquement).

Sélection du backend par variables d'environnement *ou* par objet `Client` configurable. Plusieurs backends peuvent cohabiter dans le même process (bench, fallback applicatif, comparaison).

## Statut

**v0.1.0 — alpha.** Implémentation complète des trois backends (Anthropic natif, LiteLLM, `claude -p` dev-only), surface publique stable, ≥95 % de couverture. Streaming et tool calls reportés à v0.2/v0.3. Documentation associée :

- `README.md` — ce fichier
- `CLAUDE.md` — instructions pour Claude Code travaillant sur ce repo
- `ARCHITECTURE.md` — décisions techniques structurantes
- `SPEC.md` — contrat d'API publique
- `CHANGELOG.md` — historique des versions
- `pyproject.toml` — métadonnées du package
- `docs/prd/` — PRD-001 (architecture deux niveaux), PRD-002 (séparation `claude -p`), PRD-003 (multi-backend simultané)

## Pourquoi cette lib

LiteLLM résout déjà 90 % du problème (interface unifiée, 100+ providers, format OpenAI partout). `apicol` ajoute deux choses que LiteLLM ne fait pas bien :

1. **Un chemin Anthropic natif préservé.** Le compatibility layer OpenAI d'Anthropic ne supporte ni le prompt caching ni le détail du thinking. Pour les usages long-context avec caching agressif, il faut le SDK Anthropic natif. `apicol` expose explicitement cette voie quand `APICOL_TYPE=anthropic`, via une méthode `client.anthropic_native()`.
2. **Un backend `claude -p`** pour le dev local interactif. Strictement marqué « dev only » et exposé via une fonction séparée — **pas** routé dans l'interface unifiée — pour éviter toute confusion avec un usage programmatique qui violerait les TOS Anthropic (voir PRD-002).

Le reste (OpenAI, Gemini, modèles locaux, OpenRouter) est délégué à LiteLLM sans réinventer la roue.

## Installation

### Depuis PyPI (cible v0.1.0)

```bash
pip install apicol
```

### Depuis le repo Git (phase alpha)

```bash
# Dernière version de main
pip install git+https://github.com/Sandjab/apicol.git

# Tag spécifique
pip install git+https://github.com/Sandjab/apicol.git@v0.1.0

# Branche dev
pip install git+https://github.com/Sandjab/apicol.git@dev
```

### Installation editable (dev local)

```bash
git clone https://github.com/Sandjab/apicol.git
cd apicol
pip install -e ".[dev]"  # base + outils dev (pytest, ruff, mypy)
```

### Ajout en dépendance d'un projet tiers

**Dans `pyproject.toml`** (par exemple celui d'Athanor) :

```toml
[project]
dependencies = [
    "apicol>=0.1.0",
    # OU depuis git en phase alpha
    "apicol @ git+https://github.com/Sandjab/apicol.git@main",
]
```

**Dans `requirements.txt`** :

```
apicol>=0.1.0
```

**Avec uv** :

```bash
uv add apicol
# ou depuis git
uv add "apicol @ git+https://github.com/Sandjab/apicol.git"
```

### Dépendances installées

`apicol` installe automatiquement :

- `anthropic` (SDK natif pour le backend Anthropic et l'échappatoire native)
- `litellm` (délégation pour tous les autres backends)

Python ≥ 3.10 requis.

## Variables d'environnement

| Variable | Valeurs | Rôle |
|----------|---------|------|
| `APICOL_TYPE` | `anthropic`, `litellm` | Backend par défaut (utilisé par les fonctions globales `chat`, `achat`) |
| `APICOL_KEY` | string | Clé d'API par défaut |
| `APICOL_MODEL` | string | Modèle par défaut (ex. `claude-opus-4-7`, `openai/gpt-5`, `ollama/qwen3:32b`) |
| `APICOL_URL` | URL (optionnel) | Endpoint custom (vLLM local, LM Studio, gateway, etc.) |

Pour `claude_cli_chat()` aucune variable n'est requise.

Pour un usage **multi-backend simultané**, ces variables ne sont pas suffisantes — on construit des `Client` explicites (voir Usage ci-dessous).

## Usage

### Mode simple — fonctions globales et env vars

```python
import os
import apicol

os.environ["APICOL_TYPE"]  = "anthropic"
os.environ["APICOL_KEY"]   = "sk-ant-..."
os.environ["APICOL_MODEL"] = "claude-opus-4-7"

response = apicol.chat(
    messages=[{"role": "user", "content": "Bonjour"}],
    reasoning_effort="medium",
)
print(response["choices"][0]["message"]["content"])
```

Bascule de backend sans toucher au code applicatif :

```bash
export APICOL_TYPE=litellm
export APICOL_MODEL=openai/gpt-5
export APICOL_KEY=sk-...
```

### Mode async — `achat`

```python
import asyncio, apicol

async def main():
    response = await apicol.achat(
        messages=[{"role": "user", "content": "Bonjour"}],
    )
    return response

asyncio.run(main())
```

### Mode multi-backend — objet `Client`

Pour avoir plusieurs configurations actives simultanément dans le même process (bench, fallback applicatif, comparaison) :

```python
import apicol

claude = apicol.Client(
    backend="anthropic",
    api_key="sk-ant-...",
    model="claude-opus-4-7",
)

gpt = apicol.Client(
    backend="litellm",
    api_key="sk-...",
    model="openai/gpt-5",
)

qwen_local = apicol.Client(
    backend="litellm",
    model="ollama/qwen3:32b",
    base_url="http://localhost:11434",
)

prompt = [{"role": "user", "content": "Explique la relativité en 3 phrases"}]

# Bench parallèle
for name, client in [("claude", claude), ("gpt", gpt), ("qwen", qwen_local)]:
    response = client.chat(prompt)
    print(f"\n=== {name} ===\n{response['choices'][0]['message']['content']}")
```

Un `Client` est **immutable** après construction. Pour changer de configuration, on crée un nouveau client. Cette rigidité simplifie le raisonnement multi-instance.

### Mode multi-backend async — `AsyncClient`

```python
import asyncio, apicol

claude = apicol.AsyncClient(backend="anthropic", api_key="...", model="claude-opus-4-7")
gpt    = apicol.AsyncClient(backend="litellm",   api_key="...", model="openai/gpt-5")

async def bench():
    return await asyncio.gather(
        claude.chat(prompt),
        gpt.chat(prompt),
    )

claude_resp, gpt_resp = asyncio.run(bench())
```

### Accès au SDK Anthropic natif (features avancées)

Pour le prompt caching avec breakpoints fins, les citations, le PDF input, le batch API, ou tout autre feature non-portable :

```python
import apicol

# Via un Client
claude = apicol.Client(backend="anthropic", api_key="...", model="claude-opus-4-7")
native = claude.anthropic_native()  # → anthropic.Anthropic préconfiguré

response = native.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": gros_document,
            "cache_control": {"type": "ephemeral"},
        }
    ],
    messages=[{"role": "user", "content": "Question sur le document"}],
)
# À partir d'ici, tu utilises le SDK Anthropic avec TOUTES ses features.

# Variante depuis les env vars (alias rétrocompatible)
native = apicol.anthropic_client()  # équivalent à Client().anthropic_native()
```

### Backend dev only — `claude_cli_chat`

⚠️ **Dev only.** Cette fonction est destinée à un **usage personnel interactif** (un script local que tu lances toi-même). Elle n'est *pas* destinée à servir une charge programmatique routée selon coût/dispo — un tel usage enfreint les TOS de Claude Pro/Max. Voir PRD-002 pour le détail.

```python
import apicol

# Aucune variable APICOL_* requise — utilise le `claude` CLI authentifié localement
response = apicol.claude_cli_chat(
    messages=[{"role": "user", "content": "Résume CHANGELOG.md du dossier courant"}],
)
print(response["choices"][0]["message"]["content"])
```

Cette fonction est volontairement **séparée** des fonctions globales `chat()` / `achat()` et des objets `Client` / `AsyncClient` : aucun chemin de routage ne mène automatiquement vers `claude -p`.

## Paramètres unifiés (niveau 1)

Les méthodes `Client.chat()`, `AsyncClient.chat()` et les fonctions globales `chat()`, `achat()` acceptent tous les paramètres suivants :

| Paramètre | Type | Comportement |
|-----------|------|--------------|
| `messages` | `list[dict]` | Format OpenAI standard |
| `model` | `str \| None` | Override du modèle du Client / des env vars |
| `temperature` | `float \| None` | 0.0 à 2.0, sémantique OpenAI |
| `max_tokens` | `int \| None` | Default 4096 |
| `reasoning_effort` | `"none" \| "low" \| "medium" \| "high"` | Mappé selon backend (voir SPEC) |
| `extra_body` | `dict` | Passthrough silencieux vers le SDK sous-jacent (ex. `cache_control` Anthropic) |

Détails complets et table de mapping `reasoning_effort` → `thinking` dans [SPEC.md](./SPEC.md).

## Hors périmètre

- **Pas de cost tracking, virtual keys, rate limiting, dashboard.** Utiliser le proxy LiteLLM standalone pour ça.
- **Pas de routage automatique avec fallback/loadbalance** au niveau de la lib. Pour ces patterns, l'application orchestre ses `Client` à la main.
- **Pas de support des modalités exotiques** (audio, embeddings, fine-tuning) en v0.1. Chat completion uniquement.
- **Pas de streaming en v0.1** (reporté à v0.2 — interface d'events unifiée à concevoir).
- **Pas de support des tool calls en v0.1** (reporté à v0.3).
- **Pas de routage automatique vers `claude -p`.** Volontaire — voir PRD-002.

## Licence

À définir (MIT probablement).
