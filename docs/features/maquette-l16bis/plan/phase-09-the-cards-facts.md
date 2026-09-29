# Phase 9 — The card's facts

**No STOP C** — OPEN 1 is ruled at phase 1; this phase draws the two fields it named.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n '"seeding"\|"stalled"\|"errored"' frontend/maquette/design/src/i18n/fr.json` → nothing: no
  word for any of the eight states; `grep -n "GIGABYTE" frontend/maquette/design/src/features/trackers/trackers-tab.tsx`
  → line **33**: the page writes volumes in « Go » by hand, and no size writer exists — the size, the volumes and the
  rates share ONE writer in `features/trackers/format.ts` (beside `written`, `dayOf`).
- **Points ≈ 11.** R-L16bis-d's facts holds (state, size, down / up, popularity, date — each from its field, each
  absence said) 2; the state chip, eight words and tones (≈ 15 lines + 8 `fr.json`) 2; the size writer, and the size,
  down / up, sources and date as `cardAnnotations` (≈ 20 lines) 2; states `torrent-card-downloading`, `-stalled`, `-paused`, `-queued`,
  `-errored`, `-missing`, `-no-popularity` (posed) — 7 at ½ each, re-using one pose 3; the report 2.
- **Readers.** `harness/trackers_page.py` reads the ratio `torrents/ratio` — kept on the card.

## Red today

R-L16bis-d's popularity hold over `torrent-card-no-popularity`: nothing drawn (the field does not exist yet in the
drawing).

## Move

1. `swarmSeeds: null` is « sources inconnues », `0` is « aucune source » — two sentences (a dead swarm is not an
   unknown one).
2. The date added in the interface's language, day and month (`features/trackers/format.ts`'s `dayOf`).

## Mutation

Draw `0` for a null popularity → the absence hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every « Torrents » state (the new lines), declared by script; the seven new states.

## Commit

`feat(maquette-l16bis): a torrent card says its state, size, exchange, sources and date`
