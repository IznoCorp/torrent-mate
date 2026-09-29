# Phase 7 — The removal's shared files, and the external-removal read

Round 9 Q7's own precision: when the removed torrent's files are SHARED with other qBittorrent
entries (a cross-seed of the same content), the confirmation names the consequence and the gesture
takes every sharing entry with it — never one left behind in error. And the HANDLED case ruling 18
simplifies, refined by round 10 M4 and Q4: a torrent removed BY HAND in qBittorrent, its obligation
released CLEANLY (`released_at` set, no in-app call), reads the SAME way this lot's own gesture
leaves it — gone, its trace « Libérée — retrait externe » in Système's history, never a second
« released » list to keep honest against the first. A torrent whose obligation the ENGINE BROKE
(`breached_at` set, no release ever recorded) before it left qBittorrent is a DIFFERENT fact: it does
not just vanish — it is what phase 9's « N obligations rompues » list exists for (round 10 Q4). This
phase draws the first reading (a clean absence); phase 9 draws the second (a broken record that
persists on the tracker).

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"`
  → `released_at` and `satisfied_at` among the 13 fields: the external case is already answerable by
  the read phase 1 declared, once the entry it belongs to is simply ABSENT from the downloads seed
  (no second field to read). `ls frontend/maquette/design/src/mocks/seeds | wc -l` → 48 — a seeded
  scenario where a torrent is already gone from the downloads seed, its obligation's `released_at` set
  and no removal call anywhere in the session's own walk, is a NEW seed row; `python3
  scripts/check-mock-seeds.py` reads it. No mutation can produce this state against `main`: nothing
  there exists to mutate.
- **Points ≈ 9.** The grouped-removal logic in the mock route (≈ 20 new; every entry sharing the
  removed torrent's files is found and removed in the SAME call) 2; the confirmation's shared-files
  copy — the consequence named, every tracker with a running obligation listed (round 9 Q7's
  hit-and-run naming, ≈ 15 new) 1½; **R-L16-c re-aimed** (the grouped hold: every sharing entry gone
  in the same render) with its new mutation 3; the external-removal read (≈ 10 new — an absence,
  never a label) 1; the state `torrent-remove-confirm-shared`, needing a new seed row (two entries
  sharing files, one with a running obligation elsewhere) 2; `fr.json`
  (`screens.torrents.removeSharedConsequence`, the hit-and-run naming) 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** No row of the prior re-read matches this one directly: its
  phase 8 (« an external removal is handled », 8 points) drew a SEPARATE label,
  « Libérée — retrait externe », on a SECOND list the prior reading's own phase 7 kept alive. **This
  redraw deletes that surface outright** (round 9 Q3 kills the second list) and replaces it with the
  simplest possible read — an absence — which costs less (1 of this phase's 9) than the prior
  reading's own dedicated screen text did. The points freed go to round 9 Q7's own new requirement
  (the grouped removal), which the prior reading, written before that ruling, never drew at all.

A BEHAVIOUR change on a state the interface must recognise without ever having caused it, and an
extension of phase 6's own hold to more than one entry.

- **2026-09-29, served:** the external case is POSED (`poseExternalRemoval`, RULINGS 6), not a seed row; the
  shared-files copy lives beside phase 6's, `verbs.trackers.remove.shared`; the shared subject needs no new seed
  (President Curtis on c411 / tr4ker).

## The proof FIRST

R-L16-c re-aimed (its label was bound in phase 2).

- **What it drives.** From `/trackers?tab=torrents`, remove a torrent whose files are shared with a
  cross-seeded entry on another tracker; separately, a SEEDED torrent whose `released_at` is already
  set (a clean external release) with no removal call anywhere in the session's own walk.
- **What it reads.** The confirmation naming the consequence and every tracker with a running
  obligation; BOTH entries gone from the Torrents tab in the SAME render the operation answers; the
  seeded CLEAN external case reading as simply ABSENT — never still active, never a label of any
  kind. (A seed whose obligation is `breached_at`-only, never released, is phase 9's own case, not
  drawn as an absence here — DESIGN § 4.4.)
- **Red today.** Neither case exists to read — fails against `main` for that reason; **no mutation is
  needed or possible** for the external case (nothing to mutate), the same shape L20's phase 1 rules
  held for surfaces that do not exist yet.
- **Mutation.** `scripts/mutate.sh` leaves the cross-seeded sibling entry present after the removal —
  the grouped hold must fall, naming the entry left behind.

## The move

- **The mock route (phase 6's)**, extended: removing one entry finds every OTHER entry sharing its
  files (by `info_hash`'s underlying identity, or the mock's own join) and removes them all, moving
  every matching obligation to `released_at` set in the SAME call.
- **The confirmation's copy**, when files are shared: names the consequence (every share of these
  files ends) and lists each tracker with a running obligation (the hit-and-run risk).
- **The external-removal read**: a CLEANLY-released entry (`released_at` set) the mock's seed never
  carries as active reads as simply ABSENT from the Torrents tab — no label, no button, no row. A
  BROKEN entry (`breached_at` set, no release) is left to phase 9's own list.
- **The seed** and **`harness/states/trackers.ts`** — `torrent-remove-confirm-shared`.
- **`i18n/fr.json`** — `screens.torrents.removeSharedConsequence`.

## Mutation

The one above — committed and restored.

## Register

§ 18's external-removal HANDLED case reads `served` for its CLEAN half, by an absence rather than a
label on this page — reported by phase 17, which also notes the prior reading's « Libérée — retrait
externe » surface never lands ON TRACKERS (it moves to Système's history, L20's, a design correction,
not a scope cut). The BROKEN half is phase 9's.

## Oracle: states that diverge, declared by name

**None.** `torrent-remove-confirm-shared` is NEW, drawn on `trackers/body`'s existing region. Any
change to the Trackers tab's own recorded reading (phases 3, 4) is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `torrent-remove-confirm-shared`.

## Commit

`feat(maquette-l16): a shared-files removal names its consequence, and an external removal reads as gone`
