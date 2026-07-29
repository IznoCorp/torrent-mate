# Phase 05 — Surfaçage UI + events + ACC + déploiement

## Gate (dernière phase)

- `make check` vert (lint + tests + module-size + typed-api).
- `make openapi` sans dérive (si un modèle web change, régénérer + committer les deux fichiers).
- ACC-01..05 ré-exercées (commandes du DESIGN) + preuve Chrome 390 px si UI touchée.
- Déploiement prod vérifié (BUILD_COMMIT + health 200).

## Sous-phases

### 5.1 — Event catalog + surfaçage read-model

- Déclarer `GrabReswitched` au catalogue d'events (`docs/reference/event-bus.md` + le module
  d'events) ; s'assurer que l'émission tient le contrat (event_bus requis).
- Read-model acquisition (`web/acquisition/states.py` / `truth.py`) : exposer la raison de bascule
  et le nb de tentatives (`len(tried_hashes)`) pour un item en cours, de façon véridique.
- Carte d'acquisition (`FollowedPanel` / File d'acquisition) : afficher « Source bloquée — bascule
  vers une autre release » quand une rebascule a eu lieu (mapping pur d'un fait serveur, pas de
  dérivation client). Si un modèle Pydantic change ⇒ `make openapi` + commit `schema.d.ts`.
- Tests front (vitest) si un composant change.

### 5.2 — ACC + preuve + déploiement

- Ré-exécuter chaque `ACC-NN` du DESIGN (commandes) et coller le déroulé daté dans le corps de PR.
- Preuve Chrome 390 px (harness iframe) si l'UI change.
- `make check`, push, PR, CI, review adversariale avant merge, merge squash, autodeploy prod,
  vérif BUILD_COMMIT + health 200, preuve visuelle, clôture #342.
