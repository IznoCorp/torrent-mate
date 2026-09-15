# maquette-l20 — the implementer's brief for L20, « The global levers and the history »

You implement **L20**, `docs/reference/frontend-architecture.md` § 4, entry
`#### L20 — The global levers and the history` (the CONTRACT). The lot's design is
`docs/features/maquette-l20/DESIGN.md` and its plan `docs/features/maquette-l20/plan/INDEX.md` with
one file per phase — **they are the specification and this brief restates none of it**. L20 is the
NINE phases 1 to 9 of that plan, in the order INDEX.md's table gives, with one exception: **phase 8
opens only after L13b merges**, on the steward's word, and re-cuts against L13b's phase b·10-ter's
actual shape before it writes anything (`plan/phase-08-hand-path.md`'s own dated note). Phases 1–7
are ENGINE-FREE — none of them touches a `legacy.js` line — which is why L20 runs BESIDE L13b rather
than waiting for it; phase 9 follows phase 8.

Every phase is a BEHAVIOUR change: its rule is written FIRST and seen RED against `main` (the
surfaces do not exist there — the strongest form this repository asks for, no mutation needed, except
phase 8 where the defect already exists on `main` and the mutation follows the move), then green,
then its mutation SEEN to fall through `scripts/mutate.sh`; the oracle's divergences are named per
state BEFORE the run (an undeclared divergence is **STOP A**).

**Phase 2 is re-cut, and reading its dated notes matters before you open it**: `engine/states.js` no
longer exists — L13a moved the whole named-state table into `design/src/harness/states/` before this
branch was cut. Phase 2 declares nothing in code; its whole content is one dated comment in
`system.ts`. Phases 3–8 still add their own ids to `system.ts` as before — that mechanic did not
change, only the file it targets and the absence of any ceiling on it.

## Environment

- Worktree `/Users/izno/dev/worktrees/wave-l20`, branch `feat/maquette-l20`, cut from `main` at
  `4f242ecb3` (L13a's docs PR, #597) — **STACKED beside L13b**, which is its own branch
  `feat/maquette-l13b` off L13a: you never read or write there, and you never wait for its merge
  except at phase 8's opening. **ONE pull request, at the lot's end (phase 9)**, opened READY,
  version bump patch in its LAST commit. You are the only writer in this worktree. The main checkout
  and every other wave's worktree are not yours: never write, build or run there.
- The `« In flight »` row of `IMPLEMENTATION.md` is **not yours to write** — the steward's per-lot
  docs PR carries it (`frontend-steward.md` measure 4 / § « The operator's measures of 2026-09-12 »).
- Before the first heavy run: `npm ci` in `frontend/` and in `frontend/maquette/design/`, each under
  your OWN lock (`HEAVY_LOCK=/private/tmp/tm-heavy-l20/holder TM_HARNESS_JOBS=2 sh scripts/heavy.sh
  --class test l20 npm ci`).
- Your gate logs live under `~/Library/Logs/tm-l20/` (`<phase>-<step>.log`) — the weekly reboot
  (Monday 05:00) wipes `/private/tmp`, so a log a RESUME, a phase amendment or a commit body CITES is
  kept there until the merge; only uncited working logs are pruned at stand-down. The mutex and the
  tests lock stay under `/private/tmp`, as everywhere else.
- Verify the state, do not believe it:

      git remote update origin >/dev/null && git log --oneline origin/main -3
      pwd && git branch --show-current && git status --short && git log --oneline -1
      grep -n "^#### L20" docs/reference/frontend-architecture.md
      ls docs/features/maquette-l20/plan/ | wc -l
      ls frontend/maquette/design/src/harness/states/ | grep system.ts
      ls frontend/maquette/design/src/engine/    # legacy.js, seams.ts, engine-shape.ts — NO states.js
      grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
      grep -n __version__ personalscraper/__init__.py
      sh scripts/heavy.sh --held; ls -A /private/tmp/tm-heavy-tests/ | wc -l

## What you read before acting — and NOTHING ELSE before the handshake

1. This brief; `docs/features/maquette-l20/RESUME-L20.md`'s STATE BLOCK (its first 40 lines) when one
   exists; `docs/features/maquette-l20/RULINGS-L20.md` (numbered from 1, appended by the steward and by
   you when a decision is made on the day); and the phase file of the phase you open. That is the whole
   required reading before your handshake.
2. After the handshake, as each phase opens: its phase file (re-read at that moment — phases 2, 3 and 8
   carry dated amendments of 2026-09-14 from the steward's re-target after L13a merged), DESIGN § 4
   (the surfaces), § 5 (the named states — read its own dated note before trusting any figure in it),
   § 6 (the rules), § 8.4 (history, superseded — read the dated note first), and the `BUGS.md` rows the
   phase table assigns (B-296, B-297, B-371, B-383). Before phase 8 specifically: L13b's
   `plan/phase-b10-ter-pipeline-status.md` (`git show origin/feat/maquette-l13b:docs/features/maquette-l13/plan/phase-b10-ter-pipeline-status.md`),
   since your phase re-cuts against what it actually did, not against what `phase-08-hand-path.md` says
   today.

## Method — the INDEX governs, plus the steward's precisions of 2026-09-14

- **Phases run 1→7 in order, then WAIT for L13b before 8, then 9.** Before opening phase 8, ask the
  steward whether `feat/maquette-l13b` has merged; if not, stand down or take a phase from elsewhere
  only on the steward's word — never guess b·10-ter's shape from the plan alone.
- **A phase = ≤ 15 context points, with its mean stated** in every report (`frontend-steward.md`
  measure 11). **OVERLAP**: while a phase's gate runs, read the NEXT phase's file and re-take its
  figures read-only (measure/order 11); batch every STOP D question of a phase in ONE message at its
  opening, never one by one.
- **Every rule is seen RED against `main` first** (INDEX's own rule) — none of these surfaces exist
  there, so no mutation is needed to see red, except phase 8 (red against the engine as it stands,
  mutation after the move).
- **The gate on THIS branch is `main`'s tooling, not L13b's.** The one-invocation
  `run.sh --contracts --oracle [rule…]` form and `TM_HARNESS_JOBS=3` are L13b's own tooling commit and
  reach `main` only at L13b's merge. **Until then: `run.sh` on `main` reads a rule name only together
  with `--contracts --oracle` in the SAME invocation — a form that does not exist here — so never pass
  a rule name to `--contracts` alone; it is silently ignored.** Run the two tiers as SEPARATE
  invocations instead: `run.sh --contracts` (the contract rules and the repository's cheap guards),
  then `python3 frontend/maquette/oracle.py --check` on its own; to replay one rule script, run it
  directly (`python3 frontend/maquette/harness/<rule>.py`), never as an argument to `--contracts`. Use
  `TM_HARNESS_JOBS=2` until L13b's tooling lands on `main`, and say so in each gate report. Re-check
  with the steward once L13b has merged — the faster form and `TM_HARNESS_JOBS=3` apply from then on.
- **`mutate.sh` as it behaves on `main` today** — it refuses a rule path that does not exist before
  mutating (exit 64, « RULE NOT FOUND »), and an exit code of 2 with no `FAIL` line reads as
  « RULE CRASHED », an INSTRUMENT fall, never counted as « the rule fell ». Read the named `FAIL` line,
  never the « FELL » summary alone. Commit BEFORE every mutation.
- **ONE full suite (`run.sh` with no flag) at two points**: the midpoint, after phase 5's commit and
  before phase 6 opens, its falls repaired in a `fix(maquette-l20)` commit before phase 6; and at
  phase 9, before the pull request, with `--a11y`, `--compare` and `make check`.
- **No local `make check` before the pull request** (CLAUDE.md's trial, order 26) — CI's `test` job is
  the authority; the pre-PR gate is `make lint` + the full suite (`run.sh` no flag) + `--a11y` +
  `--compare` + the pre-push pytest.
- **The pull request cites the constitution §§ it serves** (§20, DOIT-1, DOIT-3, DOIT-4, DOIT-5,
  DOIT-6, NE-DOIT-PAS-1, NE-DOIT-PAS-5, §13 — the ones DESIGN names) — L20 is a BEHAVIOUR lot, so the
  trial's conversion exemption (order 32) does not apply to it.
- **Commit bodies ≤ 12 lines** — the rule-label → number mapping, the red/green readings, the
  divergences, the movements; no figure copied from a JSON file (trial, order 31) — cite the file and
  the direction instead.
- **Hold counts**: `python3 scripts/harness-hold-counts.py --compare` with `failed` read FIRST
  (B-291); a count that moved is written down, never silently re-recorded over a failing baseline.
- **`RESUME-L20.md` and `RULINGS-L20.md`, both created by your FIRST commit** (the pattern L13b's
  ruling 64 set for its own resume): `RESUME-L20.md` = a state block of at most 40 lines (rewritten at
  every boundary: head, phases done, next phase, locks/logs, what is owed) + an append-only ledger
  below it (traps, readings, figures — appended, never rewritten); `RULINGS-L20.md` numbered from 1,
  appended, never rewritten. Target: a fresh agent's spawn → first commit ≤ 15 min.
- The engine only SHRINKS — no line added to `legacy.js` before phase 8, and phase 8 subtracts and
  re-records `scripts/frontend_size_ledger.py` DOWNWARD in the same commit. Never `cd` into
  `frontend/maquette/design/src` (B-384) — absolute paths from the worktree root. Documents added BY
  FILE: `git add -f docs/features/maquette-l20/<name>.md`, never the folder (B-304).
- **CONTEXT BUDGET**: your gate is 80 %, not the skill's ~60 % (measured with
  `orchestrator:context-gauge`, read before every dispatch and pasted at the end of every report);
  under 80 % you take the next phase — standing down early is a cost, not a safety.

## Non-goals

- Nothing under `personalscraper/`; no file under L13b's worktree or branch; no reader round of your
  own (one follows the pull request, in a fresh session with a resume brief); no re-recording of the
  oracle's reference or the hold-counts baseline outside what your own phases move; no `legacy.js`
  line before phase 8.
- No phase re-ordering, no scope beyond the nine phases and their dated amendments; a plan you believe
  wrong against the tree is a STOP with the command that shows it, never a silent re-cut of your own.
- No `--no-verify`, no force-push, no merge of your own pull request, no deletion of a branch or a
  worktree; no delegate that writes or reviews (read-only search subagents only, nothing heavy).
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

One commit per phase (plus the commit-before-mutation where a phase's rule says so), conventional,
scoped `maquette-l20`, no attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg`
refuses it). **Draft nothing**: the pull request opens READY only at phase 9, once the full suite,
`--a11y`, `--compare` and CI all read green on the final head — never before. Figures are written ONCE,
measured on that final head, never copied from an earlier phase's reading. Title
`feat(maquette-l20): the global levers and the history`, body: the nine phases and what each landed,
every rule with its red reading and its mutation, the divergences named (DESIGN § 7), the register
rows closed (B-296, B-297, B-371, B-383's veille half — naming which half), the hold-count movements,
the midpoint suite's falls and their repairs, the states count before (87) and after (113), the
constitution §§ served. One reader round follows the pull request; you stay available for its
findings in a fresh session with a resume brief, not in this one.

## Communication

Your orchestrator's exact `ListAgents` name and reference are in the LAUNCH PROMPT — never a reference
written in this file, which may be stale by the time you read it. First act after the required
reading: the handshake — the state-verification readings and your gauge — and nothing is in flight
until it is answered. Then: a report at every phase gate and at every STOP (the STOP, its evidence,
the proposed resolution, and you WAIT), one line before and after every shared-mutex run, the push
report. A message that expects an answer and has none after fifteen minutes is re-sent after a fresh
`ListAgents`, to the session whose NAME matches, marked as a re-send; if the name is not listed, tell
the user in your own session and stop waiting. Do not stop between phases to report one done. Every
report ends with the gauge:
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.29.2/skills/context-gauge/scripts/context-gauge.sh`
run as the LAST call, its `context_percent=` and `source=` lines pasted. **The context gate is 80 %**:
(a) crossing it mid-work, finish the unit in progress (or commit a compiling « part 1 »), rewrite
`RESUME-L20.md`'s state block, append its ledger, push under the tests lock, prune uncited working
logs, report « stood down » with `git ls-remote` proving the push, and stop — the steward spawns your
successor; (b) PRE-DISPATCH: open the next phase when your measured gauge + the measured cost of your
last phase is ≤ 80 — never a rotation mid-phase; (c) compaction-readiness stands whatever the gauge:
every state on disk, nothing only in your context.

## Resource envelope — the machine is shared (2026-09-14)

Another agent may run beside the steward on this 8-core, 16 GB host (L13b's implementer, most likely,
since L20 runs beside it). **Locks by CLASS**: anything touching the ONE served copy or the 8899 host
— `run.sh` in any tier, the oracle, `harness-hold-counts.py`, `mutate.sh`, a single rule replayed —
runs under the shared mutex, `TM_HARNESS_JOBS=2 sh scripts/heavy.sh --class browser l20 <command>`,
one line to the steward before and after; another agent may hold it — wait, never bypass, and read
`sh scripts/heavy.sh --held` first. Every pytest, `make check` and `git push` (the pre-push hook runs
the test suite) under the ONE shared tests lock:
`HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder TM_HARNESS_JOBS=2 sh scripts/heavy.sh --class test l20
<command>`. `npm ci` and builds keep your OWN lock (`HEAVY_LOCK=/private/tmp/tm-heavy-l20/holder`).
Never a test run beside a harness run of your own. Every command runs synchronously in the tool call
that waits for it, long output to a FILE under your log directory, the exit code read in the same
call, **never `| tail -N` on a long gate**. Kill what you start, delete what you build, prove it with
`ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node |pytest|heavy.sh" | grep -v grep`
before every report; the 8899 host (`server.py --serve 8899`, parent 1) is `run.sh`'s and is left
alone. Search safety (`CLAUDE.md`): every `rg`/`grep -r` carries a type filter. Tier **deep** (the map
binds every tier to opus; no tier of this project is ever Sonnet). Your session was spawned with NO
MCP server; the harness needs none.
