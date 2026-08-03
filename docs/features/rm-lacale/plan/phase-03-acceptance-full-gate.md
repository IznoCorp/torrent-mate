# Phase 3 — ACCEPTANCE.md (SH-16 executable criteria) + full gate

## Gate (inputs from phase 2)

Phases 1-2 committed: zero lacale in py/ts/tsx/json5/md across
`personalscraper/ tests/ frontend/src/ config.example/ docs/reference/ CLAUDE.md
.env.example` except the exempted regression file; openapi regenerated and
committed; all backend + frontend gates green.

## Command-form note (BINDING — INDEX deviation 1)

DESIGN D8/D10 write the greps as `--type py -g '*.ts' …`. On ripgrep 15.1.0
(this machine) the globs override the type filter — that exact command searches
ZERO py files (verified 2026-08-03). Every criterion below uses the corrected
all-glob form (`-g '*.py'` instead of `--type py`), empirically confirmed to
catch all py hits. Same intent, corrected letter — cite this note in the PR.

## Sub-phase 3.1 — write ACCEPTANCE.md + first full run — `test(rm-lacale): …`

Create `docs/features/rm-lacale/ACCEPTANCE.md` (`git add -f` — global gitignore
`docs/` rule). Every criterion = executable command + documented expected
output (SH-16; prose criteria invalid). Criteria:

- **ACC-01 (D10) lacale zero-hit** — exemption: the removed-tracker regression
  suite only.
  `rg -i "lacale" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.json5' -g '*.md' -g '!tests/acquire/test_removed_tracker_history.py' personalscraper/ tests/ frontend/src/ config.example/ docs/reference/ CLAUDE.md .env.example`
  Expected: no output, exit 1. (docs/archive/** + docs/features/rm-lacale/** are
  outside the scanned paths — D10's stated exemptions hold by construction;
  historical `docs/analysis/` files are untracked.)
- **ACC-02 (D8) torr9 zero-hit** — exemption: same single regression file (it
  pins torr9 absence + historic readability; phase 1 reworded the two
  explanatory comments in `api/tracker/_base.py` and `tests/unit/test_c411_client.py`).
  `rg -i "torr9" -g '*.py' -g '*.ts' -g '*.tsx' -g '*.json5' -g '*.md' -g '!tests/acquire/test_removed_tracker_history.py' personalscraper/ tests/ frontend/src/ config.example/ docs/reference/`
  Expected: no output, exit 1.
- **ACC-03 enum + factory absence**:
  `python -c "from personalscraper.api._contracts import ProviderName; assert not hasattr(ProviderName, 'LACALE')"`
  and
  `python -c "from personalscraper.api.tracker._factory import _TRACKER_CLASSES; assert 'lacale' not in _TRACKER_CLASSES"`
  Expected: exit 0, no output.
- **ACC-04 factory raises its standard unknown-tracker error for "lacale"** —
  one-liner invoking the factory build path with name `"lacale"` and asserting
  the same exception type as any unknown name (exact snippet taken from the
  absence pin added to `tests/unit/test_tracker_factory.py` in phase 1.5).
  Expected: exit 0.
- **ACC-05 (D2) historic rows render** —
  `pytest tests/acquire/test_removed_tracker_history.py -q`
  Expected: all pass, 0 failed (covers obligations read-model, cross-seed,
  ratio_state, dispatch/grab writers, enum absence — parametrized torr9+lacale).
- **ACC-06 dead docs/fixtures gone** —
  `test ! -f docs/reference/lacale-api.md && test ! -d docs/reference/_samples/lacale && echo OK`
  Expected: `OK`.
- **ACC-07 openapi no drift** —
  `make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts`
  Expected: exit 0, empty diff.
- **ACC-08 backend gate** — `make check` (lint + test + module-size + typed-api).
  Expected: zero errors, `NNNN passed`, 0 failed, 0 ERROR.
- **ACC-09 frontend gate** —
  `cd frontend && npm run typecheck && npm run lint && npm run lint:ds && npm run test -- --run && npm run build`
  Expected: all green.

Run EVERY ACC now; record dated outputs in ACCEPTANCE.md (§méthode:
proof-or-non-conforme — no "conforme" without an executed dated run).

## Sub-phase 3.2 — full gate + fallout + tidy — `refactor(rm-lacale): …`

1. `make lint` → 0 errors. 2. `make test` → summary `NNNN passed`, 0 failed,
   **0 ERROR** (an ERROR = crashed collection; fix imports before anything else).
2. `make check` → green (includes openapi-drift + check-frontend when
   `frontend/node_modules` present). 4. Residual-import grep (Phase Gate rule,
   deleted module): `rg -n "tracker.lacale|tracker import lacale|LaCaleClient" -g '*.py' personalscraper/ tests/` → zero.
3. `python -c "import personalscraper"` smoke.
4. Tidy `ROADMAP.md` #156 entry (mark shipped — completion hygiene; flag in PR
   if the operator prefers it untouched). `git status --short` afterwards: no
   stray uncommitted reformat (dirty worktree masks CI lint).
5. Fix any fallout; re-run the failed gate + the affected ACC; final commit.

## Exit

All ACC-01…09 pass with dated outputs recorded. Plan INDEX rows all [x]
(orchestrator updates IMPLEMENTATION.md). Next: /implement:feature-pr — PR body
cites the D8/D10 command-form deviation (this file's note) for operator sign-off.
