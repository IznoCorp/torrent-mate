# Phase 6 — The torrent's cross-seed mark

**The cross-seed is a MARK on the Torrents tab's ORIGIN row (DESIGN § 3.3), never a second page** — organisation
ruling 19 killed the `/trackers/$name` detail screen. **Ruled**: OPEN 5 = A and round 10 Q5 = A, six words. The
virtual window their growth costs (F24) is its own phase (16); this phase is drawn AT the ceiling on that account.

**Opening measure (2026-09-27, on `1d1282567` — the Torrents tab does not exist on this head; figures are from
L16's plan, re-drawn on `5e5ecd052`):**

- **Commands.** `ls frontend/maquette/design/src/features/trackers` → none; `docs/features/maquette-l16/plan/phase-05-torrents-tab.md@f3d8fed01`
  places the row in `features/trackers/torrents-tab.tsx` (≈ 55 lines: title as a path, tracker, ratio on size,
  deadline, origin colour, up to three obligation marks). The nested-disclosure analogue: `sed -n 1,40p
  frontend/maquette/design/src/ui/disclosure.tsx` (`<Disclosure summary={…}>`, used by L16's policy panel).
  `sed -n 60,80p frontend/maquette/design/src/ui/variants/surfaces.ts` — the `chip` tones.
- **Points ≈ 15.** The mark's component ≈ 50 lines 5; its query hook on the SAME downloads call ≈ 8 lines 1;
  `fr.json` ≈ 10 lines 1; the row order ≈ 15 lines 1½; two states 2; R-L17-b re-aimed 1; R-L17-k 3; R-L17-a
  re-aimed 1 → 15½, drawn at 15 by folding the empty state into the existing library fixture, no new seed.

## What it builds

- **The mark**: a disclosure ADDED to the origin row only — `features/trackers/torrents-cross-seed.tsx`, mounted
  from `torrents-tab.tsx`, never a file of its own address; one row per other eligible tracker, with its state.
- **Its read is NOT a second operation**: it is the `crossSeed` array demand B extends the downloads read with
  (phase 1), so R-L17-k is proven by counting calls.
- **Row order (F64)**: failures first, then ordinary refusals, then `active`, `stopped`, `trackerWithout`,
  `noMatch`/`notSearched` last; newest date first within a state.
- **Links**: each row's title leads to its sheet by provider ID (NE-DOIT-PAS-9, L16's field, fact 17); a torrent
  with no identity leads to the resolution, never to a dead link.

## Red today

**R-L17-k — one read per visit** (DESIGN § 5, NE-DOIT-PAS-8): opening the roster and the Torrents tab makes each
operation ONE call, and a wait on the page makes none (`window.__mocks.answered()`). Red: the mark does not exist.

## Move

1. `features/trackers/torrents-cross-seed.tsx`, mounted inside `torrents-tab.tsx`'s origin row, reading the SAME
   downloads call. `data-part`: `torrents/cross-seed`, `torrents/cross-seed-row`, `torrents/cross-seed-state`;
   `data-region="torrents/cross-seed"`.
2. The named states `torrents-cross-seed` and `torrents-cross-seed-empty` (the mark's zero-row reading) in
   `harness/states/trackers.ts`, or `harness/states/cross-seed.ts` when it would not fit — the opening measure decides.
3. R-L17-k written first, seen red; R-L17-b re-aimed (its second hold: the roster's count agrees with the mark's own
   rows, summed across torrents); R-L17-a re-aimed at the mark's chips.

## Mutation

Commit first: add a refetch interval to the mark's read → R-L17-k falls; declare a second operation for the mark
→ falls; render the count from a constant → R-L17-b falls; render a state as the raw enum value → R-L17-a falls;
reorder the rows against F64 → the order hold falls. **Register**: —.

## Oracle and gate — done when

Oracle: L16's `torrents-list` (the origin row gains a disclosure) diverges, accepted with « L17 § 3.3: the
cross-seed mark »; any other divergence is STOP A. Gate: per INDEX « Gates »; `--a11y` on `torrents-cross-seed`.

## Commit

`feat(maquette-l17): a torrent's row says where it cross-seeds, tracker by tracker`
