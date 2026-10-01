# Phase 2 — The season's row, on the series sheet and on the follow sheet (S1, S6's rows)

**Opening measure** (taken on `9234341fc`; re-taken at the real opening):
`grep -n 'ASKED_ONCE) continue' frontend/maquette/design/src/features/media/asked-seasons.ts` → **33** (the
`request` filter); `git grep -n "seasonAskedOnce" -- frontend/maquette/design/src` → 3 sites; `grep -cv '^\s*$'
frontend/maquette/design/src/features/media/season-list.tsx` → **390** (nothing added there); the row's mark is
`chip({ tone: "info" })` once the train's phase 9 has landed — read, not assumed.

## What changes

1. **« Demandée » reads the one derivation** (S1): `askedSeasons` reads phase 1's `lib/` answer — every season card
   on its way, arrivals included, whatever its requester — and the season from the card's `season` field, never the
   line; the act « Récupérer la saison N » withdrawn while the mark shows.
2. **One mark at a time** (DECIDED 4): « En file — pipeline en cours » while the request waits, then « Demandée ».
3. **« auto »** (DECIDED 6): « Demandée · auto » in the same chip when the season card's `trigger` is `automatic`.
4. **The key renamed**: `seasonAskedOnce` → `seasonRequested` through `scripts/rename-identifiers.py --values`, the
   diff re-read (its French unchanged).
5. **The rows' end** (S6): shelved → no mark, the fraction `7/7`; `season-row-ask-failed`, `season-row-ask-held`.
6. **Its register row** (order 57): « « Demandée » reads a list « En cours » does not » (DESIGN § 6).

## Acceptance — red first on the old code, then green

- **R-season-recovery-b** — red on `season-row-requested-sheet` (Silo, followed, draws no mark);
  **R-season-recovery-g**, its row half — red on `season-row-requested-automatic-sheet`.
- Re-aimed OUT LOUD: `queued_ask_mark.py`, `queued_by_hand.py` (the mark now read through the derivation).
- Named states: every S1 id; `season-recovery-shelved-sheet`, `season-recovery-shelved-panel`.
- Walked by finger: the media sheet and the follow panel, the same row, the same mark.

## Commit

`feat(maquette-season-recovery): the season's row says « Demandée » on both sheets until the library, and « auto » when the engine asked`
