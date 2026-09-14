# maquette-l20 — RESUME

## STATE BLOCK (rewritten at every boundary — at most 40 lines)

- **Updated**: 2026-09-14, phase 3 committed (Agent : l20 1).
- **Branch / worktree**: `feat/maquette-l20`, `/Users/izno/dev/worktrees/wave-l20`, cut from `main`
  at `4f242ecb3`; plan re-target `b7e600cc5`.
- **Phases done**: 1 (the contract), 2 (the comment), 3 (the host and the locks, R184).
- **Next**: phase 4 — the levers (`plan/phase-04-levers.md`), rules R178/R179/R181 + R184's agreement half.
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
- 2026-09-14 — phase 2: the plan asks the comment to NAME DESIGN § 5 and be dated;
  `check-maquette-comments.py` refuses any lot/phase/date reference in a maquette comment (CLAUDE.md
  § Language, binding) — the comment says what it does and names no document. system.ts: 4 states.
- 2026-09-14 — phase 2 gate: `run.sh --contracts` 0 (18 rules + 26 guards, no violation),
  `run.sh --oracle` 0 (87 states x 34 regions, no divergence), `harness-hold-counts.py --compare
  frontend/maquette/hold-counts-baseline.json --only states.py` 0 — states.py 87 holds, 0 rule changed
  count. `--compare` TAKES THE BASELINE FILE as its argument; a bare `--compare` exits 2.
- 2026-09-14 — the 8899 host does NOT survive a run: `harness-hold-counts.py` found nothing listening
  right after a green `run.sh --oracle`. Started by hand per the steward's procedure — after the build,
  `(python3 frontend/maquette/harness/server.py --serve 8899 /tmp/tm-refonte &)`, `pkill -f` after,
  port proved free.
- 2026-09-14 — PLATFORM STOP 13:12→16:46: the session was refused by the organisation's policy. The
  steward committed the work in flight (cbbae5ca3, 06ddb8301) and pushed the branch. Both re-read and
  folded into phase 2's single commit; `comment-references-baseline.json` 417→418 is phase 1's new
  files, references unchanged (guard re-run: 216 references, 0 grown).
- 2026-09-14 — the host switched this session's model on its own during the stop: it answered as
  claude-opus-5 until 13:12 and the gauge reads `<synthetic>` after. Said to the operator and the steward.
- 2026-09-14 — phase 3: R184 read RED first (21 holds, 20 violations: « état inconnu : locks-free »,
  every row null, no control), then GREEN in the contracts tier. locks.py was ADDED to run.sh's
  CONTRACTS list — it falls when a named state or a data-part name moves, which is that tier's subject.
- 2026-09-14 — a hold of mine was WEAK and the run said so: « the row carries a value » compared the
  row's whole text against the length of its data-part name, and « Pause »+« Inactive » reads
  `PauseInactive`. It now reads the emitter's own `flux/name` and `flux/value` parts separately.
- 2026-09-14 — the oracle: 71 divergences, on `system`, `system-outage` and the five NEW states, and on
  nothing else (no STOP A). Ratified with `oracle.py --accept`; the diff reads +5 states, the new region
  `system/locks` (null on every state that does not draw it) and the two system states' page height
  2540.5 → 2899.4. Regions 34 → 35, states 87 → 92.
- 2026-09-14 — the layer gained DIALS (`mockDials` in state.ts, spread into `window.__mocks`): a named
  state runs synchronously, so it cannot ask the layer through the network. `mocks/index.ts` sits at the
  400-line ceiling — the dials cost it TWO lines (a spread, and `MockDials` on the existing
  intersection), 395 → 397.
- 2026-09-14 — `code-vocabulary.txt` gained 8 more English words (day, free, hour, locks, orphan,
  orphans, parts, sentinels).
- 2026-09-14 — phase 3 mutations, both SEEN to fall naming the right defect: a skeleton over the whole
  block → « locks/pipeline · pause-sentinel · watcher-sentinel still answers while the sweep is
  pending » (4 violations); the age dropped from a held lock → « a held lock says so AND says since
  when », measured value `Pris —` (1 violation). Restored by the tool, tree clean.
- 2026-09-14 — `mutate.sh` rebuilds the served copy but does NOT start the 8899 host: the first attempt
  read « FELL — the rule exited 1 with no FAIL line », which is an INSTRUMENT crash
  (ERR_CONNECTION_REFUSED), never a fall. Start the host first, kill it by captured PID.
