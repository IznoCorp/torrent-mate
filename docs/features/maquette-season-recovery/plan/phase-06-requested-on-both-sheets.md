# Phase 6 — « Demandée » on both sheets

**STOP C: OPEN 4 and OPEN 6** (DESIGN § 5). Written for A and A: « En file » alone while the ask waits, then
« Demandée »; an automatic recovery drawn as a manual one. Under OPEN 4 = B both marks draw (≈ 1 point less); under
OPEN 6 = B the derivation keeps a requester filter for manual asks (the engine must then say which — a demand).

**Opening measure (2026-09-29, on `b63a45438`):**

- **Commands.** `grep -n 'ASKED_ONCE) continue' frontend/maquette/design/src/features/media/asked-seasons.ts` → line
  **33**; `git grep -n "seasonAskedOnce" -- frontend/maquette/design/src` → **3** (`panel-seasons.tsx:183`,
  `season-list.tsx:373`, `i18n/fr.json:388`); `grep -cv '^\s*$' frontend/maquette/design/src/features/media/season-list.tsx`
  → **390**: the mark is already drawn there, nothing is added.
- **Points ≈ 14.** R-season-recovery-b with its mutations 3; `askedSeasons` reads the moved derivation — every season
  card on its way, arrivals included, whatever its requester — and the season from the card's `season` field, never
  the line 2; the key renamed `seasonRequested` through `scripts/rename-identifiers.py --values`, its diff re-read 1;
  the one-mark-at-a-time order of OPEN 4 on both rows 1; states `season-row-requested-sheet`,
  `season-row-requested-panel`, `season-row-requested-one-off`, `season-row-queued`, `season-row-queue-loading`,
  `season-row-queue-unread` 6 (re-using the seeds); the report 1.
- **Readers.** `harness/season_grab_unfollowed.py` (R158) reads « Demandée » on the one-off — re-aimed OUT LOUD to the
  new key; `harness/queued_ask_mark.py` (R138) reads « En file » — unchanged under OPEN 4 = A.

## Red today

R-season-recovery-b on `season-row-requested-sheet`: Silo's S03 row draws « Récupérer la saison 3 », no mark.

## Move

1. `askedSeasons` reads the derivation; its header's « fragile » paragraph goes with the line parsing.
2. The two rows' JSX unchanged but for the key.

## Mutation

Restore `via === "request"` → falls on Silo; read `queue.inFlight` instead of the derivation → falls at
`season-card-arrived` (held from phase 8; until then on a posed arrival).

## Register

None.

## Oracle: states that diverge, declared by name

Every media and follow-panel state on « Silo », declared by script; the six `season-row-*` ids above are new.

## Commit

`feat(maquette-season-recovery): a season being recovered reads « Demandée » on both sheets, followed or not`
