# maquette-l20 — RESUME

## STATE BLOCK (rewritten at every boundary — at most 40 lines)

- **Updated**: 2026-09-14, phase 1 committed (Agent : l20 1).
- **Branch / worktree**: `feat/maquette-l20`, `/Users/izno/dev/worktrees/wave-l20`, cut from `main`
  at `4f242ecb3`; plan re-target `b7e600cc5`.
- **Phases done**: 1 (the contract).
- **Next**: phase 2 — one dated comment in `harness/states/system.ts` (`plan/phase-02-named-states.md`).
- **Waiting on**: nothing. Phase 8 waits for L13b's merge AND the steward's word.
- **Rule numbers**: RULINGS-L20.md ruling 1 (a…h → R178–R185, j → R187, R186 unused).
- **Register rows**: RULINGS-L20.md ruling 4 — L20's `BUGS.md` rows start at B-530 (L13b holds B-512–B-529).
- **Data sources**: ruling 3 — `seeds/pipeline-runs.json` is a one-off real snapshot (`PIPELINE_RUNS`,
  converted class); locks are `x-unseeded`, derived from layer state.
- **Tooling**: `main`'s — tiers as separate invocations (`run.sh --contracts`, then `run.sh --oracle`),
  `TM_HARNESS_JOBS=2`. A lone rule replay needs the 8899 host started by hand (ledger).
- **Locks**: shared mutex `scripts/heavy.sh --class browser l20 …` (announce before/after to the
  steward; shared with `Agent : l13b 2`); tests lock `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder`;
  own lock `HEAVY_LOCK=/private/tmp/tm-heavy-l20/holder` for `npm ci` and builds.
- **Logs**: `~/Library/Logs/tm-l20/<phase>-<step>.log`; `npm ci` done in `frontend/maquette/design` only.
- **Owed**: phase 3 — `locks-orphans` has no real entry (STOP D at its opening); phase 4 — the bound key
  in `settings.json` (+ `format.test.ts`'s 159 corpus); phase 5 — the real detection counts differ from
  DOIT-6's names; phase 6 — the transitional `result` filter in `queries.ts`, frozen clock vs snapshot
  dates; phase 7 — `readRun` of an unknown uid answers `null`, a 404 is owed. Midpoint full suite after
  phase 5; at phase 9 the full suite, `--a11y`, `--compare`, `make lint`, pre-push pytest, ONE PR READY.

---

## LEDGER (append-only)

- 2026-09-14 — handshake readings: origin/main `4f242ecb3`; highest rule R177 (the plan's « R160 »
  is stale); `__version__` 0.98.92; `engine/` holds no `states.js`; the shared mutex was held by l13b.
- 2026-09-14 — the demands register read « required and missing » **15** before phase 1 (the plan
  says 14 — a stale figure, not a defect; the before/after comparison uses 15).
- 2026-09-14 — DESIGN.md's three present-tense measurements of the dead `engine/states.js` re-pointed
  at the `60530dbd8` blob (steward's note); both commands re-run on that blob read 786 and 87.
- 2026-09-14 — **STOP D at phase 1's opening (seeds vs the engine-free rule).** `pipeline-executions.json`
  is re-derived byte-for-byte from `legacy.js:1383` (`EXECUTIONS`, not `converted`) by
  `check-mock-seeds.py --arm correspondence`; adding `runUid` needs a legacy.js edit, and converting the
  family needs the literal DELETED (`--arm classification` refuses « converted and still declared »),
  plus its refs at `legacy.js:1958` and `:3754`. No engine fixture holds a run's trigger code, ISO
  times, counts, steps, output tail, nor any lock/sweep data. `SETTINGS` and `PIPELINE` ARE converted
  (their committed seeds are authoritative, held by schema + oracle), so the bound key is guard-legal.
  Asked the steward; waiting.
- 2026-09-14 — ruling 3 (A) applied. Snapshot: 10 real rows, `sqlite3 "file:…/.data/library.db?mode=ro"`,
  `SELECT run_uid, trigger, dry_run, started_at, ended_at, outcome, steps_json, error, kind, command,
  options_json, output_tail FROM pipeline_run WHERE run_uid = ?` — the six `EXECUTIONS` rows (matched on
  date AND duration: 2b598104 104 s = « 1 min 44 », 93376cff, 4682518d, 60e0c557, c431ce3e, cea7b880),
  then c8a5851f (failed pipeline, log), 1d4cabd2 (no output), 74bd260c (maintenance `prime`, options),
  43c48209 (the one web-triggered `follow-detect`). ISO/elapsed serialised as the backend's route does;
  `output_tail` kept as its last 16 KiB cut at a line start (seed 205 KB). Secret scan: one « Secret »
  word inside a rendered table, no token.
- 2026-09-14 — the register's « required and missing » did NOT move (15 → 15), and that is right: the
  backend already HAS `watcher`, `history/{run_uid}` and `locks`; they now count as « declared by both »
  (requires 59→62, shape 44→47, spelling 14→15, status 12→11 — detect's 200→202 left it, unused 21→18).
  The plan's « must move » assumed the backend lacked them.
- 2026-09-14 — the bound key (`pipeline.tunnels.max_parallel`) is NOT in phase 1's seed: the settings page
  draws every field of `settings.json` (`features/settings/page.tsx:146`), so adding it moves settings'
  states and phase 1's oracle must read zero. It lands with its first drawing, phase 4 — told the steward.
- 2026-09-14 — owed to phase 7: `readRun` of an unknown uid answers `null` — the layer has no way for a
  handler to choose its status and `mocks/index.ts` is at the 400-line ceiling; `run-detail-not-found`
  needs a 404.
- 2026-09-14 — owed to phase 5: the real `follow-detect` step counts `detected, enqueued, skipped_owned,
  skipped_dup, resurrected, closed_owned` — no `available`, no `grabbed`. The contract carries DOIT-6's
  three names on `StepCounts.counts` and says it is a demand.
- 2026-09-14 — owed to phase 6: the frozen clock is 2026-08-10 and three snapshot rows are later
  (08-14, 09-08); `queries.ts` draws only rows carrying the fixture line until phase 6 composes it.
- 2026-09-14 — trap: a Python `json.dumps(sort_keys)`/sorted rewrite of `contract/openapi.json` moved
  5 116 lines; the file is indent 2, raw unicode, insertion order — append, never sort. eslint ignores
  `frontend/maquette/design/src` entirely (not a maquette gate). `check-no-french`'s vocabulary gained 19
  English words (age … while).
- 2026-09-14 — the oracle on `main` is `run.sh --oracle` (it builds, starts the 8899 host, runs
  `oracle.py --check`); the brief's « oracle.py --check on its own » needs the host up (steward agreed).
  A DIRECT replay of one rule, until L13b's tooling lands: after the build/copy, when nothing listens,
  `(python3 frontend/maquette/harness/server.py --serve 8899 /tmp/tm-refonte &)`, stop it after, prove
  it on `lsof -nP -iTCP:8899`. A Traceback with no FAIL line is a CRASH, never a fall — the first
  phase-1 replay of `declared_codes.py` and `oracle.py --check` crashed on ERR_CONNECTION_REFUSED.
- 2026-09-14 — phase 1 gate: `run.sh --contracts` first read exit 1 (declared_codes: runDetection's
  new 202 undriven; boundaries: `handlers/pipeline.ts` imported `../state` twice), repaired; re-run
  exit 0 — 18 rules and 26 repository guards, no violation (`~/Library/Logs/tm-l20/p1-contracts.log`).
