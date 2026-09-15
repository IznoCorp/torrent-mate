# maquette-l13r — the implementer's brief for L13r, « The engine's residue »

You implement **L13r**, the third sub-lot of **L13 — The engine's residue** (`docs/reference/frontend-architecture.md`
§ 4, entry `#### L13`, the CONTRACT), born of ruling 99 (Q5 = B, 2026-09-15): L13b closed at b·12 and what
`engine/legacy.js` still holds — 1 601 live non-blank lines, measured at ruling 98 — is a CONVERSION the size
of a sub-lot, not a deletion. The lot's design is `docs/features/maquette-l13/DESIGN.md` and its plan
`docs/features/maquette-l13/plan/INDEX.md` § « L13r — The engine's residue », one file per phase
(`plan/phase-r01-…md` to `plan/phase-r14-…md`) — **they are the specification and this brief restates none of
it**. L13r is the fourteen phases r·1 to r·14 (ruling 101 cut r·3 in two, ruling 105 cut r·6 in six, ruling 106 added the system families, ruling 107 cut r·10 in two), in that order: the interface constants and helpers find homes (r·1),
the served fixtures go to their seeds (r·2), the settings machine, `render()`/`applyState` and the search mount
leave the engine (r·3 the product verbs and r·4 the frame verbs, the BEHAVIOUR phases), `__referentiel` and the nine
slices die (r·5), `engine-shape`'s family labels become the contract's names, one family group per phase (r·6 to r·13), the file
and its instruments die under the full gate (r·14).

**Rulings 1–99 are in `docs/features/maquette-l13/RULINGS.md`** — one numbered file, non-reopenable; L13r appends
from 100. The ones that shape L13r: 57 (the constants' homes), 86-bis and 98 (what the engine still holds and why),
96 (the frame-domain ratchet at lib/ 28, app/ 139 — a raise is a STOP D with its reason), 99 (this sub-lot).

## Environment

- Worktree `/Users/izno/dev/worktrees/wave-l13r`, branch `feat/maquette-l13r`, cut from L13b's FINAL head
  `fcaff976f` (pull request #601) — STACKED (measure 9): L13b's reader round and merge are never awaited. **When the
  steward tells you L13b is squashed onto `main`, you MERGE `origin/main` in at your next unit boundary**
  (`git merge --no-edit <sha the steward names>`; never a rebase — the auto-mode classifier refuses a force-push on a
  shared branch, and a plain push after a merge is the shape #601 took); a conflict you cannot resolve by re-applying
  your own phase is a STOP, never a hand-merge. You are the only writer there. The main checkout
  `/Users/izno/dev/PersonalScraper`, `/Users/izno/dev/worktrees/wave-l13b`, `/Users/izno/dev/worktrees/reader-l13b`
  and `/Users/izno/dev/worktrees/control-l13b` are not yours: never write, build or run there.
- Both `node_modules` are installed. Your log directory is `~/Library/Logs/tm-l13r/` (order 34): `<phase>-<step>.log`;
  gate logs kept until the merge, working logs pruned at every stand-down and proved by `ls`; a log a RESUME line or a
  commit body CITES is kept.
- Verify the state, do not believe it:

      git remote update origin >/dev/null && git log --oneline origin/main -3
      pwd && git branch --show-current && git status --short && git log --oneline -1
      ls docs/features/maquette-l13/plan/ | grep -c "phase-r"        # 14
      grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/legacy.js   # 1 600
      python3 scripts/check-frontend-boundaries.py --arm size; echo "exit $?"
      python3 scripts/check-frame-domain.py; echo "exit $?"
      grep -n __version__ personalscraper/__init__.py               # 0.98.94 (bump at the PR only)
      sh scripts/heavy.sh --held; ls -A /private/tmp/tm-heavy-tests/ | wc -l

## What you read before acting — and NOTHING ELSE before the handshake (auditor's order 8)

1. This brief; `docs/features/maquette-l13/RESUME-L13r.md`'s STATE BLOCK (its first 40 lines); `RULINGS.md` 57, 85,
   86-bis, 96–99; and `plan/phase-r01-constants-and-helpers.md`. That is the whole required reading before your handshake.
2. After the handshake, as each phase opens: its phase file (re-read at that moment), DESIGN § 9 (homes) and
   § 6 for r·3 and r·4, `frontend/maquette/README.md` § named states and § traps (one-line rules since #599, stories cited),
   `CLAUDE.md` § Critical Rules (search safety, language, naming, `scripts/rename-identifiers.py` — never a rename by
   hand), and `scripts/check-mock-seeds.py`'s docstring for r·2 (the register's classes: a family is served, interface
   or converted, and the count must FALL by the families moved).

## Method — the INDEX governs, plus the office's precisions

- **A conversion phase proves by « nothing observable changed »**: the contracts tier + the named rules that draw each
  moved name (grep `window.__go` ids under `harness/states/` at the phase's opening) stay green with their hold counts
  unchanged; the oracle at ZERO divergence — any divergence is STOP B, never accepted under a conversion's name. A moved
  pure function gets a vitest where none exists. **r·3 and r·4 are BEHAVIOUR**: its rule is written FIRST and seen RED, green
  after, its mutation SEEN to fall through `scripts/mutate.sh` (commit before every mutation); where no hold taps a
  moved function, a rule is written for it before it moves.
- **Sizes**: every phase ≤ 15 points against the stated mean (11); the former « contract names » phase was measured
  and cut into r·6–r·13 by rulings 105, 106 and 107, whose method (the contract type first, `tsc`'s diagnostics as the reader list)
  each of those phase files carries.
- **Locks by CLASS.** Anything touching the ONE served copy or the 8899 host — `run.sh` in any tier, the oracle,
  `harness-hold-counts.py`, `mutate.sh`, a single rule replayed — runs under the shared mutex, in the ONE form that
  reads rule names: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l13r frontend/maquette/harness/run.sh
  --contracts --oracle <rule paths>` (rulings 66, 81, 92: full paths, one build, one verdict block), one line to the
  steward before and after; **L13b's reader holds the mutex for its mutation series tonight — wait, never bypass, and
  read `sh scripts/heavy.sh --held`**. Every pytest and `git push` under the ONE tests lock:
  `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh --class test l13r <command>`
  — and a harness run never starts while the tests lock is held, nor a push while the mutex is (read both first).
  `npm ci` and builds keep your own lock `HEAVY_LOCK=/private/tmp/tm-heavy-l13r/holder`.
- **Mutations**: `sh scripts/mutate.sh <full path> "<python expression>" frontend/maquette/harness/<rule>.py` — read the
  NAMED `FAIL` line; « RULE CRASHED » and « RULE NOT FOUND » prove nothing; a hold that prints nothing cannot fall by name.
- **A phase's gate** = one wrapped `run.sh --contracts --oracle <named rules>` + the 26 cheap guards it runs, logs
  POSTDATING the commit they measure (`ls -lT` against `git log -1 --format=%ci`); `tests/scripts/test_check_maquette_comments.py`
  alone under the tests lock before any push, `check-maquette-comments.py --record` INSIDE the commit when a maquette
  file moved (only `read` moves — read the diff). **The FULL SUITE runs TWICE in L13r (measure 20)**: at the midpoint,
  after r·4 and before r·5, its falls repaired by you before r·5; and at r·14 before the pull request, with `--a11y`,
  `scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` (its `taken_at_commit` may
  not be an ancestor of your head — compare against a `.review`-style copy re-pointed at main's sha, the repo file
  untouched, and say so) and `make lint`; no local `make check` (measure 19).
- **The three arms**: `python3 scripts/check-frame-domain.py` on the head BEFORE each phase's move (send its ceiling
  line; ruling 96's figures are the ceiling); `check-frontend-boundaries.py --arm fan-in` and `--arm cycles` after r·4
  and r·5; `check-no-french.py` after every vocabulary addition and `--counts` at r·14; `check-mock-seeds.py` after r·2.
  Exit codes are the verdict, never the prose.
- The engine only shrinks; `scripts/frontend_size_ledger.py` re-recorded DOWNWARD in the same commit (the entry dies
  at r·7); guards and baselines die in the phase that kills what they read (the reference-slice arm at r·5, the parser
  arms and `resync.py` at r·14); re-aims said out loud in the docstring and the body; never `cd` into `design/src` (B-384).
- **The RESUME**: `docs/features/maquette-l13/RESUME-L13r.md` = a STATE BLOCK of at most 40 lines (rewritten at every
  boundary) + an APPEND-ONLY ledger below it. Rulings go to `RULINGS.md`, appended from 100. No register row for an
  unshipped defect (ruling 85): a ledger line on the phase instead; the steward numbers rows at the close.
- **`IMPLEMENTATION.md` is the steward's**: the wave does not touch it. **No edit to `docs/reference/*`, `CLAUDE.md`,
  the office**; a full-path citation of a file your phase deletes, refused by `check-docs-cited-paths.py`, is re-cited
  `path@fcaff976f` and nothing else in that file, said in the body.
- **CONTEXT BUDGET ≤ 15 points per phase**: gate logs read by their verdict line only; commit bodies ≤ 12 lines, no
  baseline figure in a body (order 31: file + direction in one line); a phase-file amendment is ONE dated line. Gauge
  at every phase boundary, before and after; **under 45 % you TAKE the next phase**. Overlap: while a gate runs you read
  the next phase's file and re-take its figures read-only; every STOP D of a phase is ONE message at its opening.

## Non-goals

- No phase of L13c; no conversion of anything the plan does not name; no new guard, arm or tool (measure 1 — a phase's
  own rule or a re-aim is not new apparatus). No redrawing: every visual change is STOP B.
- No `--no-verify`, no force-push, no merge of your own pull request, no deletion of a branch or a worktree; no delegate
  that writes or reviews (read-only search subagents only, nothing heavy). No run on 8712, 8931, 8973 or 8974 (the
  reader's ports), never `/tmp/tm-refonte` by hand.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

One commit per phase (plus the commit-before-mutation where a phase says so), conventional, scoped `maquette-l13r`, no
attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg` refuses it). Push at every stand-down and at
r·14 under the tests lock. At r·14: merge `origin/main` in, bump the version above whatever `main` reads then (patch), the
full gate, pull request READY titled `refactor(maquette-l13r): the engine's residue — legacy.js dies`; a CONVERSION pull
request cites no constitution §§ (order 32, the rule) — r·3's and r·4's behaviour half is SAID in the body with its rule and §§.
Body: the six phases and what each moved and deleted (by command, measured ONCE on the final head), every rule written
or re-aimed with its red run and its mutation, the hold-count movements with their cause, the midpoint suite's falls
and repairs, the ledger's final count (0), the surfaces whose look or behaviour a first-time reader would notice (for
the reader's affordance lens). One reader round follows (measure 2); you stay available for its findings in a fresh
session with a resume brief, not in this one.

## Communication

Your orchestrator's exact `ListAgents` name and reference are in the launch prompt. First act after the required
reading: the handshake — the state-verification readings and your gauge — and nothing is in flight until it is
answered. Then: a report at every phase gate and at every STOP (the STOP, its evidence, the proposed resolution, and
you WAIT), one line before and after every shared-mutex run, the arm readings named above, the push report. A message
that expects an answer and has none after fifteen minutes is re-sent after a fresh `ListAgents`, to the session whose
NAME matches, marked as a re-send; if the name is not listed, tell the user in your session and stop waiting. **Do not
stop between phases to report one done.** Every long run is waited for INSIDE the tool call (timeout ≤ 600 s, or a
bounded loop polling its log) — never a turn ended on a run still going (order 36). Every report ends with the gauge:
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.29.2/skills/context-gauge/scripts/context-gauge.sh`
run as the LAST call, its `context_percent=` and `source=` lines pasted. **The context gate is 80 %** (measure 8): (a)
crossing it mid-work, you finish the unit in progress (or commit a compiling « part 1 »), rewrite the RESUME's state
block, append the ledger, push under the tests lock, prune, report « stood down » with `git ls-remote` proving the
push, and stop — the steward spawns your successor; (b) PRE-DISPATCH: you OPEN the next phase when your measured gauge
+ the measured cost of your last phase is ≤ 80 — never a rotation mid-phase; (c) every state on disk, nothing only in
your context.

## Resource envelope — the machine is shared

TWO agents may run beside the steward on this 8-core, 16 GB host (L13b's reader overlaps your first phases): the mutex
and the tests lock serialise the heavy runs; you announce yours. Every command runs synchronously in the tool call that
waits for it, long output to a FILE under `~/Library/Logs/tm-l13r/`, the exit code read in the same call. Fan-out has a
name and a value, every time: `TM_HARNESS_JOBS=3`, `PYTEST_XDIST_AUTO_NUM_WORKERS=3`. Kill what you start, delete what
you build (`design/dist`, bench copies, screenshots), prove it with
`ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node |pytest|heavy.sh" | grep -v grep` before every report;
the 8899 host (`server.py --serve 8899`, parent 1) is `run.sh`'s and is left alone. Search safety (`CLAUDE.md`): every
`rg`/`grep -r` carries a type filter. Tier **deep** (the map: deep = opus), chosen because r·3 and r·4 write rules whose red
reading nobody else takes before the reader round and the contract-name phases' readers are found by the compiler, not re-read by anyone. Your session was spawned
with NO MCP server; the harness needs none.
