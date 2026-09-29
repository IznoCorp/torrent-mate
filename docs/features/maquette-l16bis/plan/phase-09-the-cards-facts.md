# Phase 9 — The card's facts

**STOP C: DECIDED 1** (2026-09-29, PR #637 — DESIGN § 5): down / up is not one drawing but THREE named states —
default (volumes), while downloading (a progress bar + the download rate), while uploading (no bar, the upload rate
alone). This phase draws all three and the fields phase 1 named.

**Opening measure (2026-09-29, on `f3d8fed01`):**

- **Commands.** `grep -n '"seeding"\|"stalled"\|"errored"' frontend/maquette/design/src/i18n/fr.json` → nothing: no
  word for any of the eight states; `grep -n "GIGABYTE" frontend/maquette/design/src/features/trackers/trackers-tab.tsx`
  → line **33**: the page writes volumes in « Go » by hand, and no size writer exists — the size, the volumes and the
  rates share ONE writer in `features/trackers/format.ts` (beside `written`, `dayOf`); `grep -rn "export const.*[Pp]rogress"
  frontend/maquette/design/src/ui/variants/card.ts` → `cardStrip` only, a STAGE strip (steps of a journey), not a
  byte-fill bar — a new element, not a redraw of it (DESIGN § 1.8).
- **Points ≈ 15.** R-L16bis-d's facts holds (state, size, popularity, date — each from its field, each absence said —
  and down / up's own three-way switch: volumes by default, the rate while downloading or uploading, no engine
  state read for it — DECIDED 1 is not the eight engine tokens, a `seeding` torrent with no live upload is still the
  default) 2; the state chip, eight words and tones (≈ 15 lines + 8 `fr.json`) 2; the size writer, and the size,
  sources and date as `cardAnnotations` (≈ 20 lines) 2; the progress-bar fill (≈ 10 lines, one variant, not a redraw
  of `cardStrip`, which is a stage strip — a different mechanism) 1; three named states `torrent-card-volumes`,
  `torrent-card-downloading-progress`, `torrent-card-uploading-rate` (re-using the existing seed rows, a new field
  each) — 3 at 1 each 3; states `torrent-card-downloading`, `-stalled`, `-paused`, `-queued`, `-errored`, `-missing`,
  `-no-popularity` (posed) — 7 at ½ each, re-using one pose 3; the report 2.
- **Readers.** `harness/trackers_page.py` reads the ratio `torrents/ratio` — kept on the card.

## Red today

R-L16bis-d's popularity hold over `torrent-card-no-popularity`: nothing drawn (the field does not exist yet in the
drawing). R-L16bis-d's down/up hold over `torrent-card-downloading-progress`: no bar, no rate — the annotation is
absent.

## Move

1. `swarmSeeds: null` is « sources inconnues », `0` is « aucune source » — two sentences (a dead swarm is not an
   unknown one).
2. The date added in the interface's language, day and month (`features/trackers/format.ts`'s `dayOf`).
3. Down / up, per DECIDED 1: nothing active draws `downloadedBytes` / `uploadedBytes`; a live download draws the
   progress bar and `downloadRate`; a live upload (no live download) draws `uploadRate` alone, no bar. Whichever
   fields the client does not say stays « inconnu », never a bar at 0 %.

## Mutation

Draw `0` for a null popularity → the absence hold falls by name. Draw the bar while uploading, or a rate while
neither is active → the state-switch hold falls by name.

## Register

None.

## Oracle: states that diverge, declared by name

Every « Torrents » state (the new lines), declared by script; the ten new states (three of DECIDED 1, seven posed).

## Commit

`feat(maquette-l16bis): a torrent card says its state, size, exchange, sources and date`
