# Phase 12 — The ranking's contract

The ranking editor calls `POST /api/acquisition/ranking/preview` and the maquette's contract does not declare it. This phase declares it, seeds and mocks it, and
files the fourth demand row — a ratio-derived field on the scored release (DESIGN § 2.3 item 4). No surface is drawn: the operation is declared with the phases
that call it, in the order the INDEX gives (« Why fifteen phases »).

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print([p for p in d['paths'] if 'ranking' in p])"` → `[]` on
  `dafe29ec1` (the backend's own contract answers `/api/acquisition/ranking/preview`). `python3 -c "import json;d=json.load(open('frontend/openapi.json'));print(sorted(d['components']['schemas']['RankingConfig']['properties']));print(sorted(d['components']['schemas']['RankingPreviewResponse']['properties']))"`
  → `bonuses`, `criteria`, `min_seeders`, `size_thresholds_by_type` and `known_trackers`, `ranked`. **`getattr(r, c.field, None)` is at
  `personalscraper/api/tracker/_ranking.py:100`** (the first drawing cited `:99`, the `for` line above it) — a criterion scores whatever field `TrackerResult`
  (`personalscraper/api/tracker/_base.py:58`) carries, `provider` today; **no ratio-derived field exists on it**. `grep -cve '^[[:space:]]*$'
  frontend/maquette/design/src/mocks/handlers/trackers.ts` → the file phase 1 opened (three read handlers and, by phase 6 and 7, two writes); the preview handler
  ranks the POSTed criteria against the seeded releases (≈ 30 lines of ranking logic, derived from the backend's `rank()` semantics), and the file is re-measured
  against the 400 ceiling at this opening.
- **Points ≈ 9.** `ranking/preview` declared new 2; its mock route new 2 and the ranking logic it needs (≈ 30 new) 3; the ratio-derived field on the scored
  release (the demand row: a contract edit of the criterion's field set) 1; the `fixture-register.json` / `x-seeded-from` row for the release seed 1.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing (its phase 1 declared this operation with three others; its phase 7 drew the editor) → this phase
  **9**: moved by **the scale**, and the phase is **new by the cut** — the operation moves out of phase 1 (which would otherwise stand at 22) and out of the editor's
  phase (which would otherwise stand at 23). No ruling touched it.

A CONTRACT change: no behaviour is drawn yet.

## No rule in this phase, and that is stated rather than skipped

What holds it is `scripts/compare-contracts.py --check`, `contract/types.d.ts`, and `scripts/check-mock-seeds.py`. The rule that reads the preview is R-L16-f, in phase 14.

## The move

- **`POST /api/acquisition/ranking/preview`** declared in `frontend/maquette/contract/openapi.json` (`RankingConfig` in, `RankingPreviewResponse` out, seeded from the backend's
  own shapes, D7), and **the ratio-derived scoring field** filed as a demand: a `RankingCriterion` whose `field` names it (`tracker_ratio_state` or equivalent) can
  score it the way `field: "provider"` does — `rank()` needs nothing else.
- **A mock route** in `mocks/handlers/trackers.ts` that ranks the POSTed criteria (weights, `prefer`, `min_seeders`) and returns `ranked` with `excluded` rows flagged
  and sunk last, and `known_trackers` — the roster the tracker-keyed criterion is populated from.
- **The register and the types**, regenerated and read: `python3 scripts/compare-contracts.py --write`, `--check`, `npm --prefix frontend/maquette/design run
  generate-contract-types`.

## Gate

`sh scripts/heavy.sh --class rule l16 frontend/maquette/harness/run.sh --contracts`; `python3 scripts/check-mock-seeds.py`; `compare-contracts.py --check`. The oracle:
**zero divergence everywhere**.

## Register

B-144's last demand row (the ranking term) is filed here; it closes with phase 15's report, the operation's caller landing in phase 14.

## Commit

`feat(maquette-l16): the ranking preview's contract and the ratio-derived criterion field`
