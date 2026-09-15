# Phase 3 — A tracker's detail

`/trackers/$name` (DESIGN § 3, § 4.2): the head repeats the list row's own ratio, volumes and trend
(§13 — one derivation, drawn twice from the same read), then the tracker's obligations — each with
its deadline and its ratio owed vs. observed — and its active torrents, each with its own deadline
and ratio (DESIGN § 2.3 item 3's demand).

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `sed -n '/SCREEN_PARENTS/,/};/p' frontend/maquette/design/src/lib/addresses.ts` →
  six entries (`/add`, `/quality/$name`, `/media/$provider/$id`, `/releases/$title`,
  `/resolution/$folder`, `/run/$runUid`), none for a tracker. `python3 -c "import
  json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"`
  → `accumulated_seed_time_s`, `added_at`, `breached_at`, `dispatched_path`, `hnr_count`,
  `info_hash`, `min_ratio`, `min_seed_time_s`, `observed_ratio`, `released_at`, `satisfied_at`,
  `source_tracker`, `title` — 13 fields, `source_tracker` already the join key this screen filters
  on. `grep -n B-144 BUGS.md` → `open`, 1× (the read half this phase and phase 2 together answer).
- **Points ≈ 11.** New screen file + route entry + `SCREEN_PARENTS` entry ≈ 3; one new rule
  (R-L16-a, NE-DOIT-PAS-1 — the ratio is the tracker's, drawn at both the list and here) with its
  mutation ≈ 3; the address rule (R-L16-h, content-tier push) with its mutation ≈ 3; two named
  states plus the two the contract requires (`tracker-detail`, `tracker-detail-empty-active`,
  `tracker-detail-loading`, `tracker-detail-error`) ≈ 2. Under 15, no cut.

A BEHAVIOUR change: the screen did not exist; it reads the same operations phase 2's list does,
filtered to one tracker, plus the active-torrents demand's shape once phase 1 has settled which
reading it took.

## The proof FIRST

Its label is bound to the next free number, re-taken against `origin/main`.

- **What it drives.** From `/trackers`, tap a row.
- **What it reads**:
  1. the ratio, volumes and trend drawn at the head, compared against the SAME field the list row
     read for that tracker (R-L16-a);
  2. the URL, `/trackers/$name`, and `history.length` before and after the tap (R-L16-h — opening a
     content-tier surface PUSHES, D1b rule 1).
- **Red today.** `/trackers/$name` resolves nowhere — both rules fail for that reason against
  `main`.
- **Mutation.** For R-L16-a: `scripts/mutate.sh` swaps the head's ratio for a different tracker's
  field — the comparison must fall, naming the mismatch. For R-L16-h: make the route REPLACE
  instead of push — the `history.length` hold must fall.

## The move

- **`features/trackers/tracker-screen.tsx`** — the head (ratio, volumes, trend,
  `data-part="tracker/ratio"` etc.), the obligations list (`data-part="tracker/obligation"`, each
  with its deadline and ratio owed/observed — the release verb itself is phase 5's, this phase
  draws the row only), the active torrents (`data-part="tracker/torrent"`, each with its deadline
  and ratio).
- **`routes/tracker.tsx`** — the screen route.
- **`lib/addresses.ts`** — `SCREEN_PARENTS["/trackers/$name"] = "trackers"`.
- **`harness/states/trackers.ts`** — `tracker-detail`, `tracker-detail-empty-active` (« Rien en
  cours sur ce tracker. »), plus loading/error.
- **`i18n/fr.json`** — `screens.tracker.emptyActive`, and the head's labels if they diverge from
  the list's own keys (§13 — reuse `screens.trackers.ratio` etc. where the SAME derivation applies;
  a new key only where the sentence genuinely differs, e.g. a deadline's own phrasing).

## Mutation

Two mutations, one per rule, as above — each committed and restored separately (INDEX's « commit
before every mutation »).

## Register

DOIT-13's row gains its per-tracker DETAIL half; still not `served` in full until phases 4–6 land
the write, the release verb and the alert. Reported precisely by phase 8, not asserted here.

## Oracle: states that diverge, declared by name

**None.** `tracker-detail`, `tracker-detail-empty-active` and their loading/error twins are NEW.
No existing state's region changes — this phase adds a screen behind a brand-new page, touching no
region any other surface reads. Any divergence elsewhere is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the new states ×
`tracker/body`.

## Commit

`feat(maquette-l16): a tracker's detail — its obligations and its active torrents`
