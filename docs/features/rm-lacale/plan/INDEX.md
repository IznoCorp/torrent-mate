# rm-lacale — Implementation Plan Index

**Feature**: [#156] Complete removal of the LaCale tracker (+ Torr9 zero-remnant proof)
**Branch**: `refactor/rm-lacale` · **Version**: 0.77.0 (bumped at create-branch, `b8a6297f`)
**Design**: `docs/features/rm-lacale/DESIGN.md` (removal map §3 is the authority)

## Phases

| #   | Phase                                           | File                                   | Status |
| --- | ----------------------------------------------- | -------------------------------------- | ------ |
| 1   | Backend removal + test rewrites + D2 regression | `phase-01-backend-removal.md`          | [ ]    |
| 2   | Web + frontend + config + docs purge            | `phase-02-web-frontend-config-docs.md` | [ ]    |
| 3   | ACCEPTANCE (SH-16) + full gate                  | `phase-03-acceptance-full-gate.md`     | [ ]    |

## Deviations from DESIGN §3 (verified against the tree 2026-08-03 — flag for operator sign-off)

1. **D8/D10 grep commands as written in DESIGN are BROKEN on this machine.**
   Verified on ripgrep 15.1.0: combining `--type py` with `-g '*.ts' …` makes the
   globs override the type filter — the command silently searches ZERO `.py` files
   (empirically confirmed: the design's exact D10 command misses all 69 py hits).
   The plan replaces `--type py` with an explicit `-g '*.py'` glob (all-glob form,
   additive — confirmed to catch all 69 py files). Intent (zero-hit proof) preserved;
   letter corrected. See phase-03 for the corrected criteria.
2. **Torr9 grep is NOT currently zero-hit in py** (the design's broken command hid
   this): 3 files reference torr9 — `tests/acquire/test_removed_tracker_history.py`
   (the removed-tracker regression suite itself, legitimate → exempted),
   `personalscraper/api/tracker/_base.py` + `tests/unit/test_c411_client.py`
   (historical explanatory comments → reworded in phase 1 so only the regression
   file needs exemption).
3. **D9 "~10 test files" is actually 53 py test files + 5 frontend test files**
   (full enumeration in phase-01/phase-02). Most are mechanical fixture-string
   renames; ~11 pin registry/factory/activation membership.
4. **D3 location**: the `k != "lacale"` code exclusion lives at
   `personalscraper/web/routes/acquisition_ranking.py:248` (+ comment line 244) —
   `web/models/acquisition.py:622` is docstring-only. Both handled in phase 2.
5. **D4 scale**: only 2 of the 12 preview samples use `provider="lacale"`
   (`acquisition_ranking.py:96,108` — s5/s6), not all 12.
6. **Extra surfaces found by grep, absent from the §3 map**: `_base.py:63`,
   `_registry.py:162` (docstrings/comments), `docs/reference/config-overlay-layout.md:123`,
   `.env.example:133-140` (LACALE block), `docs/reference/_samples/lacale/` (5 JSON
   fixtures), `ROADMAP.md` (#156 entry — completion tidy).
7. **D2 vehicle already exists**: `tests/acquire/test_removed_tracker_history.py`
   is the established removed-tracker (torr9) regression pattern — the lacale
   regression extends it by parametrization rather than creating a new file.

## Conventions (all phases)

- One sub-phase = one commit, `refactor(rm-lacale): …` or `test(rm-lacale): …`.
- Every `rg` in this plan carries a type/glob filter — **unfiltered rg crashes this
  machine** (14 GB fixture dir). Hard rule.
- Repo traps: PostToolUse ruff hook strips an import added without a same-edit
  usage; any FastAPI model/route/docstring change ⇒ `make openapi` + commit the
  regenerated `frontend/openapi.json` + `frontend/src/api/schema.d.ts` in the same
  commit; `git add -f` required for new/renamed files under `docs/` (global
  gitignore has a `docs/` rule).
- Live config (`~/.torrentmate/config/tracker.json5`) and DB rows: OUT OF SCOPE
  (post-merge operator step, DESIGN D6/D2/§6).
