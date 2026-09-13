# maquette-l13b — the implementer's brief for L13b, « The engine's verbs and the ladder's shape »

You implement **L13b**, the second sub-lot of **L13 — The engine's residue** (`docs/reference/frontend-architecture.md`
§ 4, entry `#### L13`, the CONTRACT). The lot's design is `docs/features/maquette-l13/DESIGN.md` and its plan
`docs/features/maquette-l13/plan/INDEX.md` with one file per phase — **they are the specification and this brief
restates none of it**. L13b is the TWELVE BEHAVIOUR phases b·1 to b·11 of that plan, in that order, **with b·10-bis
between b·10 and b·11**: the engine's 62 delegation names registered by feature, its gesture listeners, one ladder
shape (D-L13-1, ratified), the panel's return, the library's membership read, then `legacy.js` and its React-side
support die. Every phase is a BEHAVIOUR change: **its rule is written FIRST and seen RED against the engine, then
green, and its mutation is SEEN to fall** through `scripts/mutate.sh`; the oracle's divergences are NAMED per state
BEFORE the run (a divergence the phase did not name is STOP B).

**Rulings 1–61 are in `docs/features/maquette-l13/RULINGS.md`** — one numbered file, non-reopenable; L13b appends
from 62. The ones that shape L13b: 9 (doors, not import owners), 10 (`queries.ts` leaves `FAN_IN_EXEMPT` when the
engine's last read goes), 16 (`applyState` leaves at b·7), 28 (D-L13-1 = A, STOP E lifted), 41 + 53 (b·10-bis's
subjects), 57 (b·11's subjects and the twelve constants' homes), 59 (the #ptr utilities erased by `__reposPTR`, b·8's).

## Environment

- Worktree `/Users/izno/dev/worktrees/wave-l13b`, branch `feat/maquette-l13b`, cut from L13a's FINAL head
  `37e54d0fd` (pull request #596) — STACKED, by the auditor's order 7 of 2026-09-13: L13a's reader round
  and merge are never awaited. **When the steward tells you L13a is squashed onto `main`, you rebase at your next
  unit boundary** (`git rebase origin/main`, the steward names the base sha); a conflict you cannot resolve by
  re-applying your own phase is a STOP, never a hand-merge. You are the only writer there. The main checkout
  `/Users/izno/dev/PersonalScraper` and `/Users/izno/dev/worktrees/wave-l13a` are not yours: never write, build or run there.
- Before the first heavy run: `npm ci` in `frontend/` and in `frontend/maquette/design/` of the worktree, each under
  your OWN lock (`HEAVY_LOCK=/private/tmp/tm-heavy-l13b/holder sh scripts/heavy.sh --class test l13b npm ci`).
- Your log directory is `/private/tmp/tm-l13b/` (ruling 36): `<phase>-<step>.log`; gate logs kept until the merge,
  working logs pruned at every stand-down and proved by `ls`.
- Verify the state, do not believe it:

      git remote update origin >/dev/null && git log --oneline origin/main -3
      pwd && git branch --show-current && git status --short && git log --oneline -1
      grep -n "^#### L13" docs/reference/frontend-architecture.md
      ls docs/features/maquette-l13/plan/ | wc -l && ls docs/features/maquette-l13/RULINGS.md
      grep -cve '^[[:space:]]*$' frontend/maquette/design/src/engine/legacy.js
      python3 scripts/check-frontend-boundaries.py --arm size; echo "exit $?"
      python3 scripts/check-frame-domain.py; echo "exit $?"
      grep -n __version__ personalscraper/__init__.py
      sh scripts/heavy.sh --held; ls -A /private/tmp/tm-heavy-tests/ | wc -l

## What you read before acting — and NOTHING ELSE before the handshake (auditor's order 8)

1. This brief; `docs/features/maquette-l13/RESUME.md`'s STATE BLOCK (its first 40 lines) when one exists;
   `RULINGS.md`; and the phase file of the phase you open. That is the whole required reading before your handshake.
2. After the handshake, as each phase opens: its phase file (re-read at that moment — each carries dated amendments
   of 2026-09-13 from the steward's dry read of the three arms), DESIGN § 6 (the verbs), § 8 (the ladder, ratified)
   and § 9 (homes), `frontend/maquette/README.md` § named states and § traps, `CLAUDE.md` § Critical Rules (search
   safety, language, naming, the rename tool `scripts/rename-identifiers.py` — never a rename by hand), and the
   `BUGS.md` rows the phase table assigns (B-465, B-337, B-290, B-397, B-275).

## Method — the INDEX governs, plus the office's precisions of 2026-09-13

- **Behaviour phases prove by RULE**: written first, RED against the engine as it stands (the red run's log kept
  and named in the body), green after, its mutation SEEN to fall through `scripts/mutate.sh` (commit before every
  mutation). The oracle: divergences named per state in the phase's amendment before the gate; zero elsewhere.
  Hold counts: `failed` read FIRST, every movement written.
- **Locks by CLASS.** Anything touching the ONE served copy or the 8899 host — `run.sh` in any tier, the oracle,
  `harness-hold-counts.py`, `mutate.sh`, a single rule replayed — runs under the shared mutex,
  `TM_HARNESS_JOBS=2 sh scripts/heavy.sh --class browser l13b <command>`, one line to the steward before and after;
  **another agent (L13a's reader) may hold it — wait, never bypass, and read `sh scripts/heavy.sh --held`**. Every
  pytest, `make check` and `git push` under the ONE tests lock:
  `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder PYTEST_XDIST_AUTO_NUM_WORKERS=2 sh scripts/heavy.sh --class test l13b <command>`.
  `npm ci` and builds keep your own lock. Never a test run beside a harness run.
- **A phase's gate** = the contracts tier + the oracle, one wrapped run each, logs POSTDATING the commit they
  measure (read `ls -lT` against `git log -1 --format=%ci`; a log older than its commit measured the working tree
  and is re-run). **The FULL SUITE runs TWICE in L13b (auditor's order 5)**: once at the MIDPOINT — after b·6 is
  committed and before b·7 opens, on b·6's head, its falls repaired by you in a `fix(maquette-l13b)` commit before
  b·7 — and once at b·11 before the pull request, with `--a11y`, `--compare`, `make check`.
- **The three arms, before and after (audit order 2)**: `python3 scripts/check-frame-domain.py` on the head BEFORE
  each phase's move (send its ceiling line); `python3 scripts/check-frontend-boundaries.py --arm fan-in` and
  `--arm cycles` AFTER b·5, b·6 and b·10; `python3 scripts/check-no-french.py` after every vocabulary addition and
  `--counts` at b·11 (a vacuous arm shows there before it turns red). Exit codes are the verdict, never the prose.
- **After each phase's commit and before any push**: `tests/scripts/test_check_maquette_comments.py` alone under
  the tests lock; `check-maquette-comments.py --record` INSIDE the phase's commit when a maquette file or a dated
  comment moved; read the diff (only `read` moves). `harness/page_host.py` is at 999/1000: zero-net-line edits only,
  said in the body; the first added line extracts a module.
- **The RESUME (order 8)**: `docs/features/maquette-l13/RESUME.md` = a STATE BLOCK of at most 40 lines (rewritten
  at every boundary: head, phases done, next phase, locks/logs, what is owed) + an APPEND-ONLY ledger below it
  (traps, readings, figures — appended, never rewritten). Rulings go to `RULINGS.md`, appended and numbered.
  Target: a fresh agent's spawn → first commit ≤ 15 min.
- The engine only shrinks; `scripts/frontend_size_ledger.py` re-recorded DOWNWARD in the same commit; guards and
  baselines die in the phase that kills what they read; re-aims said out loud in the docstring and the body;
  documents added by file; never `cd` into `design/src` (B-384); labels bound to numbers when a rule is written.
- **The « In flight » row of `IMPLEMENTATION.md` is the steward's per-lot docs PR's (auditor's order 15, 2026-09-13)**:
  the wave does not touch `IMPLEMENTATION.md` beyond a citation the paths guard forces; the PR body carries the
  figures. Register rows your phases close read `fixed #<your PR>` in the closure's commit.

- **CONTEXT BUDGET ≤ 15 points per phase (auditor's order 10, on the operator's word of 2026-09-13 19:2x)**: gate
  logs are read by their verdict line only (`grep -E 'no violation|no divergence|FAILED|violation'`), never `cat`;
  no whole-file read where a grep answers; commit bodies ≤ 12 lines (figures, re-aims, movements — nothing narrated);
  a phase-file amendment is ONE dated line; the RESUME is append-only (above). You read your gauge at every phase
  boundary and report it before and after; **under 45 % you TAKE the next phase** — standing down under the gate is
  a cost, not a safety. Target: at least two phases per agent.
- **OVERLAP (order 11)**: while a phase's gate runs (~7 min, it measures the committed head), you read the NEXT
  phase's file and re-take its figures read-only; every STOP D question of a phase is batched in ONE message at
  its opening, never raised one by one.
- **YOUR FIRST COMMIT is a tooling fix (order 12, the operator's word lifting the apparatus freeze for time given
  back)**: `frontend/maquette/harness/run.sh` builds and copies the served copy ONCE when `--contracts` and
  `--oracle` are asked in one invocation (a `--contracts --oracle` form, or the equivalent), with its test
  (`tests/scripts/test_run*.py` or the harness's own) seen RED first; ~2 min saved per gate. Nothing else in that
  commit: `fix(maquette-l13b): run.sh builds once for the contracts tier and the oracle`. Use that form for every
  gate after it.

## Non-goals

- No phase of L13c; no conversion of anything the plan does not name; no new guard, arm or tool (the operator's
  first measure of 2026-09-12 — a phase's own rule, named in its phase file, is not new apparatus; a re-aim is not).
- No redrawing beyond what the phase names: what is in the maquette is validated (§ 15); every visual change is
  a NAMED divergence in the phase's amendment or it is STOP B.
- **Not yours: the operator's two defects of 2026-09-13** (the candidates' check mark, the releases seed limited to
  Silo) — they belong to the steward's repair train on `main`.
- No edit to `docs/reference/*`, `CLAUDE.md`, the office: what you find wrong there goes to the steward with the
  command. ONE narrow exception (ruling 60): a FULL-PATH citation of a file your phase deletes, refused by
  `check-docs-cited-paths.py`, is re-cited `path@<sha of main's base>` and nothing else in that file, said in the
  body. `CLAUDE.md` never — tell the steward.
- No `--no-verify`, no force-push, no merge of your own pull request, no deletion of a branch or a worktree; no
  delegate that writes or reviews (read-only search subagents only, nothing heavy).
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

One commit per phase (plus the commit-before-mutation where a phase says so), conventional, scoped
`maquette-l13b`, no attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg` refuses it).
Push at every stand-down and at b·11 under the tests lock, after `make check` and the full gate; merge
`origin/main` first and bump the version above whatever `main` reads then (patch). Pull request READY, title
`feat(maquette-l13b): the engine's verbs and the ladder's shape — legacy.js dies`, body: the twelve phases and
what each landed and deleted (by command, measured ONCE on the final head), every rule written with its red run
and its mutation, the divergences named, the register rows closed, the hold-count movements, the midpoint suite's
falls and their repairs, the ledger's final count (0), **and for the reader's affordance lens (auditor's order 6)
the list of the surfaces whose behaviour changed**. One reader round follows the pull request (measure 2); you stay
available for its findings in a fresh session with a resume brief, not in this one.

## Communication

Your orchestrator's exact `ListAgents` name and reference are in the launch prompt. First act after the required
reading: the handshake — the state-verification readings and your gauge — and nothing is in flight until it is
answered. Then: a report at every phase gate and at every STOP (the STOP, its evidence, the proposed resolution,
and you WAIT), one line before and after every shared-mutex run, the arm readings named above, the push report.
A message that expects an answer and has none after fifteen minutes is re-sent after a fresh `ListAgents`, to the
session whose NAME matches, marked as a re-send; if the name is not listed, tell the user in your session and stop
waiting. **Do not stop between phases to report one done.** Every report ends with the gauge:
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.29.2/skills/context-gauge/scripts/context-gauge.sh`
run as the LAST call, its `context_percent=` and `source=` lines pasted. **The context gate is 80 % (the operator's word of 2026-09-13 19:2x: « Tu peux monter le contexte des agents à 80 % au lieu
de 60 si ça peut aider »)**: (a) crossing 80 % mid-work, you finish the unit in progress (or commit a compiling
« part 1 »), rewrite the RESUME's state block, append the ledger, push under the tests lock, prune, report « stood
down » with `git ls-remote` proving the push, and stop — the steward spawns your successor; (b) PRE-DISPATCH: you
OPEN the next phase when your measured gauge + the measured cost of your last phase (before/after, order 10) is
≤ 80 — never a rotation mid-phase; (c) compaction-readiness stands whatever the gauge: every state on disk, nothing
only in your context.

## Resource envelope — the machine is shared (2026-09-13)

TWO agents may run beside the steward on this 8-core, 16 GB host (L13a's reader round overlaps your first
phases): the mutex and the tests lock serialise the heavy runs; you announce yours. Every command runs
synchronously in the tool call that waits for it, long output to a FILE under `/private/tmp/tm-l13b/`, the exit
code read in the same call; a run longer than the tool's ceiling goes to the background and you read its exit
file when its notification wakes you — never a turn ended « waiting for » anything else. Fan-out has a name and a
value, every time: `TM_HARNESS_JOBS=2`, `PYTEST_XDIST_AUTO_NUM_WORKERS=2`. Kill what you start, delete what you
build (`design/dist`, bench copies, screenshots), prove it with
`ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node |pytest|heavy.sh" | grep -v grep` before every
report; the 8899 host (`server.py --serve 8899`, parent 1) is `run.sh`'s and is left alone. Search safety
(`CLAUDE.md`): every `rg`/`grep -r` carries a type filter. Tier **deep** (the map binds every tier to opus; no tier
of this project is ever Sonnet), chosen because every phase of L13b writes a rule whose red reading nobody else
takes before the reader round. Your session was spawned with NO MCP server; the harness needs none.
