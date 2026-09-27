# Phase 6 — The torrent's cross-seed mark

**Replaces the first drawing's standalone « tracker's section » outright** — ORGANISATION RULING 19 killed the
`/trackers/$name` detail screen that section would have opened on, before this lot ever built it (it never landed
on `main`). The cross-seed is now a MARK on the Torrents tab's ORIGIN row (DESIGN § 3.3), never a second page. **No
OPEN question remains conditional**: OPEN 5 = A and round 10 Q5 = A both draw here, six words, cut into its own
phase (16) is the virtual window their growth costs (F24) — this phase is drawn AT the ceiling on that account and
says so rather than silently absorbing it.

**Opening measure (2026-09-27, on `1d1282567` — the Torrents tab does not exist on this head; figures are from
L16's plan, already re-drawn on `5e5ecd052`):**

- **Commands.** `ls frontend/maquette/design/src/features/trackers` → none; `docs/features/maquette-l16/plan/phase-05-torrents-tab.md`
  places the row in `features/trackers/torrents-tab.tsx` (≈ 55 lines: title as a path, tracker, ratio on size,
  deadline, origin colour, up to three obligation marks). **The cross-seed mark is a disclosure ADDED to that same
  row, on the origin entry only** — `features/trackers/torrents-cross-seed.tsx` (new), mounted from
  `torrents-tab.tsx`, never a file of its own address. The analogue for a nested disclosure: `sed -n 1,40p
  frontend/maquette/design/src/ui/disclosure.tsx` (`<Disclosure summary={…}>`, already used by L16's own policy
  panel). `sed -n 60,80p frontend/maquette/design/src/ui/variants/surfaces.ts` — the `chip` tones.
- **Points ≈ 15.** The mark's component ≈ 50 lines new 5; its query hook, reading the SAME downloads call the row
  already answers from — no new operation (≈ 8 lines new) 1; the `fr.json` keys ≈ 10 lines 1; the row order (F64:
  failures first, then ordinary refusals, then `active`, `stopped`, `trackerWithout`, `noMatch`/`notSearched` last,
  newest date first within a state) ≈ 15 lines 1½; three states — `torrents-cross-seed`, `torrents-cross-seed-empty`
  (fold into the mark's own zero-row reading, no separate seed needed) — 2; R-L17-b re-aimed at the mark (its
  second hold: the roster's count agrees with the mark's own rows, summed across torrents) 1; **R-L17-k, one read
  per visit (NE-DOIT-PAS-8)** — the mark folded into the SAME downloads call, never a second read — 3; R-L17-a
  re-aimed at the mark's chips 1. → 15½, drawn at 15 by folding the empty-state seed into the existing library
  fixture rather than a dedicated new one.
- **Found.** Each row's title leads to its sheet by provider ID (NE-DOIT-PAS-9, already L16's own field, fact 17);
  a torrent with no identity leads to the resolution, never to a dead link. **The mark's own read is NOT a second
  operation**: it is the `crossSeed` array demand B extends the downloads read with (phase 1), so R-L17-k's hold is
  proven by counting calls, not by a route that does not exist.

## Red today

**R-L17-k — one read per visit** (DESIGN § 5): opening the roster and the Torrents tab makes each operation ONE
call, and a wait on the page makes none (`window.__mocks.answered()`). Red: the mark does not exist.

## Move

1. `features/trackers/torrents-cross-seed.tsx`, mounted inside `torrents-tab.tsx`'s origin row, reading the SAME
   downloads call. `data-part`: `torrents/cross-seed`, `torrents/cross-seed-row`, `torrents/cross-seed-state`;
   `data-region="torrents/cross-seed"`.
2. `torrents-cross-seed` in `harness/states/trackers.ts` (or `harness/states/cross-seed.ts` when it would not fit,
   the opening measure decides).
3. R-L17-k written first, seen red; R-L17-b re-aimed.

## Mutation

Commit first: add a refetch interval to the mark's read → R-L17-k falls; declare a second operation for the mark
→ falls; render the count from a constant → R-L17-b falls; render a state as the raw enum value → R-L17-a falls;
reorder the rows against F64's own order → the order hold falls.

## Register

—

## Oracle: states that diverge, declared by name

L16's `torrents-list` (the origin row gains a disclosure) — accepted with « L17 § 3.3: the cross-seed mark ». Any
other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on `torrents-cross-seed`.

## Commit

`feat(maquette-l17): a torrent's row says where it cross-seeds, tracker by tracker`
