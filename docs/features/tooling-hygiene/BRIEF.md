# tooling-hygiene — the instruments' own debts, taken by one micro-wave

You open a **micro-wave of TOOLING**, ordered by the operator on 2026-09-12 (« lance tout ce qui
peut être parallélisé »). Its subject is the repository's instruments — `scripts/`, `hooks/`,
`frontend/maquette/harness/common.py` and the rule modules' entry points, `frontend/maquette/design/vite.config.mjs`
— and **never a surface**: nothing under `frontend/maquette/design/src/` changes, nothing the
application runs changes, no register body is rewritten but the entries you close and the ones you
file. It is not a lot; § 0 of the plan elects no lot for it and `IMPLEMENTATION.md`'s rows are not
yours to edit. Branch `chore/tooling-hygiene`, worktree `/Users/izno/dev/worktrees/wave-tooling`
(cut from `origin/main` at `468162dc6`, version 0.98.83), one pull request opened READY, squash
merge, the version bumps (patch). You are the only writer in that worktree.

**One kind of change per commit, one commit per entry, each with the test that falls when the
repair is reverted — and seen RED before the repair.** A guard is not judged by `mutate.sh`
(B-273): its exit code is read by hand, and the mutation is recorded in the commit message's body
or in the entry.

## The entries — read each one WHOLE in `BUGS.md` before touching anything

Numbers below are `BUGS.md` line numbers on `468162dc6`; re-read them, they move.

1. **B-384** (index row ~432, body « B-384 — the build identity hashes the hook's command log »):
   `buildIdentity()` in `frontend/maquette/design/vite.config.mjs` walks all of `src/` and hashes the
   command-logging hook's `.claude/logs/bash-commands.log`. **Closes when** it skips `.claude/` and
   every git-ignored path, held by a test that writes a file there and reads the id unchanged.
   Shape: the walk consults `git ls-files --cached --others --exclude-standard` (tracked + untracked-
   not-ignored) or `git check-ignore`, never a hand-written list; the test lives where the design's
   tests live (`npm test` in `frontend/maquette/design/` — read `package.json` for the runner) or as
   a Python test under `tests/scripts/` that runs `node -e` against the exported function — you
   choose and say why. Mutation: the skip removed → the id moves.
2. **B-385** (~433, « the pre-push hook takes every core »): `hooks/pre-push` runs `pytest -n auto`.
   **Closes when** the hook caps its workers at three unless `PYTEST_XDIST_AUTO_NUM_WORKERS` is
   already set, and prints the cap it applied. Test under `tests/scripts/` beside
   `test_pre_push_env_sanitization.py` (the precedent for reading the hook's text or running it on a
   synthetic repository): the variable absent → 3, present → honoured, and the printed line read.
3. **B-386** (~434, « the heavy wrapper has one readiness floor for every run »): `scripts/heavy.sh`
   waits for 4 096 MB and load 6 whatever the run. **Closes when** the floor is read from the
   command's CLASS — `--class browser` (a harness run: one or two Playwright groups at ~1.1 GB each),
   `--class test` (a parallel pytest at three workers, `make check`, a build), `--class rule` (a
   single-rule replay, one browser), with the arithmetic of the office's § Instrument hygiene
   written beside each number in the script — and the bypass by environment
   (`HEAVY_FREE_FLOOR_MB`) is REFUSED for a value below the class's floor while `HEAVY_LOCK` (the
   test suite's door) stays. A run with no `--class` keeps today's floor (4 096) so every existing
   invocation still works. **The hard floor (2 048, the watchdog) does not move.** Extend
   `tests/scripts/test_heavy.py` (it exercises every path on a lock moved aside by `HEAVY_LOCK`, one
   second of overhead on an instant command — keep that measure green). Then update the office's
   invocation lines in `docs/reference/frontend-steward.md` § Instrument hygiene and the envelope
   below in ONE sentence each, and say in the pull request that today's loosened floor (2 560 by the
   operator's word of 2026-09-12) is what this replaces.
4. **B-387** (~435, « the formatter hook edits files outside the tracked tree »):
   `.claude/hooks/auto_format_project.py` (tracked — `git ls-files .claude/hooks` prints it) forwards
   every non-Markdown file to the global formatter, including files under untracked or ignored
   directories (`.review/` of a reader's worktree). **Closes when** it skips a path that is
   git-ignored or untracked (`git check-ignore -q` / not in `git ls-files`) and says so on stderr,
   held by a test that writes a `.py` under an ignored directory of a synthetic repository, runs the
   hook's function on it, and reads it unchanged. The global `~/.claude/hooks/auto_format.py` is NOT
   yours (it is the configuration repository's): the skip lives in the project hook.
5. **B-325** (~387, « no rule can be pointed at a build »): `frontend/maquette/harness/common.py`'s
   `PROTOTYPE` is hard-coded to `http://127.0.0.1:8899/`, every rule self-runs on import, and the
   served-copy stamp (`served_copy.assert_unchanged`, `Journal.summary`) reads `/tmp/tm-refonte`
   whatever the rule was pointed at. **Closes when** `PROTOTYPE` reads an environment override
   (`TM_PROTOTYPE_URL`, say — an English name, added to `scripts/code-vocabulary.txt` if a word is
   new), the served-copy assertions read the root that URL serves (a second variable, or a mapping
   from the port to the root — you choose and say why), and every rule module guards its run with
   `if __name__ == "__main__":` so it can be IMPORTED. The guard is mechanical over ~120 files: do
   it with a script committed under `scripts/` or with `scripts/rename-identifiers.py` if it fits,
   never by hand; **re-read the diff** — the tool is not the proof. `run.sh`, `harness-hold-counts.py`,
   `mutate.sh`, `a11y.py`, `oracle.py` run rules as scripts and must be unchanged in behaviour: the
   full suite once at the end proves it (below). Test: a rule imported without running (a
   `tests/scripts/` test importing three rule modules and asserting no browser started), and the
   override read by `common.PROTOTYPE`.
6. **B-346** (~394, « an entry's body ends at the first paragraph that opens with another entry's
   identifier »): `scripts/check-bug-register.py`'s `BODY_HEAD` is `^\*\*([BE]-\d{3})\b`. **Closes
   when** a head is `**B-NNN —` or `**B-NNN** —` (the register's own grammar — the operator's
   register writes heads that way; verify by counting both shapes before you choose) and
   `entry_bodies` keeps every entry's WHOLE span; re-take the « 25 of 278 heads are second-or-later »
   count with the command in the entry and write the new figure in the entry. Test beside the
   guard's existing tests (find them: `grep -rl check-bug-register tests/`).
7. **Two debts of the same guard, measured by the steward on 2026-09-11 and FILED BY YOU as new
   entries (B-420, B-421) before they are repaired** — each with the probe that shows the guard
   green over the defect, in the entry's `<sub>`:
   - **an index row whose cell wraps onto a second line is invisible**: `ANY_INDEX_ROW` and the row
     regex are line-anchored, so a row a formatter or a hand wrapped is neither counted (the corpus
     arm) nor read (the vocabulary arm). Probe: wrap one row's description onto two lines in a copy
     of the register, run the guard against the copy (`--register <path>` if the guard has one; add
     it if not, as the test suite's door), read « clean ». Repair: refuse a line that starts with
     `| B-` and is not a well-formed row, naming the line.
   - **rows out of order or outside the table are not refused**: a merge of `main` yields one
     conflict region spanning rows and bodies, and concatenating the sides puts a row BELOW a body,
     which silently ends the table — the row is then unread by every count (this happened twice on
     2026-09-08). Probe: move one row below the table's end in a copy, run the guard, read « clean ».
     Repair: every `| B-NNN |` line in the file belongs to the index table (refuse one found after
     the first body head), and the index is in ascending number order (refuse the first descent,
     naming both rows).

## What you read before acting

1. `CLAUDE.md` whole (§ Search Safety — `rg` always with `--type py` or a glob; § Commit
   Convention — no AI attribution anywhere, enforced by `hooks/commit-msg`; § Code Conventions —
   names written in full, English only, Google docstrings; § Phase Gate Checklist).
2. `docs/reference/frontend-steward.md` § « Instrument hygiene » (the arithmetic B-386 encodes) and
   § « What a review costs, and the five rules ».
3. `docs/reference/frontend-architecture.md` § 5 « The instruments' own debts, and who takes them »
   (lines ~1955–1985 on `468162dc6`) — B-325 and B-346 sit there with their owner sentence « the next
   wave that touches … takes it »: you are that wave; edit the two bullets to say so (`taken by the
   tooling micro-wave, #<PR>`), nothing else in that file.
4. `BUGS.md`: the seven entries above whole; § « Status vocabulary » and rule 3 (`fixed #<PR>`);
   B-273 and B-330 (`mutate.sh` judges a RULE, not a guard); B-256 (the served-copy stamp, which
   B-325 must not weaken); B-326 (the lock is a directory); B-102 and B-103 (the guard's own
   arms and their mutations — the shape of a guard commit in this repository).
5. `scripts/check-bug-register.py` whole (its header lists what it does NOT read — update that list
   when you change it), `scripts/heavy.sh` whole, `hooks/pre-push` whole, `.claude/hooks/auto_format_project.py`,
   `frontend/maquette/harness/common.py`, `frontend/maquette/harness/served_copy.py`,
   `frontend/maquette/harness/run.sh`, `scripts/harness-hold-counts.py`, `scripts/mutate.sh`,
   `frontend/maquette/design/vite.config.mjs`, `tests/scripts/test_heavy.py`,
   `tests/scripts/test_pre_push_env_sanitization.py`, `tests/scripts/test_served_copy.py`.
6. `frontend/maquette/README.md` § « `harness/` — the rule suite » and § « Language of the source ».

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    pwd && git branch --show-current && git status --short
    python3 scripts/check-bug-register.py --next          # B-397 on this branch; your block is B-420+
    grep -n "PROTOTYPE" frontend/maquette/harness/common.py
    grep -c 'asyncio.run(main())' frontend/maquette/harness/*.py | awk -F: '$2>0' | wc -l
    grep -n "FREE_FLOOR_MB\|HARD_FLOOR_MB" scripts/heavy.sh
    grep -n "pytest" hooks/pre-push
    grep -n "BODY_HEAD\|ANY_INDEX_ROW" scripts/check-bug-register.py
    git ls-files .claude/hooks
    ls frontend/maquette/design/node_modules | wc -l     # 0 → npm ci first (own lock)
    ls frontend/node_modules | wc -l                     # 0 → npm ci first (the pre-push hook needs it)

## Order, and why

B-385 and B-386 first (they make every later gate of yours and of the three other agents cheaper
and safer), then B-387, then B-384, then B-346 and the two filed debts (one guard, three commits),
then B-325 last (it is the widest diff and the only one that needs the full suite). Then the gate.

## Non-goals

- No file under `frontend/maquette/design/src/`, `personalscraper/`, `frontend/src/`; no rule's
  holds change (a rule's semantics are the harness's; you touch only its entry-point guard).
- No renaming of `heavy.sh`'s existing flags, no removal of `HEAVY_LOCK`, no change to the lock's
  directory or its 45-minute staleness rule.
- No edit to `IMPLEMENTATION.md`; no edit to the office beyond the one sentence B-386 obliges.
- No register body rewritten except the seven entries you close and the two you file; no
  renumbering of anyone's block (settings holds B-397+, L20 design B-440+, #585 B-393..396).
- No global `~/.claude` file — that repository is not yours.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Gate, then delivery

Per commit: `make lint`; the tests you touched; `python3 scripts/check-bug-register.py` clean.
Before the pull request, on the final head, each exit code read in the call that ran it:
`make check` (own lock, 3 workers, 0 failed / 0 errors); `run.sh --contracts` (shared lock — B-325
changed the rules' entry points); the FULL suite once (`run.sh`, shared lock, `TM_HARNESS_JOBS=2`,
20–25 min, expected no violation and the same rule count as `hold-counts-baseline.json`'s);
`python3 scripts/harness-hold-counts.py --compare --jobs 2` with `failed` read FIRST — counts
must be UNCHANGED (you changed no hold; a moved count is a STOP). No oracle, no a11y: no surface
moved (say so with `git diff --stat origin/main -- frontend/maquette/design/src | wc -l` → 0).
Then a wrapped push (own lock — the pre-push hook runs the suite at 3 workers), `git ls-remote`
read, the pull request opened READY: title
`chore(tooling-hygiene): the instruments' own debts — floors by class, a capped hook, a guarded rule entry, a register guard that reads its whole table`,
body in English with one section per entry (what fell red, the mutation, the figure once), the
reserved register block named, the CI run id. Register rows `fixed #<PR>` by rule 3. Then the final
report to the orchestrator: head sha, run id, the two figures re-taken (B-346's count, the rule-file
count guarded), gauge. You then stop as the sole writer; review findings go to a fresh session.

## Resource envelope — the machine is shared with three other agents (2026-09-12)

Four agents and the steward run on this 8-core, 16 GB host at once, by the operator's order of
2026-09-12 (« tout ce qui peut être parallélisé doit l'être ; les agents lancés ne doivent pas être
bloqués »). The same word loosened the wrapper for this day: the readiness floor of
`scripts/heavy.sh` is 2 560 MB for every run of this wave (its hard floor stays 2 048 MB — it
kills its own child under it, never anything else), and B-386 is what turns this into a rule
by class instead of a number set by hand. Nothing below is optional.

- **Two locks, by what the run reads.** Anything that touches the ONE served copy
  (`/tmp/tm-refonte`) or the 8899 host — `run.sh` in any tier, the oracle, `harness-hold-counts.py`,
  `mutate.sh`, a single rule replay — runs under the SHARED lock:
  `HEAVY_FREE_FLOOR_MB=2560 TM_HARNESS_JOBS=2 sh scripts/heavy.sh <wave> <command>`. Everything
  else that is heavy — `npm ci`, `npm run build`, `make check`, `pytest`, a `git push` (the pre-push
  hook runs the test suite) — runs under the wave's OWN lock, so it can proceed beside another
  wave's harness run:
  `HEAVY_LOCK=/private/tmp/tm-heavy-<wave>/holder HEAVY_FREE_FLOOR_MB=2560 PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh <wave> <command>`.
  `<wave>` is your wave's codename. A run that holds the shared lock is announced to the steward
  in one line before it starts (« harness run starting ») and one after (« done, exit N »).
- **Fan-out has a name and a value, every time**: `TM_HARNESS_JOBS=2`,
  `PYTEST_XDIST_AUTO_NUM_WORKERS=3`. Never a build beside a parallel test run of your own.
- **Every command runs synchronously in the tool call that waits for it**, output to a FILE
  (`> /tmp/<wave>-<step>.log 2>&1`), the exit code read in the same call; never `| tail -N` on a
  long gate, never a turn ended « waiting for » a run. A push landed only when
  `git ls-remote --heads origin <branch>` prints the ref.
- **Kill what you start, delete what you build, prove it with `ps`** (`ps -eo pid,etime,command |
  grep -E "chrom|playwright|vite|node|pytest" | grep -v grep`) before every report. The 8899 host
  (`server.py --serve 8899`, pid at parent 1) is `run.sh`'s and is left alone.
- **Never `cd` into `frontend/maquette/design/src`** (B-384): absolute paths from your worktree root.
- **Read the lock, never the directory**: `sh scripts/heavy.sh --held` (or with `HEAVY_LOCK` set).
- Context: run `/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.26.1/skills/context-gauge/scripts/context-gauge.sh`
  as the LAST call before every report and paste its `context_percent=` and `source=` lines; past
  60 %, finish the unit in progress, push a resume note in your folder, and stop.
- Tier **deep** (the map binds every tier to opus; no tier of this project is ever Sonnet), chosen
  because every deliverable here is judged by nothing downstream but the steward's reading. Your
  session was spawned with NO MCP server; the harness needs none.
