# CHANGELOG.md

Toutes les modifications notables de ce projet sont documentées ici.

Le format est inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et le projet adhère au [Versioning Sémantique](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### À faire avant v0.1.0

- Choisir le nom définitif du projet (voir section *Naming* du README).
- Implémenter le squelette du package selon `ARCHITECTURE.md`.
- Implémenter et tester les deux niveaux de l'API publique.
- Implémenter le wrapper `claude_cli_chat` avec ses garde-fous.
- Atteindre les seuils des métriques de succès des PRD-001 et PRD-002.

---

_Convention : chaque release listera les sections `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security` selon ce qui s'applique._
