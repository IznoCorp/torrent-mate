# Phase 1 — The reads' contract (D7)

Three of the surfaces below read operations the maquette's own contract does not declare, and the tracker as a
subject is read by no operation anywhere. This phase declares the three READS, seeded and mocked; the writes are
declared in the phase that draws them (INDEX, « Why fifteen phases »). It is FIRST because `scripts/compare-contracts.py
--check` refuses the three artefacts apart and because the demands filed here are what make DESIGN § 2.3's
divergences decisions rather than discoveries.

**Opening measure (2026-09-26, on `dafe29ec1`):**

- **Commands.** `python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sorted(p for p in d['paths'] if 'obligation' in p or 'stalled' in p or 'download' in p or 'ranking' in p or 'tracker' in p))"`
  → `[]` — none of the operations exists in the maquette's own contract (the same command on `frontend/openapi.json` reads
  `/api/acquisition/downloads`, `/api/acquisition/obligations`, `/api/acquisition/ranking/preview`,
  `/api/acquisition/stalled-grabs` — no path names `tracker`). The contract holds **63** operations
  (`python3 -c "import json;d=json.load(open('frontend/maquette/contract/openapi.json'));print(sum(len(v) for v in d['paths'].values()))"`).
  `sed -n 20,29p docs/reference/frontend-backend-demands.md` → required and missing **16**, different shape 47, different
  status 11, path spelled differently 15, pre-formatted fields 25, backend-only 18. `python3 scripts/compare-contracts.py
  --check` → exit 0; `python3 scripts/check-mock-seeds.py` → exit 0 (« clean », 15 payload modules, 395 literals, 0
  uncovered). `grep -cve '^[[:space:]]*$' frontend/maquette/design/src/mocks/handlers/acquisition.ts` → **359** non-blank
  lines (338 on `08400a22a`), 41 under the 400 ceiling: three read handlers do not fit, so they open
  `mocks/handlers/trackers.ts`, by SUBJECT (the `staging.ts` / `pipeline.ts` precedent, `frontend-architecture.md` § 4,
  L20 phase 1). `ls frontend/maquette/design/src/mocks/handlers/` → 14 files, none named `trackers.ts`; `ls
  frontend/maquette/design/src/mocks/seeds | wc -l` → 48, none for a tracker, an obligation or a download. `grep -n
  '^| B-144' BUGS.md` → `open`.
- **Found (2026-09-26).** **`scripts/build-mock-seeds.py` no longer exists** — the first drawing's « `python3
  scripts/build-mock-seeds.py --write` then `check-mock-seeds.py` » is not a command: the seeds are edited by hand and
  `scripts/check-mock-seeds.py` (its `schema` and `provenance` arms) is the guard, with `frontend/maquette/fixture-register.json`
  and each operation's `x-seeded-from` / `x-unseeded` naming where a seed came from (L22's phase 1 found the same).
- **Points ≈ 14.** Three operations declared new — the tracker summary read (DESIGN § 2.3 item 1), the obligations, the
  downloads carrying the active torrent's tracker, ratio and deadline (§ 2.3 item 3) — 6; three mock routes new (`trackers.ts`) 6;
  the `fixture-register.json` / `x-seeded-from` rows for the two new families (the roster, the obligations with the downloads) 2.
  Regenerating the register and the types is mechanical.
- **Re-measured (2026-09-26, on `dafe29ec1`).** First drawing 10 → **14**, moved by **the scale** (declared once in `INDEX.md`;
  the first drawing scored an operation at 1 and a demand row at ≈ 0.6): no ruling touched this phase. The four operations
  the first drawing declared here are now three — `stalled-grabs` moves to phase 11 and `ranking/preview` to phase 12, each
  with the surface that calls it, because declaring them here would have put the phase at 22.

A CONTRACT change: no behaviour is drawn yet.

## No rule in this phase, and that is stated rather than skipped

A contract is not a behaviour: what holds it is `scripts/compare-contracts.py --check`, the generated
`contract/types.d.ts`, and `scripts/check-mock-seeds.py`. The rules that read these operations are written in phases 2 to
14, each beside the surface that calls it. **A phase with no rule says so; it does not invent one to look complete.**

## The move

### 1. Declare the three reads in `frontend/maquette/contract/openapi.json`

`GET /api/acquisition/obligations` (`ObligationsResponse`) and `GET /api/acquisition/downloads`
(`AcquisitionDownloadsResponse`) seeded from the backend's own answered shapes (D7 — no divergence needed for the
obligations, DESIGN § 2.2), and the downloads' one deliberate divergence: each `AcquisitionDownload` carries its tracker,
its ratio and its deadline (or the tracker-keyed join the summary read carries instead — the phase measures which the mock
can answer without a second, disagreeing source, and the report says which reading it took). **The tracker summary read**
is declared new — name, ratio, Download / Upload volumes, trend, the alert threshold (§ 2.3 item 1); its operationId is a
proposal, and adjusts.

### 2. File the two demand rows these operations carry, by editing the CONTRACT, never the register

`docs/reference/frontend-backend-demands.md` says so in its own first line — « COMPUTED, NEVER WRITTEN », built by
`python3 scripts/compare-contracts.py --write` from the diff of `frontend/maquette/contract/openapi.json` against
`frontend/openapi.json`. The summary read (§ 2.3 item 1) and the extended download (§ 2.3 item 3) are demand rows by that
edit. The other three rows of § 2.3 — the policy write (item 2), the release verb (item 5), the ratio-derived scoring field
(item 4) — are filed by phases 6, 7 and 12.

### 3. The mocks, and each MOVES something (D7)

Three routes in `mocks/handlers/trackers.ts`, registered in `mocks/handlers/index.ts`. What each must move (DESIGN § 2.4):
the obligations list is the list a later release REMOVES an item from; the downloads and the summary read PROJECT one seed,
never two that can disagree. Seeds are derived from the real payloads the running backend answers, never invented, and
`python3 scripts/check-mock-seeds.py` is run in the SAME commit; a field no real payload carries is `x-unseeded`.

### 4. Regenerate, and read what came out

    python3 scripts/compare-contracts.py --write     # rewrites docs/reference/frontend-backend-demands.md
    python3 scripts/compare-contracts.py --check
    npm --prefix frontend/maquette/design run generate-contract-types   # → src/contract/types.d.ts

**Read the regenerated register's counters and put them in the report**, before and after. « 16 required and missing »
must move; a register that did not move means the contract edit did not land, and a failed command is an edit that did not
happen.

## Gate

`sh scripts/heavy.sh --class rule l16 frontend/maquette/harness/run.sh --contracts` (announced to the steward before and
after); `python3 scripts/check-mock-seeds.py`; `compare-contracts.py --check`. The oracle: **zero divergence everywhere** —
no surface changed.

## Register

None closes here. B-144's reading half is answered by the declared operations; its remaining half (the write, the alert, the
release verb, the ranking term) is what phases 6–12 close.

## Commit

`feat(maquette-l16): the contract of the trackers' reads and its two demands`
