# Phase 17 — The feed: its surface

**Reads OPEN 4 — reading B only.** Under reading A this phase does not exist (phase 16's note).

**Opening measure (2026-09-27, on `46806a88d` — the Trackers page is L16's):**

- **Commands.** `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/system/run-list.tsx` → **176** (the analogue of a chronological list); `frontend/maquette/design/src/ui/virtual-rows.tsx`
  exists for a list that passes a screenful. **Its address is this phase's to measure** (D1: a view of the same page is a search parameter, adjusting replaces — `sed -n 1,40p
  frontend/maquette/design/src/lib/addresses.ts`), never improvised in the design.
- **Points ≈ 14.** The surface ≈ 60 lines new 6; four states — `cross-seed-feed`, `-empty`, `-loading`, `-error` — 4; R-L17-j 3; `fr.json` ≈ 8 lines 1.
- **Found.** The feed is a second view of `/trackers`, not a page (DESIGN § 3.0); each entry carries its date, its tracker, its title and, for a refusal, its sentence (phase 4's helper); an empty feed says why.

## Red today

**R-L17-j — the feed** (DESIGN § 5): newest first; each entry carries its date, its tracker, its title and, for a refusal, its sentence; an empty feed says why. Red: no surface.

## Move

1. The surface and its address; the four states; R-L17-j written first, seen red.

## Mutation

Commit first: unsort the feed → R-L17-j falls; drop the reason → falls; draw the code → R-L17-a falls too.

## Register

—

## Oracle: states that diverge, declared by name

L16's `trackers-list` if the feed's entry point sits on the page (a control or a segment) — accepted with « L17 § 3.7: the feed's entry ». Any other divergence is STOP A.

## Gate

Per INDEX « Gates »; `--a11y` on the four states.

## Commit

`feat(maquette-l17): the cross-seed feed, newest first, each event with its reason`
