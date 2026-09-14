# maquette-l20 — RESUME

## STATE BLOCK (rewritten at every boundary — at most 40 lines)

- **Updated**: 2026-09-14, `Agent : l20 2` at the phase-7 boundary; phase 8 waits for L13b's merge
  and the steward's word.
- **Branch / worktree**: `feat/maquette-l20`, `/Users/izno/dev/worktrees/wave-l20`, cut from `main`
  at `4f242ecb3`. HEAD = pushed head; `git ls-remote` proves it.
- **Phases done**: 1 (contract), 2 (comment), 3 (locks, R184), 4 (levers, R178/R179/R181 + R184's
  agreement half), 5 (veille, R180), 6 (history list, R182's list half), 7 (run detail: R183, R182's
  detail half, R187 in screen_addresses.py + back.py). Plus ruling 6's tooling fix and the midpoint
  repair.
- **Next**: phase 8 next (`plan/phase-08-hand-path.md`), on the steward's word after L13b merges —
  re-cut against L13b's b·10-ter as merged, not against the plan; 9 closes. `Agent : l20 2` STOOD
  DOWN at the phase-7 boundary (L13b not merged, gauge 33).
- **Rule numbers**: ruling 1 — R178 levers-act, R179 DOIT-4, R180 veille, R181 §13-loading,
  R182 history, R183 fold, R184 locks, R185 B-371 (phase 8), R187 addresses (R186 unused).
- **Register rows**: ruling 4 — L20's `BUGS.md` rows start at B-530.
- **Data**: ruling 3 — `seeds/pipeline-runs.json` (10 real rows) and ruling 5 — `seeds/tmp-orphans.json`
  (one real entry). Both converted-class families; locks are `x-unseeded`.
- **Owed**: the composed row line LOSES « 1 bloqué » — the fixture's blocked count came from the
  engine's `blockedCount` and the real `steps_json` verify step has no equivalent (a demand, or
  another field; not invented). Three feature files still write `<details>` raw (DESIGN § 9's debt,
  `ui/disclosure.tsx` now exists) — not this lot's to convert. Hold counts moved and NOT re-recorded
  (phase 9's): screen_addresses.py 51→58, back.py 17→21, run_history.py and raw_log.py new (23, 13).
  `mocks/state.ts` 398/400 non-blank.
- **Tooling**: a scratch replay (acquire, build, publish, 8899 by captured pid, rules, release) is
  described in the ledger; tiers are SEPARATE invocations (`run.sh --contracts`, then `run.sh --oracle`),
  `TM_HARNESS_JOBS=2`. The oracle now REFUSES to write over another wave's build (ruling 6) — accept
  inside ONE heavy invocation and verify the reference BY NAME, never by the total.
- **Locks**: shared mutex `TM_HARNESS_JOBS=2 sh scripts/heavy.sh --class browser l20 …` (announce
  before/after; shared with l13b); tests lock `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder` for
  pytest, `make check` and every push; own lock `/private/tmp/tm-heavy-l20/holder` for npm/tsc.
- **Logs**: `~/Library/Logs/tm-l20/<phase>-<step>.log`.

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
- 2026-09-14 — phase 4: R178/R179/R181 red first (levers.py 26 holds / 19 violations), R184's
  agreement half red too (locks.py 23 holds / 2 violations, its 21 phase-3 holds still green).
  Then 20 rules + 26 guards, no violation.
- 2026-09-14 — TWO of my own holds were WEAK and the runs said so, both repaired before green:
  (a) the finger test read « covered by nothing » on every lever — the section sits far down a long
  page and `elementFromPoint` answers null OUTSIDE the viewport; a finger scrolls first, so the
  press now scrolls the control to the centre before hit-testing; (b) `levers-loading` drove the
  PAGE's loading phase, which draws the page-wide skeleton and proves nothing about this section —
  it now holds the section's own reads back (60 s latency) over a READY page.
- 2026-09-14 — INCIDENT (B-256's species): `oracle.py --accept` run as its OWN heavy invocation
  measured ANOTHER WAVE'S BUILD — the ONE served copy was republished in the gap — and rewrote the
  reference with 87 states, none of this lot's twelve. Caught by reading the diff, reverted, redone
  with build+publish+serve+accept INSIDE ONE heavy invocation, and the new reference verified BY
  NAME (99 states, 36 regions, the twelve present). Ruling 6 turns that into tooling.
- 2026-09-14 — the contract's `Pipeline` gained `state`: the pipeline's run state was in NO read of
  the maquette contract (the hole phase 8 repairs); the backend answers it as `StatusResponse.state`.
- 2026-09-14 — phase 5: R180 green in the tier (21 rules, 26 guards). DEVIATION, said plainly: its
  RED reading was NOT taken before the move — the rule and the code were written in one pass. The
  defect it names is real on `main` (the « ⋮ » button carried `data-standby`, which nothing answers),
  and the mutations below cover the same claims, but the red was owed and was not read.
- 2026-09-14 — THREE probes of mine were wrong and the gate said so: (a) `page.evaluate` passes ONE
  argument — a rule reading `(part, verb)` got the array as `part` and found nothing; (b) the counts
  probe read « the newest run », which is a REAL snapshot row (the frozen clock is older than the
  real passages), not the veille's — it now finds the run by what launched it; (c) the success-word
  hold read the whole page, where the passages list says « réussi » about other runs — it now reads
  the veille's own block and the message.
- 2026-09-14 — DESIGN § 5 spells the veille's states in FRENCH (`veille-idle` …). A named state id is
  a NAME and is English (CLAUDE.md § Language, and `check-no-french` refuses it): they are
  `watch-idle`, `watch-running`, `watch-figures`, `watch-nothing`, `watch-error`.
- 2026-09-14 — the oracle: 118 divergences, and `sheet-more` NOT among them — the panel's button
  gained an attribute and no pixel. 99×36 → 104×36, verified by name.
- 2026-09-14 — MIDPOINT full suite (131 rules): 2 falls. `settings.py` was MINE and the rule was right
  — it holds that every setting comes from a REAL configuration file, and the bound is a DEMAND whose
  file does not exist. Repaired by taking the key OUT of the settings seed: the row says « pas encore
  réglable » and offers no path onto a panel that would not open (DOIT-7). `load_more_scale.py` was an
  INSTRUMENT fall — `BrowserType.launch: Timeout 180000ms` on a machine running two waves — and it
  passes alone (8 rules, no violation).
- 2026-09-14 — phase 6: R182's list half read RED FIRST (14 holds, 13 violations), then green — 22
  rules in the tier. THE RED TAUGHT THE RULE: the history's newest row is a MAINTENANCE command
  (`prime`, 09-08) whose steps carry no counts, so « the first run » was the wrong subject; the rule
  now reads the first PIPELINE run and finds its row by `data-run`.
- 2026-09-14 — `scen.py` caught a real defect of mine before any reader did: the row drawn as four
  columns SPILLED sideways at 390 px (3 spills on `system`). The row is a stack now
  (`features/system/variants.ts`), and the page scrolls in one direction only.
- 2026-09-14 — and the same run showed the rows printing a raw ISO timestamp for every passage the
  fixture line does not cover. A date is composed now; the six runs whose fixture line the oracle
  measures keep theirs.
- 2026-09-14 — phase 6 DECLARED THE ROUTE `/run/$runUid` with a thin screen (the identifier only),
  because a row leading to an address that does not exist is not a path. `SCREEN_PARENTS` carries it
  with `sys` as its parent. Phase 7 fills the screen.
- 2026-09-14 — oracle 104×36 → 107×37 (`system/runs`), verified by name.
- 2026-09-14 — phase 6's mutation B found a WEAK HOLD of mine, and `mutate.sh` said it in as many
  words: « NO RULE FELL. That is the finding. » The hold read « the answered count appears somewhere
  in the line », which any other number satisfies — a constant 9 where the layer said 1 stayed green
  because the duration « 1 min 44 » carries a 1. It now requires the count IN ITS OWN PHRASE
  (« 1 rangé », or « rien de nouveau » at zero).
- 2026-09-14 — TRAPS PAID FOR, for whoever takes phase 7 (each cost a run):
  * `page.evaluate` passes ONE argument — a probe reading `(a, b)` gets the array as `a`.
  * `elementFromPoint` answers null OUTSIDE the viewport: a finger SCROLLS first, or every press
    reads « covered by nothing ».
  * a rule replayed alone needs the 8899 host: `run.sh` starts it and `heavy.sh` stops what it
    started, so start it by hand after the build and kill it BY CAPTURED PID (never by pattern —
    a pattern kill reaches the other wave's host).
  * a Traceback with no FAIL line is a CRASH, never a fall.
  * `mutate.sh` refuses a dirty tree: commit, then mutate.
  * the frozen clock (2026-08-10) is OLDER than the real snapshot rows (08-14, 09-08), so « the
    newest run » in the history is a real maintenance command, not the one a state just launched.
  * a hold reading « the number appears somewhere in the line » is satisfied by any other number.
  * the settings rule holds that every setting comes from a REAL configuration file: a demanded key
    cannot sit in the settings seed.
- 2026-09-14 — `Agent : l20 2` took over at phase 7 (handshake answered; gauge 10). Ruling 7 made on
  the day: the running state derived from 2b598104 by `setRunInProgress`, a handler-chosen 404 through
  `refused()`, the failed state marks no step (a demand line in the contract).
- 2026-09-14 — phase 7 RED, every hold read with no crash after making the probes null-safe (the first
  red crashed three rules after their first FAIL — a crash hides the holds behind it): raw_log.py 13 / 11,
  run_history.py 23 / 9 (the list half stays green), screen_addresses.py 58 / 3, back.py 21 / 2.
- 2026-09-14 — TRAP, measured: `offsetParent` is BLIND to a native fold. Chrome hides a closed
  `<details>`' content with `content-visibility: hidden`, the boxes stay laid out, and `offsetParent`
  stays non-null over lines nobody can see — the plan's own instrument read green over a closed fold's
  « rendered » lines on the first green run. The hold now also asks `checkVisibility()`.
- 2026-09-14 — `raw_log.py` ADDED to run.sh's CONTRACTS: it falls when a named state or a data-part
  name moves, which is that tier's subject (locks.py's reason). `back.py` stays out of that tier.
- 2026-09-14 — `mocks/state.ts` sits at 398 non-blank lines after the dial (ceiling 400);
  `mocks/index.ts` unchanged at 397. The named states pick a run through `__mocks.pipelineRuns()`
  (a seed accessor in `mock-seeds.ts`), never by a uid written in `system.ts`.
- 2026-09-14 — phase 7 oracle: 96 divergences, all on the six new `run-detail*` states, Système's at
  zero. Accepted inside one heavy invocation; verified by name: 107×37 → 113×38, added exactly the six,
  every other state differs only by a null `run/body`.
- 2026-09-14 — the replay tool: a scratch script acquires the served copy, builds, publishes, starts
  8899 with a CAPTURED pid, runs named rules each to its own log, stops, releases — and refuses when
  8899 already listens (it met l13b's host once, which is the refusal working).
- 2026-09-14 — phase 7 mutations, all four SEEN to fall naming the right defect (`mutate.sh`, 8899 by
  captured pid, tree restored): A `open` at rest → raw_log « at rest its lines are NOT rendered »; B the
  null drawn as an empty box → raw_log « a passage whose output was not kept says so »; C the fold
  pushing an entry → back.py « stacks nothing » (4 → 5); D steps ahead said « pas faite » → run_history
  « each says — ». Logs `~/Library/Logs/tm-l20/p7-mutation-{a,b,c,d}.log`.
- 2026-09-14 — phase 7 ACCEPTED by the steward on 5dd670772; L13b not merged, so l20 2 stood down.
  The `<details>`/`offsetParent` trap written into `frontend/maquette/README.md`'s traps list.
