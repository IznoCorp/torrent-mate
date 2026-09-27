# maquette-l22b — the implementer's brief for L22b, « Arrivées dans Acquisition », second and last sub-lot

You implement **L22b**, the second and last sub-lot of **L22 — Arrivées dans Acquisition**
(`docs/reference/frontend-architecture.md` § 4, entry `#### L22`, the CONTRACT). The lot's design is
`docs/features/maquette-l22/DESIGN.md` (§ 7.3 carries the operator's rulings of 2026-09-26 evening) and its plan
`docs/features/maquette-l22/plan/INDEX.md`, one file per phase — **they are the specification and this brief restates
none of it**. L22b is the plan's **phases 15 to 27**, in that order: « Laisser tel quel » means later (15 — **read
ruling 16: « Mis de côté » is a FOLDED section at the END of « À traiter », outside its count and the bar's badge,
where the operator sees, deletes with a confirmation like the Médiathèque's, deletes from disk, or handles each
item**; the phase file carries it as a dated line — RE-MEASURE it at its opening, it grew), « Ce n'est pas un média »
(16), « Suivre » proposed (17), a film's follow ends alone (18), Système leaves the bar (19 — the frame rule R-L22-s,
the bar at 1/n, 2 to 4), the menu button's badge (20), the sentences that sent the reader to Arrivées (21), the
readers re-aimed (22, 23 — the four rules that started a pass by finger re-aim OUT LOUD, OPEN 6 ruled A), the live
rule Système was borrowing (24), the death of Arrivées (25), the records of a dead page (26), the close (27 — the
lot's gesture: `docs/features/maquette-l22/` deleted WHOLE, every citation of it re-cited `path@<the merge sha>`).
L22b is stacked on L22a's pull request head at its READY (measure 9); L22a's reader round and merge are never
awaited — when the steward tells you L22a is squashed onto `main`, you MERGE `origin/main` in at your next unit
boundary (`git merge --no-edit <sha>`, never a rebase).

**The operator's rulings are the design's spine**: organisation rulings 1–15 in `docs/reference/operator-method.md`
(2026-09-15 and 2026-09-26) and the eleven rulings on the design's OPEN questions, written into DESIGN § 7.2 as
« Ruled ». They are not reopened. The lot's own rulings — the steward's, on your STOPs — go to
`docs/features/maquette-l22/RULINGS.md`, one numbered file, appended from the number after L22a's last (read the file).

## Environment

- Worktree `/Users/izno/dev/worktrees/wave-l22b`, branch `feat/maquette-l22b`, cut from `origin/main` at the head the
  launch prompt names (the squash of #612, which carries DESIGN and plan). You are the only writer there. The main
  checkout `/Users/izno/dev/PersonalScraper` and every other worktree are not yours: never write, build or run there.
- Both `node_modules` are installed. Your log directory is `~/Library/Logs/tm-l22b/`: `<phase>-<step>.log`; gate logs
  kept until the merge, working logs pruned at every stand-down and proved by `ls`; a log a RESUME line or a commit
  body CITES is kept.
- Verify the state, do not believe it:

      git remote update origin >/dev/null && git log --oneline origin/main -3
      pwd && git branch --show-current && git status --short && git log --oneline -1
      ls docs/features/maquette-l22/plan/ | grep -c "^phase-"      # 27
      python3 scripts/check-frontend-boundaries.py --arm size; echo "exit $?"
      python3 scripts/check-frame-domain.py; echo "exit $?"
      grep -n __version__ personalscraper/__init__.py               # bump at the PR only
      sh scripts/heavy.sh --held

## What you read before acting — and NOTHING ELSE before the handshake (auditor's order 8)

1. This brief; `docs/features/maquette-l22/RESUME-L22b.md`'s STATE BLOCK (its first 40 lines); DESIGN § 0 and § 7.2;
   `plan/INDEX.md` whole; and `plan/phase-01-contract.md`. That is the whole required reading before your handshake.
2. After the handshake, as each phase opens: its phase file (re-read at that moment), the DESIGN sections it cites,
   `frontend/maquette/README.md` § named states and § traps, `CLAUDE.md` § Critical Rules (search safety, language,
   naming, `scripts/rename-identifiers.py` — never a rename by hand), and `scripts/check-mock-seeds.py`'s docstring
   before any seed row.

## Method — the INDEX governs, plus the office's precisions

- **Every phase is BEHAVIOUR or a MOVE, as its file says** (`plan/INDEX.md` § « The rule that governs every phase »):
  **the rule FIRST, seen RED**, its label R-L22-x bound to the next free number (`grep -rhoE '^"""R[0-9]+ '
  frontend/maquette/harness/*.py | sort -V | tail -1` against `origin/main` at the moment phase 1 runs, the mapping
  written into the RESUME), then the move, then the same rule green with its holds counted, then a mutation that fells
  it by name. The oracle may diverge ONLY on the states each phase names, each accepted by name with its reason (D8);
  any other divergence is STOP A.
- **Sizes**: every phase ≤ 15 points (measure 11) — at a phase's opening you RE-MEASURE it against its own file on
  YOUR head before committing to the shape written there; a phase above 15 is cut at its opening and the steward told;
  a figure that no longer supports the phase's home is STOP D, reported with the command, never improvised past. Two
  STOP D are already announced by the plan (phase 9's seeds, phase 13's unnamed walks): they are ONE message each, at
  that phase's opening.
- **Re-aims are said out loud** in the rule's docstring and the commit body (the operator's rule of 2026-09-08);
  ruling 6 on OPEN 6 makes four harness rules lose their finger in L22b, not here — if a phase of yours touches one,
  say it.
- **Locks by CLASS.** Anything touching the ONE served copy or the 8899 host — `run.sh` in any tier, the oracle,
  `harness-hold-counts.py`, `mutate.sh`, a single rule replayed — runs under the shared mutex, in the ONE form that
  reads rule names: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l22b frontend/maquette/harness/run.sh
  --contracts --oracle <full rule paths>` (one build, one verdict block), one line to the steward before and after;
  **read `sh scripts/heavy.sh --held` and wait, never bypass**. Every pytest and every `git push` under the same mutex,
  class test, with NO `HEAVY_LOCK=` override: `PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh --class test l22b
  <command>`. The push is its OWN command from the worktree root — `sh scripts/heavy.sh --class test l22b git push -u
  origin feat/maquette-l22b` — never prefixed by `cd … &&` (the operator's permission rule matches that form). If the
  classifier refuses a push, STOP with the refusal's EXACT text and the command: no retry, no other route, and never
  ask another session to push for you.
- **Mutations**: `sh scripts/mutate.sh <full path> "<python expression>" frontend/maquette/harness/<rule>.py` — read
  the NAMED `FAIL` line, keep the EXPRESSION in the log; « RULE CRASHED » and « RULE NOT FOUND » prove nothing; commit
  before every mutation.
- **A phase's gate** = one wrapped `run.sh --contracts --oracle <named rules>` + the cheap guards it runs, logs
  POSTDATING the commit they measure; `tests/scripts/test_check_maquette_comments.py` alone under the test mutex
  before any push, `check-maquette-comments.py --record` INSIDE the commit when a maquette file moved.
  **The FULL SUITE runs TWICE in L22b** (measure 20): at the MIDPOINT, after phase 20 and before phase 21 opens,
  every fall re-read ALONE on a quiet machine before it is charged to the code or to load (the RESUME says which and
  why, per rule), its real falls repaired by you before phase 21; and after phase 27, before the pull request, with
  `--a11y` (also on EVERY phase gate that draws — L22a's phases 5–7 skipped it once and the light ledger rose),
  `scripts/harness-hold-counts.py --compare frontend/maquette/hold-counts-baseline.json` (`failed` read FIRST),
  `python3 scripts/check-bug-register.py`, `python3 scripts/check-intent-map.py`, `python3
  scripts/check-docs-cited-paths.py`, read by OUTPUT. `TM_HARNESS_JOBS=3` on EVERY heavy invocation, the full suite
  included (it ran at 8 by omission on 2026-09-16 and two timeouts were the price). **No local `make check`** (measure
  19): CI's `test` job is the authority; the pre-PR gate is `make lint` + the full suite + `--a11y` + `--compare` + the
  pre-push pytest.
- **The oracle ACCEPTS the states a phase declares, by name, in a commit** (`frontend/maquette/oracle.py --accept
  <state…>`), never a blanket re-record; the steward re-records the references at the merge.
- **The RESUME**: `docs/features/maquette-l22/RESUME-L22b.md` = a STATE BLOCK of at most 40 lines (rewritten at every
  boundary) + an APPEND-ONLY ledger below it. No register row for an unshipped defect: a ledger line on the phase
  instead; a register row a phase closes is closed in that phase, with the rule's red reading and its mutation.
- **`IMPLEMENTATION.md` is the steward's**: the wave does not touch it. **No edit to `docs/reference/*`, `CLAUDE.md`,
  the office**; DESIGN and the plan under `docs/features/maquette-l22/` are amended by ONE dated line where a phase
  proves them wrong. A full-path citation of a file your phase deletes, refused by `check-docs-cited-paths.py`, is
  re-cited `path@<the last MAIN commit holding it>` — never a branch head (a squash makes it unresolvable on a fresh
  clone).
- **CONTEXT BUDGET ≤ 15 points per phase**: gate logs read by their verdict line only; commit bodies ≤ 12 lines, no
  baseline figure in a body; a phase-file amendment is ONE dated line. Gauge at every phase boundary, before and
  after; **under 45 % you TAKE the next phase**. While a gate runs you read the next phase's file and re-take its
  figures read-only.

## Non-goals

- Phases 1–14 and 14-bis/14-ter (L22a's, merged or under review — a defect you find there is a STOP, not a
  repair of yours); the Trackers page (L16, L17); the rights model, accounts and the reassign gesture (L18); the
  engine (after the freeze). No new guard, arm or tool (measure 1 — a phase's own rule or a re-aim is not new
  apparatus). No redrawing beyond what a phase's move names: every visual change outside it is STOP A.
- No `--no-verify`, no force-push, no rebase, no merge of your own pull request, no deletion of a branch or a
  worktree; no delegate that writes or reviews (read-only search subagents only, nothing heavy). Never
  `/tmp/tm-refonte` by hand, never 8899 by hand.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

One commit per phase (plus the commit-before-mutation where a phase says so), conventional, scoped `maquette-l22`
(e.g. `feat(maquette-l22): …`), no attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg`
refuses it). Push at every stand-down and after phase 27 under the test mutex. After phase 27: merge `origin/main` in
(`git merge --no-edit`, never a rebase), bump the version (patch) above whatever `main` reads then, the full gate,
pull request READY titled `feat(maquette-l22b): Arrivées dans Acquisition — « Mis de côté », the bar without Système,
and the death of Arrivées` — a BEHAVIOUR pull request, so it cites the constitution §§ each phase serves (§ 2, § 3,
§ 12, § 13, § 16, § 17, § 20). Body: the thirteen phases and what each moved, every rule written with its red run and
its mutation (EXPRESSION and FAIL line), the oracle states accepted by name, the register rows closed, the midpoint
suite's falls and repairs, the ledger's final count (0). **The lot's gesture is yours**: `docs/features/maquette-l22/` is deleted
WHOLE at phase 27 (documentation-model.md § 4 — the folder is the LOT's and dies at its last sub-lot), every citation
of it in the tree re-cited `path@<the last MAIN commit holding it>` — never a branch head. One reader round
follows (measure 2); you stay available for its findings in a fresh session with a resume brief, not in this one.

## Communication

Your orchestrator's exact `ListAgents` name and reference are in the launch prompt. First act after the required
reading: the handshake — the state-verification readings and your gauge — and nothing is in flight until it is
answered. Then: a report at every phase gate and at every STOP (the STOP, its evidence, the proposed resolution, and
you WAIT), one line before and after every shared-mutex run, the push report. A message that expects an answer and
has none after fifteen minutes is re-sent after a fresh `ListAgents`, to the session whose NAME matches, marked as a
re-send; if the name is not listed, tell the user in your session and stop waiting. **Do not stop between phases to
report one done.** Every long run is waited for INSIDE the tool call (timeout ≤ 600 s, or a bounded loop polling its
log) — never a turn ended on a run still going. Every report ends with the gauge:
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.29.2/skills/context-gauge/scripts/context-gauge.sh` run
as the LAST call, its `context_percent=` and `source=` lines pasted. **The context gate is 80 %** (measure 8):
(a) crossing it mid-work, you finish the unit in progress (or commit a compiling « part 1 »), rewrite the RESUME's
state block, append the ledger, push under the test mutex, prune, report « stood down » with `git ls-remote` proving
the push, and stop — the steward spawns your successor; (b) PRE-DISPATCH: you OPEN the next phase when your measured
gauge + the measured cost of your last phase is ≤ 80 — never a rotation mid-phase; (c) every state on disk, nothing
only in your context.

## Resource envelope — the machine is shared

TWO agents may run beside the steward on this 8-core, 16 GB host (measure 6). The mutex serialises the heavy runs;
you announce yours. Every command runs synchronously in the tool call that waits for it, long output to a FILE under
`~/Library/Logs/tm-l22b/`, the exit code read in the same call, **never `| tail -N` on a long gate**. Fan-out has a
name and a value, every time: `TM_HARNESS_JOBS=3`, `PYTEST_XDIST_AUTO_NUM_WORKERS=3`. Kill what you start, delete
what you build (`design/dist`, bench copies, screenshots), prove it with
`ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node |pytest|heavy.sh" | grep -v grep` before every
report; the 8899 host is `run.sh`'s and is left alone. Never `cd` into `frontend/maquette/design/src` (B-384): absolute
paths from the worktree root. Search safety (`CLAUDE.md`): every `rg`/`grep -r` carries a type filter. No `git stash`,
ever. Tier **deep**, chosen because every phase writes a rule whose red reading nobody else re-reads before the reader
round. Your session was spawned with NO MCP server; the harness needs none.
