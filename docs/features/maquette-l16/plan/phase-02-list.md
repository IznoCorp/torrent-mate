# Phase 2 — The trackers list, and its host

A new page, `features/trackers/page.tsx`: one row per tracker, its ratio, its trend, its Download /
Upload volumes (DESIGN § 4.1). Its own address, `/trackers`, and a navigation row whose `inBar`
value follows the operator's ruling on DESIGN § 5's open question, or Reading B (the drawer) by
default until it lands.

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `ls frontend/maquette/design/src/features/` → `account`, `acquisition`,
  `arrivals`, `library`, `maintenance`, `media`, `releases`, `settings`, `system` — no `trackers`.
  `grep -n "id: \"" frontend/maquette/design/src/app/navigation.ts` → 8 rows (`acq`, `lib`, `arr`,
  `sys`, `maint`, `cfg`, `profile`, `404`); `grep -c "inBar: false"
  frontend/maquette/design/src/app/navigation.ts` → `4`. `sed -n '20,27p'
  frontend/maquette/design/src/lib/addresses.ts` → `PAGE_PATHS` holds 7 entries, none named
  `trackers`. `ls frontend/maquette/design/src/routes/` → 14 files, no `trackers.tsx`. `ls
  frontend/maquette/design/src/harness/states/` → 11 files, no `trackers.ts`. `grep -c
  "\"tracker\"\|screens.tracker" frontend/maquette/design/src/i18n/fr.json` → `0` (the two
  `settings.labels.max_per_tracker` / `timeout_per_tracker` keys are unrelated config labels, not
  this domain). `grep -n "$name\b" frontend/maquette/design/src/lib/addresses.ts | grep -c
  SCREEN_PARENTS` — informational only, phase 3's concern.
- **Points ≈ 9.** New page + route + `PAGE_PATHS` entry + navigation row ≈ 4; one new rule
  (R-L16-h's list half — the page resolves, its region records) with its mutation ≈ 3; four named
  states (`trackers-list`, `trackers-empty`, `trackers-loading`, `trackers-error`) ≈ 2. Under 15, no
  cut.

A BEHAVIOUR change: the list did not exist; it now reads three operations phase 1 declared and
draws them per tracker, never averaged (§ 18's own first clause).

## The proof FIRST

- **What it drives.** Navigate to `/trackers` (or the drawer entry, per the ruling).
- **What it reads.** Each row's ratio, trend and volumes, compared against the mock's own field for
  that tracker — never a client-side mean across rows.
- **Red today.** `/trackers` resolves nowhere (no route, no `PAGE_PATHS` entry) — the rule fails
  for exactly that reason against `main`.
- **Mutation.** `scripts/mutate.sh` makes a row compute its trend or its ratio from a DIFFERENT
  tracker's field (a swapped index). The rule must fall, naming the mismatched tracker.

## The move

- **`features/trackers/page.tsx`** — the roster, one row per tracker (`data-part="trackers/row"`),
  its ratio (`screens.trackers.ratio`), trend (`screens.trackers.trend`, in words —
  NE-DOIT-PAS-4), volumes (`screens.trackers.volumes`). A row is a `data-tracker="<name>"` PATH to
  `/trackers/$name` (phase 3's screen — the route may 404 gracefully until then, or phase 3 lands
  in the same round; the plan's phases chain, DESIGN's own instruction).
- **`routes/trackers.tsx`** — the route file, thin, per the existing precedent
  (`component: () => null`, the page's body drawn from `NAVIGATION.Body`).
- **`lib/addresses.ts`** — `PAGE_PATHS.trackers = "/trackers"`.
- **`app/navigation.ts`** — one new row, `id: "trackers"`, `path: PAGE_PATHS.trackers`, `Body:
  TrackersPage`, `labelKey: "navigation.pages.trackers"`, an icon (`app/icons.ts` gains one if none
  fits — the ratio's own icon, not reused from an unrelated domain), `inBar` and `group` per
  DESIGN § 5's ruling or Reading B by default.
- **`harness/states/trackers.ts`** — the four named states, `data-region="trackers/body"`
  registered in `regions.json`.
- **`i18n/fr.json`** — `screens.trackers.ratio`, `.trend`, `.volumes`, `.empty`;
  `navigation.pages.trackers`.

## Mutation

`scripts/mutate.sh` swaps one row's drawn tracker for its neighbour's field. The rule must fall,
naming which tracker's ratio was drawn under the wrong name.

## Register

DOIT-13's row moves from `to draw` toward its first half `served` — the per-tracker read, not yet
the write (phase 4) or the alert (phase 6). The closing phase (8) reads and reports the exact
wording, not this one.

## Oracle: states that diverge, declared by name

**None.** `trackers-list`, `trackers-empty`, `trackers-loading`, `trackers-error` are NEW — the
reference records them and proves nothing about them (D8). No EXISTING state's region changes:
this phase adds a page, not a row to one that already exists. Any divergence elsewhere is
**STOP A**.

## Gate

Per INDEX « Gates ». Additionally: `python3 frontend/maquette/oracle.py --record` for the four new
states × `trackers/body`.

## Commit

`feat(maquette-l16): the trackers list, one row per tracker, never averaged`
