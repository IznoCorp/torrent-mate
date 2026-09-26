# Phase 11 — A card deferred for ratio names its tracker

DOIT-2's ratio half (DESIGN § 4.6): a medium deferred for ratio reads its cause on its **acquisition card** in « En cours », and the card carries a
path to the tracker that holds the obligation. **`stalled-grabs` is declared here**, with the surface that calls it (INDEX, « Why fifteen phases »). The
first drawing put this on Arrivées' stuck queue; that page dies at L22b, and the surface DOIT-2 moves to is the card (L22 § 6.3, ruling 7).

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `git grep -n -w 'stalled-grabs' -- frontend/maquette` → one comment, in `features/acquisition/panel-more.ts:8`: **nothing consumes the
  operation**. `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['StalledGrabItem']['properties']))"`
  → `episode`, `info_hash`, `kind`, `reason`, `release_name`, `season`, `since`, `title`, `wanted_id`; `reason` is a plain string (`{'title': 'Reason',
  'type': 'string'}`), French, with no structured cause code — the ratio-specific wording is COMPOSED by the mock from the obligation it defers against
  (DESIGN § 2.4), not read from a second field. The rollup's docstring (`frontend/openapi.json`, `stalled_grabs`) says these are the acquisitions parked at
  « récupéré » that never reached the library, « DISTINCT de `stuck` ». `ls frontend/maquette/design/src/mocks/seeds | grep -i 'block\|wait\|in-flight\|moving'`
  → `blocked.json`, `in-flight.json`, `moving.json`; no seed names a ratio cause. `git grep -n 'crossReference()' -- frontend/maquette/design/src` → seven
  draws, of which `features/system/locks.tsx:146` (toward Maintenance) is the precedent; the one in `features/acquisition/now-tab.tsx:106` goes to Arrivées and
  dies at L22b's phase 21. `grep -n B-257 BUGS.md` → `fixed #534`.
- **Found (2026-09-26) — STOP D, the one already known.** **No card of the mock's seeds is deferred for ratio**, and § 13 forbids inventing data. The steward
  decides, at the opening, between (a) re-casting a real waiting card under the ratio reason its obligation composes — a derivation, shown as one — and (b)
  drawing the state from its seed marked `x-unseeded`, the contract's own word for « nothing was invented here » and « nobody looked » being different things
  (the precedent L22's phases 9 and 10 set). The cost is the same either way (the seed row counted below).
- **Points ≈ 12.** `stalled-grabs` declared new 2 and its mock route new 2 (the reason composed from phase 1's obligation, never a second fact); the card's
  path — « Voir le tracker », a `crossReference()` toward `/trackers/$name` in `features/acquisition` (≈ 15 new; an address, never an import of
  `features/trackers`, invariant 7) 2; **one new rule, R-L16-g** with its mutation 3; the state `acq-card-ratio-reason`, needing a new seed row (the STOP D)
  2; `fr.json` (`screens.acquisition.ratioReasonTracker`) 1.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (the DOIT-2 half of its phase 6, on Arrivées' stuck row) → this phase **12**: moved by **the
  scale** and by **the rulings that kill Arrivées** (organisation rulings 2 and 7 of 2026-09-15, through L22): the surface is a card, not a row of a page that
  will not exist, and the state moves from `arrivals.ts` to `acquisition.ts`. It comes after phases 9 and 10 because the card names a tracker one can now open
  and a threshold one can now read.

A BEHAVIOUR change on an existing surface: the card says why it waits, and where.

## The proof FIRST

Its label R-L16-g is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** The acquisition card whose `reason` names a ratio cause, in « En cours ».
- **What it reads.** The card's path to `/trackers/$name`, read on the URL after a tap; the reason in full, never truncated (a card's reason is what the
  operator decides on — L22 § 3.2).
- **Red today.** `stalled-grabs` is called by nothing and no card names a ratio — fails against `main` for that reason.
- **Mutation.** `scripts/mutate.sh` drops the path while keeping the reason text. The hold must fall, naming the missing address.

## The move

- **The operation**, declared in the maquette's contract (`GET /api/acquisition/stalled-grabs`, `StalledGrabsResponse`, seeded from the backend's own shape)
  and answered by a mock route composing the ratio reason from the obligation.
- **`features/acquisition`** — the card gains « Voir le tracker » (`screens.acquisition.ratioReasonTracker`) where its reason names a ratio cause: a PATH
  (`lib/addresses.ts`) to `/trackers/$name`, never an import of `features/trackers`.
- **`harness/states/acquisition.ts`** — `acq-card-ratio-reason`.
- **`i18n/fr.json`** — `screens.acquisition.ratioReasonTracker`.

## Mutation

One, as above — committed and restored.

## Register

DOIT-2's row gains its ratio half; the space half stays untouched, and phase 15's report says so rather than reading the whole row `served`. The row's
surface is proposed as `features/acquisition` by L22 (its § 6.3); the map is the operator's.

## Oracle: states that diverge, declared by name

**None on other states.** `acq-card-ratio-reason` is NEW. **On Acquisition's own region**: the card's HEIGHT may grow by one line where its reason names a ratio
cause — accepted, named, with the reason « L16 § 4.6: DOIT-2's ratio-cause cards gain a path to their tracker ». **Any divergence on a card whose reason is NOT
ratio-caused is a finding, not an acceptance** — the change must not touch what it does not name.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for `acq-card-ratio-reason`.

## Commit

`feat(maquette-l16): a card deferred for ratio names its tracker`
