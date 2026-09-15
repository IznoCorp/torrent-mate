# maquette-l13c — the implementer's brief for L13c, « What the engine was blocking »

You implement **L13c**, the third and LAST sub-lot of **L13 — The engine's residue**
(`docs/reference/frontend-architecture.md` § 4, entry `#### L13`, the CONTRACT). L13a moved the
engine's code out unchanged, L13b moved its verbs and repaired the ladder's shape, L13r converted
what remained of `legacy.js` and deleted the file; L13c is the eight BEHAVIOUR repairs the engine's
presence was blocking, plus the close. The lot's design is `docs/features/maquette-l13/DESIGN.md`
and its plan `docs/features/maquette-l13/plan/INDEX.md` § « L13c — What the engine was blocking »,
one file per phase (`plan/phase-c01-…md` to `plan/phase-c09-close.md`) — **they are the
specification and this brief restates none of it**. L13c is nine phases c·1 to c·9, in that order:
the selection survives the lens (c·1, B-312), a fresh add screen (c·2, B-340), a disabled action
looks disabled (c·3, B-339), the kind chips hide their scrollbar (c·4, B-336), the pull indicator
(c·5, B-331), the seventh scheduler (c·6, B-327), no follow without a sheet (c·7, B-366), the
library's states at rest (c·8, B-345's library half), and the close (c·9 — the register re-read,
the stale reference sentences, the report; DESIGN § 9, § 10).

**Rulings 1–109(+) are in `docs/features/maquette-l13/RULINGS.md`** — one numbered file,
non-reopenable; L13c appends from **110** (the steward's number, in the launch prompt — L13r holds
100–103 as it opens; the margin is deliberate). The ones that shape L13c: 27/Ruled B (the three-lot
cut), the D-L13-1 lines (28, and DESIGN § 8) that c·1's selection-bar and c·7's follow contract
build beside, and 98–99 (why L13r exists between L13b and this sub-lot). DESIGN § 9 and § 10 are
this brief's real reading, not restated here.

## Environment

- Worktree `/Users/izno/dev/worktrees/wave-l13c`, branch `feat/maquette-l13c`, cut from L13r's FINAL
  head `22166378e` (its pull request's head) — STACKED (measure 9): L13r's reader round and merge
  are never awaited. **When the steward tells you L13r is squashed onto `main`, you MERGE
  `origin/main` in at your next unit boundary** (`git merge --no-edit <sha the steward names>`;
  never a rebase — the auto-mode classifier refuses a force-push on a shared branch, and a plain
  push after a merge is the shape #601 took); a conflict you cannot resolve by re-applying your own
  phase is a STOP, never a hand-merge. You are the only writer there. The main checkout
  `/Users/izno/dev/PersonalScraper`, `/Users/izno/dev/worktrees/wave-l13r` (L13r's, under its reader
  round) and any reader's worktree (`reader-l13r`, `control-l13r`) are not yours: never write, build
  or run there.
- Both `node_modules` are installed. Your log directory is `~/Library/Logs/tm-l13c/` (order 34):
  `<phase>-<step>.log`; gate logs kept until the merge, working logs pruned at every stand-down and
  proved by `ls`; a log a RESUME line or a commit body CITES is kept.
- Verify the state, do not believe it:

      git remote update origin >/dev/null && git log --oneline origin/main -3
      pwd && git branch --show-current && git status --short && git log --oneline -1
      ls docs/features/maquette-l13/plan/ | grep -c "phase-c0"        # 9
      python3 scripts/check-frontend-boundaries.py --arm size; echo "exit $?"
      python3 scripts/check-frame-domain.py; echo "exit $?"
      grep -n __version__ personalscraper/__init__.py               # above 0.98.94 (bump at the PR only)
      sh scripts/heavy.sh --held; ls -A /private/tmp/tm-heavy-tests/ | wc -l

## What you read before acting — and NOTHING ELSE before the handshake (auditor's order 8)

1. This brief; `docs/features/maquette-l13/RESUME-L13c.md`'s STATE BLOCK (its first 40 lines);
   `RULINGS.md` 27–28, 98–99; and `plan/phase-c01-selection-survives-lens.md`. That is the whole
   required reading before your handshake.
2. After the handshake, as each phase opens: its phase file (re-read at that moment), DESIGN § 9 and
   § 10 (the register, assigned, and what the plan got wrong), `frontend/maquette/README.md` §
   named states and § traps (one-line rules since #599, stories cited), `CLAUDE.md` § Critical Rules
   (search safety, language, naming, `scripts/rename-identifiers.py` — never a rename by hand), and
   `scripts/check-mock-seeds.py`'s docstring for c·8 (the register's classes: served, interface or
   converted).

## Method — the INDEX governs, plus the office's precisions

- **Every phase of L13c is BEHAVIOUR** (`plan/INDEX.md` § « The rule that governs every phase »):
  **the rule FIRST, seen RED**, its label bound to the next free number
  (`grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1` against
  `origin/main`), then the move, then the same rule green with its holds counted, then a mutation
  that fells it by name — as BRIEF-L13r § Method describes for r·3 and r·4, the shape every c-phase
  takes here. Where the phase file names a second reading before the move (c·5's off-centre sample,
  c·7's type mutation, c·8's measurement against the drawing), that reading is taken FIRST and its
  result is what the rule is written from. The oracle may diverge ONLY on the states each phase
  names, each accepted with its register row (D8); any other divergence is STOP B.
- **Sizes**: every phase ≤ 15 points (measure 11, `docs/reference/frontend-steward.md`) — at a
  phase's opening you MEASURE it against its own file before committing to the shape written there;
  a figure that no longer supports the phase's move is STOP D, reported with the command, never
  improvised past.
- **Locks by CLASS.** Anything touching the ONE served copy or the 8899 host — `run.sh` in any
  tier, the oracle, `harness-hold-counts.py`, `mutate.sh`, a single rule replayed — runs under the
  shared mutex, in the ONE form that reads rule names: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh
  --class browser l13c frontend/maquette/harness/run.sh --contracts --oracle <rule paths>` (rulings
  66, 81, 92: full paths, one build, one verdict block; measure 17), one line to the steward before
  and after; **read `sh scripts/heavy.sh --held` and wait, never bypass**. Every pytest and
  `git push` under the ONE tests lock:
  `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh --class test l13c <command>`
  — and a harness run never starts while the tests lock is held, nor a push while the mutex is
  (read both first). `npm ci` and builds keep your own lock
  `HEAVY_LOCK=/private/tmp/tm-heavy-l13c/holder`.
- **Mutations**: `sh scripts/mutate.sh <full path> "<python expression>" frontend/maquette/harness/<rule>.py`
  — read the NAMED `FAIL` line; « RULE CRASHED » and « RULE NOT FOUND » prove nothing; a hold that
  prints nothing cannot fall by name; commit before every mutation.
- **A phase's gate** = one wrapped `run.sh --contracts --oracle <named rules>` + the 26 cheap guards
  it runs, logs POSTDATING the commit they measure (`ls -lT` against `git log -1 --format=%ci`);
  `tests/scripts/test_check_maquette_comments.py` alone under the tests lock before any push,
  `check-maquette-comments.py --record` INSIDE the commit when a maquette file moved. **The FULL
  SUITE runs TWICE in L13c**: at the MIDPOINT, after c·5 and before c·6 opens (auditor's order 5,
  the shape L13b's own midpoint took — measure 20), its falls repaired by you before c·6; and at
  c·9 before the pull request, with `--a11y`, `scripts/harness-hold-counts.py --compare
  frontend/maquette/hold-counts-baseline.json` (its `taken_at_commit` may not be an ancestor of your
  head — compare against a `.review`-style copy re-pointed at main's sha, the repository file
  untouched, and say so), `python3 scripts/check-bug-register.py` and `python3
  scripts/check-intent-map.py`, both read by OUTPUT. **No local `make check`** (measure 19): CI's
  `test` job is the authority; the pre-PR gate is `make lint` + the full suite + `--a11y` +
  `--compare` + the pre-push pytest.
- **Fixture checks**: `python3 scripts/check-mock-seeds.py` exits 0 after c·8's seed fill.
- The engine is already dead (L13r's gesture); no phase of L13c touches `legacy.js` — if one
  believes it must, that is a STOP, not a move. Re-aims said out loud in the docstring and the body;
  never `cd` into `design/src` (B-384).
- **The RESUME**: `docs/features/maquette-l13/RESUME-L13c.md` = a STATE BLOCK of at most 40 lines
  (rewritten at every boundary) + an APPEND-ONLY ledger below it. Rulings go to `RULINGS.md`,
  appended from 115 (L13r closed at 114). No register row for an unshipped defect (ruling 85's precedent): a ledger line
  on the phase instead; each phase's OWN register row (B-312, B-340, B-339, B-336, B-331, B-327,
  B-366, B-345) closes in the phase that lands it, with the rule's red reading and its mutation, in
  the register itself.
- **`IMPLEMENTATION.md` is the steward's**: the wave does not touch it. **No edit to
  `docs/reference/*` (`docs/features/maquette-l13/DESIGN.md`'s own § 9 amendment excepted — the
  wave amends only the file under its own folder), `CLAUDE.md`, the office**; a full-path citation
  of a file your phase deletes, refused by `check-docs-cited-paths.py`, is re-cited
  `path@08400a22a` (L13r's squash on main — never the PR head, whose commits leave the remote with
  the branch) and nothing else in that file, said in the body.
- **CONTEXT BUDGET ≤ 15 points per phase**: gate logs read by their verdict line only; commit bodies
  ≤ 12 lines, no baseline figure in a body (order 31: file + direction in one line); a phase-file
  amendment is ONE dated line. Gauge at every phase boundary, before and after; **under 45 % you
  TAKE the next phase**. Overlap: while a gate runs you read the next phase's file and re-take its
  figures read-only; every STOP D of a phase is ONE message at its opening.

## Non-goals

- No phase already closed (L13a, L13b, L13r); no conversion of anything the plan does not name; no
  new guard, arm or tool (measure 1 — a phase's own rule or a re-aim is not new apparatus). No
  redrawing beyond what a phase's move names: every visual change outside it is STOP B.
- No `--no-verify`, no force-push, no merge of your own pull request, no deletion of a branch or a
  worktree; no delegate that writes or reviews (read-only search subagents only, nothing heavy). No
  run on the reader's ports, never `/tmp/tm-refonte` by hand.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

One commit per phase (plus the commit-before-mutation where a phase says so, and c·5's/c·7's
extra reading commit if the phase file's own proof needs one), conventional, scoped `maquette-l13`
(the commit subjects `plan/phase-c0*.md` already name — e.g. `fix(maquette-l13): …`), no
attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg` refuses it). Push at
every stand-down and at c·9 under the tests lock. At c·9: merge `origin/main` in, bump the version
above whatever `main` reads then (patch), the full gate, `docs/features/maquette-l13/REPORT.md`
written (new file, added BY FILE — never a folder), pull request READY titled
`fix(maquette-l13c): the engine's own repairs — selection, the add screen, the seventh scheduler,
and the close` — a BEHAVIOUR pull request, so it cites the constitution §§ each phase's DESIGN entry
serves (order 32 exempts conversions only). Body: the nine phases and what each moved, every rule
written with its red run and its mutation, the register rows closed (B-312, B-340, B-339, B-336,
B-331, B-327, B-366, B-345), the midpoint suite's falls and repairs, the ledger's final count (0),
**the lot's own gesture** — `docs/features/maquette-l13/` deleted whole (documentation-model.md §
4: the folder is the LOT's, and dies at its LAST sub-lot's gesture), every citation of it in the
tree rewritten `path@<the merge sha>`. One reader round follows (measure 2); you stay available for
its findings in a fresh session with a resume brief, not in this one.

## Communication

Your orchestrator's exact `ListAgents` name and reference are in the launch prompt. First act after
the required reading: the handshake — the state-verification readings and your gauge — and nothing
is in flight until it is answered. Then: a report at every phase gate and at every STOP (the STOP,
its evidence, the proposed resolution, and you WAIT), one line before and after every shared-mutex
run, the arm readings named above, the push report. A message that expects an answer and has none
after fifteen minutes is re-sent after a fresh `ListAgents`, to the session whose NAME matches,
marked as a re-send; if the name is not listed, tell the user in your session and stop waiting. **Do
not stop between phases to report one done.** Every long run is waited for INSIDE the tool call
(timeout ≤ 600 s, or a bounded loop polling its log) — never a turn ended on a run still going
(order 36). Every report ends with the gauge:
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.29.2/skills/context-gauge/scripts/context-gauge.sh`
run as the LAST call, its `context_percent=` and `source=` lines pasted. **The context gate is 80 %**
(measure 8): (a) crossing it mid-work, you finish the unit in progress (or commit a compiling « part
1 »), rewrite the RESUME's state block, append the ledger, push under the tests lock, prune, report
« stood down » with `git ls-remote` proving the push, and stop — the steward spawns your successor;
(b) PRE-DISPATCH: you OPEN the next phase when your measured gauge + the measured cost of your last
phase is ≤ 80 — never a rotation mid-phase; (c) every state on disk, nothing only in your context.

## Resource envelope — the machine is shared

TWO agents may run beside the steward on this 8-core, 16 GB host (measure 6). The mutex and the
tests lock serialise the heavy runs; you announce yours. Every command runs synchronously in the
tool call that waits for it, long output to a FILE under `~/Library/Logs/tm-l13c/`, the exit code
read in the same call. Fan-out has a name and a value, every time: `TM_HARNESS_JOBS=3`,
`PYTEST_XDIST_AUTO_NUM_WORKERS=3`. Kill what you start, delete what you build (`design/dist`, bench
copies, screenshots), prove it with
`ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node |pytest|heavy.sh" | grep -v grep`
before every report; the 8899 host (`server.py --serve 8899`, parent 1) is `run.sh`'s and is left
alone. Search safety (`CLAUDE.md`): every `rg`/`grep -r` carries a type filter. Tier **deep** (the
map: deep = opus), chosen because every phase writes a rule whose red reading nobody else re-reads
before the reader round, and c·9's close re-reads the whole lot's debts against the tree, a judgment
nobody re-checks. Your session was spawned with NO MCP server; the harness needs none.
