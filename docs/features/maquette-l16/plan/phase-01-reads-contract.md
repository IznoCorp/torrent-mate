# Phase 1 — The reads' contract (D7)

Three surfaces below read operations the maquette's own contract does not declare, and the tracker
as a subject is read by no operation anywhere. This phase declares the three READS, seeded and
mocked; the writes (the removal, the ranking's save reusing an existing one) are declared in the
phase that draws them (INDEX, « Why sixteen phases »). It is FIRST because
`scripts/compare-contracts.py --check` refuses the three artefacts apart and because the demands
filed here are what make DESIGN § 2.3's divergences decisions rather than discoveries.

**Opening measure (2026-09-27, on `5e5ecd052`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted(p for p in d['paths'] if 'obligation' in p or 'download' in p or 'ranking' in p or 'tracker' in p))"`
  → `[]` — none of the operations exists in the maquette's own contract. The same command on
  `frontend/openapi.json` reads `/api/acquisition/downloads`, `/api/acquisition/obligations`,
  `/api/acquisition/ranking/preview`, `/api/acquisition/stalled-grabs` (this lot declares none of the
  last — DESIGN § 2.5, F14) — no path names `tracker`.
  `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['ObligationItem']['properties']))"`
  → 13 fields (`accumulated_seed_time_s`, `added_at`, `breached_at`, `dispatched_path`, `hnr_count`,
  `info_hash`, `min_ratio`, `min_seed_time_s`, `observed_ratio`, `released_at`, `satisfied_at`,
  `source_tracker`, `title`) — these three terminal fields are the MARKS ruling 18 wants read on a
  torrent's own row, never a second list (DESIGN § 4.3).
  `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts` → **395**
  non-blank lines, 5 under the 400 ceiling — no read handler of this lot's fits there, so all three
  open `mocks/handlers/trackers.ts`, by SUBJECT (`staging.ts` / `pipeline.ts` precedent,
  `frontend-architecture.md` § 4, L20 phase 1). `ls frontend/maquette/design/src/mocks/handlers/` —
  no file named `trackers.ts`. `ls frontend/maquette/design/src/mocks/seeds | wc -l` → 48, none for a
  tracker, an obligation or a download.
  `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['AcquisitionDownload']['properties']))"`
  → no tracker, no ratio, no deadline field — the extension DESIGN § 2.3 item 3 asks for.
  `sed -n '590,712p' frontend/maquette/design/src/mocks/seeds/settings.json` — the `economy` rows
  already seeded, `file: "tracker"`, `key: "tracker.providers.<name>.economy.<field>"`, confirming the
  alert threshold (item 2) is a NEW KEY in this SAME family, never a new file or write.
- **Found (2026-09-27).** `python3 scripts/check-mock-seeds.py` → exit 0 (« clean »): the guard reads
  `fixture-register.json` and each operation's `x-seeded-from` / `x-unseeded`, not a
  `build-mock-seeds.py` script (which does not exist) — seeds are edited by hand, this guard is run
  in the same commit.
- **Points ≈ 14.** Three operations declared new — the tracker summary (name, ratio, volumes, trend,
  the alert threshold, the refused-identifier health fact — DESIGN § 2.3 item 1), the obligations,
  the downloads extended per active entry with tracker / ratio-on-size / deadline / origin (item 3) —
  6; three mock routes new (`trackers.ts`) 6; the `fixture-register.json` / `x-seeded-from` rows for
  the two new seed families (the roster, the obligations-and-downloads join) 2.
- **Re-cut (2026-09-27, on `5e5ecd052`).** The prior re-read's phase 1 (14) is UNCHANGED in shape —
  three reads, the same reasoning — but its CONTENTS moved: the tracker summary now carries the alert
  threshold and the refused-identifier fact (round 9 Q1, Q2), and `stalled-grabs` is confirmed absent
  from this lot's own contract entirely (F14, DESIGN § 2.5) rather than moved to a later phase as the
  prior reading did.

A CONTRACT change: no behaviour is drawn yet.

## No rule in this phase, and that is stated rather than skipped

A contract is not a behaviour: what holds it is `scripts/compare-contracts.py --check`, the generated
`contract/types.d.ts`, and `scripts/check-mock-seeds.py`. The rules that read these operations are
written in phases 2 to 15, each beside the surface that calls it. **A phase with no rule says so; it
does not invent one to look complete.**

## The move

### 1. Declare the three reads in `frontend/maquette/contract/openapi.json`

`GET /api/acquisition/obligations` (`ObligationsResponse`) seeded from the backend's own answered
shape (D7 — no divergence needed, DESIGN § 2.2). `GET /api/acquisition/downloads`
(`AcquisitionDownloadsResponse`) with its one deliberate divergence: each active entry carries the
tracker it runs on, its ratio ON THAT TRACKER computed on the torrent's OWN SIZE (never a division by
zero for a cross-seeded entry, ruling 18), its deadline, and whether it is the torrent's ORIGIN grab
or a cross-seed of it. **The tracker summary read** is declared new — name, ratio, Download / Upload
volumes, trend, the alert threshold, and whether the identifier is refused (since when) — its
operationId is a proposal, and adjusts.

### 2. File the demand rows these operations carry, by editing the CONTRACT, never the register

`docs/reference/frontend-backend-demands.md` says so in its own first line — « COMPUTED, NEVER
WRITTEN », built by `python3 scripts/compare-contracts.py --write` from the diff of
`frontend/maquette/contract/openapi.json` against `frontend/openapi.json`. The tracker summary and
the extended download are demand rows by that edit. The remaining rows of § 2.3 — the alert threshold
as a config key (item 2, filed alongside the write in phase 4), the removal (item 5, phase 6), the
grouped-removal read (phase 7), the ratio-derived scoring field (item 4, phase 12) and the deferral
demand (phase 11) — are filed by the phase that draws each.

### 3. The mocks, and each MOVES something (D7)

Three routes in `mocks/handlers/trackers.ts`, registered in `mocks/handlers/index.ts`. What each must
move (DESIGN § 2.4): the obligations list answers rows a later removal REMOVES (DESIGN § 4.4); the
downloads and the summary read PROJECT one seed, never two that can disagree — a torrent
cross-seeded onto two trackers seeds as TWO entries, one marked origin. Seeds are derived from the
real payloads the running backend answers, never invented; `python3 scripts/check-mock-seeds.py` is
run in the SAME commit; a field no real payload carries is `x-unseeded`.

### 4. Regenerate, and read what came out

    python3 scripts/compare-contracts.py --write     # rewrites docs/reference/frontend-backend-demands.md
    python3 scripts/compare-contracts.py --check
    npm --prefix frontend/maquette/design run generate-contract-types   # → src/contract/types.d.ts

**Read the regenerated register's counters and put them in the report**, before and after. A register
that did not move means the contract edit did not land, and a failed command is an edit that did not
happen.

## Gate

`sh scripts/heavy.sh --class rule l16 frontend/maquette/harness/run.sh --contracts` (announced to the
steward before and after); `python3 scripts/check-mock-seeds.py`; `compare-contracts.py --check`. The
oracle: **zero divergence everywhere** — no surface changed.

## Register

None closes here. B-144's reading half is answered by the declared operations; its remaining half
(the writes, the alert, the removal, the ranking term) is what phases 4–12 close.

## Commit

`feat(maquette-l16): the contract of the trackers' reads and its demands`
