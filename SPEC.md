# SPEC.md

Contrat d'API publique de `apicol`. Ce document décrit le **quoi** (signatures, comportements observables). Le **comment** est dans `ARCHITECTURE.md`.

Versionning : ce document décrit la **v0.3**. Toute modification d'API publique nécessite un PRD et une bump de version mineure.

## Variables d'environnement

### `APICOL_TYPE` (requis)

Valeurs acceptées :

| Valeur | Backend |
|--------|---------|
| `anthropic` | SDK Anthropic natif |
| `openai-compatible` | SDK OpenAI vers tout endpoint `/v1/chat/completions` (OpenAI, Mistral, Ollama, vLLM, LM Studio, OpenRouter, Groq, DeepSeek, Together, Fireworks, Anyscale, gateway custom…) |
| `litellm` | LiteLLM pour les providers qui ne parlent pas OpenAI nativement (Gemini natif Google AI Studio / Vertex AI, Bedrock, Azure OpenAI, Cohere, Replicate, HuggingFace Inference) |

Toute autre valeur (y compris `claude_cli`, `openai`, `gemini`) lève `ConfigError`. En particulier, `claude_cli` est rejeté avec un message explicite renvoyant vers `claude_cli_chat()`.

### Quel backend choisir ?

| Tu veux parler à… | Utilise |
|---|---|
| OpenAI, Mistral, Ollama, vLLM, LM Studio, OpenRouter, Groq, DeepSeek, Together, Fireworks, Anyscale, n'importe quel proxy OpenAI-compatible | `backend="openai-compatible"` |
| Gemini natif (Google AI Studio / Vertex AI), Bedrock, Azure OpenAI, Cohere, Replicate, HuggingFace Inference | `backend="litellm"` |
| API Anthropic native (caching fin, citations, PDF, batch, thinking détaillé) | `backend="anthropic"` |
| `claude -p` localement (dev only, conformité TOS) | `claude_cli_chat()` (pas un backend de `chat()`) |

### `APICOL_KEY` (requis sauf cas locaux)

Clé d'API propagée selon le backend :

- `anthropic` → utilisée comme clé Anthropic
- `openai-compatible` → passée telle quelle au SDK OpenAI (`openai.OpenAI(api_key=...)`). **Pas de magie** : la clé est ce qu'elle est, le SDK l'envoie en `Authorization: Bearer ...` à l'endpoint pointé par `APICOL_URL`.
- `litellm` → utilisée selon le provider du modèle (LiteLLM lit son propre nom d'env var par provider — voir ci-dessous)

**Cas où la clé n'est pas requise** : modèles locaux (Ollama, LM Studio, vLLM) accédés via `APICOL_URL`. Dans ce cas la variable peut être absente ou contenir une valeur factice (`"ollama"`, `"local"`).

**Comportement avec LiteLLM** : `apicol` injecte `APICOL_KEY` dans le bon nom d'env var attendu par LiteLLM pour le provider détecté à partir de `APICOL_MODEL`. Exemple : `model=openai/gpt-5` → injection dans `OPENAI_API_KEY`. C'est la seule magie acceptée sur les env vars (sinon l'utilisateur devrait connaître les conventions LiteLLM).

**Mappings LiteLLM observés** (déduits du préfixe `provider/` de `APICOL_MODEL`) :

| Préfixe modèle | Env var injectée |
|---|---|
| `openai/...` | `OPENAI_API_KEY` |
| `gemini/...` | `GEMINI_API_KEY` |
| `anthropic/...` | `ANTHROPIC_API_KEY` |
| `cohere/...` | `COHERE_API_KEY` |
| `openrouter/...` | `OPENROUTER_API_KEY` |
| `ollama/...` | `OLLAMA_API_KEY` (ignorée par Ollama en pratique) |
| `lm_studio/...` | `LM_STUDIO_API_KEY` |
| `<x>/...` | `<X>_API_KEY` (uppercase, fallback générique) |

**Asymétrie volontaire vs `openai-compatible`** : avec `openai-compatible`, pas d'injection — l'utilisateur choisit lui-même son endpoint (`APICOL_URL`) et y associe la clé qui correspond. C'est plus explicite et c'est cohérent avec le fait qu'on ne tente pas de détecter le provider à partir d'un nom de modèle (un `qwen3:32b` peut servir derrière Ollama, vLLM ou OpenRouter — l'URL fait la différence, pas le nom).

### `APICOL_MODEL` (requis)

Nom du modèle. Format :

- Pour `api_type=anthropic` : nom Anthropic direct (ex. `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`).
- Pour `api_type=openai-compatible` : nom de modèle nu, sans préfixe provider (ex. `gpt-5`, `gpt-5-mini`, `qwen3:32b` pour Ollama, `meta-llama/Meta-Llama-3.1-70B-Instruct` pour vLLM, `anthropic/claude-haiku-4-5` pour OpenRouter — la convention `provider/modele` d'OpenRouter est leur format, pas le nôtre).
- Pour `api_type=litellm` : format `provider/modèle` attendu par LiteLLM (ex. `gemini/gemini-2.5-pro`, `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0`, `azure/gpt-4-deployment`, `cohere/command-r-plus`).

### `APICOL_URL` (optionnel)

URL d'endpoint custom. Utile pour :

- vLLM local (`http://localhost:8000/v1`)
- LM Studio (`http://localhost:1234/v1`)
- Ollama (`http://localhost:11434`)
- Gateway custom (Vercel AI Gateway, LiteLLM proxy, etc.)

Si absent, chaque backend utilise son URL par défaut.

## Niveau 1 — Interface unifiée

L'interface unifiée existe sous deux formes équivalentes : un objet **`Client`** (ou `AsyncClient`) configurable explicitement, et des **fonctions globales** (`chat`, `achat`) qui en sont des wrappers de commodité utilisant les variables d'environnement.

### `Client(backend, *, api_key=None, model=None, base_url=None, extra_headers=None)`

Objet de configuration **immutable** (dataclass frozen). Encapsule un backend, une clé, un modèle, et éventuellement une URL custom et des headers de connexion.

**Paramètres** :

- `backend: Literal["anthropic", "openai-compatible", "litellm"]` — type de backend. La valeur `"claude_cli"` est rejetée avec `ConfigError`.
- `api_key: str | None` — clé d'API. Requise sauf pour les backends locaux accédés via `base_url`.
- `model: str | None` — nom du modèle. Requis pour pouvoir appeler `.chat()` sans override.
- `base_url: str | None` — endpoint custom.
- `extra_headers: dict[str, str] | None` — headers HTTP attachés à la connexion (ex. `{"HTTP-Referer": "...", "X-Title": "..."}` pour OpenRouter). Honoré par les backends `openai-compatible` (via `default_headers` du SDK OpenAI) et `anthropic` (via le SDK Anthropic) ; **ignoré silencieusement** par `litellm` qui n'expose pas de propagation propre au niveau du Client.

**Méthodes** :

| Méthode | Retour | Description |
|---------|--------|-------------|
| `chat(messages, **kwargs)` | `dict` | Appel synchrone, retour format OpenAI |
| `anthropic_native()` | `anthropic.Anthropic` | Échappatoire native, uniquement si `backend="anthropic"` |

Les paramètres de `chat()` sont identiques à ceux de la fonction globale `chat()` (voir ci-dessous). Le `model`, `base_url`, et `api_key` passés à `chat()` overrident ceux du `Client` pour cet appel uniquement.

**Erreurs à la construction** :

- `ConfigError` — backend invalide, `claude_cli` interdit, ou combinaison de paramètres incohérente.

### `AsyncClient(backend, *, api_key=None, model=None, base_url=None, extra_headers=None)`

Pendant async de `Client`. Mêmes paramètres, mêmes erreurs, méthodes correspondantes :

| Méthode | Retour | Description |
|---------|--------|-------------|
| `chat(messages, **kwargs)` | `Awaitable[dict]` | Appel asynchrone |
| `anthropic_native()` | `anthropic.AsyncAnthropic` | Échappatoire native async |

### Fonctions globales `chat()` / `achat()`

Ces fonctions sont des **wrappers de commodité** qui utilisent un `Client` (ou `AsyncClient`) implicite, construit lazy depuis les variables d'environnement. Le client implicite est mis en cache et invalidé automatiquement si les env vars changent entre deux appels.

**Quand utiliser quoi** :

- **Fonctions globales** (`chat`, `achat`) : un seul backend par run, configuration par env vars, ergonomie minimale.
- **Client / AsyncClient explicite** : plusieurs backends simultanés dans le même process, ou injection de dépendance dans une app (Athanor, etc.).

### `chat(messages, *, model=None, base_url=None, reasoning_effort=None, temperature=None, max_tokens=None, extra_body=None) -> dict`

Appel synchrone.

**Paramètres** :

- `messages: list[dict]` — format OpenAI. Chaque message a `role` (`system`, `user`, `assistant`) et `content` (str ou liste de blocks `{type, text}`).
- `model: str | None` — override de `APICOL_MODEL`. Si fourni, prime sur l'env.
- `base_url: str | None` — override de `APICOL_URL`. Si fourni, prime sur l'env.
- `reasoning_effort: Literal["none", "low", "medium", "high"] | None` — niveau de raisonnement étendu. Mapping selon backend :
  - `anthropic` : traduit en `thinking={type, budget_tokens}` selon table ci-dessous
  - `litellm` : passé tel quel (LiteLLM gère la traduction par provider)
- `temperature: float | None` — 0.0 à 2.0. Comportement standard OpenAI.
- `max_tokens: int | None` — limite de tokens de sortie. Default 4096 si non précisé.
- `extra_body: dict | None` — kwargs passés tels quels au SDK sous-jacent. Utile pour les params provider-spécifiques (ex. `cache_control` Anthropic).

**Retour** : `dict` au format OpenAI :

```python
{
    "id": "...",
    "model": "claude-opus-4-7",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "..."},
            "finish_reason": "stop",  # ou "length", "tool_calls", etc.
        }
    ],
    "usage": {
        "prompt_tokens": 42,
        "completion_tokens": 100,
        "total_tokens": 142,
    },
}
```

**Erreurs possibles** :

- `ConfigError` — env vars manquantes ou invalides
- `NotSupportedError` — feature demandée non supportée à ce stade (ex. tools)
- `BackendError` — erreur remontée du SDK upstream (vérifier `.__cause__` pour le détail)

**Table de mapping `reasoning_effort` (backend Anthropic)** :

| `reasoning_effort` | Mapping Anthropic |
|--------------------|-------------------|
| `None` ou `"none"` | Pas de champ `thinking` envoyé |
| `"low"` | `{"type": "enabled", "budget_tokens": 1024}` (Sonnet) / mode `adaptive` (Opus 4.7) |
| `"medium"` | `{"type": "enabled", "budget_tokens": 4096}` (Sonnet) / mode `adaptive` (Opus 4.7) |
| `"high"` | `{"type": "enabled", "budget_tokens": 16384}` (Sonnet) / mode `adaptive` (Opus 4.7) |

Note : pour Opus 4.7, `budget_tokens` est rejeté ; seul le mode `adaptive` est supporté. Le mapping détecte automatiquement le modèle.

### `achat(messages, *, model=None, base_url=None, reasoning_effort=None, temperature=None, max_tokens=None, extra_body=None) -> dict`

Identique à `chat()` mais asynchrone. Signature, paramètres et retour identiques. Utilise `anthropic.AsyncAnthropic` ou `litellm.acompletion` selon le backend.

### `stream(messages, **kwargs) -> Iterator[dict]` / `Client.stream(messages, **kwargs) -> Iterator[dict]`

Streaming synchrone. Accepte les mêmes `**kwargs` que `chat()`. Disponible comme méthode sur `Client` et comme fonction globale `apicol.stream(...)` (utilise le client implicite depuis les variables d'environnement).

**Backends couverts** : `anthropic`, `openai-compatible`, `litellm`. `claude_cli` est hors périmètre (dev-only).

**Retour** : générateur qui yield des dicts au format OpenAI chunk :

```python
# Chunk intermédiaire
{"model": "...", "choices": [{"index": 0, "delta": {"content": "..."}, "finish_reason": None}]}

# Dernier chunk (finish_reason non nul, usage best-effort)
{"model": "...", "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {...}}
```

Le texte incrémental est dans `choices[0]["delta"].get("content")`. L'`usage` est fourni sur le dernier chunk **si** le backend le rapporte (best-effort, pas de normalisation inter-backend garantie).

**Sémantique du générateur** : les erreurs sont levées **à l'itération**, pas à l'appel. Toute erreur SDK est wrappée en `BackendError` (cause préservée dans `__cause__`).

**`chat(..., stream=True)` est interdit.** Sur les trois backends routables, passer `stream=True` à `chat()` lève `NotSupportedError` pointant vers `stream()`/`astream()`.

### `astream(messages, **kwargs) -> AsyncIterator[dict]` / `AsyncClient.stream(messages, **kwargs) -> AsyncIterator[dict]`

Pendant asynchrone de `stream()`. `AsyncClient.stream()` retourne un `AsyncIterator[dict]` consommé avec `async for`. La fonction globale `apicol.astream(...)` est le wrapper de commodité correspondant. Même contrat de chunks, même sémantique d'erreurs.

```python
async for chunk in client.stream(messages=[...]):
    delta = chunk["choices"][0]["delta"].get("content")
    if delta:
        print(delta, end="", flush=True)
```

## Niveau 2 — Échappatoire native

L'échappatoire native est désormais accessible **principalement** via la méthode `client.anthropic_native()` du Client. Les fonctions globales `anthropic_client()` et `anthropic_async_client()` sont conservées comme **alias rétrocompatibles** (utilisent un Client implicite construit depuis les env vars).

### `Client.anthropic_native() -> anthropic.Anthropic`

Retourne un client Anthropic synchrone préconfiguré avec la `api_key` et la `base_url` (si définie) du Client. **Disponible uniquement si le `Client` a été construit avec `backend="anthropic"`** — sinon lève `BackendUnavailableError`.

**Usage typique** :

```python
client = apicol.Client(backend="anthropic", api_key="...", model="claude-opus-4-7")
native = client.anthropic_native()
response = native.messages.create(
    model="claude-opus-4-7",
    max_tokens=8192,
    system=[
        {
            "type": "text",
            "text": "Long document...",
            "cache_control": {"type": "ephemeral"},
        }
    ],
    messages=[{"role": "user", "content": "Question"}],
)
```

À partir de ce point, **tu utilises le SDK Anthropic natif avec toutes ses features** : prompt caching avec breakpoints fins, citations, PDF input, batch API, agent skills, tout.

### `AsyncClient.anthropic_native() -> anthropic.AsyncAnthropic`

Identique mais async.

### Alias rétrocompatibles : `anthropic_client()` / `anthropic_async_client()`

Fonctions globales conservées pour la rétrocompat avec la v0.1. Elles construisent un `Client` (ou `AsyncClient`) implicite depuis les variables d'environnement et appellent `.anthropic_native()` dessus. Équivalent à :

```python
apicol.anthropic_client()
# ≡
apicol.Client(
    backend=os.environ["APICOL_TYPE"],
    api_key=os.environ["APICOL_KEY"],
    model=os.environ.get("APICOL_MODEL"),
    base_url=os.environ.get("APICOL_URL"),
).anthropic_native()
```

**Comportement** :

- Si `APICOL_TYPE != "anthropic"` → lève `BackendUnavailableError`.
- Si `APICOL_KEY` absent → lève `ConfigError`.

## Backend dev only

### `claude_cli_chat(messages, *, model=None, timeout=120) -> dict`

Wrappe une invocation `claude -p` en subprocess synchrone.

**⚠️ Dev only.** Cette fonction est destinée à un usage **personnel interactif** : tu écris un script local qui utilise ton Claude Code installé. Elle **n'est pas** destinée à servir une charge programmatique routée selon coût/dispo — un tel usage enfreint les TOS de Claude Pro/Max.

**Paramètres** :

- `messages: list[dict]` — format OpenAI, comme `chat()`. Aplati en un seul prompt avant invocation.
- `model: str | None` — passé en `--model` si fourni.
- `timeout: int` — timeout subprocess en secondes (default 120).

**Retour** : `dict` au format OpenAI minimal (pas de `usage` détaillé car `claude -p` ne le rapporte pas de manière standard) :

```python
{
    "id": "claude-cli-<uuid>",
    "model": "claude (cli)",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "..."},
            "finish_reason": "stop",
        }
    ],
    "usage": None,  # non disponible
}
```

**Erreurs** :

- `BackendUnavailableError` — `claude` introuvable dans le PATH
- `BackendError` — subprocess a renvoyé un code non-zéro ou timeout

### `claude_cli_achat(messages, *, model=None, timeout=120) -> dict`

Version asynchrone. Utilise `asyncio.create_subprocess_exec`. Signature identique.

## Compatibilité backends

| Feature | `anthropic` (niveau 1) | `anthropic` (niveau 2) | `openai-compatible` | `litellm` | `claude_cli` |
|---------|-----------------------|------------------------|---------------------|-----------|--------------|
| Chat completion sync | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chat completion async | ✅ | ✅ | ✅ | ✅ | ✅ |
| System message | ✅ | ✅ | ✅ | ✅ | ✅ (aplati) |
| `temperature`, `max_tokens` | ✅ | ✅ | ✅ | ✅ | ❌ (CLI) |
| `reasoning_effort` | ✅ (mappé) | ✅ (natif `thinking`) | ✅ (natif o-series/gpt-5) | ✅ (passé tel quel) | ❌ |
| `extra_headers` (connexion) | ✅ | ✅ (via SDK) | ✅ (`default_headers`) | ⚠️ (ignoré) | ❌ |
| Prompt caching | ⚠️ (via `extra_body`) | ✅ (natif, breakpoints fins) | ⚠️ (selon endpoint) | ⚠️ (selon provider) | ❌ |
| Citations | ❌ | ✅ | ❌ | ❌ | ❌ |
| PDF input | ❌ | ✅ | ❌ | ❌ | ❌ |
| Streaming | ✅ (stream/astream) | ✅ (SDK natif) | ✅ (stream/astream) | ✅ (stream/astream) | ❌ |
| Tool calls | ❌ v0.3 | ✅ (SDK natif) | ❌ v0.3 | ❌ v0.3 | ❌ |
| Batch API | ❌ | ✅ (SDK natif) | ⚠️ (selon endpoint) | ⚠️ (selon provider) | ❌ |

Légende : ✅ supporté · ⚠️ supporté avec limites/conventions · ❌ non supporté

## Exemples de scénarios

### Scénario 1 — Portabilité maximale (mode mono-backend, fonctions globales)

```python
import os
import apicol

# Run 1 : Anthropic
os.environ.update({
    "APICOL_TYPE": "anthropic",
    "APICOL_KEY": "sk-ant-...",
    "APICOL_MODEL": "claude-opus-4-7",
})
response = apicol.chat(
    messages=[{"role": "user", "content": "Explique la relativité"}],
    reasoning_effort="high",
)

# Run 2 : Ollama local — même code applicatif
os.environ.update({
    "APICOL_TYPE": "openai-compatible",
    "APICOL_KEY": "ollama",  # factice, accepté par le SDK OpenAI
    "APICOL_MODEL": "qwen3:32b",
    "APICOL_URL": "http://localhost:11434/v1",
})
response = apicol.chat(
    messages=[{"role": "user", "content": "Explique la relativité"}],
)

# Run 3 : Gemini natif via LiteLLM — toujours le même code
os.environ.update({
    "APICOL_TYPE": "litellm",
    "APICOL_KEY": "...",
    "APICOL_MODEL": "gemini/gemini-2.5-pro",
})
response = apicol.chat(
    messages=[{"role": "user", "content": "Explique la relativité"}],
    reasoning_effort="high",
)
```

### Scénario 1ter — OpenRouter avec headers de tracking (`openai-compatible`)

```python
import apicol

openrouter = apicol.Client(
    backend="openai-compatible",
    api_key="sk-or-...",
    model="anthropic/claude-haiku-4-5",
    base_url="https://openrouter.ai/api/v1",
    extra_headers={
        "HTTP-Referer": "https://github.com/Sandjab/apicol",
        "X-Title": "apicol",
    },
)
response = openrouter.chat(messages=[{"role": "user", "content": "Bonjour"}])
```

### Scénario 1bis — Multi-backend simultané (Client explicite)

```python
import apicol

claude = apicol.Client(backend="anthropic", api_key="sk-ant-...", model="claude-opus-4-7")
gpt    = apicol.Client(backend="litellm",   api_key="sk-...",     model="openai/gpt-5")

prompt = [{"role": "user", "content": "Explique la relativité"}]
claude_response = claude.chat(prompt)
gpt_response    = gpt.chat(prompt)
# → deux backends actifs simultanément, pas d'état global partagé
```

### Scénario 2 — Caching agressif (niveau 2)

```python
import apicol

client = apicol.Client(backend="anthropic", api_key="sk-ant-...", model="claude-opus-4-7")
native = client.anthropic_native()

response = native.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": gros_document_100k_tokens,
            "cache_control": {"type": "ephemeral"},
        },
    ],
    messages=[{"role": "user", "content": "Question sur le document"}],
)
```

### Scénario 3 — Dev local interactif

```python
import apicol

# Aucune variable APICOL_* requise — utilise le `claude` CLI authentifié sur la machine
response = apicol.claude_cli_chat(
    messages=[{"role": "user", "content": "Résume CHANGELOG.md du dossier courant"}],
)
print(response["choices"][0]["message"]["content"])
```

## Engagements de compatibilité

- Toute modification de signature d'une fonction publique listée ci-dessus est une **breaking change** et nécessite une bump de version mineure + un PRD.
- L'ajout de paramètres optionnels (avec default `None`) n'est **pas** une breaking change.
- L'ajout de nouvelles valeurs à `APICOL_TYPE` n'est **pas** une breaking change.
- La modification de la table de mapping `reasoning_effort` (changement de `budget_tokens`) **est** une breaking change documentée dans CHANGELOG.
