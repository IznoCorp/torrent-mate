# Phase 4 — A tracker's detail: the head

`/trackers/$name` (DESIGN § 3, § 4.2): the screen, its address, its parent page and its head — the ratio, the volumes and the
trend, repeating the roster row (§ 13 — one derivation, drawn twice from the same read). What hangs off the head — the obligations
and the active torrents — is phase 5's; the address is proved here before anything is drawn under it.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `sed -n '/SCREEN_PARENTS/,/};/p' frontend/maquette/design/src/lib/addresses.ts` → six entries (`/add`,
  `/quality/$name`, `/media/$provider/$id`, `/releases/$title`, `/resolution/$folder` → `arr`, `/run/$runUid`), none for a tracker;
  **L22a's phase 2 moves `/resolution/$folder` to `acq`** (re-taken at this lot's opening). `git grep -n SCREEN_PARENTS --
  frontend/maquette` → `lib/addresses.ts` (declares it) and `harness/common.py:506` (**reads it from the source**, and
  `harness/screen_addresses.py` walks every declared screen: the new entry enters that walk). `routes/run.tsx` is the thin-route
  precedent (13 lines: `createRoute({ getParentRoute: () => rootRoute, path, component })`); `ls frontend/maquette/design/src/routes/`
  → 14 files, no `tracker.tsx`. `lib/addresses.test.ts` exists. `python3 -c "import
  json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"` → 13 fields
  (`accumulated_seed_time_s`, `added_at`, `breached_at`, `dispatched_path`, `hnr_count`, `info_hash`, `min_ratio`, `min_seed_time_s`,
  `observed_ratio`, `released_at`, `satisfied_at`, `source_tracker`, `title`) — `source_tracker` is the join key phase 5 filters on.
  `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/features/system/run-screen.tsx` → 323 (the analogue for a screen with its list
  and its head; this phase's is the smaller half).
- **Points ≈ 13.** `features/trackers/tracker-screen.tsx`, the head and the screen's skeleton (≈ 45 new) 4½; `routes/tracker.tsx` (≈ 13
  new) 1½; `SCREEN_PARENTS` entry and the address test's case (≈ 3 edited) ½; **R-L16-a re-aimed** to the head — a rule file re-aimed 1;
  **R-L16-h re-aimed** to the content-tier push — a rule file re-aimed 1; `harness/screen_addresses.py`'s walk gaining the address 1; three
  states — `tracker-detail` re-using the roster's seeds 1, `tracker-detail-loading` 1, `tracker-detail-error` 1; `fr.json` (the head's
  labels where they differ from the roster's, § 13 — reuse `screens.trackers.ratio` where the SAME derivation applies) 1.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 3, detail) 11 → this phase **13** and phase 5 **14**: moved by
  **the scale**, and by one reader the first drawing missed — `harness/screen_addresses.py` reads `SCREEN_PARENTS` from the source. **The
  host page's id is settled**: `trackers`, the id of the navigation row phase 2 wrote (the first drawing left it « once the host page's id is
  settled »). No ruling touched this phase.

A BEHAVIOUR change: the screen did not exist; it reads the same operation phase 3's roster does, filtered to one tracker.

## The proof FIRST

Its rules are the two phases 2 and 3 wrote, re-aimed; a hold is added to each.

- **What it drives.** From `/trackers`, tap a row.
- **What it reads**:
  1. the ratio, volumes and trend drawn at the head, compared against the SAME field the roster row read for that tracker (R-L16-a);
  2. the URL, `/trackers/$name`, and `history.length` before and after the tap (R-L16-h — opening a content-tier surface PUSHES, D1b
     rule 1), and the back gesture landing on `/trackers`.
- **Red today.** `/trackers/$name` resolves nowhere — both holds fail for that reason against `main`.
- **Mutation.** For R-L16-a: `scripts/mutate.sh` swaps the head's ratio for a different tracker's field — the comparison must fall,
  naming the mismatch. For R-L16-h: make the route REPLACE instead of push — the `history.length` hold must fall.

## The move

- **`features/trackers/tracker-screen.tsx`** — the head (ratio, volumes, trend; `data-part="tracker/ratio"`, `tracker/volumes`,
  `tracker/trend`; `data-region="tracker/body"`), and the loading and error skeletons.
- **`routes/tracker.tsx`** — the screen route, `/trackers/$name`.
- **`lib/addresses.ts`** — `SCREEN_PARENTS["/trackers/$name"] = "trackers"`.
- **`harness/states/trackers.ts`** — `tracker-detail`, `tracker-detail-loading`, `tracker-detail-error`.
- **`i18n/fr.json`** — the head's labels only where the sentence genuinely differs from the roster's.

## Mutation

Two mutations, one per rule, as above — each committed and restored separately.

## Register

DOIT-13's row gains its per-tracker HEAD; still not `served` in full until the lists (5), the write (6) and the alert (9, 10) land. Reported
precisely by phase 15, not asserted here.

## Oracle: states that diverge, declared by name

**None.** `tracker-detail` and its loading/error twins are NEW. No existing state's region changes — this phase adds a screen behind a
page whose row phase 3 already recorded. Any divergence elsewhere is **STOP A**.

## Gate

Per INDEX « Gates ». `python3 frontend/maquette/oracle.py --record` for the three states × `tracker/body`.

## Commit

`feat(maquette-l16): a tracker's detail — its address and its head`
