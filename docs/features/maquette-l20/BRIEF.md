# maquette-l20 — the design and the plan of L20, prepared ahead of its wave

You prepare **L20 — The global levers and the history** (`docs/reference/frontend-architecture.md`
§ 4, entry `#### L20`, which is the CONTRACT and is not restated here). You **draw and plan; you do
not implement**: this wave produces `docs/features/maquette-l20/DESIGN.md` and
`docs/features/maquette-l20/plan/` (INDEX.md + one file per phase), nothing under
`frontend/maquette/design/src/`, no rule, no mock, no code. The lot itself opens AFTER the
`maquette-settings` micro-wave merges (the operator's order of 2026-09-12); its implementer will
read your two documents from `main` and execute the plan. So the documents are written for a
session that has none of your context — every figure with its command, every decision with its
reason, every screen with its named states.

Branch `docs/maquette-l20-design`, worktree `/Users/izno/dev/worktrees/wave-l20-design` (cut from
`origin/main` at `468162dc6`), one pull request opened READY with the label `no-version-bump`
(prose only — the version does not move), squash merge on the operator's word once he has validated
the drawing. You are the only writer there. `IMPLEMENTATION.md` is not yours: its « In flight » row
stays « None » (a design is not an open lot) and the steward writes the rows.

## What « drawn » means here, since no pixel is drawn

The plan's method (§ 5): a surface is drawn BEFORE it is coded, with named states and a rule that
bites. For a design document that means, per surface:

1. **Its place** — the address (D1: identity in the path, state in the query), the navigation
   table row it needs (`app/navigation.ts`: bar, drawer, or a section of an existing page), the
   feature folder (invariant 10: `features/pipeline/` or the Système feature — the blocking note
   below decides).
2. **Its named states** — English ids in the harness's shape (`window.__go("<id>")`, read
   `frontend/maquette/README.md` § « Every state has a name »), one per distinct drawing: at rest,
   loading (§13: unknown parts are not printed as answers), empty, error, each lever's pending and
   queued forms (DOIT-4: a legitimate action is accepted and its queueing is visible), the history
   list, a run's detail with its raw log FOLDED (B-296), the locks block (B-297). For each: what is
   on the screen, in words, with the French copy in « guillemets » exactly as `fr.json` will carry it
   (English keys proposed beside), the interactive parts and the `data-*` NAMES they emit (English,
   D4), what changes when the operation answers.
3. **The rule that bites** — for each state, the rule's name (R165+ are the free numbers — verify
   with the command in « Verify the state » — but settings and tooling take numbers in parallel, so
   write `R-L20-a`, `R-L20-b`… and let the implementer bind them), what it READS (network through
   `window.__mocks.answered()`, the DOM, a finger's hit test — never a toast alone, never a named
   state alone for a path a hand walks: R128's own design), and the mutation that fells it.
4. **The contract** (D7): the operations the interface REQUIRES, seeded from `frontend/openapi.json`
   (`/api/pipeline/run|pause|resume|kill|watcher|status|stages|history|history/{run_uid}`,
   `/api/maintenance/locks`; the parallelism bound is a SETTING and reads through the settings
   feature's contract — name the key after reading `config.example/*.json5` and the engine's
   `personalscraper/web/routes/pipeline.py`), the mock's shape per operation (what it MOVES, D7 — a
   mock that answers without moving certifies nothing), and every difference recorded as a demand in
   `docs/reference/frontend-backend-demands.md`'s form (you write the demand text in DESIGN.md; the
   implementer files it).
5. **What the oracle will do** (D8): the surfaces are NEW, so the reference records them as new;
   name the states that will appear in `regions.json` and say that no existing state may diverge.

Two production surfaces are your inventory, not your model: `frontend/src/pages/Pipeline.tsx` and
its `frontend/src/components/pipeline/*` (FlowBoard, PipelineControls, RunHistoryTable, RunDetail,
RunLogFeed, InterpretedRunFeed, RecentResolutions, TriggerLegend, PipelineActionBanner), and the
locks block of `frontend/src/pages/SystemPage.tsx`. Read them to know what production answers today
and what the operator has seen; the constitution and the plan decide what the maquette draws — D12
(no event feed), the operator's Q6 (no Pipeline tab, no badge), the trigger legend refused (the
trigger is written in words), §20 (the per-media half is L19's and DRAWN: a card's progress, the
journey sheet, the blocked queue — you do not redraw it, you LINK to it from a run's detail).

## The blocking note is an arbitration for the OPERATOR, and you send it in your first hour

« Where the levers land — a page of their own, or a section of Système » is the operator's UX
question. Within your first hour, before drawing the levers, send the steward ONE message in this
shape: what the thing is (the three levers and their state, the watcher's relaunch, the history's
entry point), **two readings** — (A) a page of their own under the drawer, with the history as its
second half; (B) a « Pipeline » section of Système for the levers and the locks, the history
reached from Arrivées (« les passages ») — what each costs (a navigation row and its rules; the
frame's drawer list; DOIT-6's discoverability; how Arrivées' pilot's bar — `data-pipe` in
`features/arrivals/page.tsx`, the run/stop/pause/resume the operator already has — relates to the
global levers: one control in two places, or the bar becomes the levers' surface), and **one
recommendation**. Then CONTINUE on your recommended reading; if the ruling differs, redraw the
affected part — the plan is written so that the choice touches one phase. Any other screen
question with two defensible answers (the history row's figures — which of DOIT-6's numbers; the
bound's control — stepper or field; the raw log's fold) is put to the steward the same way, batched,
never one at a time, and never blocks the rest.

## The plan

`plan/INDEX.md` in L21's shape (read it: `git show 2ffdc4ba3:docs/features/maquette-l21/plan/INDEX.md`
and one phase, `git show 2ffdc4ba3:docs/features/maquette-l21/plan/phase-02-season-grab.md`):
« the phases chain, they do not pause », the governing rule (rule first, seen red — here against
`main`, where the surfaces do not exist: the strongest form), the STOPs (B: an oracle divergence on
a state the lot did not touch; C: the pull request), the table of phases with what each lands and
its register entries (B-296, B-297, B-371 are L20's — read them whole; DOIT-3's « relancer le
watcher », DOIT-5's progress, DOIT-6's figures read `served` in `docs/reference/product-intent-map.md`
at the end), the ordering and its reason. One kind of change per phase; the contract first (it
produces the demands); one surface per phase; the closing phase re-reads the map and the register.
Each phase file: the rule first (what it reads, how it is seen red), the move (files created —
ceiling 400 non-blank lines per file, invariant 7's import rules between features), the gate, the
commit message.

## What you read before acting, in order

1. `docs/reference/product-intent.md` whole (French, the constitution) — §20, DOIT-1, DOIT-3,
   DOIT-4, DOIT-5, DOIT-6, NE-DOIT-PAS-1, NE-DOIT-PAS-5, §13.
2. `docs/reference/frontend-architecture.md` § 0, § 2 (D1, D1b, D4, D5, D7, D8, D12), § 3, § 4's
   L15, L19, L21 entries (what exists), L20 (yours), § 5, § 6.
3. `docs/reference/product-intent-map.md` rows DOIT-3, DOIT-4 (B-371), DOIT-5, DOIT-6 and the
   operations list (`watcher`, `stages`, `history/{run_uid}` → L20).
4. `docs/reference/frame-model.md` (the frame's parts — a lever that is a global control may be a
   frame concern: say whether it is), `docs/reference/backend-demands-architecture.md` (§20's tunnel
   per media — what the backend will owe the levers), `docs/reference/frontend-backend-demands.md`
   and `frontend-backend-demands-stream.md` (which stream events a run's history and the levers
   claim — `live.ts` of the feature).
5. `frontend/maquette/README.md` whole; `frontend/maquette/contract/README.md` § « How to change it ».
6. `BUGS.md` entries B-296, B-297, B-371, B-256, B-369 (a fixture change moves named states — cost
   every seed you ask for), B-383 (« said, not done » — the class your levers must not join).
7. The maquette as it stands: `frontend/maquette/design/src/app/navigation.ts`,
   `features/arrivals/page.tsx` (the pilot's bar), `features/acquisition/` (the status sheet's
   « Lancer la veille maintenant »), `features/system/` if it exists (`ls features/`), the mock
   handlers for the pipeline routes (`grep -rn "pipeline" frontend/maquette/design/src/mocks/handlers/`),
   `mocks/scenario.ts` (the busy scenario), `lib/verbs.ts`, `ui/variants/frame.ts` (the ranked list —
   a lever's confirmation is a dialog at 56).
8. `frontend/src/pages/Pipeline.tsx`, `frontend/src/components/pipeline/`, `frontend/src/pages/SystemPage.tsx`
   (inventory only).
9. Optional, if the design host serves `main`: `http://127.0.0.1:8712/` is `tm-design` (pm2, the main
   checkout's build) — read it in a browser to see the existing Arrivées and Système; never rebuild
   or restart it.

## Verify the state; do not believe it

    git remote update origin >/dev/null && git log --oneline origin/main -3
    pwd && git branch --show-current && git status --short
    grep -n "^#### L20" docs/reference/frontend-architecture.md
    grep -o "| \*\*In flight\*\*[^|]*| [^.]\{0,40\}" IMPLEMENTATION.md
    grep -rhoE '^"""R[0-9]+ ' frontend/maquette/harness/*.py | sort -V | tail -1
    python3 -c "import json;d=json.load(open('frontend/openapi.json'));print([p for p in d['paths'] if '/pipeline' in p or 'locks' in p])"
    grep -rn "pipeline" frontend/maquette/design/src/mocks/handlers/ | wc -l
    grep -n "data-pipe" -r frontend/maquette/design/src/features/arrivals/ | wc -l
    ls frontend/maquette/design/src/features/
    git check-ignore -v docs/features/maquette-l20/BRIEF.md; echo "exit $? (1 = not ignored, expected)"

## Non-goals

- No file under `frontend/maquette/design/`, `frontend/maquette/harness/`, `personalscraper/`,
  `scripts/`; no rule written, no mock, no seed, no i18n edit — the implementer does those from
  your plan.
- No edit to `docs/reference/frontend-architecture.md`, `IMPLEMENTATION.md`, `BUGS.md`,
  `product-intent-map.md`: a design that finds the plan wrong says so in DESIGN.md § « What the
  plan gets wrong, measured » with the command, and the steward amends the plan.
- No redrawing of L19's per-media surfaces; no Pipeline tab or badge; no event feed (D12).
- No heavy run: you build nothing and drive no browser; the one exception is reading `tm-design`
  in a browser if you want to see the existing pages. (`npm ci` is not needed for this wave —
  your push with the pre-push hook needs `frontend/node_modules` and `frontend/maquette/design/node_modules`
  for the suite it runs: `npm ci` in both, under your OWN lock, before your first push, or push with
  the hook's suite in your own log — never `--no-verify` without saying so in the report.)
- If you believe something outside this list is needed, STOP and ask the orchestrator first.

## Delivery

Commits: `docs(maquette-l20): …`, one per document (DESIGN, INDEX, each phase), conventional, no
attribution of any kind (CLAUDE.md § Commit Convention; `hooks/commit-msg` refuses it). Push wrapped
under your own lock; `git ls-remote --heads origin docs/maquette-l20-design` read. Pull request READY,
label `no-version-bump`, title `docs(maquette-l20): the design and the plan of the global levers and the history`,
body: the arbitration(s) and their rulings, the states count, the phases, what the plan gets wrong
if anything. Report to the orchestrator: on the handshake (readings + gauge), on the arbitration, on
the push (head sha, PR number, run id), with the gauge each time. Do not stop between documents to
report one done.

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
