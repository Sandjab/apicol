# ARCHITECTURE.md

Décisions techniques de `apicol`. Toute décision structurante référencée ici renvoie à un PRD dans `docs/prd/`.

## Vue d'ensemble

```
                     ┌─────────────────────────────────────────────────┐
                     │              Code applicatif                     │
                     │   (scripts, Athanor, notebooks, etc.)            │
                     └────┬─────────────────────┬──────────────────────┘
                          │                     │
            (mono-backend │                     │ (multi-backend
             via env vars)│                     │  via Client explicite)
                          ▼                     ▼
       ┌────────────────────────────────────────────────────────────────┐
       │                          apicol (lib)                            │
       │                                                                  │
       │   ┌──────────────────────┐    ┌──────────────────────────────┐ │
       │   │ Fonctions globales : │    │  Client(backend, key, ...) /  │ │
       │   │   chat / achat       │───▶│  AsyncClient(...)             │ │
       │   │ (wrappers commodité, │    │  ── objet config + méthodes   │ │
       │   │  client implicite    │    │     .chat() / .anthropic_     │ │
       │   │  depuis env vars)    │    │     native()                  │ │
       │   └──────────────────────┘    └──────────────┬────────────────┘ │
       │                                              │ dispatch          │
       │                                              ▼                   │
       │                            ┌───────────────────────────┐         │
       │                            │   _route.pick_backend()   │         │
       │                            │   match config.backend    │         │
       │                            └──┬───────┬───────┬────────┘         │
       │                               │       │       │                  │
       │                               ▼       ▼       ▼                  │
       │                          ┌────────┐┌──────────┐┌─────────┐       │
       │                          │anthropic││ openai-  ││ litellm │       │
       │                          │backend  ││compatible││ backend │       │
       │                          │         ││ backend  ││         │       │
       │                          └───┬────┘└────┬─────┘└────┬────┘       │
       │                              │          │           │             │
       └──────────────────────────────┼──────────┼───────────┼─────────────┘
                                      │          │           │
                                      ▼          ▼           ▼
                           ┌──────────┐┌────────────────┐┌─────────────────┐
                           │ Anthropic││ OpenAI SDK     ││ LiteLLM         │
                           │ SDK natif││ (OpenAI,       ││ (Gemini natif,  │
                           │          ││  Mistral,      ││  Bedrock, Vertex,│
                           │          ││  Ollama, vLLM, ││  Azure, Cohere) │
                           │          ││  OpenRouter…)  ││                 │
                           └──────────┘└────────────────┘└─────────────────┘

       Échappatoire native (depuis Client ou fonction globale) :
       Client(backend="anthropic", ...).anthropic_native() → anthropic.Anthropic
       apicol.anthropic_client() (alias rétrocompatible)

       Backend dev only — séparé, jamais routé :
       ┌────────────────────────────────────┐
       │  claude_cli_chat() → subprocess    │
       │  `claude -p ...`                    │
       └────────────────────────────────────┘
```

## Décisions structurantes

### D1 — Architecture à deux niveaux

**Décision.** La surface publique est volontairement divisée en deux niveaux : un niveau unifié format OpenAI (`Client.chat`, `AsyncClient.chat`, et leurs wrappers globaux `chat`, `achat`) qui marche partout avec quelques mappings, et un niveau « échappatoire native » (`client.anthropic_native()` ou son alias rétrocompatible `anthropic_client()`) qui retourne un SDK Anthropic configuré pour les features non-portables.

**Pourquoi.** Une abstraction qui prétend exposer 100 % des features de tous les backends est une fiction. LiteLLM lui-même fuit pour les cas avancés (caching breakpoints, citations, PDF). Plutôt que prétendre à l'étanchéité et laisser l'utilisateur découvrir les fuites en debug, on délimite explicitement le périmètre portable et on offre une sortie nommée.

**Conséquences.** Le code applicatif qui n'utilise que `chat()` ou `Client.chat()` est 100 % portable entre backends. Le code applicatif qui appelle `anthropic_native()` est conscient qu'il se lie au backend Anthropic — c'est explicite à la lecture.

**Référence.** `docs/prd/PRD-001-architecture-deux-niveaux.md`, complété par PRD-003 pour le passage à un Client réifié.

### D2 — Format OpenAI comme lingua franca

**Décision.** Les `messages` en entrée et la réponse en sortie suivent le format OpenAI (`{"role": "user", "content": "..."}`, retour avec `choices[0].message.content`).

**Pourquoi.** C'est le format que tout l'écosystème supporte. Anthropic propose même un endpoint OpenAI-compatible (mais incomplet — d'où D1). LiteLLM utilise déjà ce format. Choisir le format Anthropic en surface impliquerait de traduire vers OpenAI à chaque appel LiteLLM, soit 90 % des appels.

**Conséquence pour le backend Anthropic.** La traduction OpenAI→Anthropic se fait à la frontière de `_backends/anthropic.py`. Le rôle `system` est extrait des messages et passé en kwarg `system` au SDK. Les blocks `content` sont mappés. La réponse Anthropic est reformatée en `{"choices": [{"message": {...}}], "usage": {...}}`.

### D3 — Mapping des features avancées par catégorie

| Catégorie | Exemples | Stratégie |
|-----------|----------|-----------|
| **A. Optimisations silencieusement ignorables** | `cache_control` inline, beta headers | Passées via `extra_body`. Le backend qui ne sait pas → ignore. Conforme à la convention LiteLLM. |
| **B. Features mappables avec table de correspondance** | `reasoning_effort` ↔ `thinking.budget_tokens` | Paramètre unifié exposé dans `chat()`. Le backend Anthropic traduit `low/medium/high/none` en budgets concrets ou en mode adaptif selon le modèle. |
| **C. Features non-portables** | citations natives, PDF structuré, batch API, agent skills | **Pas dans `chat()`**. L'utilisateur sort par `anthropic_client()` pour y accéder. |

**Référence pour le mapping reasoning_effort → thinking** : `SPEC.md` section « Paramètres unifiés ».

### D4 — Délégation maximale à LiteLLM

**Décision.** Le backend `litellm` est un wrapper extrêmement fin autour de `litellm.completion()` / `litellm.acompletion()`. On ne réimplémente ni le routage interne de LiteLLM, ni la gestion de ses providers, ni son système de retry.

**Pourquoi.** LiteLLM gère déjà 100+ providers, a 12h de load tests sur chaque release, et est plus mature que tout ce qu'on pourrait écrire. Le risque c'est d'ajouter une couche qui casse plus qu'elle ne simplifie.

**Conséquence.** Quand l'utilisateur veut passer un param spécifique à LiteLLM (ex. `custom_llm_provider`, `api_base`, `mock_response`), il passe par `extra_body` et c'est transmis tel quel. Pas d'allowlist, pas de filtrage.

### D5 — `claude -p` est strictement séparé

**Décision.** Le backend `claude -p` n'est **pas** sélectionnable via `APICOL_TYPE`. Il est exposé via une fonction publique distincte `claude_cli_chat()` (et `claude_cli_achat()` pour l'async).

**Pourquoi (technique).** `claude -p` n'est pas une API stateless de chat completion ; c'est un CLI agentique avec son propre cycle de vie, ses propres modes (interactif, prompt, JSON output), et des capacités (tools, skills, MCP) qu'on ne veut pas exposer accidentellement dans un appel routé.

**Pourquoi (TOS).** L'abonnement Claude Pro/Max sous `claude -p` est une licence d'usage personnel interactif. Le router programmatiquement comme « un backend parmi d'autres » dans une logique de coût/dispo enfreint les TOS Anthropic. La séparation lexicale rend cette frontière visible dans le code applicatif.

**Garde-fou.** `_config.py` rejette explicitement `APICOL_TYPE=claude_cli` avec un message qui pointe vers `claude_cli_chat()`. Ce n'est pas un bug, c'est intentionnel.

### D6 — Sync ET async, en miroir

**Décision.** Chaque fonction publique a un pendant async :

| Sync | Async |
|------|-------|
| `chat()` | `achat()` |
| `anthropic_client()` | `anthropic_async_client()` |
| `claude_cli_chat()` | `claude_cli_achat()` |

**Pourquoi.** Les deux SDKs (`anthropic`, `litellm`) exposent nativement les deux modes. Forcer l'utilisateur à wrapper en `asyncio.run()` ou en `run_in_executor` est gratuit. Le coût d'implémentation est faible : on duplique le dispatch, pas la logique métier.

**Conséquence.** Les fonctions de traduction (OpenAI↔Anthropic) sont synchrones et partagées entre les deux chemins. Seul le `await` change.

### D7 — Pas de streaming en v0.1 *(supersédée par D12)*

**Décision.** v0.1 supporte uniquement les réponses complètes (non-streaming).

**Pourquoi.** Le streaming a des formats de chunk différents par backend (Anthropic envoie des events typés `message_start`, `content_block_delta`, etc. ; OpenAI envoie des chunks avec `delta`). Unifier ça nécessite une couche d'événements abstraits que l'on ne veut pas concevoir avant d'avoir des cas d'usage concrets. Reporté à v0.2.

**Note :** décision négative désormais levée — voir **D12** (v0.3.0).

### D8 — Configuration : 4 variables, pas de fichier

**Décision.** La configuration passe exclusivement par les 4 variables d'environnement documentées dans `SPEC.md`. Pas de `apicol.yaml`, pas de `.apicolrc`, pas de fichier dotenv chargé automatiquement.

**Pourquoi.** Une lib aussi fine n'a pas besoin de système de config. Si l'utilisateur veut un fichier, il charge un dotenv dans son application avant d'importer `apicol`. Garder la lib stateless et déterministe par rapport à l'environnement.

**Conséquence.** Pas de fallback caché vers `ANTHROPIC_API_KEY` ou `OPENAI_API_KEY` même s'ils sont définis. C'est volontaire — l'utilisateur doit savoir quelle clé est utilisée.

### D9 — Erreurs typées, jamais d'exception brute

```python
apicol.errors.ConfigError              # env vars manquantes / invalides
apicol.errors.BackendUnavailableError  # backend demandé pas installé / pas autorisé
apicol.errors.BackendError             # erreur remontée du SDK sous-jacent (wrap)
apicol.errors.NotSupportedError        # feature explicitement non supportée en v0.1 (ex. tools)
```

Les erreurs SDK upstream (`anthropic.APIError`, `litellm.exceptions.*`) sont accessibles en `__cause__` pour debug, mais on remonte toujours une erreur `apicol.*` typée.

### D10 — Réification de la configuration en `Client`

**Décision.** La configuration est réifiée en un objet `Client` (sync) / `AsyncClient` (async), immutable après construction. Les fonctions globales `chat()`, `achat()` sont **redéfinies** comme des wrappers de commodité qui construisent un client implicite à partir des variables d'environnement (avec cache lazy invalidé par hash de la config courante).

**Pourquoi.** Tant que la configuration est globale et implicite, un seul backend peut exister à un instant donné dans le process. Réifier la config permet d'en avoir plusieurs simultanément, chacune référencée par un objet distinct, ce qui débloque les cas multi-backend (bench, fallback applicatif, comparaison) sans état global partagé. C'est le pattern standard de l'écosystème (`openai.OpenAI`, `anthropic.Anthropic`, `boto3.client`).

**Conséquences** :

- Surface publique étendue : `Client`, `AsyncClient`, plus la méthode `client.anthropic_native()` qui remplace fonctionnellement `anthropic_client()`. Cette dernière est conservée comme alias rétrocompatible.
- Le `Client` est immutable (dataclass frozen). Pour changer de config, on crée un nouveau client. Simplifie le raisonnement multi-instance.
- Les fonctions globales restent l'API minimale pour les usages mono-backend — ergonomie v0.1 préservée.
- `claude_cli_chat()` reste fonction globale séparée. **Pas** exposée comme méthode du Client. La frontière TOS reste lexicale (cf. D5).

**Référence.** `docs/prd/PRD-003-multi-backend-simultane.md`

### D11 — Backend `openai-compatible` distinct de LiteLLM


**Décision.** Trois backends coexistent : `anthropic`, `openai-compatible`, `litellm`. Le backend `openai-compatible` utilise le SDK officiel `openai` pour parler à tout endpoint qui expose `/v1/chat/completions` au format OpenAI (OpenAI, Mistral, Ollama, vLLM, LM Studio, OpenRouter, Groq, DeepSeek, Together, Fireworks, Anyscale, et tout proxy compatible — y compris LiteLLM en mode proxy). LiteLLM reste pour les providers qui **ne parlent pas** OpenAI nativement : Gemini natif (Google AI Studio / Vertex AI), Bedrock, Azure OpenAI, Cohere, Replicate, HuggingFace Inference.

**Pourquoi.** Pour 6/7 des providers ciblés à l'origine par le README (OpenAI, Mistral, Ollama, vLLM, LM Studio, OpenRouter), LiteLLM est techniquement surdimensionné : ces endpoints sont déjà OpenAI-compatibles, et `openai.OpenAI(base_url=...)` suffit. Charger LiteLLM (~200 transitives, surface qui bouge) pour ces cas-là, c'est payer sans contrepartie. LiteLLM gagne sa place uniquement pour les providers exotiques où il fait du vrai travail de traduction de format et d'auth. Aligner la dépendance sur la valeur ajoutée réelle, c'est l'application à LiteLLM de la règle qu'on lui applique déjà (D2 — « ne pas réinventer ce qui existe »).

**Conséquences** :

- Une **règle de décision claire** dans SPEC.md et README.md : `openai-compatible` pour les endpoints OpenAI HTTP, `litellm` pour les providers natifs exotiques, `anthropic` pour le SDK natif Anthropic. L'utilisateur choisit explicitement.
- **Asymétrie sur `APICOL_KEY`** : pour `litellm`, la clé est injectée dans l'env var attendue par le provider détecté à partir du nom de modèle (« seule magie acceptée » de D8). Pour `openai-compatible`, la clé est passée telle quelle au SDK OpenAI — pas de magie de détection. Documentée dans SPEC.
- **Nouveau kwarg `extra_headers`** sur `Client` / `AsyncClient` : attaché à la connexion (`default_headers` du SDK OpenAI), utile pour OpenRouter (`HTTP-Referer`, `X-Title`) ou pour un gateway custom. Cohabite avec `extra_body` (qui reste par appel).
- **Pas d'`openai_native()`** : contrairement au cas Anthropic, le SDK OpenAI est trivialement instanciable par l'utilisateur (`openai.OpenAI(api_key=..., base_url=...)`) et toutes ses features sont accessibles au niveau 1 d'apicol. Ajout reporté si demande émerge.
- **LiteLLM reste dépendance directe en v0.2** ; le rendre optionnel via extras (`pip install apicol[litellm]`) est reporté à un éventuel PRD-005.

**Référence.** `docs/prd/PRD-004-backend-openai-compatible.md`

### D12 — Streaming via méthodes dédiées (amende D7)

**Décision.** Le streaming est exposé via des méthodes/fonctions dédiées `stream()`/`astream()` — **pas** via un paramètre `stream=True` sur `chat()`. Les chunks yielded sont des dicts au format OpenAI (best-effort). Implémenté en v0.3.0 ; amende D7 (« pas de streaming en v0.1 »).

**Surface publique ajoutée** :

| Symbole | Type de retour |
|---------|---------------|
| `Client.stream(messages, **kwargs)` | `Iterator[dict[str, Any]]` |
| `AsyncClient.stream(messages, **kwargs)` | `AsyncIterator[dict[str, Any]]` |
| `stream(...)` (globale) | `Iterator[dict[str, Any]]` |
| `astream(...)` (globale) | `AsyncIterator[dict[str, Any]]` |

**Pourquoi des méthodes dédiées et non `stream=True` sur `chat()`.** Un retour polymorphe `dict | Iterator` est intenable en `mypy --strict` et brouille le contrat de `chat()`. La séparation lexicale préserve le type de retour de `chat()` et maintient le miroir sync/async lisible — cohérent avec la norme du projet.

**Pourquoi D7 est levée maintenant.** D7 reportait parce que les formats de chunks diffèrent par backend. Or c'est exactement le problème résolu par D2 (lingua franca OpenAI) pour les réponses complètes. Deux des trois backends routables (`openai-compatible`, `litellm`) émettent déjà des chunks format OpenAI — pass-through quasi-immédiat. Seul Anthropic exige un codec events→chunks, strictement localisé dans `_backends/anthropic.py` (même frontière que la traduction de réponses complètes).

**Codec Anthropic** : localisé dans `_backends/anthropic.py`. Les events `content_block_delta` (type `text_delta`) sont mappés en chunks `delta.content` ; l'event `message_delta` porte le `finish_reason` et l'`usage` (best-effort). Events de structure (`message_start`, `content_block_start/stop`, `message_stop`, `thinking_delta`) ignorés.

**`openai-compatible` et `litellm`** : pass-through. Le SDK retourne déjà des chunks format OpenAI ; `stream()` appelle le SDK avec `stream=True` et yield chaque chunk en dict.

**Garde `stream=True` sur `chat()`** : helper `reject_chat_stream(kwargs)` dans `_backends/__init__.py`, appelé en tête des fonctions `complete`/`acomplete` des 3 backends. Lève `NotSupportedError` pointant vers `stream()`/`astream()`. Centralisé et homogène sur les 3 backends (corrige une incohérence latente où openai/litellm auraient transmis `stream=True` au SDK et fait échouer la conversion).

**`claude_cli` non couvert** : dev-only, subprocess, format JSON-lines propriétaire. Hors périmètre — éventuel PRD ultérieur si besoin émerge.

**Référence.** `docs/prd/PRD-005-streaming.md`

## Flux de dispatch

**Via `Client` explicite (chemin principal en multi-backend) :**

```
Client(backend, api_key, model, base_url)
  │
  ├─→ _config.Config(...)            # dataclass frozen, validé à la construction
  │     ├─ valide les valeurs
  │     └─ si backend == "claude_cli" → ConfigError (« utiliser claude_cli_chat() »)
  │
  ├─→ stocke la config + résout le callable backend une fois
  │
  └─→ client.chat(messages, **kwargs)
       └─→ _backends.{anthropic|openai_compatible|litellm}.complete(messages, config, **kwargs)
            └─→ retourne dict format OpenAI : {"choices": [...], "usage": {...}, "model": "..."}
```

**Via fonctions globales (chemin de commodité mono-backend) :**

```
chat(messages, **kwargs)
  │
  ├─→ _client._get_implicit_client()    # cache lazy en module-state
  │     ├─ hash(env vars APICOL_*) inchangé → réutilise le client en cache
  │     └─ sinon → construit un nouveau Client depuis _config.load_from_env()
  │
  └─→ implicit_client.chat(messages, **kwargs)
       └─→ [identique au chemin Client ci-dessus]
```

## Frontières de traduction

**OpenAI → Anthropic** (à l'entrée du backend anthropic) :

- Extraction du message `system` → kwarg `system`
- Mapping `messages` : `role` reste (`user`, `assistant`), `content` reformaté si liste de blocks
- Mapping `reasoning_effort` → `thinking={"type": "enabled", "budget_tokens": N}` selon table
- `max_tokens` requis par Anthropic — si absent, default raisonnable (4096) avec warning

**Anthropic → OpenAI** (à la sortie du backend anthropic) :

- `response.content[0].text` → `choices[0].message.content`
- `response.usage.input_tokens` → `usage.prompt_tokens`
- `response.usage.output_tokens` → `usage.completion_tokens`
- `response.stop_reason` → mapping vers `finish_reason` OpenAI

**LiteLLM** : aucune traduction. LiteLLM accepte du format OpenAI et renvoie du format OpenAI. On passe les `messages` tels quels, on récupère la réponse telle quelle. Les seules manipulations sont : préfixer le model avec le provider si nécessaire, injecter `api_base` depuis `APICOL_URL`.

**`openai-compatible`** : aucune traduction non plus. Le SDK OpenAI parle déjà OpenAI. La seule manipulation est l'appel à `.model_dump()` sur le `ChatCompletion` Pydantic retourné pour respecter le contrat `dict[str, Any]` partagé par tous les backends. `extra_headers` est appliqué une seule fois à la construction du client SDK (`default_headers`), pas par appel.

## Tests : stratégie

| Niveau | Type | Cible |
|--------|------|-------|
| `tests/test_config.py` | unitaire | Validation des env vars, erreurs claires |
| `tests/test_route.py` | unitaire | Dispatch correct selon api_type, rejet de `claude_cli` |
| `tests/test_anthropic_backend.py` | unitaire (mock) | Traduction OpenAI↔Anthropic, mapping reasoning_effort |
| `tests/test_litellm_backend.py` | unitaire (mock) | Pass-through correct, injection api_base |
| `tests/test_openai_compatible_backend.py` | unitaire (mock) | Pass-through, propagation api_key/base_url/extra_headers au constructeur SDK |
| `tests/test_claude_cli_backend.py` | unitaire (mock subprocess) | Format de l'invocation, parsing de la sortie |
| `tests/integration/` | integration (réseau) | Smoke tests sur vraies APIs, marqués `@pytest.mark.integration` |

## Extensions futures

- v0.3 ✅ : streaming sync + async — livré (`stream`/`astream`, D12, PRD-005)
- v0.3 (reste) : support des tool calls (mapping OpenAI ↔ Anthropic ↔ LiteLLM)
- v0.4 : éventuel support des embeddings via une fonction `embed()` dédiée
- Pas prévu : cost tracking, fallback automatique, virtual keys (utiliser le proxy LiteLLM pour ça)

## Limites assumées

- **Couplage à LiteLLM.** Si LiteLLM disparaît ou change radicalement, on a un problème. Acceptable parce qu'on ne paie pas le coût de maintenir nous-mêmes 100+ intégrations.
- **Compatibility layer Anthropic incomplet.** Pas un problème ici parce qu'on n'utilise pas le layer OpenAI d'Anthropic — on utilise le SDK natif quand `api_type=anthropic`.
- **Pas de garantie de parité fine** entre les comportements des backends (ex. `temperature=0` ne donne pas les mêmes sorties chez OpenAI et chez Anthropic). C'est une limite inhérente à toute couche d'abstraction LLM, pas spécifique à ce projet.
