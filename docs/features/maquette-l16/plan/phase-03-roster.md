# Phase 3 — The roster

One row per tracker: its ratio, its trend, its Download / Upload volumes (DESIGN § 4.1) — read from the summary read phase 1
declared, never averaged (§ 18's first clause, NE-DOIT-PAS-1). The page's shell and its tab are phase 2's; this phase fills the
page and gives it its other three states.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `ls frontend/maquette/design/src/features/` → no `trackers` (phase 2 creates it: at this phase's opening `ls
  frontend/maquette/design/src/features/trackers/` → `page.tsx` only). `grep -n -i 'tracker' frontend/maquette/design/src/i18n/fr.json` → four lines, all `settings.labels` of the search configuration
  (`max_per_tracker`, `timeout_per_tracker`, `search_query_format`, `tiers`), unrelated to this domain (`python3 -c "import
  json;d=json.load(open('frontend/maquette/design/src/i18n/fr.json'));print([k for k in d['screens'] if 'track' in k.lower()])"` → `[]`).
  `grep -c enabled config.example/tracker.json5` → `2` — two providers, `c411` and `tr4ker` (DESIGN § 2.1): the roster
  the mock answers. `python3 -c "import glob,re;print(sum(len(re.findall(r'^\s*\[\s*\"([^\"]+)\"\s*,\s*\"',open(f).read(),re.M)) for f in glob.glob('frontend/maquette/design/src/harness/states/*.ts')))"`
  → **114** on `dafe29ec1` (before this lot).
- **Points ≈ 13.** The rows in `page.tsx` (≈ 55 new; a row carries the ratio, the trend in words, the volumes and a path to
  `/trackers/$name`) 5½; **one new rule, R-L16-a's list half** (NE-DOIT-PAS-1: every ratio drawn compared against the mock's own
  field) with its mutation 3; three states — `trackers-list` re-using phase 1's roster seed 1, `trackers-loading` 1,
  `trackers-error` 1; `fr.json` (`screens.trackers.ratio`, `.trend` with its three words, `.volumes`) 1; the region's record in
  `regions.json` ½.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 2, list half) → this phase **13**: moved by **the scale**;
  no ruling touched it. The trend is spoken in words, never a bare arrow (NE-DOIT-PAS-4) — unchanged.

A BEHAVIOUR change: the roster did not exist; it now reads the summary read and draws it per tracker.

## The proof FIRST

- **What it drives.** Navigate to `/trackers`.
- **What it reads.** Each row's ratio, trend and volumes, compared against the mock's own field for that tracker — never a
  client-side mean across rows (R-L16-a).
- **Red today.** The rows do not exist to read: the rule fails for that reason against `main` (and, on the branch, against
  phase 2's shell, which draws none).
- **Mutation.** `scripts/mutate.sh` makes a row compute its ratio from a DIFFERENT tracker's field (a swapped index). The rule
  must fall, naming the mismatched tracker.

## The move

- **`features/trackers/page.tsx`** — the roster, one row per tracker (`data-part="trackers/row"`), its ratio
  (`data-part="trackers/ratio"`), trend (`trackers/trend`, in words), volumes (`trackers/volumes`). A row is a
  `data-tracker="<name>"` PATH to `/trackers/$name` (phase 4's screen — the route may 404 gracefully until then, or phase 4 lands in
  the same round; the phases chain).
- **`features/trackers/queries.ts`** — the summary read's query, declared by the feature (the frame never names it).
- **`harness/states/trackers.ts`** — `trackers-list`, `trackers-loading`, `trackers-error`, `data-region="trackers/body"`.
- **`i18n/fr.json`** — `screens.trackers.ratio`, `.trend`, `.volumes`.

## Mutation

`scripts/mutate.sh` swaps one row's drawn tracker for its neighbour's field. The rule must fall, naming which tracker's ratio was
drawn under the wrong name.

## Register

DOIT-13's row moves from `to draw` toward its first half `served` — the per-tracker read, not yet the detail (4, 5), the write (6)
or the alert (9, 10). The closing phase (15) reads and reports the exact wording, not this one.

## Oracle: states that diverge, declared by name

**None.** `trackers-list`, `trackers-loading`, `trackers-error` are NEW — the reference records them and proves nothing about
them (D8). No EXISTING state's region changes. Any divergence elsewhere is **STOP A**.

## Gate

Per INDEX « Gates ». Additionally: `python3 frontend/maquette/oracle.py --record` for the three new states × `trackers/body`.

## Commit

`feat(maquette-l16): the trackers roster, one row per tracker, never averaged`
