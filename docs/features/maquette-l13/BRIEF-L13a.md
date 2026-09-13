# maquette-l13a — the implementer's brief for L13a, « What moves unchanged »

You implement **L13a**, the first sub-lot of **L13 — The engine's residue**
(`docs/reference/frontend-architecture.md` § 4, entry `#### L13`, the CONTRACT). The lot's design is
`docs/features/maquette-l13/DESIGN.md` and its plan `docs/features/maquette-l13/plan/INDEX.md` with one
file per phase — **they are the specification and this brief restates none of it**. L13a is the
nineteen CONVERSION phases a·1 to a·19 of that plan, in that order, and nothing else: the harness
module, the seams as imports, the ladder's handler and the boot out of the engine, what nobody
reaches, the identity contract, then the drawing surface by surface with the fixture families and
`legacy.css`, then `refonte.html` and R72. Every phase is a conversion: **the oracle at zero divergence
and the hold counts unchanged are its proof**, and a phase that needs a behaviour change has found a
defect in the plan — STOP D, report with the command, do not improvise.

**The cut is ruled B (operator, 2026-09-13)**: L13a is its own wave and its pull request is your
STOP C. **Q2 is ruled B the same day**: the ≡ harness panel dies in ONE commit, a·18-bis, before
a·19's full gate. **D-L13-1 (DESIGN § 8) is ratified as A, and is L13b's, not yours.** The rulings
are `RESUME.md`'s 27 to 30.

## Environment

- Worktree `/Users/izno/dev/worktrees/wave-l13a`, branch `feat/maquette-l13a`, cut from `origin/main` at
  `f1e7ac662` (#594, the design). You are the only writer there. The main checkout
  `/Users/izno/dev/PersonalScraper` is the steward's: never write, build or run there.
- Before the first heavy run: `npm ci` in `frontend/` and in `frontend/maquette/design/` of the
  worktree, each under your OWN lock (`HEAVY_LOCK=/private/tmp/tm-heavy-l13a/holder sh scripts/heavy.sh --class test l13a npm ci`),
  never beside a harness run of anyone. The pre-push hook's suite needs both.
- Verify the state, do not believe it:

      git remote update origin >/dev/null && git log --oneline origin/main -3
      pwd && git branch --show-current && git status --short
      grep -n "^#### L13" docs/reference/frontend-architecture.md
      ls docs/features/maquette-l13/plan/ | wc -l
      wc -l frontend/maquette/design/src/engine/legacy.js frontend/maquette/design/src/engine/states.js frontend/maquette/design/src/styles/legacy.css frontend/maquette/design/refonte.html
      python3 scripts/check-frontend-boundaries.py --arm size; echo "exit $?"
      grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
      grep -n __version__ personalscraper/__init__.py
      sh scripts/heavy.sh --held; ls -A /private/tmp/tm-heavy-tests/ | wc -l
      git check-ignore -v docs/features/maquette-l13/BRIEF-L13a.md; echo "exit $? (1 = not ignored, expected)"

## What you read before acting, in order

1. `docs/reference/frontend-architecture.md` § 0, § 2 (D1, D1b, D4, D5, D7, D8, D10, D-L06-4, D-L07-7),
   § 3, § 4's L13 entry, § 5, § 6.
2. `docs/features/maquette-l13/DESIGN.md` whole; then `plan/INDEX.md` whole; then the nineteen
   `plan/phase-a*.md` files — each phase file is re-read at the moment its phase opens.
3. `frontend/maquette/README.md` whole (the harness, the named states, the traps already paid for);
   `CLAUDE.md` § Critical Rules (search safety, the language rule, the naming rule, the
   rename tool `scripts/rename-identifiers.py` — never a rename by hand).
4. `docs/reference/frontend-steward.md` § « Instrument hygiene » and § « What a review costs » —
   the machine's arithmetic and the review rules your delivery is read against.
5. `BUGS.md` bodies of the rows the phase table assigns to L13a (B-352, B-232, and every row a phase
   file names), and B-291, B-303, B-304, B-307, B-384, B-386.

## Method — the INDEX governs, with three precisions the INDEX predates

The INDEX's rules bind: one kind of change per phase; the oracle and hold counts unchanged read with
`failed` FIRST; re-aims said out loud in the docstring and the commit body; the engine only shrinks and
`scripts/frontend_size_ledger.py` re-recorded DOWNWARD in the same commit; guards and baselines die in
the phase that kills what they read; commit before every mutation; `scripts/mutate.sh` for mutations;
documents added by file; never `cd` into `design/src`; labels bound to numbers when a rule is written.
Three precisions, from the office as amended on 2026-09-13 (they override the INDEX's envelope
paragraph, and you amend that paragraph in your first commit, dated, so the plan says what you do):

1. **Locks by CLASS, not by floor.** Anything touching the ONE served copy (`/tmp/tm-refonte`) or the
   8899 host — `run.sh` in any tier, the oracle, `harness-hold-counts.py`, `mutate.sh`, a single rule
   replayed — runs under the shared mutex with `TM_HARNESS_JOBS=2 sh scripts/heavy.sh --class browser l13a <command>`,
   announced to the steward one line before and one after. **Every pytest, `make check` and `git push`**
   (the pre-push hook runs the suite) runs under the ONE tests lock shared by every wave:
   `HEAVY_LOCK=/private/tmp/tm-heavy-tests/holder PYTEST_XDIST_AUTO_NUM_WORKERS=2 sh scripts/heavy.sh --class test l13a <command>`.
   `npm ci` and a build into your own `dist/` keep your own lock (`/private/tmp/tm-heavy-l13a/holder`).
   **Never a test run beside a harness run, whatever the locks say**, and never a lower floor by
   environment under a named class (refused, exit 64). Read a lock with `sh scripts/heavy.sh --held`,
   never the directory.
2. **A phase's gate is the contracts tier plus the oracle, in one wrapped run each**; the full suite,
   `--a11y`, `harness-hold-counts.py --compare` and `make check` run once, at a·19, before the push.
   The pre-push suite is the hook's, under the tests lock, no `--no-verify`.
3. **The « In flight » row of `IMPLEMENTATION.md` is written when your pull request opens** (the wave,
   PR number, version, brief and figures, as the rows before it) and **goes back to « None » in your
   LAST commit before the merge** — the steward's post-merge gesture writes the trace. The register
   rows your phases close read `fixed #<your PR>` in the same commit as the closure's reading.

## Non-goals

- No phase of L13b or L13c; no behaviour change of any kind (a verb move, a timer removal, B-290,
  B-397, B-275 and every « repair » are L13b's and L13c's); no new guard, arm or tool (the operator's
  first measure of 2026-09-12 — a repair's own rule is not new apparatus, and L13a writes no rule).
- No redrawing: every conversion draws the SAME thing (§ 15 — what is in the maquette is validated),
  proved by the oracle at zero divergence; a divergence the phase did not name is STOP B.
- No edit to `docs/reference/frontend-architecture.md`, `docs/reference/frame-model.md`,
  `docs/reference/frontend-steward.md`, `docs/reference/product-intent*.md`: what you find wrong
  there is reported to the steward with the command. The INDEX and the phase files are the wave's
  own plan: an amendment there is dated and says what it makes void.
- No `--no-verify` on any push; no force-push; no merge of your own pull request; no deletion of a
  branch or a worktree.
- No delegate that writes or reviews: read-only search subagents only, and they run nothing heavy.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

One commit per phase (two where a phase says « commit before the mutation »), conventional, scoped
`maquette-l13a`, no attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg`
refuses it). Push at a·19 only, under the tests lock, after `make check` and the full gate; merge
`origin/main` first and bump the version above whatever `main` reads then (patch). Pull request
READY, title `feat(maquette-l13a): what moves unchanged — the harness module, the ladder, the boot and the drawing leave the engine`,
body: the nineteen phases and what each deleted (lines, by command, measured ONCE on the final head),
the re-aims named, the register rows closed, the oracle and hold-count readings, the lift-out figures
of a·1, the ledger's final count. **No reader round is owed before the merge for a micro-wave; L13a is
a LOT, so one reader round follows your pull request** (the operator's second measure) — you stay
available for its findings in a fresh session with a resume brief, not in this one.

## Communication

Your orchestrator's exact `ListAgents` name and reference are in the launch prompt. First act after
reading: the handshake — the state-verification readings and your gauge — and nothing is in flight
until it is answered. Then: a report at every full gate and at every STOP (the STOP, its evidence,
the proposed resolution, and you WAIT), one line before and after every shared-mutex run, the push
report (head sha, PR number, run id). A message that expects an answer and has none after fifteen
minutes is re-sent after a fresh `ListAgents`, to the session whose NAME matches, marked as a
re-send; if the name is not listed, tell the user in your session and stop waiting. **Do not stop
between phases to report one done.** Every report ends with the gauge:
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.28.3/skills/context-gauge/scripts/context-gauge.sh`
run as the LAST call, its `context_percent=` and `source=` lines pasted. **Past 60 %**: finish the
phase in progress, commit, push a `RESUME.md` in `docs/features/maquette-l13/` (the exact state, the
next phase, the decisions taken and marked non-reopenable, the traps met) under the tests lock,
report « stood down » with `git ls-remote` proving the push, and stop; the steward spawns your
successor from it.

## Resource envelope — the machine is shared (2026-09-13)

At most two agents beside the steward on this 8-core, 16 GB host. Every command runs synchronously
in the tool call that waits for it, long output to a FILE (`> /tmp/l13a-<step>.log 2>&1`), the exit
code read in the same call; never `| tail -N` on a long gate, never a turn ended « waiting for »
anything. Fan-out has a name and a value, every time: `TM_HARNESS_JOBS=2`,
`PYTEST_XDIST_AUTO_NUM_WORKERS=2`. Kill what you start, delete what you build (`design/dist`, bench
copies, screenshots), prove it with `ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node|pytest|heavy.sh" | grep -v grep`
before every report; the 8899 host (`server.py --serve 8899`, parent 1) is `run.sh`'s and is left
alone. Search safety (`CLAUDE.md`): every `rg`/`grep -r` carries a type filter; never `rg` a directory
bare. Tier **deep** (the map binds every tier to opus; no tier of this project is ever Sonnet), chosen
because a conversion of thirty thousand lines is judged by the oracle and by one reader round, and
the judgment inside each phase — which reader of a family is its last — is re-read by nobody else.
Your session was spawned with NO MCP server; the harness needs none.
