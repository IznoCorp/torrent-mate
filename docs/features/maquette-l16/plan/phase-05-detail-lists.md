# Phase 5 — The detail's obligations and active torrents

What hangs off the head (DESIGN § 4.2): the tracker's **obligations** — each with its deadline and its ratio owed against observed —
and its **active torrents**, each with its own deadline and ratio (DESIGN § 2.3 item 3's demand, in the shape phase 1 settled). The
release verb on an obligation is phase 7's; this phase draws the rows.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"`
  → 13 fields, `source_tracker` the join key (`min_ratio`, `observed_ratio`, `min_seed_time_s`, `accumulated_seed_time_s`, `added_at`,
  `breached_at`, `satisfied_at`, `released_at`). `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['AcquisitionDownload']['properties']))"`
  → no tracker, no ratio and no deadline field on the backend's shape (DESIGN § 2.1) — **the maquette's declared shape (phase 1) carries
  them**; the phase reads whichever reading phase 1 took (the extended download, or the tracker-keyed join the summary read carries).
  `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/system/run-list.tsx` → 176 (the analogue for a list of rows with a
  deadline-like line each; a list of ≈ 50 lines is the smaller case). `ls frontend/maquette/design/src/mocks/seeds | wc -l` → 48 — the
  seeds phase 1 added are the two lists' source; **a tracker with NO active torrent** (the state `tracker-detail-empty-active`) needs one
  more seed row.
- **Points ≈ 14.** The obligations list (≈ 55 new; each row: title, deadline, ratio owed against observed, the state open / satisfied) 5½;
  the active torrents list (≈ 40 new; each row: title, deadline, its own ratio) 4; **R-L16-a re-aimed** to the per-torrent list 1; the state
  `tracker-detail-empty-active` (« Rien en cours sur ce tracker. »), needing a new seed row 2; `fr.json` (`screens.tracker.emptyActive`, the
  deadline's own phrasing) 1. **Nearly at the ceiling; what to cut**: the active torrents' list and the empty state, as their own phase.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 3, lists half) → this phase **14**: moved by **the scale**; no ruling
  touched it. § 8 holds unchanged: a tracker with nothing running says so, it is not a blank.

A BEHAVIOUR change: the lists did not exist; they read phase 1's operations, filtered to one tracker.

## The proof FIRST

R-L16-a re-aimed (its label was bound in phase 2).

- **What it drives.** `/trackers/$name` for a tracker with obligations and active torrents, then for one with none active.
- **What it reads.** Every ratio drawn in the lists compared against the mock's own field (owed against observed for an obligation, the
  torrent's own for an active one) — never a computation; the empty answer reads « Rien en cours sur ce tracker. ».
- **Red today.** The lists do not exist to read — fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` draws an obligation's ratio as the tracker's (the head's) instead of its own — the comparison must fall,
  naming the row.

## The move

- **`features/trackers/tracker-screen.tsx`** — the obligations (`data-part="tracker/obligation"`) and the active torrents
  (`data-part="tracker/torrent"`), each with its deadline and its ratio; the release verb's place on the obligation row is left for phase 7.
- **`harness/states/trackers.ts`** — `tracker-detail-empty-active`.
- **`i18n/fr.json`** — `screens.tracker.emptyActive`, and the deadline's phrasing.

## Mutation

One, as above — committed and restored.

## Register

DOIT-13's row gains its per-tracker DETAIL half; reported precisely by phase 15.

## Oracle: states that diverge, declared by name

**None.** `tracker-detail-empty-active` is NEW. The region `tracker/body`'s CONTENT changes with the new rows, which the oracle records as new,
not as a divergence of an existing state (D8: a state that did not exist cannot diverge) — but **`tracker-detail`'s own recorded reading (phase
4: the head alone) grows by the two lists**, and that is a divergence on a state THIS lot recorded one phase earlier: it is accepted with the
reason « L16 phase 5: the detail draws its obligations and active torrents » and named. Any divergence elsewhere is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `tracker-detail-empty-active`.

## Commit

`feat(maquette-l16): a tracker's obligations and its active torrents, each with its deadline and ratio`
