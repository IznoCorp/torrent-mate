# Phase 12 — A card deferred names its tracker

DOIT-2's ratio half (DESIGN § 4.6), corrected against F14: a medium deferred reads its cause on its
**acquisition card** in « En cours », for ALL THREE of DOIT-2's kinds — ratio, insufficient space,
missing content — not the ratio one alone, and its reason is NOT composed from `stalled-grabs` (a
different rollup, F14, DESIGN § 2.5). **A new demand is filed here** (`classify_deferrals`, exposed on
a route this lot's query can call), with the surface that names it (INDEX, « Why seventeen phases »).

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `git grep -n -w 'stalled-grabs' -- frontend/maquette` → one comment, in
  `features/acquisition/panel-more.ts:8` (phase 11 removes the panel it sits beside; the comment
  itself is untouched, since it names an operation, not a fact this lot draws): **nothing consumes the
  operation, and this lot declares it for no surface**. `sed -n '1,45p' personalscraper/ingest/deferral.py`
  → `classify_deferrals` reads a torrent's own hold, never the legacy top-level `ingest.min_ratio`
  key for a ratio cause; `grep -n 'min_ratio' personalscraper/ingest/deferral.py` → line 12 and 39,
  BOTH reading the OBLIGATION's own `min_ratio`, never the global key (confirming F14's own finding:
  the legacy key is dead code for this path, not the source a card should ever name). `git grep -n
  'crossReference()' -- frontend/maquette/design/src` → seven draws, of which
  `features/system/locks.tsx:146` (toward Maintenance) is the precedent; the one in
  `features/acquisition/now-tab.tsx:106` goes to Arrivées and dies at L22b's phase 21.
- **Found (2026-09-27) — STOP D, the one already known, now across three kinds.** **No card of the
  mock's seeds is deferred for any of the three reasons**, and § 13 forbids inventing data. The steward
  decides, at the opening, per kind: (a) re-casting a real waiting card under the reason its cause
  composes — a derivation, shown as one — or (b) drawing the state from its seed marked `x-unseeded`
  (the precedent L22's phases 9 and 10 set). The cost is the same either way, per kind (counted
  below).
- **Points ≈ 13.** **`classify_deferrals`'s route declared new** (a demand, § 2.3) 2; the card's reason
  drawn for all three kinds, one derivation shared, three named states (≈ 20 new) 2; the ratio kind's
  path — « Voir le tracker », a `crossReference()` toward `/trackers?tab=trackers&tracker=$name` in
  `features/acquisition` (≈ 15 new; an address, never an import of `features/trackers`, invariant 7)
  2; **one new rule, R-L16-g** with its mutation 3; three states, each needing a new seed row (the
  STOP D, per kind) 2×3 = 6, minus one already counted in the states line above — net 4; `fr.json`
  (three reason sentences, `.ratioReasonTracker`) 1.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phase 11 (12, the ratio kind alone,
  sourced from `stalled-grabs`) is CORRECTED, not merely renamed: F14 found its own source wrong (a
  different rollup composing a matching sentence, exactly the invention § 2.4 already forbade) and its
  own scope short (DOIT-2 names three kinds, the prior reading drew one). The point count grows only
  slightly (12 → 13) because most of the added scope (two more kinds) reuses the SAME derivation and
  the SAME rule, drawn once and read three ways.

A BEHAVIOUR change on an existing surface: the card says why it waits, for any of the three reasons,
and where — for the ratio one.

- **2026-09-29, corrected:** the opening measure above is WRONG — `deferral.py:73` reads the GLOBAL
  `ingest.min_ratio` (RULINGS 10, a demand in the contract); « Voir le tracker » goes to
  `/trackers?list=trackers&tracker=$name` (RULINGS 1), not `?tab=`; served as 12a (the causes) / 12b (the path);
  the three causes are POSED on « This City Is Ours », the one card of « En vol » not yet arrived.

## The proof FIRST

Its label R-L16-g is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** The acquisition card whose deferral names a ratio, space, or missing-content
  cause, in « En cours ».
- **What it reads.** The reason drawn matches the KIND `classify_deferrals` answers, never a sentence
  composed from an unrelated rollup; for the ratio kind, the path to `/trackers`, read on the URL
  after a tap, and the ratio hold it names equal to the tracker's OWN `ObligationItem.min_ratio`,
  never the legacy `ingest.min_ratio`.
- **Red today.** No card names any of the three causes and no route answers `classify_deferrals` —
  fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` drops the path while keeping the reason text (ratio kind) — the hold
  must fall, naming the missing address. A second mutation names the legacy `ingest.min_ratio` instead
  of the obligation's own — the hold must fall too.

## The move

- **The demand**, filed as a proposed route exposing `classify_deferrals`'s own answer: the reason
  KIND (ratio / space / missing) and, for ratio, the tracker's name and its obligation's `min_ratio`.
- **`features/acquisition`** — the card's current rung reads the reason kind (extending L22's demand
  B, which already carries a reason token per rung); for the ratio kind it gains « Voir le tracker »
  (`screens.acquisition.ratioReasonTracker`), a PATH (`lib/addresses.ts`) to
  `/trackers?tab=trackers&tracker=$name`, never an import of `features/trackers`.
- **`harness/states/acquisition.ts`** — `acq-card-deferred-ratio`, `acq-card-deferred-space`,
  `acq-card-deferred-missing`.
- **`i18n/fr.json`** — the three reason sentences, `screens.acquisition.ratioReasonTracker`.

## Mutation

Two, as above — each committed and restored separately.

## Register

DOIT-2's row gains ALL THREE of its deferral kinds this time, not the ratio one alone; the row's
surface is proposed as `features/acquisition` by L22 (its § 6.3); the map is the operator's. Reported
precisely by phase 17, which also notes the prior reading's single `acq-card-ratio-reason` state never
lands (split into three, F14).

## Oracle: states that diverge, declared by name

**None on other states.** The three named states are NEW. **On Acquisition's own region**: a card's
HEIGHT may grow by one line where its reason names any of the three causes — accepted, named, with the
reason « L16 § 4.6: DOIT-2's deferral-cause cards gain their reason and, for ratio, a path ». **Any
divergence on a card whose reason is none of the three is a finding, not an acceptance** — the change
must not touch what it does not name.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the three new states.

## Commit

`feat(maquette-l16): a deferred card names its reason, and its tracker for a ratio cause`
