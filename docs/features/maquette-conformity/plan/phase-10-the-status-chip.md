# Phase 10 — The status chip (D.1 #5)

**Opening measure (2026-09-29, on `660049325`):**

- **Commands.** `rg -n "queuedMark|seasonShortfall|trailerSource|runOutcome" -g '*.ts' -g '*.tsx'
  frontend/maquette/design/src` → `features/media/variants.ts:157, 198, 241`; uses at `season-list.tsx:296, 303,
  321, 372`, `panel-seasons.tsx:175, 182, 189`, `media-hero.tsx:165`; `runOutcome` at `features/system/run-screen.tsx:190`;
  `rg -n '"muted"' features/acquisition/follow-vocabulary.ts` → lines **19, 105**; the section head re-typed at
  `features/acquisition/follows-tab.tsx:252`.
- **Points ≈ 12.** Seven media call sites onto `chip` tones (≈ 14 lines, 3); `seasonShortfall` on an air date → text
  (1); three variants die (1); the run screen's outcome and step status → the chip, one tone map with the list
  (phase 2) (2); `muted` → `neutral` (1); `sectionInnerMarkup` at `follows-tab.tsx:252` (1); R-conformity-d (3).
- **Readers.** `queued_by_hand.py`, `season_family.py`, `season_grab.py`, `queued_ask_mark.py` and four others read
  `season/queued|asked|missing` — the parts stay, only the class changes.

## Red today

R-conformity-d: every state pill on `followsheet-gaps`, `runs-list`, `run-detail` is a `.chip` — falls on the
seasons' marks and the run screen's outcome.

## Mutation

Restore `queuedMark` → falls by name.

## Oracle: states that diverge, declared by name

The media sheet and follow sheet states drawing a season mark, `run-detail` (built by script).

## Commit

`refactor(maquette-conformity): every state pill is the chip — seasons, run outcome, follow tones`
