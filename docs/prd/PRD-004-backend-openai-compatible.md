# PRD-004 : Backend `openai-compatible` à côté de LiteLLM

**Statut** : Implémenté (v0.2.0)
**Date** : 2026-05-16
**Auteur** : Sandjab
**Source** : conversation de design — observation que pour le périmètre dominant du README (OpenAI, Mistral, Ollama, vLLM, LM Studio, OpenRouter), LiteLLM est surdimensionné parce que ces backends sont **tous OpenAI-compatibles nativement**.

---

## Vision

**Le quoi : quel pattern ce PRD propose-t-il ?**

Ajouter une troisième valeur acceptée à `APICOL_TYPE` (et à `Client(backend=...)`) : **`openai-compatible`**. Ce backend utilise le SDK officiel `openai` pour parler à n'importe quel endpoint qui expose `/v1/chat/completions` au format OpenAI — c'est-à-dire `api.openai.com`, Ollama, vLLM, LM Studio, OpenRouter, Mistral La Plateforme, DeepSeek, Groq, Together AI, Fireworks, Anyscale, et le proxy LiteLLM lui-même. Le backend `litellm` est **conservé** pour ce qu'il fait vraiment bien : les providers qui ne parlent pas OpenAI nativement (Gemini natif, Bedrock, Vertex AI, Azure OpenAI, Cohere).

**Le pourquoi : pourquoi ce pattern fonctionne-t-il ?**

Le mécanisme est celui de l'**alignement de la dépendance sur la valeur ajoutée réelle**. Aujourd'hui, un utilisateur qui veut juste parler à Ollama doit installer LiteLLM et toute sa fermeture transitive (~200 paquets, surface qui change vite, historique de breaking changes), alors que le SDK OpenAI seul suffit techniquement. LiteLLM apporte de la valeur uniquement quand on parle à un provider non-OpenAI-compatible (traduction de format, mapping d'env vars exotiques). Donner à l'utilisateur un chemin direct pour les 6/7 providers OpenAI-compatibles du README rend la lib plus légère sans rien lui retirer.

C'est la même logique que la D2 de `ARCHITECTURE.md` (« on ne réinvente pas ce que LiteLLM fait déjà ») appliquée à elle-même : **on ne charge pas LiteLLM pour ce que OpenAI SDK fait déjà**.

**Le comment** : renvoyé au Plan d'implémentation.

## Exemple bout-en-bout (projeté)

```python
# === Cas 1 — OpenAI direct via openai-compatible (au lieu de LiteLLM) ===
import apicol

openai = apicol.Client(
    backend="openai-compatible",
    api_key="sk-...",
    model="gpt-5",
    base_url="https://api.openai.com/v1",  # optionnel, c'est le défaut
)
response = openai.chat(messages=[{"role": "user", "content": "Bonjour"}])

# === Cas 2 — Ollama local sans LiteLLM ===
ollama = apicol.Client(
    backend="openai-compatible",
    model="qwen3:32b",
    base_url="http://localhost:11434/v1",
    api_key="ollama",  # factice, ignoré par Ollama
)
response = ollama.chat(messages=[{"role": "user", "content": "Bonjour"}])

# === Cas 3 — OpenRouter avec headers de tracking ===
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

# === Cas 4 — Cohabitation des trois backends dans le même process ===
claude = apicol.Client(backend="anthropic",          api_key="sk-ant-...", model="claude-opus-4-7")
gpt    = apicol.Client(backend="openai-compatible",  api_key="sk-...",     model="gpt-5")
gemini = apicol.Client(backend="litellm",            api_key="...",        model="gemini/gemini-2.5-pro")
# → anthropic SDK + openai SDK + litellm SDK, trois chemins distincts, zéro recoupement

# === Cas 5 — Fonctions globales, env vars ===
# export APICOL_TYPE=openai-compatible
# export APICOL_KEY=sk-or-...
# export APICOL_MODEL=anthropic/claude-haiku-4-5
# export APICOL_URL=https://openrouter.ai/api/v1
response = apicol.chat(messages=[{"role": "user", "content": "Bonjour"}])
```

---

## Contexte

La v0.1 d'apicol accepte deux valeurs pour `APICOL_TYPE` côté niveau 1 : `anthropic` (SDK natif) et `litellm` (délégation à `litellm.completion`). La SPEC justifie ce choix par le périmètre couvert par LiteLLM : « OpenAI, Gemini, Mistral, Ollama, vLLM, LM Studio, OpenRouter ».

Mais sur cette liste de 7 providers, **6 exposent nativement `/v1/chat/completions` au format OpenAI** :

| Provider | Endpoint OpenAI-compatible natif | Doc |
|---|---|---|
| OpenAI | ✅ (`api.openai.com/v1`) | trivial |
| Mistral | ✅ (`api.mistral.ai/v1`) | La Plateforme expose `/v1/chat/completions` |
| Ollama | ✅ (`localhost:11434/v1`) | depuis Ollama 0.1.24+ |
| vLLM | ✅ (`localhost:8000/v1`) | objectif déclaré du serveur vLLM |
| LM Studio | ✅ (`localhost:1234/v1`) | objectif déclaré du serveur LM Studio |
| OpenRouter | ✅ (`openrouter.ai/api/v1`) | trivial |
| Gemini | ⚠️ partiel (`generativelanguage.googleapis.com/v1beta/openai`) | compat layer limitée |

Pour 6/7 cas, LiteLLM n'apporte techniquement rien que `openai.OpenAI(base_url=..., api_key=...)` ne ferait. Il apporte par contre :

- Une dépendance transitive lourde (~200 paquets) à installer, parser, sécuriser.
- Un historique de breaking changes documenté qui force des contraintes de version étroites.
- Une traduction interne qui peut casser silencieusement quand un provider évolue.

LiteLLM continue de gagner sa place pour ce qui **ne se réduit pas** au format OpenAI HTTP :

- Gemini natif (au-delà de la compat partielle)
- Bedrock (auth SigV4, format Converse)
- Vertex AI (auth IAM Google Cloud)
- Azure OpenAI (deployment names, API versions)
- Cohere, Replicate, HuggingFace Inference
- Mapping de features avancées cross-provider (reasoning_effort traduit en `thinking` Anthropic / `thinking_budget` Gemini / `reasoning_effort` natif OpenAI)

---

## Problème

**Comment ajouter un chemin direct OpenAI-SDK pour les providers OpenAI-compatibles, sans casser la rétrocompat v0.1, sans dégrader la couverture des providers exotiques, et sans introduire d'ambiguïté pour l'utilisateur qui se demande « lequel choisir » ?**

Trois sous-questions :

1. **Cohabitation** : `litellm` doit rester disponible (Gemini, Bedrock, Vertex, Azure, Cohere en dépendent). Comment exprimer dans la SPEC quand utiliser quoi sans labyrinthe.
2. **Mapping `APICOL_KEY`** : pour `litellm`, apicol injecte la clé dans la bonne env var par provider (la « seule magie acceptée », D6 d'ARCHITECTURE). Pour `openai-compatible`, il n'y a pas de magie possible — la clé est passée directement à `OpenAI(api_key=...)`. Comment documenter cette asymétrie sans rendre le user model confus.
3. **Extra headers** : OpenRouter exige `HTTP-Referer` / `X-Title`. Aujourd'hui, ces headers passent par `extra_body` (passthrough opaque, vérification à l'exécution). Avec `openai-compatible`, on a la possibilité de les exposer typés au niveau du `Client` (`extra_headers={}`), comme concordance le fait.

---

## Solution

**Ajouter `openai-compatible` comme troisième backend, avec son propre module `_backends/openai_compatible.py`, sans toucher au backend `litellm` existant.** Documenter explicitement la règle de décision dans la SPEC et le README.

### Surface publique cible

| Symbole | Avant (v0.1) | Après (v0.2) |
|---|---|---|
| Valeurs `APICOL_TYPE` | `anthropic`, `litellm` | `anthropic`, `openai-compatible`, `litellm` |
| Valeurs `Client(backend=...)` | `"anthropic"`, `"litellm"` | `"anthropic"`, `"openai-compatible"`, `"litellm"` |
| `Client(..., extra_headers={...})` | n/a | nouveau kwarg (utile pour OpenRouter, gateway custom) |

Aucune autre signature ne change. Aucun symbole n'est renommé. Aucune méthode n'est retirée.

### Règle de décision (à mettre dans la SPEC et le README)

| Tu veux parler à… | Utilise |
|---|---|
| OpenAI, Mistral, Ollama, vLLM, LM Studio, OpenRouter, Groq, DeepSeek, Together, Fireworks, Anyscale, n'importe quel proxy OpenAI-compatible | `backend="openai-compatible"` |
| Gemini natif (Google AI Studio / Vertex), Bedrock, Azure OpenAI, Cohere, Replicate, HuggingFace Inference | `backend="litellm"` |
| API Anthropic native (caching fin, citations, PDF, batch) | `backend="anthropic"` |
| `claude -p` localement (dev only) | `claude_cli_chat()` |

### Mapping `APICOL_KEY` pour `openai-compatible`

Pas de magie : la clé est passée telle quelle à `openai.OpenAI(api_key=...)`. Pour les backends locaux qui n'ont pas besoin de clé (Ollama, vLLM, LM Studio), accepter une valeur factice (`"ollama"`, `"local"`, n'importe quoi non-vide) — c'est ce que le SDK OpenAI tolère déjà. Documenter cette asymétrie avec `litellm` explicitement dans la SPEC (1 paragraphe).

### `extra_headers` : nouveau kwarg de `Client`

Aujourd'hui, l'utilisateur OpenRouter doit faire :

```python
apicol.chat(messages=..., extra_body={"extra_headers": {"HTTP-Referer": "..."}})
```

C'est verbeux et opaque. Avec `openai-compatible`, on expose :

```python
client = apicol.Client(
    backend="openai-compatible",
    api_key="sk-or-...",
    model="anthropic/claude-haiku-4-5",
    base_url="https://openrouter.ai/api/v1",
    extra_headers={"HTTP-Referer": "https://...", "X-Title": "apicol"},
)
```

Les headers sont attachés à la connexion (`openai.OpenAI(default_headers=...)`), pas répétés par appel.

Décision : `extra_headers` est ajouté à `Client.__init__` et `AsyncClient.__init__`. Pour `backend="anthropic"` et `backend="litellm"`, le kwarg est accepté et passé aux SDKs sous-jacents si possible, ou ignoré avec un `warnings.warn` si non supporté. Non-breaking parce que c'est un kwarg keyword-only avec default `None`.

### Pas d'`openai_native()` dans ce PRD

Le SDK OpenAI est **trivialement instanciable par l'utilisateur lui-même** (`openai.OpenAI(api_key=..., base_url=...)`). Contrairement au cas Anthropic (compat layer OpenAI limitée → besoin de l'échappatoire native), il n'y a pas de feature OpenAI qui soit accessible *uniquement* via le SDK natif et non via apicol. Si une demande utilisateur émerge plus tard, on ajoutera `Client.openai_native() -> openai.OpenAI` dans un PRD ultérieur. Conservatisme volontaire (D7 — surface minimale stable).

### Statut de la dépendance `openai`

Aujourd'hui, `openai` arrive **transitivement** via `litellm`. Dans ce PRD, on en fait une **dépendance directe** dans `pyproject.toml`. C'est une formalisation, pas un changement de fait : `pip install apicol` installait déjà `openai`.

Décision **différée** au PRD-005 (si besoin) : rendre `litellm` optionnel via extras (`pip install apicol[litellm]`). C'est un changement breaking-soft (un user qui faisait `backend="litellm"` sans installer l'extra recevrait une `ImportError` contextuelle au dispatch). On ne le fait **pas** dans ce PRD pour rester additif et non-breaking.

---

## Options évaluées

### Option A (retenue) : Ajouter `openai-compatible` à côté de `litellm`

Décrite ci-dessus.

**Avantages** :

- **Non-breaking** : aucun utilisateur v0.1 n'est impacté. Les `backend="litellm"` existants continuent de fonctionner à l'identique.
- **Chemin léger pour le cas dominant** : 6/7 providers du README couvrables sans charger LiteLLM (techniquement, LiteLLM reste installé en v0.2 mais voir PRD-005 différé).
- **Cohérent avec concordance** : Sandjab maintient déjà ce pattern dans un autre repo. Aucun coût cognitif additionnel pour lui ou pour quelqu'un qui passe d'un projet à l'autre.
- **Améliore l'ergonomie OpenRouter** : `extra_headers` typé au niveau du Client supprime le hack `extra_body={"extra_headers": ...}`.
- **Préserve le périmètre LiteLLM** pour ce qu'il fait vraiment bien.

**Inconvénients** :

- **Trois backends à documenter au lieu de deux** : règle de décision à formuler clairement. Risque de paralysie de l'utilisateur (« lequel je choisis ? »). Mitigation : tableau de décision unique dans la SPEC et le README, exemples bout-en-bout.
- **Asymétrie sur le mapping `APICOL_KEY`** : `litellm` injecte par provider, `openai-compatible` non. À documenter en 1 paragraphe.
- **Doublon technique sur OpenAI** : avec `backend="openai-compatible"` ET `backend="litellm"` `+ model="openai/..."`, on peut atteindre OpenAI par deux chemins. Pas un bug, mais à clarifier (réponse : on recommande `openai-compatible` par défaut, `litellm` reste valide).

### Option B : Remplacer `litellm` par `openai-compatible`

Supprimer le backend `litellm`, ne garder que `anthropic` + `openai-compatible`. Pour Gemini, demander à l'utilisateur d'utiliser le compat layer OpenAI partiel de Google.

**Avantages** :

- Une seule abstraction OpenAI-style. Dépendance maximalement allégée.

**Inconvénients** :

- **Régression fonctionnelle** : Bedrock, Vertex AI natif, Azure OpenAI deployments, Cohere ne marchent plus.
- **Breaking change** : tout user v0.1 qui passait par `litellm` doit migrer.
- **Mauvais arbitrage** : LiteLLM a une vraie valeur pour les providers exotiques. La supprimer pour économiser des transitives, c'est jeter le bébé.

### Option C : Statu quo — garder uniquement `litellm` pour les cas OpenAI-compatibles

Ne rien faire. Continuer d'utiliser LiteLLM même pour Ollama / vLLM / OpenRouter.

**Avantages** :

- Zéro changement, zéro risque.
- Surface minimale (2 backends).

**Inconvénients** :

- Continue de payer le coût de LiteLLM pour les cas où il n'apporte rien.
- Continue de répercuter sur les utilisateurs les breaking changes upstream de LiteLLM.
- Ne corrige pas l'ergonomie OpenRouter (`extra_headers` coincés dans `extra_body`).

### Option D : Hiérarchie de fallback automatique

Au dispatch, essayer `openai-compatible` d'abord ; si l'endpoint ne répond pas en OpenAI-compatible, tomber sur LiteLLM.

**Avantages** :

- Aucun choix à faire pour l'utilisateur.

**Inconvénients** :

- **Viole D6** (« zéro magie sur les env vars »). L'utilisateur ne sait plus quel chemin a été pris, ni comment forcer l'un ou l'autre.
- Surcoût latence à chaque premier appel (timeout sur le mauvais chemin).
- Échec de diagnostic : si une erreur arrive, qui est responsable ? OpenAI SDK ? LiteLLM ? L'endpoint ?
- Contraire à la philosophie générale d'apicol : exposer des frontières nommées, pas en cacher.

---

## Décision

**Option A retenue.**

Raisons clés :

1. **Non-breaking, additif, surgical** — exactement le type de changement qu'autorise une v0.2 mineure.
2. **Alignement dépendance / valeur ajoutée** : LiteLLM ne reste que pour ce qu'il fait vraiment bien.
3. **Cohérence avec un repo voisin** (concordance) où le pattern `openai-compatible` est déjà éprouvé.
4. **Ergonomie OpenRouter améliorée** sans toucher au reste.

---

## Plan d'implémentation

1. **Ajouter `openai` comme dépendance directe** dans `pyproject.toml` (aujourd'hui transitive via `litellm`). Pin minimal à la version courante stable.
2. **Créer `src/apicol/_backends/openai_compatible.py`** :
   - `complete(messages, *, model, api_key, base_url, extra_headers, **kwargs) -> dict`
   - `acomplete(messages, *, model, api_key, base_url, extra_headers, **kwargs) -> dict`
   - Utilise `import openai` puis `openai.OpenAI(...)` / `openai.AsyncOpenAI(...)` — **jamais** `from openai import OpenAI` (cf. CLAUDE.md, contrainte de mockabilité des fixtures).
   - `default_headers` du SDK OpenAI reçoit `extra_headers`.
   - `reasoning_effort` passé tel quel (le SDK OpenAI le supporte nativement pour les modèles o-series).
   - Pas de mapping conditionnel : si le modèle ne supporte pas un paramètre, le SDK renvoie une erreur HTTP → bubble-up en `BackendError`.
3. **Étendre `_config.py`** :
   - `VALID_BACKENDS = ("anthropic", "openai-compatible", "litellm")` (ajout de la valeur).
   - `claude_cli` toujours rejeté avec le message existant pointant vers `claude_cli_chat()`.
   - Ajouter `extra_headers: dict[str, str] | None` au dataclass `Config`.
4. **Étendre `_route.py`** : nouveau `case "openai-compatible":` dans le `match`, qui retourne `_backends.openai_compatible.complete` (ou `acomplete` selon contexte sync/async).
5. **Étendre `_client.py`** :
   - Ajouter `extra_headers: dict[str, str] | None = None` au `Client.__init__` et `AsyncClient.__init__`.
   - Propager au backend choisi. Pour `anthropic`, passer aux `default_headers` du SDK ; pour `litellm`, passer en kwarg si supporté, sinon `warnings.warn` à la construction (pas par appel).
6. **Mise à jour `__init__.py`** : pas de changement de surface publique. Juste s'assurer que `Client(backend="openai-compatible", ...)` fonctionne et que `chat()` / `achat()` dispatchent correctement quand `APICOL_TYPE=openai-compatible`.
7. **Tests** :
   - `tests/test_openai_compatible_backend.py` — mock de `openai.OpenAI` / `openai.AsyncOpenAI`, vérifier les paramètres passés, le `default_headers`, le bubble-up d'erreurs.
   - Étendre `tests/test_config.py` : nouvelle valeur acceptée, `extra_headers` validé.
   - Étendre `tests/test_route.py` : dispatch correct pour `openai-compatible`.
   - Étendre `tests/test_client.py` : `Client(backend="openai-compatible")` construit, `extra_headers` propagé.
   - Étendre `tests/test_v01_backcompat.py` : vérifier qu'aucun comportement v0.1 ne change.
   - Test d'intégration optionnel (`@pytest.mark.integration`) : `Client(backend="openai-compatible", base_url="http://localhost:11434/v1")` vers un Ollama local si dispo.
8. **Mise à jour SPEC.md** :
   - Ajouter `openai-compatible` au tableau des valeurs de `APICOL_TYPE`.
   - Ajouter le tableau de règle de décision (cf. Solution).
   - Documenter le mapping `APICOL_KEY` pour `openai-compatible` (pas de magie).
   - Documenter `extra_headers` au niveau du Client.
   - Étendre le tableau « Compatibilité backends » avec une colonne `openai-compatible`.
9. **Mise à jour ARCHITECTURE.md** : ajouter une décision **D11 — Backend `openai-compatible` distinct de LiteLLM** justifiant le tradeoff.
10. **Mise à jour README.md** :
    - Section « Pourquoi cette lib » : ajouter le 3ᵉ apport (« un chemin direct OpenAI SDK pour les endpoints OpenAI-compatibles, sans charger LiteLLM »).
    - Section « Variables d'environnement » : mettre à jour les valeurs acceptées.
    - Section « Usage » : nouveau scénario `openai-compatible` (Ollama, OpenRouter).
    - Tableau de règle de décision (synthèse).
11. **Mise à jour CHANGELOG.md** : entrée v0.2.0 avec `Added` (backend `openai-compatible`, kwarg `extra_headers`).
12. **Mise à jour BACKLOG.md** : déplacer PRD-004 de « En cours » à « Validés (implémentés) » à la release.

---

## Métriques de succès

- **Cohabitation des trois backends** : test d'intégration `test_three_backends_coexist.py` qui crée trois `Client` (`anthropic`, `openai-compatible` vers OpenRouter, `litellm` vers Gemini) dans le même process et vérifie que les trois retournent une réponse non vide en parallèle (`asyncio.gather` pour la version async). Critère : test passe.
- **Rétrocompat stricte v0.1** : `tests/test_v01_backcompat.py` continue de passer sans modification après l'ajout du nouveau backend. Critère : 0 régression.
- **Couverture du nouveau backend** : ≥ 90 % sur `src/apicol/_backends/openai_compatible.py`. Critère : seuil dans `pyproject.toml`.
- **Bypass de LiteLLM pour Ollama** : test d'intégration `test_ollama_via_openai_compatible.py` qui appelle un Ollama local via `backend="openai-compatible"` et vérifie que `litellm` n'apparaît **pas** dans la stack trace (via `sys.settrace` ou monkeypatch d'`import litellm`). Critère : test passe, prouve qu'on ne traverse plus LiteLLM pour ce cas.
- **`extra_headers` propagé** : test unitaire qui crée un `Client(backend="openai-compatible", extra_headers={"X-Foo": "bar"})`, appelle `.chat(...)` mocké, et vérifie que le mock `openai.OpenAI` a bien reçu `default_headers={"X-Foo": "bar"}`. Critère : test passe.
- **`extra_headers` warning sur backend qui ne supporte pas** : test unitaire qui crée un `Client(backend="litellm", extra_headers={"X-Foo": "bar"})` (si LiteLLM ne supporte pas le propagation propre) et vérifie qu'un `UserWarning` est émis à la construction. Critère : warning capté.
- **Doc cohérente** : grep automatique sur `README.md` + `SPEC.md` + `ARCHITECTURE.md` pour s'assurer que les trois mentionnent les trois backends de façon alignée. Critère : pas d'incohérence entre les listes de valeurs `APICOL_TYPE`.

---

## Points reportés / décisions différées

Pour ne pas surcharger ce PRD :

- **Rendre `litellm` optionnel via extras** (`pip install apicol[litellm]`) — différé à un PRD-005 dédié, parce que c'est un changement breaking-soft qui mérite sa propre discussion (taille de wheel, migration, message d'erreur au dispatch).
- **Ajouter `Client.openai_native() -> openai.OpenAI`** — différé. L'utilisateur peut trivialement faire `openai.OpenAI(api_key=..., base_url=...)` lui-même ; pas de feature OpenAI qui soit hors-portée d'apicol au niveau 1.
- **Nom exact du backend** (`openai-compatible` vs `openai_compat` vs `openai_compatible`) — proposition `openai-compatible` (kebab-case, explicite, aligné avec concordance). À finaliser avant code.
- **Mapping `extra_headers` côté `litellm`** — selon ce que `litellm.completion` accepte aujourd'hui. Si non propagable proprement, on émet un `warnings.warn` plutôt qu'une erreur, pour ne pas casser l'existant.

---

## Changelog

| Date | Auteur | Changement |
|------|--------|------------|
| 2026-05-16 | Sandjab + Claude | Création du PRD |
| 2026-05-16 | Sandjab + Claude | Implémentation v0.2.0 : backend `openai-compatible`, `extra_headers` sur `Client`/`AsyncClient`, tests (13 unitaires + extensions), doc SPEC/ARCHITECTURE/README/CHANGELOG. 161 tests passent. |
