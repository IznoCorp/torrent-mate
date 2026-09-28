# Phase 5 — The « Torrents » tab: every active entry, once

One row per qBittorrent entry active on ANY tracker (ORGANISATION RULING 18, round 9 Q3 —
replacing the prior reading's two doubling lists outright): the ratio ON THIS TRACKER computed on the
torrent's OWN SIZE, its deadline, its origin colour, and its obligation as a MARK, never a second
list. « Retirer de qBittorrent » is phase 6's; this phase draws the rows and the tracker filter.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"`
  → 13 fields, `source_tracker` the join key, `breached_at` / `satisfied_at` / `released_at` the three
  MARKS this phase draws (never a second list). `python3 -c "import
  json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['AcquisitionDownload']['properties']))"`
  → no tracker, no ratio, no deadline on the backend's own shape — **the maquette's declared shape
  (phase 1) carries them**, extended with the origin flag ruling 18's colour needs.
  `frontend/maquette/harness/paths_to_sheets.py` — six fixed surfaces today, `data-part` `card` /
  `tile` only (F18): this phase's rows extend `R122`'s selector to `torrents/title`, with a floor and
  the mutation « drop the path → falls ». `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/features/system/run-list.tsx` → 176 (the analogue for a list of rows
  with a deadline-like line each, richer here — a ratio, a colour, up to three marks).
- **Points ≈ 14.** The rows in `torrents-tab.tsx` (≈ 55 new; title as a path, tracker name, ratio on
  size, deadline, origin colour, up to three obligation marks) 5½; the tracker filter reading
  `trackersFilter` client-side (≈ 10 new) 1; **R-L16-a re-aimed** to the torrents-tab rows 1; **`R122`
  re-aimed** (`paths_to_sheets.py`'s selector gains `torrents/title`) 1; four states —
  `torrents-list` re-using phase 1's downloads seed 1, `torrents-list-filtered` re-using the same 1,
  `torrents-empty` needing a new seed row (nothing active anywhere) 2, `torrents-empty-filtered`
  needing its own (a tracker with nothing active, others with something) 2; `fr.json`
  (`screens.torrents.empty`, `.emptyFiltered`, the deadline's phrasing) 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phases 4–5 (13 + 14, the tracker-detail
  screen's head and lists) are GONE — ruling 19 kills the screen they lived on. This phase is their
  successor in substance (a torrent's own deadline and ratio) but drawn GLOBALLY, across every
  tracker, and MERGED with what the prior phase 5 kept as a second list (the obligations) — round 9
  Q3's own ruling. The point count (14) lands close to the prior phase 5 alone (14) because the merge
  and the filter roughly offset what a second, per-tracker address would have cost.

A BEHAVIOUR change: the tab did not exist; it now reads the downloads and obligations together and
draws one row per active entry, anywhere.

**Inherited from L22 RULINGS 25 (auditor and steward, 2026-09-27; L22b phase 31, STOP D), written in by the
steward at L22's close.** A direct add is a card only once « arrivé »; a downloading direct add — « Les Zinzins de
l'Espace », real, in `moving.json` — stays in « En vol », against the letter of ruling 2, a temporary gap named
there and closed here:

- **The card's removal.** Zinzins's « En vol » card, downloading, leaves — no direct-add card before « arrivé »
  once this phase ships (F5, ruling 25 scoped (a)).
- **A new hold, « Zinzins downloading is readable in Torrents ».** The Torrents tab's own row (above) is where a
  downloading direct add is now read, exactly like any other active qBittorrent entry; a mutation that drops
  Zinzins's row, or reads it back under « En vol », must fall by name.
- **`R229` (`frontend/maquette/harness/follow_offered.py`) re-aimed on a real subject.** Zinzins, downloading and
  real, becomes the rule's own case for « never proposes « Suivre » before a series has arrived » — the phase-17
  offer's hold, until now proved on no real row, is proved on this one.

## The proof FIRST

R-L16-a re-aimed (its label was bound in phase 2); `R122` re-aimed.

- **What it drives.** `/trackers?tab=torrents` with several trackers active, then filtered to one via
  `?tracker=$name`; tap a row's title.
- **What it reads.** Every ratio drawn compared against the mock's own field, computed on the
  torrent's size (never the tracker's own download volume — the exact hold that keeps a cross-seeded
  entry from a division by zero); the filtered view showing ONLY the named tracker's rows; the title's
  path landing on `/media/:provider/:id` (or `/resolution/:folder`), read on the URL after a tap.
- **Red today.** The rows do not exist to read — fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` draws a row's ratio using the TRACKER's own download volume instead
  of the torrent's size — the comparison must fall, naming the row. A second mutation drops the
  title's path while keeping its text — `R122`'s hold must fall, naming the missing address.

## The move

- **`features/trackers/torrents-tab.tsx`** — the rows (`data-part="torrents/row"`), the title path
  (`torrents/title`), the tracker name (`torrents/tracker`), the ratio (`torrents/ratio`), the
  deadline (`torrents/deadline`), the origin colour (`torrents/origin`), the obligation marks
  (`torrents/obligation-open`, `torrents/obligation-done`; the breach mark is phase 8's, on the same
  row); the tracker filter, reading `trackersFilter`.
- **`frontend/maquette/harness/paths_to_sheets.py`** — `R122`'s SURFACES gains the Torrents-tab row,
  selector `torrents/title`.
- **`harness/states/trackers.ts`** — `torrents-list`, `torrents-list-filtered`, `torrents-empty`,
  `torrents-empty-filtered`.
- **`i18n/fr.json`** — `screens.torrents.empty`, `.emptyFiltered`, the deadline's phrasing.

## Mutation

Two, as above — each committed and restored separately.

## Register

DOIT-13's row gains its per-torrent half — « par torrent actif son échéance et son ratio » — served;
DOIT-2's obligation-as-reason clause (§ 8) reads served on this surface too, reported precisely by
phase 16.

## Oracle: states that diverge, declared by name

**None.** All four states are NEW. The region `trackers/body`'s content changes with the second tab's
rows, which the oracle records as new, not as a divergence of an existing state (D8). Any divergence
on the « Trackers » tab (phases 3–4's own region) is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the four new states.

## Commit

`feat(maquette-l16): the Torrents tab, every active entry once, its ratio on its own tracker`
