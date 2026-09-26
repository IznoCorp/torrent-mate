# Phase 9 — The alert on the page

A per-tracker ratio alert (DESIGN § 4.5), read where the ratio lives — the roster's row, the detail's block, the policy panel's own threshold —
from ONE field (§ 13). The bar's badge is a fourth reader and is phase 10's; a card's ratio reason is phase 11's. **No push notification is
drawn**: it is a platform demand, filed (DESIGN § 4.5, § 5).

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `git grep -n -i 'alertBelow\|ratio.*threshold' -- frontend/maquette/design/src` → no match (no alert vocabulary exists to reuse).
  The threshold is SET in phase 6's panel and ships in the summary read phase 1 declared: `python3 -c "import
  json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if 'tracker' in p])"` at this phase's opening reads
  the summary path. `grep -n B-257 BUGS.md` → `fixed #534`, already naming L16 as the alert's consumer — this phase (and the next) is where that
  closure's promise is kept. `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/system/locks.tsx` → 141: the analogue of a block that
  reads one fact and draws it beside a lever (R-L20-g's shape).
- **Points ≈ 11.** The alert badge on the roster's row (≈ 8 new) 1; the alert block on the detail (≈ 20 new) 2; the panel's own threshold display
  (≈ 4 edited) 1; the one derivation the three read — `alertOf` in `features/trackers/` (≈ 10 new) 1; **one new rule, R-L16-e** (three readers, one
  field) with its mutation 3; the state `tracker-alert-active`, needing a new seed row (a tracker whose ratio is under its threshold — the mock's
  own, derived from the roster) 2; `fr.json` (`screens.trackers.alertBelowThreshold`) 1.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (the alert half of its phase 6) → this phase **11**: moved by **the scale**, and the
  first drawing's DOIT-2 reason half is now phase 11 (it is a card's, not Arrivées'). **Ruling 12 moved what the alert IS**: it speaks where it
  lives and takes a badge on its tab — no box, no Système line — so the alert has a fourth reader, which is the next phase; this phase draws the three
  that live on the ratio's own page.

A BEHAVIOUR change: a value already answered (the threshold from phase 6's write) is surfaced where an existing reader already looks — never a
write, never a new list.

## The proof FIRST

Its label R-L16-e is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** Set an alert threshold above a tracker's current ratio (phase 6's panel), then read the roster's row, the detail's block, and
  the panel itself.
- **What it reads.** All three draw the SAME crossed/not-crossed fact — changing the threshold in the panel moves what the row and the block draw,
  in the render that follows.
- **Red today.** No alert anywhere — fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` disagrees the badge from the block (one reads the threshold, the other a stale copy). The agreement must fall.

## The move

- **The alert.** `screens.trackers.alertBelowThreshold` (« Ratio sous le seuil — <tracker> »), a badge on the roster's row (`data-part="trackers/alert"`),
  a block on the detail (`data-part="tracker/alert"`), all reading the SAME threshold the panel writes through `alertOf` — no push notification
  drawn, **no notifications box and no line on Système** (organisation ruling 12).
- **`harness/states/trackers.ts`** — `tracker-alert-active`, read on the roster and on the detail (DESIGN § 4.2 and § 4.5 name the same state).
- **`i18n/fr.json`** — `screens.trackers.alertBelowThreshold`.

## Mutation

One, as above — committed and restored.

## Register

§ 18's alert clause reads `served` for its in-app half only when phase 10 has landed; reported by phase 15. Push stays a filed demand.

## Oracle: states that diverge, declared by name

**None on existing states.** `tracker-alert-active` is NEW, drawn on regions phases 3 to 5 already record: a row whose ratio is under its threshold gains
a badge, so `trackers-list` and `tracker-detail` change ONLY where a seeded tracker is under its threshold — if the seeds put none under it, both stay
at zero, and if one is, the divergence is accepted, named, with the reason « L16 phase 9: a tracker under its threshold carries its alert ». **Any
divergence on a row whose tracker is NOT under its threshold is a finding, not an acceptance.**

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `tracker-alert-active`.

## Commit

`feat(maquette-l16): the ratio alert on the page — one derivation, three readers`
