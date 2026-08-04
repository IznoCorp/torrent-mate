# Implementation Progress — media-sheet

> For Claude: read this file at session start. Current feature tracker.

**Feature**: [#388] Fiche détail média — route dédiée, réutilisable partout (+ § constitution)
**Type**: feat
**Version bump**: 0.77.4 → 0.78.0 (minor)
**Branch**: feat/media-sheet
**Ticket**: #388 — claimed (heartbeat live)
**PR merge**: auto — standing operator contract: adversarial review(s) + tests before merge.
**PR**: _(created after last phase)_
**Design**: docs/features/media-sheet/DESIGN.md
**Master plan**: docs/features/media-sheet/plan/INDEX.md

## Non-negotiable invariants (DESIGN D1-D10, frozen)

- Data comes from a LIVE provider call with a short cache (D1) — the only source that works
  for a media the library does not own (a search result exists in no database).
- Addressing is by PROVIDER ID: `/media/:provider/:id` (D2). Deliberate break from the
  repo's query-param+drawer convention — the operator asked for a real page.
- New `MediaDetails` fields are OPTIONAL and default to `None`; an unknown value is never
  rendered as an empty string (D4, §8 "rien en silence").
- The sheet CROSSES the library (owned / per-season completeness, D5) — otherwise it is
  decorative.
- Provider unreachable ⇒ the sheet still renders what is known plus a French reason
  (`degraded_reason`), never an empty screen and never a fake "no information" (D9).
- ONE link helper (`mediaSheetHref`) — a constitution rule applied in 11 places needs a
  single source of truth or it drifts (D8).
- Any route/model change ⇒ `make openapi` + regenerated files committed (CI drift guard),
  and a mirror test in `frontend/src/router.test.tsx`.
- A media with NO provider id gets NO link (it must lead to resolution, never to a dead
  link) — the single exception carved into the new §11.

## Phases

| #   | Phase                                                | File                                       | Status |
| --- | ---------------------------------------------------- | ------------------------------------------ | ------ |
| 1   | Modele + parseurs                                    | phase-01-metadata-model-parsers.md         | [x]    |
| 2   | Endpoint + cache + croisement mediatheque            | phase-02-endpoint-cache-ownership.md       | [x]    |
| 3   | Composant + page + route + helper                    | phase-03-component-page-route.md           | [x]    |
| 4   | Cablage des surfaces + S11 constitution + ACCEPTANCE | phase-04-wiring-constitution-acceptance.md | [x]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Toutes les phases sont `[x]`. Gate complet vert le 2026-08-04 : `make lint`, `make test` (10277 passed), `make check` (exit 0), `tsc -b --noEmit`, `eslint`, `lint:ds`, `vitest` (1209 passed), `npm run build`, zero derive OpenAPI, audit_design_coverage --strict 0 finding. Prochaine etape : PR + CI + reviews adversariales + merge.

**Contrat d'appel figé en phase 2 — à respecter en phase 3/4** : l'endpoint accepte
`?kind=movie|tv`. Les quatre surfaces connaissent le type ; `mediaSheetHref` **doit** le
porter, sinon chaque fiche de film paie un aller-retour provider inutile (et la sonde
sans indice reste le cas de repli d'une URL tapée à la main).
