# BACKLOG.md

Index des PRD du workspace `apicol`.

## En cours

_Aucun pour le moment._

## Validés (implémentés)

| PRD | Titre | Version | Date |
|-----|-------|---------|------|
| [PRD-001](PRD-001-architecture-deux-niveaux.md) | Architecture à deux niveaux pour la couche d'abstraction multi-backend | v0.1.0 | 2026-05-14 |
| [PRD-002](PRD-002-separation-claude-cli.md) | Séparation lexicale du backend `claude -p` | v0.1.0 | 2026-05-14 |
| [PRD-003](PRD-003-multi-backend-simultane.md) | Multi-backend simultané via objet `Client` | v0.1.0 | 2026-05-14 |
| [PRD-004](PRD-004-backend-openai-compatible.md) | Backend `openai-compatible` à côté de LiteLLM | v0.2.0 | 2026-05-16 |
| [PRD-005](PRD-005-streaming.md) | Support du streaming sync + async (`stream`/`astream`) | v0.3.0 | 2026-06-19 |

## Abandonnés

_Aucun pour le moment._

## Idées non encore PRD-isées

- Rendre `litellm` optionnel via extras `pip install apicol[litellm]` (PRD-006 envisagé)
- Support des tool calls (roadmap v0.3 — prochain cycle) — mapping OpenAI ↔ Anthropic ↔ LiteLLM
- Fonction `embed()` pour les embeddings (v0.4)
- Dépréciation à terme de `anthropic_client()` / `anthropic_async_client()` (fonctions globales) au profit de `Client.anthropic_native()` — décision à prendre quand tool calls sera proche
