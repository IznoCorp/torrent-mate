# Plan — control-medias (Design overhaul V2: Contrôle + Médias)

**Feature:** control-medias · **Ticket:** #306 · **Epic:** #304
**Binding spec:** `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §2.1, §2.2, §5.2, §5.3, §1.1
**Constitution:** `docs/reference/product-intent.md` §2, §3, §4, §6, §7, §8, DOIT-2, DOIT-3, DOIT-5, DOIT-7, DOIT-9, DOIT-10
**Merge mode:** auto (operator directive 2026-07-17)

## Wave scope (summary)

| Surface         | What changes                                                    | Wave |
| --------------- | --------------------------------------------------------------- | ---- |
| Backend         | 2 new endpoints (continue + discard) + openapi regen            | V2   |
| `/` (Dashboard) | Rebuilt into **Contrôle** — 8-panel attention-first layout      | V2   |
| `/medias` (NEW) | Promoted staging library + decisions browse + guaranteed egress | V2   |
| `/scraping`     | Redirect → `/medias` (LegacyRedirect component)                 | V2   |
| Nav labels      | « Tableau de bord » → « Contrôle », « Scraping » → « Médias »   | V2   |
| Sidebar footer  | VersionCard moved here (collapsed-rail hidden)                  | V2   |

## Hard non-goals (sequencing invariant §6)

- No changes to `/pipeline`, `/maintenance`, `/registry`, `/config`, `/acquisition` pages
- No nav-grouping flattening, no Système page (V5)
- No brand/token changes

## Phases

| #   | Phase                                          | File                                                                              | Status |
| --- | ---------------------------------------------- | --------------------------------------------------------------------------------- | ------ |
| 01  | Backend — `continue` endpoint                  | [plan/phase-01-continue-endpoint.md](phase-01-continue-endpoint.md)               | [ ]    |
| 02  | Backend — `discard` endpoint                   | [plan/phase-02-discard-endpoint.md](phase-02-discard-endpoint.md)                 | [ ]    |
| 03  | `/medias` page + LegacyRedirect + nav renames  | [plan/phase-03-medias-page-redirect-nav.md](phase-03-medias-page-redirect-nav.md) | [ ]    |
| 04  | Media-sheet egress actions                     | [plan/phase-04-media-sheet-egress.md](phase-04-media-sheet-egress.md)             | [ ]    |
| 05  | Contrôle rebuild (`/`)                         | [plan/phase-05-controle-rebuild.md](phase-05-controle-rebuild.md)                 | [ ]    |
| 06  | Final gate — mobile proof + version bump + ACC | [plan/phase-06-final-gate.md](phase-06-final-gate.md)                             | [ ]    |

## Per-commit gates (every sub-phase)

- **Frontend files touched:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`
- **Backend files touched:** `make lint && make test`
- **Route/signature changes:** `make openapi` + commit regenerated `openapi.json` + `schema.d.ts`

## Test migration map (surface → test file, same phase)

| Surface change                   | Test file                                     | Phase |
| -------------------------------- | --------------------------------------------- | ----- |
| New continue endpoint            | `tests/web/test_staging_media.py` (new tests) | 01    |
| New discard endpoint             | `tests/web/test_staging_media.py` (new tests) | 02    |
| `/scraping` → `/medias` redirect | `Decisions.test.tsx` → `Medias.test.tsx`      | 03    |
| Nav label renames + bottom tabs  | `AppShell.test.tsx`, `nav.test.ts`            | 03    |
| Media-sheet new actions          | New tests in `StagingLibrary.test.tsx` area   | 04    |
| Dashboard → Contrôle rebuild     | `Dashboard.test.tsx` → `Controle.test.tsx`    | 05    |
