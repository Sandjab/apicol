# PRD-002 : Séparation lexicale du backend `claude -p`

**Statut** : Brouillon
**Date** : 2026-05-14
**Auteur** : JP
**Source** : conversation initiale de design

---

## Vision

**Le quoi : quel pattern ce PRD propose-t-il ?**

Le wrapper `claude -p` (Claude Code CLI utilisé en sous-processus) est exposé via une **fonction publique distincte** (`claude_cli_chat`, `claude_cli_achat`), **jamais** sélectionnable via `APICOL_TYPE`. La valeur `claude_cli` pour cette variable d'environnement est **explicitement rejetée** par `_config.py` avec un message qui pointe vers la fonction dédiée.

**Le pourquoi : pourquoi ce pattern fonctionne-t-il ?**

Le mécanisme est celui de la **frontière lexicale**. Un utilisateur (ou un futur Claude Code travaillant sur ce repo) qui lit `apicol.chat(...)` dans un script ne peut pas savoir par inspection visuelle quel backend est sélectionné — c'est dans l'environnement. Mais s'il lit `apicol.claude_cli_chat(...)`, il sait immédiatement que ce script utilise le CLI Claude Code local.

Cette séparation a deux fonctions :

1. **Technique** : `claude -p` n'est pas une API stateless de chat completion. C'est un CLI agentique avec mode interactif, mode prompt, support tools, MCP, skills, accès filesystem. Le traiter comme « un backend comme les autres » dans un dispatch routeur cache la complexité spécifique de l'invocation (flags, mode JSON output, timeout, parsing).
2. **Conformité aux TOS** : l'abonnement Claude Pro/Max sous lequel tourne `claude` est une licence d'usage personnel interactif. Un script qui dispatche programmatiquement vers `claude -p` dans une logique de coût/dispo (« si l'API Anthropic est saturée, fallback sur claude -p ») enfreint les TOS Anthropic. OpenCode a retiré ses plugins qui faisaient cela en v1.3.0. La séparation lexicale rend cette frontière visible dans le code applicatif et empêche le routage automatique par construction.

## Exemple bout-en-bout (projeté)

```python
# === Usage légitime : script personnel ===
import apicol

# Aucune variable APICOL_* requise — utilise le `claude` CLI local
response = apicol.claude_cli_chat(
    messages=[{"role": "user", "content": "Résume CHANGELOG.md"}],
)
# → ce script ne peut tourner que sur la machine de l'utilisateur,
#   qui a `claude` installé et authentifié pour son usage perso.

# === Usage rejeté : routage programmatique ===
import os, apicol
os.environ["APICOL_TYPE"] = "claude_cli"  # ← rejeté
response = apicol.chat(messages=[...])
# → ConfigError: "claude_cli is not a valid value for APICOL_TYPE.
#    Use apicol.claude_cli_chat() directly. See SPEC.md for details."
```

---

## Contexte

Lors du design initial de `apicol`, l'utilisateur a exprimé le souhait de pouvoir router automatiquement entre plusieurs backends selon le coût et la disponibilité, **en incluant `claude -p`**. Le rationnel : utiliser l'abonnement Claude Pro/Max pour ne pas consommer d'API key quand c'est possible.

Ce rationnel **n'est pas conforme aux TOS Anthropic**. Anthropic interdit explicitement l'usage de l'abonnement Pro/Max pour servir une charge programmatique routée. Le projet OpenCode a explicitement retiré le support de ce pattern dans sa version 1.3.0, en citant l'interdiction Anthropic.

Cependant, il existe un usage **légitime** très proche : l'utilisateur écrit un script personnel local qui appelle `claude -p` pour son propre usage interactif (un seul utilisateur, charge ad-hoc, pas de dispatch automatique). Ce cas mérite d'être supporté.

---

## Problème

**Comment supporter `claude -p` comme backend pour les usages légitimes (script personnel interactif) tout en empêchant par construction les usages illégitimes (routage programmatique en violation des TOS) ?**

Le défi est double :

1. La frontière entre usage légitime et illégitime est sémantique, pas technique. Le même code peut être l'un ou l'autre selon le contexte d'exécution. La lib ne peut pas la garantir.
2. Mais la lib peut, par son **design**, rendre l'usage illégitime moins probable et plus visible, sans empêcher l'usage légitime.

---

## Solution

**Séparation lexicale.**

- Fonction publique distincte `claude_cli_chat()` / `claude_cli_achat()` — pas dans le dispatch de `chat()`.
- Rejet explicite de `claude_cli` comme valeur de `APICOL_TYPE` dans `_config.py`, avec un message qui pointe vers la fonction dédiée et vers la note TOS.
- Docstring de `claude_cli_chat()` explicite : « dev only — usage personnel interactif uniquement ; ne pas utiliser dans un routage programmatique selon coût/dispo ; voir TOS Anthropic ».
- Note dans `ARCHITECTURE.md` (D5) et `SPEC.md` qui documentent l'intention.

Cette approche :

- Permet l'usage légitime (un utilisateur appelle explicitement `claude_cli_chat()` dans son script).
- Empêche **par construction** le routage automatique (il n'y a pas de chemin de code qui aille de `chat()` vers `claude_cli_chat()`).
- Rend la frontière **visible à la lecture du code applicatif** : un script qui appelle `chat()` ne risque jamais d'utiliser `claude -p` par effet de bord.

---

## Options évaluées

### Option A (retenue) : Fonction publique distincte, non routable

Décrit ci-dessus.

**Avantages** :

- Empêche par construction le routage automatique. Pas de risque de basculer accidentellement vers `claude -p` en changeant une env var.
- La séparation est visible à la lecture du code applicatif : `claude_cli_chat()` est syntaxiquement distinct de `chat()`.
- L'usage légitime (script personnel) reste simple : un appel direct, pas de configuration.
- Le docstring documente la limite TOS au point d'utilisation, là où l'utilisateur (ou Claude Code travaillant sur le repo) la verra.

**Inconvénients** :

- Asymétrie de surface : `claude_cli_chat()` est un peu un citoyen de seconde classe, sans pendant pour les autres backends.
- Si l'utilisateur veut bench `claude -p` contre l'API Anthropic, il doit écrire un script qui branche manuellement sur les deux fonctions plutôt que de toggle une env var.

### Option B : Backend routable comme les autres (`APICOL_TYPE=claude_cli`)

Traiter `claude -p` comme n'importe quel autre backend, sélectionnable via `APICOL_TYPE`.

**Avantages** :

- Surface uniforme : tous les backends sont accessibles via le même mécanisme.
- Permet le routage automatique selon coût/dispo (c'était la demande initiale).
- Bench trivial : changer une variable d'environnement et relancer.

**Inconvénients** :

- **Enfreint les TOS Anthropic** dès qu'utilisé en routage automatique, ce qui est précisément le cas que ce design encouragerait.
- La frontière entre usage personnel et usage programmatique disparaît du code applicatif. Un code review ne peut plus repérer l'usage problématique sans inspecter le contexte d'exécution.
- Précédent OpenCode : ils l'ont fait, Anthropic a réagi, ils ont retiré le support.
- Risque concret : ban du compte de l'utilisateur si Anthropic détecte le pattern.

### Option C : Pas de support `claude -p` du tout

Refuser le support et orienter l'utilisateur vers les API officielles.

**Avantages** :

- Zéro risque TOS.
- Surface plus simple, moins de code.

**Inconvénients** :

- Ne couvre pas l'usage légitime (script personnel interactif), qui est une demande réelle de l'utilisateur.
- Force l'utilisateur à wrapper `subprocess.run(["claude", "-p", ...])` lui-même, sans bénéficier de la cohérence d'interface avec `chat()` (format messages OpenAI, format de retour).
- L'utilisateur est susceptible de réintroduire le pattern problématique dans ses scripts ad-hoc, sans la frontière lexicale et le docstring d'avertissement.

---

## Décision

**Option A retenue.**

Raisons clés :

1. **Conformité TOS par construction** : pas de chemin de code qui permette le routage automatique vers `claude -p`. Cette propriété est vérifiable par audit statique.
2. **Préservation de l'usage légitime** : un utilisateur qui veut scripter avec son `claude` local peut le faire, avec une interface cohérente (mêmes formats messages/réponse que `chat()`).
3. **Visibilité dans le code** : la fonction `claude_cli_chat()` est immédiatement reconnaissable. Un futur Claude Code travaillant sur ce repo ou sur un projet client comprend immédiatement la frontière.
4. **Précédent OpenCode** : Anthropic a déjà réagi à ce pattern. Ne pas reproduire l'erreur.

---

## Plan d'implémentation

1. **`_backends/claude_cli.py`** : wrapper `subprocess.run` (sync) et `asyncio.create_subprocess_exec` (async). Vérifier que `claude` est dans le PATH (sinon `BackendUnavailableError`). Aplatir les `messages` en un seul prompt avant invocation. Lire la doc actuelle de `claude --help` pour les flags exacts (`--print`, `--output-format json` éventuellement, `--model`).
2. **`__init__.py`** : exposer `claude_cli_chat` et `claude_cli_achat` au top-level du package, **séparément** de `chat` / `achat`.
3. **`_config.py`** : ajouter une garde explicite. Si `APICOL_TYPE == "claude_cli"`, lever `ConfigError` avec un message qui contient explicitement les mots `apicol.claude_cli_chat()` et `TOS` (pour faciliter la recherche).
4. **Docstring** : la docstring de `claude_cli_chat()` doit commencer par `⚠️ Dev only.` et expliquer la limite TOS en 2-3 phrases. Test unitaire qui vérifie que le mot « TOS » apparaît dans la docstring (garde-fou contre une suppression accidentelle).
5. **Tests** : test unitaire que `_config.load()` rejette `claude_cli`. Test qu'il n'y a pas de chemin d'appel entre `chat()` et `claude_cli_chat()` (audit statique simple : `grep -r claude_cli_chat src/apicol/_route.py src/apicol/_backends/anthropic.py src/apicol/_backends/litellm.py` doit retourner zéro résultat).
6. **Documentation** : section dans `SPEC.md` (déjà en place) et `ARCHITECTURE.md` (D5, déjà en place).

---

## Métriques de succès

- **Garde-fou config actif** : un test unitaire `test_config_rejects_claude_cli` passe. Il définit `APICOL_TYPE=claude_cli` et vérifie que `_config.load()` lève `ConfigError` avec un message contenant `claude_cli_chat`. Critère : test présent et passant en CI.
- **Pas de chemin de routage** : un test d'audit statique grep que les fichiers `_route.py`, `_backends/anthropic.py`, `_backends/litellm.py` ne contiennent jamais la chaîne `claude_cli`. Critère : `grep -l claude_cli src/apicol/_route.py src/apicol/_backends/{anthropic,litellm}.py` retourne 0 fichier.
- **Docstring TOS présent** : un test vérifie que `apicol.claude_cli_chat.__doc__` contient les chaînes « Dev only » et « TOS ». Critère : test présent et passant.
- **Fonction utilisable** : un test d'intégration (skippé si `claude` absent du PATH, marqué `@pytest.mark.requires_claude_cli`) appelle `claude_cli_chat([{"role": "user", "content": "Say hi"}])` et vérifie qu'une réponse non vide revient. Critère : test passe sur une machine avec `claude` installé.

---

## Changelog

| Date | Auteur | Changement |
|------|--------|------------|
| 2026-05-14 | JP + Claude | Création du PRD |
