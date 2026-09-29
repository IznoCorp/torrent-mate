# The implementer's office — what holds for every lot

Every maquette lot's launch brief CITES this file instead of copying it, and carries only what is the lot's own:
worktree, branch, log directory, the reserved rule and register ranges, the phases, the midpoint and checkpoints, the
pull request's title and §§, and any amendment — which names the line of this file it overrides. Story:
`docs/reference/frontend-steward.md@0e523349f` § « The operator's measures » (measures 1–20).

## The phase

- **The rule FIRST, seen RED**, its label bound to the next number of the range the steward reserves in the launch
  brief, the mapping in the RESUME; the move; the rule green with its holds counted; a mutation that fells it BY
  NAME.
- **≤ 15 points.** Re-measured on your head at its opening (non-blank lines for the 400-line ceiling): above 15 it is
  cut there and the steward told; a figure that no longer supports its home is STOP D, reported with the command. The
  opening measure lists the READERS of the behaviour a phase reverses, not only its writers.
- **Re-aims are said out loud** (the rule's docstring, the commit body); a state removed from a rule's list names its
  successor, read from your diff; the remaining phases are rebuilt from `ls plan/`, never from memory.
- **Navigation is proved by a finger walk**, never by a posed state alone.

## The gate (auditor's order 58)

- **A phase's gate**: the CI's static list (the `no-french` job of `.github/workflows/ci.yml`) and the cheap guards →
  the ORACLE ALONE (`run.sh --oracle`) → `run.sh --rules` on the phase's re-aimed rules plus the rule group of every
  surface it touches → `--a11y` on every gate that draws; logs POSTDATE the commit they measure. **No `--contracts`
  at a phase gate** — it runs at the midpoint, the brief's checkpoints, the close and in CI; a contract rule falling
  there on the lot's own defect is a ledger line, two bring it back at every gate. `entry.py` and `pwa.py` read the
  DEPLOYED host: full suites only.
- **The full suite twice** (measure 20): at the midpoint, its real falls repaired before the next phase opens; before
  the pull request, with `--a11y`, `scripts/harness-hold-counts.py --compare
  frontend/maquette/hold-counts-baseline.json` (`failed` read FIRST), `check-bug-register.py`, `check-intent-map.py`,
  `check-docs-cited-paths.py`, read by OUTPUT. **No local `make check`** (measure 19): `make lint` + the full suite +
  `--a11y` + `--compare` + the pre-push pytest. `tests/scripts/test_check_maquette_comments.py` before any push;
  `check-maquette-comments.py --record` inside the commit when a maquette file moved.
- **A fall set aside as « load »** (order 48): the rule under `--rules`, 5 draws, stop at 0/5; 10 against 10 on
  `main` at comparable load only if ≥ 1/5. A green re-run alone proves nothing.
- **A rule red three runs in a row for a reason classed outside the product** (timeout, infra, load) opens a register
  row in the lot's range with its MECHANISM to name, named before the pull request is READY — otherwise the rule
  leaves the gates and the row stays open (order 73). Story: the deployed-host rules, classed « timeout » thirteen
  times with no mechanism named, until #631 named it (auditor's order 73, 2026-09-29).
- **Harness budget** (order 52): harness lines added ≤ 0.6 × product lines added (`git diff --numstat
  origin/main...HEAD`), read at the midpoint and the close; a new check on a surface with a rule is a HOLD in that
  rule's file; over budget, the close carries a consolidation phase, every merged hold still falling under its
  mutation.

## The oracle accepts by name; declared lists are built by script

- `frontend/maquette/oracle.py --accept` takes no name — it rewrites the WHOLE reference — so it runs inside the
  gate, a script proves ONLY the declared keys moved, and those keys alone are committed; the steward re-records at
  merge.
- **The declared list is built BY SCRIPT**: every state whose page draws the world the phase touches (`scen` and page
  of each state in `frontend/maquette/design/src/harness/states/*.ts`), those under a layer included. Outside: STOP
  A.
- An accept so proved, on a gate whose rules and guards were green, needs no « final » full gate (order 49).
- **Mutations**: `sh scripts/mutate.sh <full path> "<python expression>" frontend/maquette/harness/<rule>.py`, commit
  BEFORE; read the NAMED `FAIL` line, keep the EXPRESSION; « RULE CRASHED » and « RULE NOT FOUND » prove nothing.

## The mutex and its classes (order 70; `docs/reference/frontend-steward.md` § Instrument hygiene)

`sh scripts/heavy.sh --class <class> <who> <command>`, no `HEAVY_LOCK=` override; read `sh scripts/heavy.sh --held`
and wait, never bypass; one line to the steward before and after. **browser**: a full gate or suite
(`TM_HARNESS_JOBS=3`). **rule**: `run.sh --rules` on a few rules, a one-rule mutation, the tm-design build. **test**:
every pytest (`PYTEST_XDIST_AUTO_NUM_WORKERS=3`) and every `git push` — its OWN command from the worktree root, never
`cd … &&`. A push the classifier refuses is a STOP with its exact text: no retry, no other route, no other session.

## The RESUME, and what is not yours

- `docs/features/<lot>/RESUME-<lot>.md`: a STATE BLOCK ≤ 40 lines rewritten at every boundary, an APPEND-ONLY ledger
  below. An unshipped defect is a ledger line, not a register row; a row a phase closes is closed in it, with the
  rule's red reading and its mutation.
- `IMPLEMENTATION.md` is the steward's; `docs/reference/*`, `CLAUDE.md` and this office are not a lot's to edit. The
  lot's DESIGN and plan take ONE dated line where a phase proves them wrong. A file a phase deletes is re-cited
  `path@<the last MAIN commit holding it>`, never a branch head.

## Context, communication, the machine

- **The context gate is the launch prompt's** (measure 8: 80 %). Past it: finish the unit, rewrite the state block,
  push, prune, report « stood down » with `git ls-remote`. Open a phase only if gauge + the last phase's cost ≤ the
  gate; under 45 %, TAKE it. Gate logs read by verdict line, commit bodies ≤ 12 lines; the gauge
  (`orchestrator:context-gauge`) runs LAST before any figure.
- Handshake first; a report at every gate and STOP (evidence, proposal, then WAIT), in French; unanswered after
  fifteen minutes, re-sent after a fresh `ListAgents` to the NAME. **Never stop between phases to report one done.**
  Long runs are waited for inside their call, output to a FILE, exit code read there, never `| tail -N`.
- Kill what you start, delete what you build, prove it with `ps`; never `/tmp/tm-refonte` or 8899 by hand; every `rg`
  carries a type filter; no `git stash`.

## Fixed non-goals and delivery

- **No backward compatibility of former addresses or links** — no alias, no redirect; a former address answers
  not-found, an unknown query is ignored (operator, 2026-09-29, verbatim: « A, pas de gestion de rétro-compatibilité
  ! »).
- No new guard, arm or tool (measure 1; a phase's own rule is none). No redrawing beyond a phase's move: STOP A. No
  `--no-verify`, force-push, rebase, self-merge, branch or worktree deletion; no delegate that writes or judges.
  Anything outside the brief: STOP and ask the orchestrator.
- One conventional commit per phase, scoped by the codename, no attribution; push at every phase end. The close: `git
  merge --no-edit origin/main`, the patch bump above `main`, the full gate, the pull request READY — reported the
  second it exists — citing the constitution §§ its phases serve; one reader round follows (measure 2).
