# Phase 6 — The alert, and DOIT-2's ratio reason

Two derived reads, both from fields phase 1 and phase 4 already put in the mock: a per-tracker
ratio alert (DESIGN § 4.5), read at the list, the detail and the panel from ONE field (§13); and
DOIT-2's ratio half — a torrent deferred for ratio, named in Arrivées' existing stuck queue and
cross-referenced to its tracker (DESIGN § 4.6).

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `grep -n "reason" frontend/maquette/design/src/features/arrivals/*.tsx` — the stuck
  queue's existing reason-drawing site this phase extends, never replaces. `grep -n
  "crossReference" frontend/maquette/design/src/features/*/` — the existing helper (L20's
  Maintenance link precedent, DESIGN § 4.6) this phase's tracker link reuses. `python3 -c "import
  json;d=json.load(open('frontend/openapi.json'));print(d['components']['schemas']['StalledGrabItem']['properties']['reason'])"`
  → a plain string field, French, no structured cause code — confirms the ratio-specific wording is
  COMPOSED by the mock, not read from a second field (DESIGN § 2.4). `grep -n B-257 BUGS.md` →
  `fixed #534`, already naming L16 as the alert's consumer — this phase is where that closure's
  promise is kept.
- **Points ≈ 12.** The alert read at three sites (list badge, detail block, panel's own threshold
  display) from one field ≈ 3; one new rule (R-L16-e, §13's agreement across the three readers)
  with its mutation ≈ 3; Arrivées' stuck row gaining a ratio-cause path (invariant 7 — an address,
  never an import) ≈ 2; one new rule (R-L16-g, DOIT-2's reason) with its mutation ≈ 3; one named
  state each side (`tracker-alert-active`, `stalled-ratio-reason`) ≈ 1. Under 15, no cut.

TWO surfaces share this phase because both are the SAME kind of change: a value already answered
(the threshold from phase 4's write, the ratio-cause reason from phase 1's mock) surfaced where an
existing reader already looks — never a write, never a new list of their own.

## The proof FIRST

Two rules, bound to the next two free labels.

- **R-L16-e — what it drives.** Set an alert threshold above a tracker's current ratio (phase 4's
  panel), then read the list row, the detail block, and the panel itself.
- **R-L16-e — what it reads.** All three draw the SAME crossed/not-crossed fact — changing the
  threshold in the panel moves what the list and the detail draw, in the render that follows.
- **R-L16-e — red today.** No alert anywhere — fails against `main` for that reason.
- **R-L16-e — mutation.** `scripts/mutate.sh` disagrees the badge from the block (one reads the
  threshold, the other a stale copy). The agreement must fall.
- **R-L16-g — what it drives.** Arrivées' stuck queue, a row whose `reason` names a ratio cause.
- **R-L16-g — what it reads.** The row's path to `/trackers/$name`, read on the URL after a tap.
- **R-L16-g — red today.** `stalled-grabs` is called by nothing (phase 1 declares it, no reader
  exists yet) — fails against `main` for that reason.
- **R-L16-g — mutation.** `scripts/mutate.sh` drops the path while keeping the reason text. The
  hold must fall, naming the missing address.

## The move

- **The alert.** `screens.trackers.alertBelowThreshold` (« Ratio sous le seuil — <tracker> »), a
  badge on S1's row (`data-part="trackers/alert"`), a block on S2's detail
  (`data-part="tracker/alert"`), all three READING the SAME threshold field the panel (phase 4)
  writes — no push notification drawn (DESIGN § 4.5, filed as a platform demand, not built here).
- **DOIT-2's ratio reason.** In `features/arrivals`, a row whose `stalled-grabs` `reason` names a
  ratio cause gains « Voir le tracker » (`screens.arrivals.stalledRatioTracker`), a PATH
  (`lib/addresses.ts`) to `/trackers/$name` — never an import of `features/trackers` (invariant 7).
- **`i18n/fr.json`** — `screens.trackers.alertBelowThreshold`, `screens.arrivals.stalledRatioTracker`.
- **`harness/states/trackers.ts`** — `tracker-alert-active`.
- **`harness/states/arrivals.ts`** — `stalled-ratio-reason`.

## Mutation

Two mutations, one per rule, each committed and restored separately.

## Register

§ 18's alert clause reads `served` (the in-app half; push stays a filed demand). DOIT-2's row gains
its ratio half — the space half stays untouched, and phase 8's report says so rather than reading
the whole row `served`.

## Oracle: states that diverge, declared by name

**None on `trackers/*`** — `tracker-alert-active` is NEW, drawn on regions phases 2–3 already
record. **On Arrivées' own region (`arrivals/body`)**: the stuck row's HEIGHT may grow by one line
(the new « Voir le tracker » path) where a row's reason names a ratio cause — accepted, named, with
the reason « L16 § 4.6: DOIT-2's ratio-cause rows gain a path to their tracker » — the same shape
L20's phases 3–4 accepted for `system/body`'s length. **Any divergence on a row whose reason is NOT
ratio-caused is a finding, not an acceptance** — the change must not touch what it does not name.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `tracker-alert-active`;
`stalled-ratio-reason`'s divergence on `arrivals/body` accepted with its written reason.

## Commit

`feat(maquette-l16): the ratio alert, and a stuck row's ratio reason names its tracker`
