# Phase 1 — The contract and its demands (D7)

Every surface below calls one of four operations. The maquette's own contract declares none of
them, though the backend answers three already; the fourth — a tracker's own policy — exists
nowhere. This phase settles all of it, and it is FIRST because `scripts/compare-contracts.py
--check` refuses the three artefacts apart and because the demands filed here are what make
DESIGN § 2.3's divergences decisions rather than discoveries.

**Opening measure (2026-09-15, on `08400a22a`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted(p for p in d['paths'] if 'obligation' in p or 'stalled' in p or 'download' in p or 'ranking' in p or 'tracker' in p))"`
  → `[]` — none of the four operations exist in the maquette's own contract. The same command
  against `frontend/openapi.json` reads `/api/acquisition/downloads`,
  `/api/acquisition/obligations`, `/api/acquisition/ranking/preview`,
  `/api/acquisition/stalled-grabs` — no path names `tracker`. `grep -n "^| required and missing"
  docs/reference/frontend-backend-demands.md` → `16`, the register's count this phase must move.
  `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts` → `338`
  non-blank lines, under the 400 ceiling; `ls frontend/maquette/design/src/mocks/handlers/` → 14
  files, none named `trackers.ts`. `grep -n B-144 BUGS.md` → `open`, 1×.
- **Points ≈ 10.** Four operations declared (`obligations`, `stalled-grabs`, `downloads`,
  `ranking/preview`), seeded from the backend's own shapes with no divergence ≈ 4; five demand rows
  filed (DESIGN § 2.3 items 1–5) ≈ 3 (filing a demand is lighter than a code change — the register
  is computed, not hand-written); the mocks that move plus the regenerated register and contract
  types ≈ 3. Under 15, no cut.

A CONTRACT change: no behaviour is drawn yet.

## No rule in this phase, and that is stated rather than skipped

A contract is not a behaviour: what holds it is `scripts/compare-contracts.py --check`, the
generated `contract/types.d.ts`, and `scripts/check-mock-seeds.py`. The rules that read these
operations are written in phases 2 to 7, each beside the surface that calls it. **A phase with no
rule says so; it does not invent one to look complete.**

## First, bind the rule numbers

    git remote update origin >/dev/null && grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1

Re-take it against this branch's base at the moment this phase runs, then bind `R-L16-a` …
`R-L16-h` (DESIGN § 4.8) to consecutive free numbers and write the mapping into the report. **A
number taken from the design without re-measuring is a collision**: this design measured `R194` on
2026-09-15 against `08400a22a`, and L13b, L13c and the `maquette-settings` micro-wave are all
ahead of L16 in the plan's order.

## The move

### 1. Declare the four existing operations in `frontend/maquette/contract/openapi.json`

Seeded from the backend's own answered shapes (D7 — no divergence needed, DESIGN § 2.2):
`GET /api/acquisition/obligations` (`ObligationsResponse`), `GET /api/acquisition/stalled-grabs`
(`StalledGrabsResponse`), `GET /api/acquisition/downloads` (`AcquisitionDownloadsResponse`),
`POST /api/acquisition/ranking/preview` (`RankingConfig` in, `RankingPreviewResponse` out).

### 2. File five demand rows (DESIGN § 2.3), by editing the CONTRACT, never the register

`docs/reference/frontend-backend-demands.md` says so in its own first line — « COMPUTED, NEVER
WRITTEN », built by `python3 scripts/compare-contracts.py --write` from the diff of
`frontend/maquette/contract/openapi.json` against `frontend/openapi.json`. Each row below is one
edit to the maquette's contract, so the register carries it after regeneration:

1. A tracker-level summary read — name, ratio, Download / Upload volumes, trend, alert threshold.
2. The tracker policy write — `min_ratio`, `min_seed_time`, the alert threshold, in one write.
3. `AcquisitionDownload` extended with the active torrent's tracker, ratio and deadline (or a
   tracker-keyed join the summary read carries instead — phase 1 measures which the mock can
   answer without a second, disagreeing source, and the report says which reading it took).
4. A ratio-derived field on `TrackerResult` a `RankingCriterion` can score categorically, the way
   `field: "provider"` already does (`personalscraper/api/tracker/_ranking.py:99`).
5. The obligation's release verb — `POST /api/acquisition/obligations/{id}/release` or equivalent.

### 3. The mocks, and each MOVES something (D7)

Measured at this design's writing, `mocks/handlers/acquisition.ts` is 338 non-blank lines — the
phase re-measures before choosing between adding the three read handlers there or opening a new
`mocks/handlers/trackers.ts`, by SUBJECT (the `staging.ts` / `pipeline.ts` precedent, L20 phase 1),
not by size alone. What each handler must move (DESIGN § 2.4): `obligations` shrinks on a release;
`stalled-grabs`' ratio-cause reason is COMPOSED from the same obligation it defers against, never a
second fact; `downloads` and the tracker summary read PROJECT one seed, never two that can
disagree; the policy write moves the seed the summary read projects back. Seeds are derived, never
invented: `python3 scripts/build-mock-seeds.py --write` then `python3 scripts/check-mock-seeds.py`
in the SAME commit.

### 4. Regenerate, and read what came out

    python3 scripts/compare-contracts.py --write     # rewrites docs/reference/frontend-backend-demands.md
    python3 scripts/compare-contracts.py --check
    npm --prefix frontend/maquette/design run generate-contract-types   # → src/contract/types.d.ts

**Read the regenerated register's counters and put them in the report**, before and after. « 16
required and missing » must move; a register that did not move means the contract edit did not
land, and a failed command is an edit that did not happen.

## Gate

`HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh l16 frontend/maquette/harness/run.sh --contracts`
(announced to the steward before and after); `python3 scripts/check-mock-seeds.py`;
`compare-contracts.py --check`. The oracle: **zero divergence everywhere** — no surface changed.

## Register

None closes here. B-144's reading half is answered by the declared operations; its remaining half
(the write, the alert, the release verb, the ranking term) is what phases 4–7 close.

## Commit

`feat(maquette-l16): the contract of the trackers domain and its five demands`
