# maquette-l16 — the implementer's brief for L16, « the ratio is steered »

You implement **L16 — §18, the ratio**, the whole lot in ONE wave
(`docs/reference/frontend-architecture.md` § 4, entry `#### L16`, the CONTRACT). The lot's design is
`docs/features/maquette-l16/DESIGN.md` (re-drawn 2026-09-27 on the operator's organisation rulings 18–20 and rounds
7–10, #623; OPEN 4 ruled C, #618) and its plan `docs/features/maquette-l16/plan/INDEX.md`, one file per phase — **they
are the specification and this brief restates none of it**. L16 is the plan's **phases 1 to 17**, in that order: the
reads' contract (1), the Trackers page, its bar button and its two tabs (2 — OPEN 4 = C: « Trackers » first, then the
last tab, reusing Acquisition's tab memory), the roster (3), the policy set from the entry (4), the « Torrents » tab (5),
« Retirer de qBittorrent » (6), the removal across shared entries (7), the alert derivation (8), the broken obligations
(9), the Trackers badge on the bar (10), the « ⋮ » panel drops its hard-coded ratio facts (11), a deferred card names its
reason and tracker (12), the ranking's contract (13), the ranking editor reads (14) and saves (15), the live preview
(16), the close (17 — everything but the folder's death: `docs/features/maquette-l16/` is deleted WHOLE, and every
citation of it re-cited `path@<L16's squash sha>`, in the STEWARD's docs pull request AFTER L16's squash — the
precedent of L13, #607 then #608 — so that the lot's RULINGS, amended plan and RESUME exist in a commit of `main`). 192 points, ONE wave and ONE reader round (the auditor's ruling of
2026-09-27: L16 is not cut).

L16 is stacked on **L22b's pull request head** at L22b's READY (measure 9): L22b's reader round and merge are never
awaited — when the steward tells you L22b is squashed onto `main`, you MERGE `origin/main` in at your next unit
boundary (`git merge --no-edit <sha>`, never a rebase).

**The operator's rulings are the design's spine**: `docs/reference/operator-method.md` (organisation rulings 1–23,
rounds 4–11) and the constitution § 18 as amended. They are not reopened. The lot's own rulings — the steward's, on
your STOPs — go to `docs/features/maquette-l16/RULINGS.md`, one numbered file, created at your first ruling.

## Opening facts — the steward's read-only re-measure of the plan (2026-09-28, on L22b's head `95b45734e`)

Each phase is still re-measured at ITS opening on YOUR head; these are the facts found ahead, so none is a surprise:

- **Size.** The INDEX says 192 points; the phase files' own line items add to ≈ 206 before any reader is counted;
  re-measured with their harness readers ≈ 225 — about 23 phases once cut. Likely cuts at opening: **2** (≈ 19: eight
  readers — `url_state.py:685`, `page_host.py:35/968` gain `trackers`; bar_shares, bar_places, journey, panel,
  discover_page, scroll_memory walk the new page), **5** (≈ 16: `paths_to_sheets.py` « card AND tile, no third », which
  L22b's phase 44 edits first), **6** (≈ 16), **9** (≈ 15–16), **12** (≥ 16: nine readers of `card/reason` or
  `card/strip`), **14** (≈ 23). Phase 4 sits at the ceiling (≈ 15).
- **Phase 2 cannot open before L22b's phase 47** (the death of Arrivées): while `arr` is in the bar, Trackers is a fifth
  button and `bar_shares.py:55` (`1 <= count <= 4`) falls. You start from L22b's READY head, after 47 — check it.
- **Three premises are false on main and on L22b alike — each is ONE STOP D at its phase's opening, with the command:**
  phase 12 — the backend's ratio cause is the GLOBAL `ingest.min_ratio` (`personalscraper/ingest/deferral.py:73`), so
  R-L16-g's second mutation would hold the opposite of what the engine does (the maquette draws the next version: a
  backend limitation is recorded, never drawn around); phase 14 — the maquette's `/api/config/files/{name}` has `put`
  only and `configuration.ts:50` lists names, not content: the read needs a new operation, a mock route and a seed;
  phase 9 — the plan's « vu » seen-mark precedent does not exist (its grep returns French prose only).
- **Mechanisms L22b added after the plan was written:** phase 10 — a badged row now carries `useBadgeReads`
  (`navigation.ts:98-104`); phase 2 — RULINGS 19 of L22 raised the frame-domain ceiling 132 → 141 for Découvrir, and this
  phase raises it again (say by how much, with the command); phase 17 — L22b's close rewrites the same README cut table
  (`README.md:783`).
- **Stale cross-references in the plan:** phases 3, 4, 5 and 10 call the close « phase 16 » (it is 17); phase 10's oracle
  reason names « phase 9 ». One dated line each when you reach them.

## Environment

- Worktree `/Users/izno/dev/worktrees/wave-l16`, branch `feat/maquette-l16`, cut by the steward from the head the
  launch prompt names. You are the only writer there. The main checkout `/Users/izno/dev/PersonalScraper` and every
  other worktree are not yours: never write, build or run there.
- Both `node_modules` are installed. Your log directory is `~/Library/Logs/tm-l16/`: `<phase>-<step>.log`; gate logs
  kept until the merge, working logs pruned at every stand-down and proved by `ls`; a log a RESUME line or a commit
  body CITES is kept.
- Verify the state, do not believe it:

      git remote update origin >/dev/null && git log --oneline origin/main -3
      pwd && git branch --show-current && git status --short && git log --oneline -1
      ls docs/features/maquette-l16/plan/ | grep -c "^phase-"      # 17
      python3 scripts/check-frontend-boundaries.py --arm size; echo "exit $?"
      python3 scripts/check-frame-domain.py; echo "exit $?"
      grep -n __version__ personalscraper/__init__.py               # bump at the PR only
      sh scripts/heavy.sh --held

## What you read before acting — and NOTHING ELSE before the handshake (auditor's order 8)

1. This brief; `docs/features/maquette-l16/RESUME-L16.md`'s STATE BLOCK (you create it at your first boundary if
   absent); DESIGN § 0 and § 6; `plan/INDEX.md` whole; and `plan/phase-01-reads-contract.md`. That is the whole required
   reading before your handshake. (Corrected by the steward's word, 2026-09-28: it read « § 7 » and « phase-01-contract.md ».)
2. After the handshake, as each phase opens: its phase file (re-read at that moment), the DESIGN sections it cites,
   `frontend/maquette/README.md` § named states and § traps, `CLAUDE.md` § Critical Rules (search safety, language,
   naming, `scripts/rename-identifiers.py` — never a rename by hand), and `scripts/check-mock-seeds.py`'s docstring
   before any seed row.

## Method — the INDEX governs, plus the office's precisions

- **Every phase is BEHAVIOUR or a MOVE, as its file says**: **the rule FIRST, seen RED**, its label bound to the next
  free number of YOUR RESERVED RANGE — rules **R260–R299**, register rows **B-570–B-589** (the steward's reservation,
  2026-09-28: two branches running side by side collided twice that day on « the highest across main and the open
  branches », which cannot see unpushed commits) — the mapping written into the RESUME; then the move, then the same rule green with its holds counted, then a mutation that fells
  it by name. The oracle may diverge ONLY on the states each phase names, each accepted by name with its reason; any
  other divergence is STOP A.
- **Sizes**: every phase ≤ 15 points (measure 11) — at a phase's opening you RE-MEASURE it against its own file on
  YOUR head (non-blank lines for the 400-line ceiling) before committing to the shape written there; a phase above 15
  is cut at its opening and the steward told; a figure that no longer supports the phase's home is STOP D, reported
  with the command, never improvised past. The plan's STOP C on phase 2 is RESOLVED (OPEN 4 = C, #618); its STOP D on phase 4 (how the three policy fields
  compose) and on phase 12 (the seed) are ONE message each, at that phase's opening.
- **Re-aims are said out loud** in the rule's docstring and the commit body; the opening measure lists the READERS of
  the behaviour a phase reverses, not only its writers (order 42 amended).
- **Locks by CLASS.** Anything touching the ONE served copy or the 8899 host — `run.sh` in any tier, the oracle,
  `harness-hold-counts.py`, `mutate.sh`, a single rule replayed — runs under the shared mutex, in the ONE form that
  reads rule names: `TM_HARNESS_JOBS=3 sh scripts/heavy.sh --class browser l16 frontend/maquette/harness/run.sh
  --contracts --oracle <full rule paths>` (one build, one verdict block), one line to the steward before and after;
  **read `sh scripts/heavy.sh --held` and wait, never bypass**. Every pytest and every `git push` under the same mutex,
  class test, with NO `HEAVY_LOCK=` override: `PYTEST_XDIST_AUTO_NUM_WORKERS=3 sh scripts/heavy.sh --class test l16
  <command>`. The push is its OWN command from the worktree root — `sh scripts/heavy.sh --class test l16 git push -u
  origin feat/maquette-l16` — never prefixed by `cd … &&`. If the classifier refuses a push, STOP with the refusal's
  EXACT text and the command: no retry, no other route, and never ask another session to push for you.
- **Mutations**: `sh scripts/mutate.sh <full path> "<python expression>" frontend/maquette/harness/<rule>.py` — read
  the NAMED `FAIL` line, keep the EXPRESSION in the log; « RULE CRASHED » and « RULE NOT FOUND » prove nothing; commit
  before every mutation.
- **Order 48 (amended)**: a fall set aside as « load » is proved by the SAME rule ≥ 10 times on your branch AND ≥ 10
  times on `main` at comparable load; a gap is a regression. A green re-run alone proves nothing.
- **A phase's gate** = one wrapped `run.sh --contracts --oracle <named rules>` + the cheap guards it runs, logs
  POSTDATING the commit they measure; `--a11y` on EVERY gate that draws; `tests/scripts/test_check_maquette_comments.py`
  alone under the test mutex before any push, `check-maquette-comments.py --record` INSIDE the commit when a maquette
  file moved. **The FULL SUITE runs TWICE** (measure 20): at the MIDPOINT, after phase 9 and before phase 10 opens,
  every fall re-read under order 48 before it is charged to load, its real falls repaired by you before phase 10; and
  after phase 17, before the pull request, with `--a11y`, `scripts/harness-hold-counts.py --compare
  frontend/maquette/hold-counts-baseline.json` (`failed` read FIRST), `python3 scripts/check-bug-register.py`,
  `python3 scripts/check-intent-map.py`, `python3 scripts/check-docs-cited-paths.py`, read by OUTPUT.
  `TM_HARNESS_JOBS=3` on EVERY heavy invocation. **No local `make check`** (measure 19): CI's `test` job is the
  authority; the pre-PR gate is `make lint` + the full suite + `--a11y` + `--compare` + the pre-push pytest.
- **The oracle ACCEPTS the states a phase declares, by name, in a commit** — and `frontend/maquette/oracle.py
  --accept` takes NO name: it rewrites the WHOLE reference. So it runs inside the gate's own invocation, then a script
  proves that ONLY the declared keys moved, and HEAD's reference is committed with those keys alone (L22b's method,
  2026-09-28); never a blanket re-record; the steward re-records at the merge. A closed `#dlg` keeping the last
  dialog's box (B-554) moves unnamed states on `shell/dialog` ALONE: RULINGS 7 of L22 applies — accept them by name, a
  script proving no other region moved, one message to the steward.
- **The declared list is built BY SCRIPT before the gate** (L22b missed states drawn under a layer three times, phases
  38, 43, 44): every state whose page draws the world the phase touches (the `scen` field and the page of each state in `states/*.ts`), those under a
  layer included (L22 RULINGS 23). A divergence outside that list stays STOP A.
- **A state removed from a rule's list names its successor** in the ledger, read from your own diff (L22b phase 41
  pushed a hole where a net hold count hid a drop of six).
- **Navigation is proved by a finger walk**, never by a posed state alone (L22b phase 38 pushed a landing that stayed on
  Système because its rule read a posed screen).
- **The remaining phase list is rebuilt from `ls plan/`** at every cut, never from memory (L22b's STATE lost a whole
  15-point phase in two renumberings).
- **The « rules only » mode of `run.sh`** (operator, 2026-09-28, question 1 = A; it lands with the day's repair train):
  when your base carries it, a red, a diagnosis or a finger walk uses it; a phase gate never does.
- **The CI's static list runs at EVERY gate**, read by output: the `no-french` job of `.github/workflows/ci.yml`
  (l. 281–294) — `check-no-french.py`, `check-css-tokens.py`, `check-compositor-css.py`,
  `check-tailwind-confinement.py`, `check-markup-contracts.py`, `check-frontend-boundaries.py`,
  `frontend/maquette/oracle.py --contracts`. Seconds each; `run.sh` does not fold them all in (L22b's branch failed
  `oracle.py --contracts` for twenty phases, seen only at phase 48).
- **2026-09-28, auditor's order 49**: before a gate, the static list, then `run.sh --oracle` ALONE, the moves it shows
  declared BY NAME with their cause in the gate's invocation; after an acceptance by name proved by script on a green
  gate, no « final » gate. Measured at the close: gates per phase (≤ 1.3), share of oracle-only failures (0).
- **2026-09-28, auditor's order 52**: harness lines added ≤ 0.6 × product lines added in this lot (`git diff --numstat
  origin/main...HEAD`, harness/ against design/src/), measured at the midpoint and the close; a new check on a surface
  that has its rule is a HOLD in that file; above the budget, a CONSOLIDATION phase before READY.
- **2026-09-28, auditor's orders 58, 59, 65, 67a, 70** (amending § Method): a phase gate is the static list → the
  oracle ALONE → `run.sh --rules` (the phase's re-aimed rules + the touched surfaces' group) → `--a11y` when it draws;
  no `--contracts` at a phase gate (it runs at 9, 14, the close and in CI; two contract falls charged to the lot bring
  it back to every gate); entry R62 and pwa (R52, R105, R108, R111) leave the phase gates; order 48 in `--rules`
  series, 5 draws for a known-unstable rule the phase does not read; exit boundary ~55 %; a light run (`--rules`, one
  rule's mutation) is `--class rule`, browser kept for `--oracle` / `--a11y` and full suites.
- **Your context**: the hook stops you at 60 % — at ~55 %, commit, push, rewrite the RESUME and stand down.
- **The RESUME**: `docs/features/maquette-l16/RESUME-L16.md` = a STATE BLOCK of at most 40 lines (rewritten at every
  boundary) + an APPEND-ONLY ledger below it. No register row for an unshipped defect: a ledger line on the phase
  instead; a register row a phase closes is closed in that phase, with the rule's red reading and its mutation.
- **`IMPLEMENTATION.md` is the steward's**: the wave does not touch it. **No edit to `docs/reference/*`, `CLAUDE.md`,
  the office**; DESIGN and the plan under `docs/features/maquette-l16/` are amended by ONE dated line where a phase
  proves them wrong.
- **CONTEXT BUDGET ≤ 15 points per phase**: gate logs read by their verdict line only; commit bodies ≤ 12 lines, no
  baseline figure in a body; a phase-file amendment is ONE dated line. Gauge at every phase boundary; **under 45 % you
  TAKE the next phase**. While a gate runs you read the next phase's file and re-take its figures read-only.

## Non-goals

- L22b's files beyond what a phase of yours names (a defect you find in L22b's work is a STOP,
  not a repair of yours); L17 (cross-seed marks), L18 (rights — L16 declares no right, OPEN 2 = A), L23 (upload); the
  engine (after the freeze). No new guard, arm or tool (measure 1). No redrawing beyond what a phase's move names:
  every visual change outside it is STOP A.
- No `--no-verify`, no force-push, no rebase, no merge of your own pull request, no deletion of a branch or a
  worktree; no delegate that writes or reviews (read-only search subagents only, nothing heavy). Never
  `/tmp/tm-refonte` by hand, never 8899 by hand.
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

One commit per phase (plus the commit-before-mutation where a phase says so), conventional, scoped `maquette-l16`
(e.g. `feat(maquette-l16): …`), no attribution of any kind (`CLAUDE.md` § Commit Convention; `hooks/commit-msg`
refuses it). **Push at EVERY phase end (after its gate), at every stand-down and at the close**, under the test mutex.
After phase 17: merge `origin/main` in (`git merge --no-edit`, never a rebase), bump the version (patch) above whatever
`main` reads then, the full gate, pull request READY titled `feat(maquette-l16): the ratio is steered — the Trackers
page, its two tabs, the removal, the alert and the ranking editor` — a BEHAVIOUR pull request, so it cites the constitution §§ each phase
serves (§ 2, § 12, § 13, § 16, § 18). Body: the seventeen phases and what each moved, every rule written with its red run and its
mutation (EXPRESSION and FAIL line), the oracle states accepted by name, the register rows closed, the midpoint suite's
falls and repairs, and **the screenshots of the Trackers page's two tabs at 390 px** (a Playwright run on the served
maquette, fixtures only), in the body, never committed. Report READY the second it exists. One reader round follows
(measure 2); you stay available for its findings in a fresh session with a resume brief, not in this one.

## Communication

Your orchestrator's exact `ListAgents` name and reference are in the launch prompt. First act after the required
reading: the handshake — the state-verification readings and your gauge — and nothing is in flight until it is
answered. Then: a report at every phase gate and at every STOP (the STOP, its evidence, the proposed resolution, and
you WAIT), one line before and after every shared-mutex run, the push report. Reports in French. A message that
expects an answer and has none after fifteen minutes is re-sent after a fresh `ListAgents`, to the session whose NAME
matches, marked as a re-send; if the name is not listed, tell the user in your session and stop waiting. **Do not stop
between phases to report one done.** Every long run is waited for INSIDE the tool call (timeout ≤ 600 s, or a bounded
loop polling its log) — never a turn ended on a run still going. Every report ends with the gauge:
`/Users/izno/.claude/plugins/cache/lounisbou/orchestrator/0.35.0/skills/context-gauge/scripts/context-gauge.sh` run
as the LAST call, its `context_percent=` and `source=` lines pasted. **The context gate is 80 %** (measure 8):
(a) crossing it mid-work, you finish the unit in progress, rewrite the RESUME's state block, append the ledger, push
under the test mutex, prune, report « stood down » with `git ls-remote` proving the push, and stop — the steward spawns
your successor; (b) PRE-DISPATCH: you OPEN the next phase when your measured gauge + the measured cost of your last
phase is ≤ 80 — never a rotation mid-phase; (c) every state on disk, nothing only in your context.

## Resource envelope — the machine is shared

TWO agents may run beside the steward on this 8-core, 16 GB host (measure 6). The mutex serialises the heavy runs;
you announce yours. Every command runs synchronously in the tool call that waits for it, long output to a FILE under
`~/Library/Logs/tm-l16/`, the exit code read in the same call, **never `| tail -N` on a long gate**. Fan-out has a
name and a value, every time: `TM_HARNESS_JOBS=3`, `PYTEST_XDIST_AUTO_NUM_WORKERS=3`. Kill what you start, delete
what you build (`design/dist`, bench copies, screenshots), prove it with
`ps -eo pid,etime,command | grep -E "chrom|playwright|vite|node |pytest|heavy.sh" | grep -v grep` before every
report; the 8899 host is `run.sh`'s and is left alone. Never `cd` into `frontend/maquette/design/src` (B-384): absolute
paths from the worktree root. Search safety (`CLAUDE.md`): every `rg`/`grep -r` carries a type filter. No `git stash`,
ever. Tier **deep**, chosen because every phase writes a rule whose red reading nobody else re-reads before the reader
round. Your session is spawned with NO MCP server; the harness needs none.
