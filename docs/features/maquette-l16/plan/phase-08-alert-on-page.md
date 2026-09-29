# Phase 8 — The ratio alert on the page

A per-tracker ratio alert, THREE components (DESIGN § 4.5, round 9 Q1 adding the third), read where
the ratio lives — the Trackers tab's entry, the Torrents tab's row — from ONE derivation each (§ 13).
The bar's badge is a fourth reader and is phase 10's. **No push notification is drawn**: it is a
platform demand, filed (DESIGN § 4.5, § 5).

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `git grep -n -i 'alertBelow\|ratio.*threshold\|identifierRefused' --
  frontend/maquette/design/src` → no match (no alert vocabulary exists to reuse). The threshold is SET
  in phase 4's entry and ships in the summary read phase 1 declared; the refused-identifier fact ships
  in the same read (round 9 Q1). `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/features/system/locks.tsx` → 141: the analogue of a block that reads
  one fact and draws it beside a lever (`R-L20-g`'s shape). `grep -n B-257 BUGS.md` → `fixed #534`,
  already naming L16 as the alert's consumer — this phase (and the next) is where that closure's
  promise is kept.
- **Points ≈ 12.** `alertOf` — the one derivation the three components and both surfaces read
  (≈ 15 new, in `features/trackers/`) 1½; the chip on the Trackers-tab entry (≈ 8 new) 1; the breach
  chip on the Torrents-tab row (≈ 10 new) 1; the refused-identifier chip on the entry (≈ 6 new) ½;
  **one new rule, R-L16-d** (three components, two readers) with its mutation 3; three states —
  `tracker-alert-active` needing a new seed row (a tracker under its own threshold) 2,
  `tracker-identifier-refused` needing its own (a refused identifier, distinct seed) 2, the breach
  chip reusing phase 5's obligation seed (no new row: `breached_at` is already a real field) 1;
  `fr.json` (`screens.trackers.alertBelowThreshold`, `.identifierRefused`) 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phase 9 (11, two readers) grows to 12
  for a THIRD component — the refused identifier, round 9 Q1's own addition, absent from every prior
  reading. The point count stays close because this redraw's Torrents-tab breach mark (phase 5) is
  the SAME chip this phase merely WIRES to the derivation, rather than a second block this phase draws
  from nothing, as the prior reading's tracker-detail screen would have needed.

A BEHAVIOUR change: values already answered (the threshold from phase 4's write, the refused fact from
phase 1's read) are surfaced where existing readers already look — never a write, never a new list.

- **2026-09-29, served:** the three states are POSED by dials, no seed row (RULINGS 7); R-L16-d = R264
  `trackers_alert.py`; `alertOf` in `queries.ts` as written; the breach copy `screens.torrents.obligationBreached`.

## The proof FIRST

Its label R-L16-d is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** Set an alert threshold above a tracker's current ratio (phase 4's entry), then
  read the Trackers-tab entry and the Torrents-tab row for that tracker's torrents; separately, a
  tracker whose identifier is refused.
- **What it reads.** All readers draw the SAME crossed / not-crossed fact for the threshold, the SAME
  breach fact for an obligation, and the SAME refused fact for the identifier — changing any of the
  three in its own source moves what every reader draws, in the render that follows; a refused
  identifier counts ONE unit for its tracker (round 10 M5), never one per torrent that tracker holds.
- **Red today.** No alert anywhere — fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` disagrees the entry's chip from the row's breach chip (one reads the
  threshold, the other a stale copy). The agreement must fall. A second mutation joins the refused fact
  against each of the tracker's torrents and counts once per torrent — the per-tracker unit hold must
  fall, naming the inflation (round 10 M5).

## The move

- **`features/trackers/queries.ts`** — `alertOf`, reading the tracker summary and the obligations
  together.
- **`features/trackers/trackers-tab.tsx`** — the alert chip (`data-part="trackers/alert"`) and the
  refused-identifier chip (`trackers/identifier-refused`) on the collapsed row.
- **`features/trackers/torrents-tab.tsx`** — the breach chip (`data-part="torrents/obligation-breached"`)
  on a row whose obligation is in breach.
- **`harness/states/trackers.ts`** — `tracker-alert-active`, `tracker-identifier-refused`,
  `torrent-obligation-breached`.
- **`i18n/fr.json`** — `screens.trackers.alertBelowThreshold`, `.identifierRefused`.

## Mutation

One, as above — committed and restored.

## Register

§ 18's alert clause reads `served` for its in-app half only when phase 10 has landed; reported by
phase 17. Push stays a filed demand.

## Oracle: states that diverge, declared by name

**None on existing states beyond the accepted growth.** `tracker-alert-active`,
`tracker-identifier-refused` and `torrent-obligation-breached` are all NEW; the Torrents tab's
`torrents-list` reading (phase 5) gains a chip only on the row whose seeded obligation is in breach —
accepted, named, with the reason « L16 phase 8: an obligation in breach carries its mark ». **Any
divergence on a row or entry whose tracker is NOT under alert is a finding, not an acceptance.**

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the three new states.

## Commit

`feat(maquette-l16): the ratio alert on the page — one derivation, three components`
