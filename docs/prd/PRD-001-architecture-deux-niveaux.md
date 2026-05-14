# PRD-001 : Architecture à deux niveaux pour la couche d'abstraction multi-backend

**Statut** : Brouillon
**Date** : 2026-05-14
**Auteur** : JP
**Source** : conversation initiale de design

---

## Vision

**Le quoi : quel pattern ce PRD propose-t-il ?**

Plutôt que prétendre à une abstraction étanche qui exposerait 100 % des features de tous les backends LLM derrière une interface unique, on délimite **explicitement** deux niveaux dans la surface publique :

- **Niveau 1 — interface unifiée portable** (`chat`, `achat`) : format OpenAI partout, mapping des features communes via des paramètres unifiés (`reasoning_effort`), passthrough silencieux des extras via `extra_body`. Le code applicatif écrit pour ce niveau est portable entre Anthropic, OpenAI, Gemini, Ollama, vLLM, etc.
- **Niveau 2 — échappatoire native explicite** (`anthropic_client`, `anthropic_async_client`) : retourne un SDK Anthropic natif préconfiguré pour les features non-portables (prompt caching avec breakpoints fins, citations, PDF, batch, agent skills, extended thinking détaillé).

L'utilisateur **choisit consciemment** son niveau. Le code applicatif qui n'utilise que le niveau 1 est portable ; le code qui appelle le niveau 2 est lisiblement lié au backend Anthropic.

**Le pourquoi : pourquoi ce pattern fonctionne-t-il ?**

Le mécanisme cognitif est celui de la **frontière nommée**. Toute couche d'abstraction multi-backend fuit pour les features avancées — c'est inhérent au fait que les fournisseurs n'ont pas la même surface. LiteLLM essaie de tout fourrer dans une interface unique et le résultat c'est une doc-labyrinthe où l'utilisateur doit savoir, pour chaque feature, quel `extra_body` passer pour quel provider, et où la traduction peut casser silencieusement.

Notre choix : ne pas prétendre à l'étanchéité. À la place, donner un nom à la sortie. Quand l'utilisateur écrit `anthropic_client()`, il *sait* qu'il sort du périmètre portable et qu'il se lie au backend Anthropic. Cette information est encodée dans le nom de la fonction, pas dans un commentaire ou une note de bas de page.

C'est le même pattern que `subprocess.run()` vs `os.execvp()` en Python : un wrapper haut-niveau pour les cas communs, un accès bas-niveau nommé pour les cas qui ont besoin de tout.

**Le comment** : renvoyé au Plan d'implémentation.

## Exemple bout-en-bout (projeté)

```python
# === Code applicatif — niveau 1 ===
# Portable : marche avec n'importe quel APICOL_TYPE
import os, apicol

os.environ["APICOL_TYPE"] = "anthropic"
os.environ["APICOL_KEY"] = "sk-ant-..."
os.environ["APICOL_MODEL"] = "claude-opus-4-7"

response = apicol.chat(
    messages=[{"role": "user", "content": "Bonjour"}],
    reasoning_effort="medium",
)
print(response["choices"][0]["message"]["content"])

# Le même code, sans modification :
os.environ["APICOL_TYPE"] = "litellm"
os.environ["APICOL_MODEL"] = "openai/gpt-5"
# → marche pareil, reasoning_effort est passé tel quel à LiteLLM

# === Code applicatif — niveau 2 ===
# Lié à Anthropic, mais accès complet aux features avancées
client = apicol.anthropic_client()
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    system=[
        {
            "type": "text",
            "text": gros_document_100k_tokens,
            "cache_control": {"type": "ephemeral"},  # caching avec breakpoint
        }
    ],
    messages=[{"role": "user", "content": "Question sur le document"}],
)
# → accès à toute la richesse du SDK Anthropic
```

---

## Contexte

`apicol` est une couche d'abstraction Python pour appeler un LLM via plusieurs backends interchangeables. L'utilisateur veut :

1. Pouvoir basculer entre **API Anthropic directe**, **LiteLLM** (qui couvre OpenAI, Gemini, locaux, OpenRouter), et **`claude -p`** sans changer le code applicatif.
2. Bénéficier des features avancées d'Anthropic (caching, thinking détaillé) quand il utilise l'API Anthropic, sans les perdre dans la traduction.
3. Pouvoir scripter avec `claude -p` localement pour son usage personnel (ce point fait l'objet du PRD-002, séparé).

Le paysage existant :

- **LiteLLM** : 100+ providers, format OpenAI, mature, mais le compatibility layer OpenAI d'Anthropic ne supporte pas le prompt caching ni le détail du thinking. Tout passer par LiteLLM = perdre des features.
- **aisuite** (Andrew Ng) : minimaliste, même approche, moins mature.
- **SDK OpenAI direct avec `base_url`** : marche pour 6/8 backends (Anthropic, Gemini, Ollama, vLLM, LM Studio, OpenRouter sont OpenAI-compatible), mais perd aussi les features Anthropic avancées et n'aide pas pour `claude -p`.

---

## Problème

**Comment concevoir la surface publique d'une lib multi-backend qui :**

1. Permette à du code applicatif d'être portable entre Anthropic, OpenAI, Gemini, locaux, etc.
2. Ne dégrade pas l'accès aux features Anthropic avancées (caching, thinking, citations, PDF) quand l'utilisateur a explicitement choisi Anthropic.
3. Reste lisible — c'est-à-dire qu'à la lecture du code applicatif, on comprenne immédiatement si le code est portable ou lié à un backend spécifique.

---

## Solution

**Architecture à deux niveaux dans la surface publique :**

- Le **niveau 1** est une fonction unifiée (`chat`, `achat`) qui prend du format OpenAI, accepte un set restreint de paramètres unifiés (`reasoning_effort`, `temperature`, `max_tokens`) et un passthrough `extra_body`. Elle dispatche en interne vers le SDK Anthropic ou vers LiteLLM selon `APICOL_TYPE`. Quand le backend est Anthropic, elle traduit OpenAI↔Anthropic à la frontière du backend, en exposant les features mappables (`reasoning_effort` → `thinking`).
- Le **niveau 2** est une fonction (`anthropic_client`, `anthropic_async_client`) qui **ne fait pas** d'appel LLM elle-même mais retourne un client SDK Anthropic natif préconfiguré. L'utilisateur appelle directement les méthodes du SDK et accède à toutes ses features.

Le code applicatif est lisible parce que le **nom de la fonction encode le niveau d'abstraction** :

- `apicol.chat(...)` → niveau 1, portable
- `apicol.anthropic_client().messages.create(...)` → niveau 2, lié à Anthropic

Aucune ambiguïté visuelle.

---

## Options évaluées

### Option A (retenue) : Architecture à deux niveaux

**Avantages** :

- Lisibilité : la frontière portable/lié-au-backend est encodée dans le nom des fonctions, visible à la lecture du code applicatif.
- Pas de dégradation pour les usages avancés Anthropic : on a accès au SDK natif sans contrainte.
- Surface du niveau 1 minimale et stable : peu de paramètres unifiés, donc peu de risque de divergence avec les SDKs upstream.
- Coût d'implémentation faible : le niveau 2 est juste un constructeur de client préconfiguré.

**Inconvénients** :

- Demande à l'utilisateur de comprendre la distinction. Ce n'est pas une abstraction « magique unifiée ».
- Le niveau 2 est asymétrique : on n'expose pas d'`openai_client()` ou de `litellm_client()`. Justifiable parce que LiteLLM est déjà l'échappatoire pour OpenAI/Gemini/etc., mais peut surprendre.
- Si un autre backend (futur) a aussi des features non-portables (ex. Gemini a la grounding search native), il faudrait ajouter `gemini_client()` au niveau 2, ce qui pourrait gonfler la surface.

### Option B : Surface unique tout-en-un (style LiteLLM)

Tout passe par `chat()` / `achat()`. Les features avancées sont exposées via convention `extra_body` (ex. `{"cache_control": ...}` inline dans les messages).

**Avantages** :

- Une seule fonction à apprendre.
- Code applicatif maximalement « unifié » en apparence.

**Inconvénients** :

- L'utilisateur doit connaître les conventions `extra_body` pour chaque feature et chaque backend. La doc devient un labyrinthe comme celle de LiteLLM.
- Certaines features sont fondamentalement impossibles à exposer proprement en surface OpenAI : citations natives Anthropic (qui renvoient une structure de citations attachée aux blocks de texte), batch API (qui retourne un job ID, pas une réponse synchrone), PDF input avec mode visuel.
- On réinvente ce que LiteLLM fait déjà, en moins bien (moins de providers couverts, moins de tests).
- La frontière portable/lié-au-backend disparaît du code applicatif : on ne sait plus, à la lecture, si un appel `chat(...)` avec un `extra_body` particulier marchera sur un autre backend.

### Option C : Surface unique format Anthropic

Tout passe par une fonction qui prend du format Anthropic (`system` séparé, `messages` avec rôles `user`/`assistant`, `content` en blocks). Quand le backend n'est pas Anthropic, on traduit Anthropic→OpenAI à la sortie.

**Avantages** :

- Surface plus expressive (`system` séparé, blocks de content typés).
- Accès natif aux features Anthropic sans passer par `extra_body`.

**Inconvénients** :

- Va à contre-courant de l'écosystème : LiteLLM, OpenAI SDK, tous les frameworks LLM, parlent OpenAI. Forcer le format Anthropic est isolant.
- La traduction Anthropic→OpenAI à la sortie est plus coûteuse que l'inverse parce qu'OpenAI est moins riche en types — on perd de l'info silencieusement.
- Si on a 6 backends sur 8 qui parlent OpenAI nativement, prendre Anthropic comme lingua franca oblige à traduire dans le sens lossy pour 75 % des appels.

---

## Décision

**Option A retenue.**

Raisons clés :

1. La **lisibilité du code applicatif** est la propriété la plus importante d'une couche d'abstraction. Le pattern « le nom encode le niveau » la garantit.
2. **Ne pas réinventer ce que LiteLLM fait déjà** : si on veut une surface unifiée 100+ providers, LiteLLM existe. Notre valeur ajoutée est précisément l'échappatoire native Anthropic, qui suppose deux niveaux.
3. **Coût d'implémentation faible** : le niveau 2 est trivial à coder (un constructeur). Le niveau 1 est restreint volontairement, donc maîtrisable.
4. L'asymétrie (`anthropic_client` mais pas `openai_client`) est **justifiée fonctionnellement** : on passe par LiteLLM pour OpenAI et le SDK OpenAI est trivialement instanciable par l'utilisateur lui-même s'il veut tomber au niveau natif.

---

## Plan d'implémentation

1. **Squelette du package** : `pyproject.toml`, structure `src/apicol/`, dépendances (`anthropic`, `litellm`).
2. **`_errors.py`** : définir `ConfigError`, `BackendUnavailableError`, `BackendError`, `NotSupportedError`.
3. **`_config.py`** : lecture et validation des 4 env vars. Rejeter `claude_cli` comme valeur de `APICOL_TYPE` avec message explicite. Tests unitaires associés.
4. **`_backends/anthropic.py`** : traduction OpenAI↔Anthropic à la frontière. Mapping `reasoning_effort` → `thinking`. Fonctions `complete()` sync et `acomplete()` async.
5. **`_backends/litellm.py`** : wrapper fin autour de `litellm.completion` / `litellm.acompletion`. Injection `api_base` depuis `APICOL_URL`. Injection clé dans la bonne env var selon le provider détecté.
6. **`_route.py`** : dispatch `match` sur `api_type`, appelle le bon backend.
7. **`__init__.py`** : expose `chat`, `achat`, `anthropic_client`, `anthropic_async_client`, et `claude_cli_chat`, `claude_cli_achat` (ces deux derniers font l'objet du PRD-002).
8. **Tests unitaires** : mock des SDKs, vérifier dispatch correct, vérifier traductions, vérifier rejet de `claude_cli`.
9. **Tests d'intégration** (marqués `@pytest.mark.integration`, optionnels) : smoke tests sur vraies APIs.
10. **Documentation** : à jour dans `README.md`, `SPEC.md`, `ARCHITECTURE.md` (ce PRD).
11. **Release v0.1.0** sur PyPI.

---

## Métriques de succès

- **Portabilité du niveau 1** : le même script applicatif utilisant uniquement `chat()` ou `achat()` produit une réponse non-vide pour les configurations suivantes : `anthropic + claude-opus-4-7`, `litellm + openai/gpt-5`, `litellm + gemini/gemini-2.5-pro`, `litellm + ollama/llama3:8b` (local). Critère : 4/4 configurations passent un smoke test scripté.
- **Accès complet aux features Anthropic via le niveau 2** : un script qui appelle `anthropic_client().messages.create(...)` avec `cache_control`, `thinking`, et un message multi-blocks reçoit une réponse incluant `usage.cache_read_input_tokens` non-nul au deuxième appel. Critère : test d'intégration dédié passe.
- **Taille du code** : `src/apicol/` ≤ 600 lignes Python hors tests et hors `__init__.py`. Critère : `find src/apicol -name '*.py' -not -name '__init__.py' | xargs wc -l` retourne ≤ 600.
- **Couverture de tests** : ≥ 85 % sur `src/apicol/` mesurée par `pytest --cov`. Critère : seuil dans `pyproject.toml`, CI fail si en-dessous.
- **Typage** : `mypy --strict src/` retourne 0 erreur. Critère : passe dans la CI.

---

## Changelog

| Date | Auteur | Changement |
|------|--------|------------|
| 2026-05-14 | JP + Claude | Création du PRD |
| 2026-05-14 | JP + Claude | Retrait de la métrique « lisibilité du code applicatif » (qualitative non mesurable) |
