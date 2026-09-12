# maquette-resolution-card — the post-merge gesture, and the round-two minors filed

You perform the **post-merge gesture** of the `maquette-resolution-card` micro-wave, merged on
2026-09-12 as squash **`561ac7a39`** (PR #585, version 0.98.84), and you file the seven minors its
second review round left. Prose, two recorded references and one register block — no surface, no
rule, no mock. Worktree `/Users/izno/dev/worktrees/wave-resolution-card`, branch
`chore/maquette-resolution-card-landed` (cut from `origin/main` at `561ac7a39`); you are its only
writer. One pull request opened READY, patch bump, squash merge. The model is the previous
gesture, read it whole: `git show fe46548df --stat` and `git show fe46548df` (#584, the desktop-frame
gesture: 8 files, 22 insertions, 439 deletions).

## The gesture, in order

1. **Verify the state**, print every line:

        git remote update origin >/dev/null && git log --oneline origin/main -3
        pwd && git branch --show-current && git status --short
        git merge-base --is-ancestor 561ac7a39 HEAD && echo squash-is-ancestor
        python3 -c "import json;d=json.load(open('frontend/maquette/hold-counts-baseline.json'));print(d['taken_at_commit'][:9], d['totals'])"
        ls docs/features/
        python3 scripts/check-bug-register.py --next
        grep -rn "maquette-resolution-card" BUGS.md IMPLEMENTATION.md docs/reference/*.md | grep -v "@561ac7a39" | cut -c1-140
        grep -o "| \*\*Between L21 and L20\*\*[^|]*| [^.]\{0,80\}" IMPLEMENTATION.md
        sh scripts/heavy.sh --held

2. **Re-record the hold-counts baseline ON THE SQUASH CHECKOUT** (your HEAD is the squash's tree):
   `python3 scripts/harness-hold-counts.py --record --jobs 2` under the SHARED lock (the wrapper's
   envelope below), and read `failed` FIRST in the new file — it must be 0, and the four rules #585
   added (`message_above_harness.py`, `resolution_card.py`, `resolution_window.py`,
   `selection_survives_the_tab.py`) must now have a reference (12 / 18 / 3 / 8 holds on a5fc8ce4e,
   re-measured here). Then `--compare --jobs 2` reads « 0 new since baseline ». Read the tool's own
   `--help` for the exact flags before running; the previous gesture's commit shows the diff shape.
3. **Re-record the oracle reference on the squash**: `make maquette-oracle` records (read the Makefile
   target and the README § « What replaced « zero divergence » » first) — under the shared lock, one
   run; the reference's commit field reads `561ac7a39`; `--check` afterwards reads no divergence.
4. **`IMPLEMENTATION.md`**: the row « Between L21 and L20 » gains the micro-wave (merged 2026-09-12,
   squash `561ac7a39`, version 0.98.84, PR #585, brief at
   `docs/features/maquette-resolution-card/BRIEF.md@561ac7a39`, NOT A LOT, three behaviour repairs
   B-393/B-394/B-395, two reader rounds 7 → 7 minors, A6 ruled A); the « Next » row gains one
   sentence: L20's design and plan landed at #587 (read its squash sha on `origin/main` —
   `git log origin/main --oneline -5` — it may land while you work; if it has not, write « #587,
   pending » and say so in the PR). « In flight » stays « None ».
5. **The wave's folder leaves the tree**: `git rm -r docs/features/maquette-resolution-card/` and
   every citation of a path under it becomes `path@561ac7a39` (BUGS.md rows B-393..B-396 and their
   bodies, IMPLEMENTATION.md, `docs/reference/frontend-architecture.md` if it cites the brief —
   `scripts/check-docs-cited-paths.py` is the instrument, run it). The B-085 recount, as #584 did it.
6. **File the seven round-two minors as ONE block, B-460 to B-466** (numbers reserved by the steward:
   settings holds B-397+, tooling B-420/B-421, L20 B-440+; gaps are accepted), each with the reading
   from `/Users/izno/dev/review-archive/resolution-card-585/round-2/r2-B.md` (read it whole; findings
   B1–B7) in the entry's `<sub>`, status `open`, owner « the next wave that opens the file »:
   - B-460 (B1) R161's h2 floor is green over a mark made invisible by `opacity: 0`, `clip-path` or an
     off-screen transform; red only over `display: none`, `visibility: hidden`, `scale(0)`.
   - B-461 (B2) R162's `LAST_FRAME = 6500` is « the message's last reachable frame » and the message's
     opacity is 0 there (1.0 at 6200, 0.19 at 6300); the sentence outruns its subject; only « the
     window shrinks » is armed — a message outliving the window passes all eighteen holds.
   - B-462 (B3) the card's accessible name is title + year only; confidence, provider, kind and
     synopsis are announced to nobody. **RULED B by the operator, 2026-09-12**: the name announces
     the confidence and the provider (« Titre Année · 90 % · TMDB »), built by the next wave that
     opens `features/arrivals/resolution-cards.tsx`, with a hold reading the accessibility tree.
     Write the ruling in the body.
   - B-463 (B4) `scripts/csstokens_ranks.py` attributes a site to the nearest `export const` above
     it: a rank smuggled under an unrelated export at an already-recorded number passes silently; at a
     different number the finding names the wrong site.
   - B-464 (B5) the same arm never opens three scopes: a `<style>` block in the shell markup
     (`refonte.html` has one at line 3), a `.css` in a subdirectory of `styles/`, a negative `-z-N`.
   - B-465 (B6, OLD) `engine/legacy.js:9344` still says « paintSelBar() below draws the bar directly »
     four lines above the call to the now-empty function; owner L13.
   - B-466 (B7) `ui/variants/frame.ts` is at 399 non-blank against a hard ceiling of 400: a rank at a
     new number costs one line and takes it to the ceiling, while the arm this wave added is what
     will demand that line.
   Also the two instruments the reader corrected in its copy, as ONE sentence in B-460's body: round
   one's `a05_edges.py:108` reads `textContent` for the name length; `desktop_frame.py:132-137` cites
   stale line numbers (B-391's block).
7. **Version**: patch bump after reading `main`'s at that moment (0.98.84 now; two other waves will
   bump to the same — re-read before you write, and again before you push if main moved).
8. **Gate**: `make check` (own lock, 3 workers) at 0 failed / 0 errors; `python3 scripts/check-bug-register.py`
   clean; `python3 scripts/check-docs-cited-paths.py` clean; `python3 scripts/check-implementation-state.py`
   if it exists. No suite, no a11y beyond what the recordings ran.
9. **Push** (own lock — the pre-push hook runs the suite at 3 workers; `npm ci` in `frontend/` and
   `frontend/maquette/design/` first if `node_modules` is absent), `git ls-remote` read, PR READY, title
   `chore(maquette-resolution-card): the post-merge gesture — references re-recorded on the squash, the micro-wave traced, the folder cited by commit, round two's minors filed`,
   body in English: what moved in each reference (rules count, holds count, `failed`), the row, the
   citations, the block B-460..B-466 with the operator's ruling on B-462. Report to the orchestrator:
   head sha, PR number, run id, gauge. Then STOP as the sole writer.

## What you read before acting

`CLAUDE.md` (§ Search Safety — `rg` only with `--type py` or a glob; § Commit Convention — no AI
attribution; § Language); `docs/reference/documentation-model.md` (the folder cited by commit);
`docs/reference/frontend-steward.md` § « Instrument hygiene »; `BUGS.md` § Status vocabulary and rule
3, B-085 (the recount), B-256, B-369; `frontend/maquette/README.md` § « What replaced « zero
divergence » » and § « `harness/` — the rule suite »; `scripts/harness-hold-counts.py --help`;
`git show fe46548df`.

## Non-goals

- No file under `frontend/maquette/design/src/`, `frontend/maquette/harness/` (the recordings write
  only the two JSON references under `frontend/maquette/`), `personalscraper/` beyond the version.
- No repair of any minor you file; no edit to other waves' register blocks; no renumbering.
- No edit to `docs/reference/frontend-architecture.md` beyond a citation's `@sha`.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Communication

Your orchestrator's exact name and reference are in your launch prompt. Handshake first (the
state readings and your gauge); report on the recordings, on the push, on any STOP; silence rule 15
min. Do not stop between steps to report one done.

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
