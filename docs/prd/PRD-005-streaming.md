# PRD-005 : Support du streaming (sync + async)

**Statut** : Accepté (cible v0.3.0)
**Date** : 2026-06-19
**Auteur** : Sandjab
**Source** : conversation de design (brainstorming) — le streaming était reporté depuis v0.1 (décision D7 « pas de streaming, formats de chunks différents par backend »). v0.2.0 ayant unifié la surface autour du format OpenAI (dict), la voie est ouverte pour lever D7 sans réintroduire l'hétérogénéité qu'elle craignait.

---

## Vision

**Le quoi : quel pattern ce PRD propose-t-il ?**

Ajouter une voie de streaming **en miroir strict** du chemin `chat()` existant, sous forme de **méthodes/fonctions dédiées** (pas un paramètre `stream=True` sur `chat()`) :

- `Client.stream(messages, **kwargs) -> Iterator[dict[str, Any]]`
- `AsyncClient.stream(messages, **kwargs) -> AsyncIterator[dict[str, Any]]`
- fonctions globales `stream(...)` (sync) et `astream(...)` (async), via le `Client` implicite, exactement comme `chat`/`achat`

Chaque itération **yield un dict au format OpenAI chunk** (`{"choices":[{"index":0,"delta":{"content": "..."},"finish_reason": null}], ...}`). Périmètre : les **3 backends routables** (`anthropic`, `openai-compatible`, `litellm`). `claude_cli` (dev-only, subprocess) est hors périmètre.

**Le pourquoi : pourquoi ce pattern fonctionne-t-il ?**

Le mécanisme est l'**alignement du streaming sur la lingua franca déjà choisie**. D7 reportait le streaming parce que « les formats de chunks diffèrent par backend ». Mais c'est exactement le problème que la D2 (« format OpenAI lingua franca ») a déjà résolu pour les réponses complètes : on traduit à la frontière de chaque backend et le reste de la lib parle OpenAI. Or **deux des trois backends routables (`openai-compatible`, `litellm`) émettent déjà des chunks au format OpenAI** — pour eux le streaming est un quasi pass-through. Seul Anthropic exige un codec events→chunks, et il est strictement localisé dans `_backends/anthropic.py`, comme l'est déjà la traduction des réponses complètes.

Le choix de **méthodes dédiées** plutôt que `stream=True` préserve deux invariants forts du projet : le type de retour de `chat()` reste `dict` (pas de retour polymorphe `dict | Iterator`, intenable en `mypy --strict` et pénible pour l'appelant), et le miroir sync/async reste lisible.

**Le comment** : renvoyé au Plan d'implémentation.

## Exemple bout-en-bout (projeté)

```python
import apicol

# === Cas 1 — streaming via Client ===
claude = apicol.Client(backend="anthropic", api_key="sk-ant-...", model="claude-opus-4-7")
for chunk in claude.stream(messages=[{"role": "user", "content": "Raconte une histoire courte"}]):
    delta = chunk["choices"][0]["delta"].get("content")
    if delta:
        print(delta, end="", flush=True)

# === Cas 2 — streaming async ===
import asyncio

gpt = apicol.AsyncClient(backend="openai-compatible", api_key="sk-...", model="gpt-5")

async def main():
    async for chunk in gpt.stream(messages=[{"role": "user", "content": "Bonjour"}]):
        delta = chunk["choices"][0]["delta"].get("content")
        if delta:
            print(delta, end="", flush=True)

asyncio.run(main())

# === Cas 3 — fonctions globales (env vars) ===
# export APICOL_TYPE=litellm ; APICOL_MODEL=gemini/gemini-2.5-pro ; APICOL_KEY=...
for chunk in apicol.stream(messages=[{"role": "user", "content": "Bonjour"}]):
    print(chunk["choices"][0]["delta"].get("content") or "", end="")

# version async : await apicol.astream(...)

# === Cas 4 — chat() reste non-streaming et rejette stream=True explicitement ===
apicol.chat(messages=[...], stream=True)
# -> NotSupportedError: "stream=True n'est pas supporté sur chat() ; utiliser stream()/astream()."
```

---

## Contexte

- **D7 (ARCHITECTURE.md)** : « Pas de streaming en v0.1 — les formats de chunks diffèrent par backend ; reporté. » C'était une décision *négative* assumée, pas un oubli.
- **BACKLOG.md** : « Support du streaming sync + async (v0.3) — interface d'events unifiée à concevoir. » Ce PRD *est* cette conception.
- **v0.2.0** a introduit le backend `openai-compatible` et confirmé le format OpenAI (dict) comme contrat de retour partagé par tous les backends (`_anthropic_to_openai`, `.model_dump()` pour openai/litellm).

État des backends vis-à-vis du streaming :

| Backend | Streaming SDK | Format des chunks émis | Travail apicol |
|---|---|---|---|
| `openai-compatible` | `stream=True` → itérateur de `ChatCompletionChunk` | déjà OpenAI | `.model_dump()` par chunk (pass-through) |
| `litellm` | `completion(stream=True)` / `acompletion` | déjà OpenAI-compatible | conversion par chunk (pass-through) |
| `anthropic` | `client.messages.stream(...)` → events typés | **events Anthropic** (message_start, content_block_delta, message_delta…) | **codec events→chunks OpenAI** |
| `claude_cli` | `--output-format stream-json` (subprocess) | JSON-lines propriétaire | hors périmètre (dev-only) |

---

## Problème

**Comment exposer le streaming de façon cohérente sur trois backends dont les formats d'events diffèrent, sans casser le miroir sync/async, sans polymorphiser le type de retour de `chat()`, et en restant `mypy --strict`-clean ?**

Trois sous-questions :

1. **Forme de surface** : `stream=True` sur `chat()` (à la OpenAI) impose un retour `dict | Iterator`. Comment exposer le streaming sans dégrader le typage ni le contrat de `chat()`.
2. **Contrat des chunks** : que yield-on, et avec quel niveau d'uniformité garanti entre backends (le nœud même de D7) ?
3. **Cohérence du chemin non-streaming** : aujourd'hui seul Anthropic rejette `stream=True` sur `chat()` ; openai/litellm le transmettraient au SDK et casseraient la conversion de réponse. Il faut un garde homogène.

---

## Solution

**Ajouter `stream`/`astream` comme voie dédiée en miroir, yieldant des dicts format OpenAI chunk (best-effort), avec un codec localisé pour Anthropic et un garde `stream=True` généralisé sur le chemin `chat()`.**

### Surface publique cible

| Symbole | Avant (v0.2) | Après (v0.3) |
|---|---|---|
| `Client.chat` / `AsyncClient.chat` | inchangé | inchangé |
| `Client.stream(messages, **kwargs)` | n/a | `Iterator[dict[str, Any]]` |
| `AsyncClient.stream(messages, **kwargs)` | n/a | `AsyncIterator[dict[str, Any]]` |
| `stream(...)` (globale) | n/a | `Iterator[dict[str, Any]]` |
| `astream(...)` (globale) | n/a | `AsyncIterator[dict[str, Any]]` |
| `__all__` | … | + `"stream"`, `"astream"` |

Aucune signature existante ne change. Aucun symbole renommé ou retiré. Le miroir des noms suit l'existant : méthodes homonymes sur les deux clients (`stream` sur `Client` et `AsyncClient`, comme `chat`), globales différenciées par le préfixe `a` (`stream`/`astream`, comme `chat`/`achat`).

### Contrat des chunks (best-effort, forme OpenAI)

On garantit la **structure** : chaque chunk est un dict avec `choices[0].delta` ; le texte incrémental est dans `choices[0].delta.content` (absent/`None` sur les chunks sans texte) ; le dernier chunk porte un `finish_reason` non nul. L'`usage` final est fourni **si** le backend le donne, **sans** normalisation fine inter-backend (pas d'activation forcée d'`include_usage`, pas d'agrégation custom — voir Points reportés). C'est l'équilibre cohérence/effort retenu pour une v0.3.

### Codec Anthropic (le seul vrai travail)

Le payload est construit par le `_openai_to_anthropic()` **existant** (réutilisé tel quel ; `stream` n'est pas passé dans ses kwargs). Puis `client.messages.stream(**payload)` est itéré et les events mappés :

- `content_block_delta` de type `text_delta` → `{"choices":[{"index":0,"delta":{"content": delta.text},"finish_reason": null}]}`
- `message_delta` portant `stop_reason` → chunk final `{"choices":[{"index":0,"delta":{},"finish_reason": _STOP_REASON_MAP[stop_reason]}], "usage": {...} si dispo}` (réutilise la table `_STOP_REASON_MAP` existante)
- events de structure (`message_start`, `content_block_start/stop`, `message_stop`) et `thinking_delta` : ignorés (texte seulement, best-effort)

### Garde `stream=True` sur le chemin `chat()` (correctif de cohérence)

Nouveau helper `reject_chat_stream(kwargs)` dans `_backends/__init__.py` (à côté de `resolve_model`), appelé en tête des 6 fonctions `complete`/`acomplete` des 3 backends. Lève `NotSupportedError("stream=True n'est pas supporté sur chat() ; utiliser stream()/astream().")` si `kwargs.get("stream")` est truthy. Cela remplace le garde local actuel d'Anthropic et **corrige une incohérence latente** : aujourd'hui `chat(messages, stream=True)` sur openai/litellm transmettrait `stream=True` au SDK et ferait échouer la conversion de réponse.

### Routage

`pick_backend()` retourne aujourd'hui `(complete, acomplete)`. Il passe à un **4-tuple** `(complete, acomplete, stream, astream)`. Nouveaux alias de types `StreamCallable = Callable[..., Iterator[dict[str, Any]]]` et `AStreamCallable = Callable[..., AsyncIterator[dict[str, Any]]]`. `Client`/`AsyncClient` stockent en plus `_stream_callable` / `_astream_callable`, résolus à la construction comme les deux existants.

### Erreurs

`stream`/`astream` sont des générateurs : ils lèvent **à l'itération**, pas à l'appel (sémantique Python normale, à documenter dans les docstrings). Toute erreur SDK — avant le premier chunk ou pendant le flux — est wrappée en `BackendError` (try/except autour de la boucle, cause préservée dans `__cause__`, conforme à D9). Politique `tools`/`role='tool'` identique à `chat()` : rejet via le codec Anthropic, pass-through pour openai/litellm.

---

## Options évaluées

### Option A (retenue) : méthodes dédiées `stream`/`astream` + chunks format OpenAI best-effort

Décrite ci-dessus.

**Avantages** :

- **Type de retour de `chat()` préservé** (`dict`), pas de polymorphisme `dict | Iterator` — propre en `mypy --strict`.
- **Cohérence avec la lingua franca** : les chunks sont des dicts OpenAI, comme la réponse de `chat()`, juste en deltas.
- **Effort proportionné** : pass-through pour 2/3 backends, codec localisé pour Anthropic uniquement (même frontière que la traduction existante).
- **Miroir sync/async respecté**, surface minimale (4 ajouts), additif et non-breaking.

**Inconvénients** :

- Deux chemins à maintenir (`chat` et `stream`) au lieu d'un seul paramètre. Mitigation : le miroir est déjà la norme du projet.
- Ergonomie : l'appelant navigue `chunk["choices"][0]["delta"].get("content")` (pattern OpenAI standard, connu).

### Option B : paramètre `stream=True` sur `chat()`/`achat()`

Calquer OpenAI : `chat(..., stream=True)` renvoie un itérateur.

**Inconvénients** : retour polymorphe `dict | Iterator` pénible en `mypy --strict` et pour l'appelant ; brouille le contrat clair de `chat()`. **Rejeté.**

### Option C : yield des deltas de texte (`str`)

`stream()` yield directement les morceaux de texte.

**Inconvénients** : très ergonomique pour l'affichage mais **incohérent** avec le dict de `chat()` (deux contrats différents dans la même lib), et perd `finish_reason`/`usage`/`role`. **Rejeté.**

### Option D : objet event unifié apicol (`dataclass StreamChunk`)

Introduire un type public `StreamChunk(text_delta, finish_reason, ...)`.

**Inconvénients** : nouveau type public à maintenir et documenter, alors que la lib privilégie les dicts et « fonctions tant que possible ». **Rejeté.**

---

## Décision

**Option A retenue**, et **D7 est amendée par une nouvelle décision D12** (ARCHITECTURE.md) : « Streaming via méthodes dédiées `stream`/`astream`, chunks au format OpenAI best-effort, codec à la frontière Anthropic. » D7 reste consignée comme trace historique mais est explicitement *superseded* par D12.

Raisons clés :

1. Préserve le typage strict et le contrat de `chat()`.
2. Réutilise la lingua franca OpenAI et la frontière de traduction déjà en place.
3. Additif, non-breaking, surface minimale — adapté à une mineure v0.3.0.
4. Corrige au passage le garde `stream=True` manquant sur openai/litellm.

---

## Plan d'implémentation

1. **`_backends/__init__.py`** : ajouter `reject_chat_stream(kwargs)` (lève `NotSupportedError` si `stream` truthy), à côté de `resolve_model`.
2. **`_backends/openai_compatible.py`** : ajouter `stream(messages, config, **kwargs)` et `astream(...)`. `reject_chat_stream` reste pour `complete`/`acomplete` ; `stream` force `stream=True` sur l'appel SDK et `yield chunk.model_dump()`. Erreurs SDK → `BackendError`.
3. **`_backends/litellm.py`** : idem, via `litellm.completion(stream=True)` / `acompletion`. Conversion par chunk en dict.
4. **`_backends/anthropic.py`** : ajouter `stream`/`astream` ; payload via `_openai_to_anthropic` existant, `client.messages.stream(...)`, codec events→chunks (helpers `_anthropic_event_to_openai_chunk`). Brancher `reject_chat_stream` dans `complete`/`acomplete` et **retirer** le garde `stream` local de `_openai_to_anthropic` (centralisé).
5. **`_route.py`** : `pick_backend` retourne `(complete, acomplete, stream, astream)` ; ajouter `StreamCallable`/`AStreamCallable`.
6. **`_client.py`** : `Client.stream()` (sync) et `AsyncClient.stream()` (async) ; stocker `_stream_callable`/`_astream_callable` ; factoriser la résolution avec l'existant.
7. **`__init__.py`** : globales `stream`/`astream` (via `_get_implicit_*_client`) ; ajouter à `__all__`.
8. **Tests** :
   - `tests/unit/test_*_backend.py` : SDK mocké yieldant des chunks fictifs → vérifier dicts OpenAI ; pour Anthropic, events mockés → vérifier le codec (deltas + chunk final + `finish_reason`). Sync **et** async.
   - garde `stream=True` sur `chat()` pour les 3 backends (`pytest.raises(NotSupportedError, match="stream")`).
   - `tests/unit/test_client.py` / `test_global_wrappers.py` : `stream`/`astream` présents, dispatch correct, miroir.
   - `tests/unit/test_route.py` : 4-tuple retourné par `pick_backend`.
   - intégration live (`@pytest.mark.integration`, skip par défaut) : un stream court réel par backend.
9. **Doc** : `SPEC.md` (tableau compat Streaming → ✅ + section `stream`/`astream`), `ARCHITECTURE.md` (**D12**, amende D7), `README.md` (exemples + statut), `CHANGELOG.md` (v0.3.0), `BACKLOG.md` (streaming → implémenté ; « litellm optionnel » → PRD-006 envisagé), `CLAUDE.md` (roadmap : streaming livré).
10. **Version** : bump `pyproject.toml` → **0.3.0**.

---

## Métriques de succès

- **Miroir complet** : `stream` et `astream` existent sur `Client`, `AsyncClient` et en globales ; présents dans `__all__`. Critère : test de surface passe.
- **Streaming des 3 backends** : pour chaque backend, un test unitaire (SDK mocké) prouve que `stream`/`astream` yield des dicts format OpenAI avec `delta.content` puis un `finish_reason` final. Critère : tests passent, sync + async.
- **Codec Anthropic** : test dédié mappant une séquence d'events Anthropic (text_delta ×N + message_delta) vers les chunks attendus. Critère : contenu concaténé == texte attendu, `finish_reason` correct.
- **Garde `stream=True` homogène** : `chat(messages, stream=True)` lève `NotSupportedError` sur les 3 backends. Critère : 3 tests passent.
- **Non-régression** : toute la suite v0.2 reste verte (161 tests). Critère : 0 régression.
- **Couverture** : ≥ 95 % maintenue (seuil `pyproject.toml`), couverture du codec Anthropic incluse.
- **Qualité** : `ruff check`, `ruff format`, `mypy --strict` clean.

---

## Points reportés / décisions différées

- **`claude_cli` streaming** (`--output-format stream-json`) — hors périmètre, dev-only, parsing JSON-lines propriétaire ; éventuel PRD ultérieur.
- **Normalisation fine de l'`usage`** en fin de stream (activer `include_usage` côté OpenAI, agréger l'usage Anthropic, schéma homogène garanti) — best-effort en v0.3 ; à reconsidérer si demande utilisateur.
- **Exposition des `thinking`/reasoning deltas** pendant le stream — ignorés en v0.3 (texte seulement) ; lié au support `tools`/thinking, hors scope.
- **Streaming des `tools`** — non supporté (cohérent avec l'absence de tools en v0.3, cf. roadmap tool calls).
- **Nom des callables internes de backend** (`stream`/`astream` vs `stream_complete`/…) — proposition `stream`/`astream` pour aligner sur `complete`/`acomplete`. À finaliser avant code.

---

## Changelog

| Date | Auteur | Changement |
|------|--------|------------|
| 2026-06-19 | Sandjab + Claude | Création du PRD (design validé en brainstorming) |
