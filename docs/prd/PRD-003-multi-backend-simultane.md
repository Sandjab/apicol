# PRD-003 : Multi-backend simultané via objet `Client`

**Statut** : Brouillon
**Date** : 2026-05-14
**Auteur** : JP
**Source** : conversation de design — besoin exprimé d'avoir plusieurs backends actifs dans le même process (bench, fallback applicatif, comparaison)

---

## Vision

**Le quoi : quel pattern ce PRD propose-t-il ?**

Introduire un objet `Client` configurable (`apicol.Client(backend=..., api_key=..., model=...)`) qui encapsule la configuration d'un backend précis. Les fonctions globales `chat()` et `achat()` introduites en v0.1 sont **redéfinies** comme des wrappers de commodité qui utilisent un client implicite construit à la demande depuis les variables d'environnement. Le pendant async est `AsyncClient` (en miroir du pattern `anthropic.Anthropic` / `anthropic.AsyncAnthropic`).

**Le pourquoi : pourquoi ce pattern fonctionne-t-il ?**

Le mécanisme est celui de la **réification de la configuration**. Tant que la configuration est *globale et implicite* (via env vars), un seul backend peut exister à un instant donné dans le process. Réifier la config en objet — un `Client` est une config + des méthodes d'appel — permet d'en créer plusieurs simultanément, chacun avec son propre backend, ses propres clés, son propre modèle. C'est le pattern standard de l'écosystème : `OpenAI()`, `Anthropic()`, `boto3.client(...)`, `requests.Session()`. L'utilisateur le connaît déjà.

Garder les fonctions globales comme wrappers préserve l'ergonomie minimale pour le cas dominant (mono-backend par run) tout en ouvrant le cas multi-backend sans changer la nature de la lib.

**Le comment** : renvoyé au Plan d'implémentation.

## Exemple bout-en-bout (projeté)

```python
# === Cas 1 — Mono-backend, ergonomie v0.1 préservée ===
import apicol
# Les env vars APICOL_TYPE, APICOL_KEY, APICOL_MODEL sont définies dans l'environnement
response = apicol.chat(messages=[{"role": "user", "content": "Bonjour"}])
# → marche comme avant, aucune migration nécessaire

# === Cas 2 — Bench multi-backend dans le même process ===
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

prompt = [{"role": "user", "content": "Explique la relativité"}]
results = {
    "claude": claude.chat(prompt),
    "gpt":    gpt.chat(prompt),
    "qwen":   qwen_local.chat(prompt),
}
# → trois appels simultanés, trois backends différents, dans le même script

# === Cas 3 — Async avec plusieurs clients ===
import asyncio, apicol

claude = apicol.AsyncClient(backend="anthropic", api_key="...", model="claude-opus-4-7")
gpt    = apicol.AsyncClient(backend="litellm",   api_key="...", model="openai/gpt-5")

async def bench():
    return await asyncio.gather(
        claude.chat(prompt),
        gpt.chat(prompt),
    )

claude_resp, gpt_resp = asyncio.run(bench())

# === Cas 4 — Accès au SDK Anthropic natif depuis un Client ===
claude = apicol.Client(backend="anthropic", api_key="...", model="claude-opus-4-7")
native = claude.anthropic_native()  # → anthropic.Anthropic préconfiguré
# Toutes les features avancées Anthropic accessibles ici
```

---

## Contexte

La v0.1 d'apicol, telle que documentée dans PRD-001 et SPEC.md, définit une surface publique composée de **fonctions globales** (`chat`, `achat`, `anthropic_client`, `anthropic_async_client`, `claude_cli_chat`, `claude_cli_achat`). Toutes ces fonctions lisent leur configuration à partir des variables d'environnement `APICOL_*`.

Ce design suffit pour le cas dominant : un script ou une application qui parle à **un** LLM par run, choisi via les env vars. Bascule de backend = changement d'env var + relance.

**Cas exprimé par l'utilisateur qui sort de ce périmètre** : faire tourner plusieurs backends *simultanément* dans le même process, pour :

- bench / comparaison côte à côte de la même réponse
- routage applicatif (l'app décide elle-même quel modèle utiliser selon la tâche)
- fallback applicatif (si Anthropic timeout, retry sur OpenAI)
- consumer le service depuis Athanor ou un autre projet qui peut vouloir interroger plusieurs sources

La config globale par env vars rend ces cas impossibles ou hackish (modifier `os.environ` à chaque appel = pas thread-safe, pas async-safe, et de toute façon les fonctions globales lisent les env vars à chaque appel donc la course est ouverte).

---

## Problème

**Comment permettre plusieurs configurations de backend simultanées dans le même process, sans casser l'ergonomie minimale de la v0.1 ?**

Le défi a deux faces :

1. **Rétrocompatibilité** : le code applicatif existant qui appelle `apicol.chat(...)` doit continuer de fonctionner sans modification.
2. **Multi-instance** : il doit être possible d'avoir N configurations actives en parallèle, chacune référencée par un objet distinct, sans état global partagé entre elles.

---

## Solution

**Réifier la configuration en objet `Client`** (et son pendant async `AsyncClient`), et redéfinir les fonctions globales comme des wrappers de commodité par-dessus un client implicite construit depuis l'environnement.

### Surface publique cible

| Symbole | Type | Construction |
|---------|------|--------------|
| `Client` | classe | `Client(backend, api_key=None, model=None, base_url=None)` |
| `AsyncClient` | classe | `AsyncClient(backend, api_key=None, model=None, base_url=None)` |
| `Client.chat(messages, **kwargs)` | méthode | appel synchrone |
| `AsyncClient.chat(messages, **kwargs)` | coroutine | appel asynchrone |
| `Client.anthropic_native() -> anthropic.Anthropic` | méthode | échappatoire native (uniquement si backend=anthropic) |
| `AsyncClient.anthropic_native() -> anthropic.AsyncAnthropic` | méthode | idem async |
| `chat(messages, **kwargs)` | fonction | wrapper qui construit un `Client` implicite depuis l'env |
| `achat(messages, **kwargs)` | fonction | idem async |

### Cycle de vie d'un Client

Un `Client` est immutable après construction. Pour changer de configuration, on crée un nouveau client. Cette rigidité simplifie le raisonnement : un Client est sa config, point.

### Cas `claude_cli_chat()` / `claude_cli_achat()`

Ces fonctions restent **séparées** (cf. PRD-002) et **ne sont pas exposées comme méthodes du Client**. La frontière TOS reste lexicale : aucun chemin `Client.X()` ne mène à `claude -p`. C'est intentionnel.

### Stratégie de partage de ressources HTTP

Chaque `Client` instancie son propre client SDK sous-jacent (`anthropic.Anthropic` ou pas de client persistant pour LiteLLM qui gère ses sessions en interne). Les connexions HTTP sont donc isolées par `Client`. C'est conservateur mais évite toute fuite de header / clé entre instances. Pour les usages haute volumétrie qui veulent du pool partagé, on ajustera dans un PRD ultérieur.

---

## Options évaluées

### Option A (retenue) : Objet `Client` + fonctions globales comme wrappers

Décrite ci-dessus.

**Avantages** :

- Pattern standard de l'écosystème (`openai.OpenAI`, `anthropic.Anthropic`, `boto3.client`). L'utilisateur n'a rien à apprendre de neuf.
- Rétrocompat parfaite : `apicol.chat(...)` continue de marcher. Le code v0.1 ne nécessite aucune migration.
- Permet le multi-backend trivialement : un Client par config.
- L'immutabilité du Client supprime toute une classe de bugs (config qui change entre deux appels).
- L'échappatoire native (`anthropic_native()`) devient une méthode du Client, ce qui est plus cohérent que la fonction globale `anthropic_client()` actuelle. Cette dernière peut être conservée comme alias rétrocompatible.

**Inconvénients** :

- Légère duplication d'API : tout ce qui est dans `Client` est aussi accessible via les fonctions globales. À documenter clairement (« utilisez `Client` si vous avez plusieurs configs ; sinon les fonctions globales suffisent »).
- Le wrapping des fonctions globales doit gérer le cache lazy d'un client implicite (sinon chaque appel reconstruit un client → coût pas nul). Décision : cache lazy en module-state, invalidé si les env vars changent (détection par hash de la config). Test unitaire dédié pour ne pas régresser.

### Option B : Context manager `apicol.config(...)`

```python
with apicol.config(backend="anthropic", api_key="..."):
    response = apicol.chat(...)
```

**Avantages** :

- Surface plus mince : pas de classe explicite.
- Possibilité d'imbriquer / scoper proprement.

**Inconvénients** :

- État implicite (contextvar) à chaque appel — coûteux mentalement à raisonner, surtout en async où les contextvar sont héritées par les tâches enfants mais pas par les autres tâches.
- Pas le pattern standard de l'écosystème — l'utilisateur doit apprendre la convention.
- Le multi-backend simultané reste tordu : pour deux backends actifs en même temps il faut imbriquer ou alterner.
- Difficile de passer un « client configuré » à une fonction qui en a besoin (alors qu'avec l'option A on passe juste l'objet).

### Option C : Module-state mutable via `apicol.configure(...)`

```python
apicol.configure(backend="anthropic", api_key="...")
apicol.chat(...)
apicol.configure(backend="litellm", api_key="...")
apicol.chat(...)
```

**Avantages** :

- Encore plus minimal en surface.

**Inconvénients** :

- Pas thread-safe par défaut. Sérieux problème pour les apps web / async.
- Pas multi-backend simultané — c'est exactement ce qu'on cherche à éviter.
- Encourage l'usage incorrect (changer la config au milieu d'un script).

### Option D : Tout passer en kwargs aux fonctions globales

```python
apicol.chat(messages=..., backend="anthropic", api_key="...", model="...")
```

**Avantages** :

- Pas d'état du tout, pas de classe.
- Trivialement thread-safe et async-safe.

**Inconvénients** :

- Verbeux à l'usage. L'utilisateur répète la config à chaque appel.
- Pas d'objet à passer à une fonction qui consomme un « client ». Athanor par exemple voudra typiquement injecter *un* client préconfiguré dans ses sous-modules ; avec D, il devra passer un dict ou un partial.
- Pas de pendant pour `anthropic_native()` — on ne peut pas retourner un SDK natif depuis une fonction d'appel.

---

## Décision

**Option A retenue.**

Raisons clés :

1. **Standard de l'écosystème** : aucun coût d'apprentissage.
2. **Rétrocompat totale** avec la surface v0.1. Aucune migration nécessaire pour les premiers utilisateurs.
3. **Multi-backend simultané natif** sans état global partagé.
4. **L'échappatoire native devient une méthode du Client** — gain de cohérence par rapport à la fonction globale `anthropic_client()` actuelle. On gardera cette dernière comme alias rétrocompatible déprécié à terme.

---

## Plan d'implémentation

1. **Refactor `_config.py`** : extraire la lecture d'env vars dans une fonction `load_from_env() -> Config`. Le `Config` devient un dataclass immutable avec champs `backend`, `api_key`, `model`, `base_url`.
2. **Créer `_client.py`** : définir `Client` et `AsyncClient`. Chacun a un attribut `config: Config` et un attribut `_route` qui pointe vers la fonction backend (`_backends.anthropic.complete` ou `_backends.litellm.complete`). La méthode `chat()` appelle directement le bon backend sans repasser par `_route.py`.
3. **Refactor `_route.py`** : devient une simple fonction `pick_backend(config: Config) -> Callable` utilisée par les fonctions globales et par le constructeur du Client. La logique de rejet de `backend="claude_cli"` reste ici.
4. **Réécrire `chat()` / `achat()` dans `__init__.py`** : maintenant des wrappers qui appellent un client implicite. Cache lazy en module-state, invalidé par hash de la config courante. Tests pour le cache.
5. **Méthode `Client.anthropic_native() -> anthropic.Anthropic`** : disponible uniquement si `config.backend == "anthropic"`, sinon `BackendUnavailableError`.
6. **Garder `apicol.anthropic_client()` et `apicol.anthropic_async_client()`** comme alias rétrocompatibles qui appellent `Client(backend="anthropic", ...).anthropic_native()` en interne. Mentionner dans la doc qu'on préfère la méthode du Client à terme.
7. **Tests** : `test_client.py` couvrant : construction valide / invalide, multi-instance dans le même process, immutabilité, échappatoire native, rétrocompat des fonctions globales, cache lazy du client implicite.
8. **Mise à jour SPEC.md** : ajouter la section Client / AsyncClient. Maintenir la section fonctions globales.
9. **Mise à jour ARCHITECTURE.md** : ajouter une décision D10 « Réification de la configuration en Client ».
10. **Mise à jour README.md** : section Usage avec les deux modes (env vars + Client).

---

## Métriques de succès

- **Rétrocompat** : un test `test_v01_backcompat.py` exécute un script écrit selon SPEC.md v0.1 (sans aucune référence à `Client`) et vérifie que la sortie est identique avant/après l'introduction du Client. Critère : test passe.
- **Multi-backend simultané** : test d'intégration `test_client_multibackend.py` qui crée deux `Client` avec des backends différents (`anthropic` + `litellm/openai`) dans le même process et vérifie que les deux retournent une réponse non vide en parallèle (via `concurrent.futures.ThreadPoolExecutor` pour sync, `asyncio.gather` pour async). Critère : test passe avec deux vraies réponses distinctes.
- **Immutabilité du Client** : test unitaire qui tente d'assigner `client.config = ...` ou `client.config.backend = ...` et vérifie que cela lève `FrozenInstanceError` (dataclass frozen) ou `AttributeError`. Critère : test passe.
- **Isolation entre Clients** : test unitaire qui crée deux clients avec des `api_key` différentes et vérifie que les SDK sous-jacents reçoivent bien les clés respectives (pas de fuite via état partagé). Critère : test passe avec mock vérifié.
- **Cache du client implicite** : test unitaire qui appelle `chat()` deux fois avec les mêmes env vars et vérifie que le client implicite n'est construit qu'une seule fois (via compteur sur le constructeur mocké). Test qui modifie une env var entre deux appels et vérifie que le client est reconstruit. Critère : les deux tests passent.
- **Performance** : le surcoût du wrapping (`chat()` → client implicite → backend) doit être ≤ 100 µs sur un appel mocké (en excluant l'appel SDK). Critère : benchmark `pytest-benchmark` dédié, seuil dans la config.
- **Couverture de tests** : maintenir ≥ 85 % sur l'ensemble, ≥ 90 % sur `_client.py` spécifiquement. Critère : seuil dans `pyproject.toml`.

---

## Changelog

| Date | Auteur | Changement |
|------|--------|------------|
| 2026-05-14 | JP + Claude | Création du PRD |
