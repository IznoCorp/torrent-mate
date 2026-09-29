# Phase 11 — The one fold chevron (D.1 #3, DECIDED 4)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "summary::before|<details" -g '*.ts' -g '*.tsx' frontend/maquette/design/src` outside `ui/`
  → **5** sites: `features/media/variants.ts:226`, `features/media/panel-seasons.tsx:143`,
  `features/media/season-list.tsx:256`, `features/acquisition/variants.ts:48`, `features/acquisition/add-screen.tsx:337`
  (a comment at `routes/media-sheet.tsx:39` is not a site); `ui/variants/surfaces.ts:407` draws `▸` / `▾`.
- **Points ≈ 12.** The seasons' `›` becomes `ui/Disclosure`'s one chevron and a `season` variant carries the
  uppercase summary (≈ 12 lines edited, 3); three raw `<details>` converted (≈ 25 lines, 5); the chevron arm of
  `check-component-once.py` and its test (L16-bis § 1.9) (3); the hold (1).
- **Readers.** `season_family.py`, `follow_seasons.py`, `queued_ask_mark.py` read the season fold's parts — kept.

## Red today

The chevron arm: **5** hits. The hold (a HOLD in `follow_seasons.py`, office): on `followsheet-gaps` the season fold
is the `ui` disclosure part; « par identifiant » opened BY FINGER on `acq-add-results` (its named state is the
catalogue's #35, not built here) is the same part.

## The one visible change

« Par identifiant » and every `Disclosure` wear the seasons' `›`, turning a quarter (DECIDED 4).

## Mutation

Restore `▸` in `ui/variants/surfaces.ts` beside the new chevron → the hold falls; a `<details` in a feature → the
arm falls.

## Oracle: states that diverge, declared by name

Every state drawing a `Disclosure` or a season fold (built by script: `summary` present in the region).

## Commit

`refactor(maquette-conformity): one fold chevron, the seasons', in ui/Disclosure only`
