# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage pipeline**. Downloaded media files land in the staging
area (defined by `paths.staging_dir` in `config/paths.json5`, outside the repository
by default), get renamed, cleaned of junk files/folders, scraped for metadata
(via TMDB/TVDB APIs, with MediaElch as manual fallback), then moved to
permanent storage on one of the configured disks.

The staging subdirectory layout (`001-MOVIES/`, `002-TVSHOWS/`, etc.) is configured
via the `staging_dirs` section of `config/patterns.json5` — not hardcoded or tracked by git.

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.
See `docs/reference/architecture.md` for the module map and package layout.

All storage paths, staging layout, and category names are in the `config/` directory.
Run `personalscraper init-config` to create `config/` from the `config.example/` template.

## Critical Rules

### Search Safety (MANDATORY — machine crash prevention)

`tests/e2e/perf/.fixture/` is **14 GB** of binary media files. `rg` without type
filters WILL consume all RAM and crash the machine (PID 39685 incident).

**Every `rg` command MUST include one of:**

- `--type py` (Python files only)
- `-g '*.py'` (glob filter)
- `-g '*.md'` or `-g '*.json5'` etc. for non-Python targets

**Examples:**

```bash
# CORRECT
rg "pattern" --type py personalscraper/ tests/
rg "pattern" -g '*.py' -g '*.md' .

# WRONG — will crash the machine
rg "pattern" personalscraper/ tests/
rg "pattern" .
```

`.rgignore` at the repo root excludes known heavy dirs as defense-in-depth,
but new fixtures can appear — the type filter is the primary safeguard.

### Commit & Push Policy

**Override the default "ask before commit" rule** — on this project we commit and push as we go, gated by quality checks.

- **Each sub-phase / logical unit of work → one commit**, made by Claude without further user prompting.
- **Before every commit**: run `make check` (lint + test + module-size + typed-api). Zero errors required. If anything fails, fix the underlying issue then commit. Never `--no-verify`.
- **Before every push**: run `make gate` (`make check` + secret scan + residual-import audit).
- **Push cadence**: after each phase gate (i.e. once a phase is closed end-to-end and its gate sub-phase committed).
- **Still requires explicit user authorization**: force-push, destructive git ops (reset --hard, branch -D, etc.), and any push to `main`. The autonomous policy applies only to feature branches.

### Commit Convention

Follows [Conventional Commits](https://www.conventionalcommits.org/) — globally enforced for all projects using this `.claude/` config.

Format :

```
<type>[(<scope>)]: <description>
```

Types : `feat | fix | chore | refactor | style | docs | test | perf | build | ci`

Examples :

- `feat(scraper): create TvShow nfo file`
- `chore: add json5 dependency`
- `refactor(dispatch): extract folder_for to resolver`
- `fix(conf): add missing Config import in scraper/run.py`

**Forbidden** :

- Version prefixes (`vX.Y.Z: Description`) — version traceability lives in `IMPLEMENTATION.md` and subagent reports (sub-phase → SHA mapping), not in commit messages
- AI attribution : `Co-Authored-By`, `Claude`, `Anthropic` — enforced by `hooks/block_ai_attribution.py`

**Milestone commits** (used by `/implement:phase` skill) include codename as scope :

```
chore(my-feature): phase 3 gate — scraper refactor
```

This is the ONLY place codename appears in milestone commits.

### Pipeline Monitoring Rules

When running `personalscraper run` or any long-running command with user observation:

1. **NEVER run in background** — foreground only, `timeout=600000`. A hook (`block_background_pipeline.py`) enforces this.
2. **Create TODO tasks BEFORE launching** — categories: bugs, incohérences, améliorations. Update in real-time.
3. **Show output after each step** — read and display incrementally, don't wait for the end.
4. **Kill on 2 identical consecutive errors** — systemic failure = STOP immediately, don't keep trying.
5. **State limitations upfront** — if you can't guarantee something, say so BEFORE agreeing.
6. **After kill: check filesystem** — orphans, lock files, temp dirs. Clean or report what can't be cleaned.

Alternative: run steps individually (`personalscraper ingest`, then `personalscraper sort`, etc.) to maintain control between steps. Use `-v` only for debugging a specific step (generates 100× more output).

### Code Conventions

- **Google-style docstrings** mandatory on all modules, classes, functions, and methods
- Docstrings include: description, `Args:`, `Returns:`, `Raises:` (as applicable)
- **Inline comments** for non-trivial logic explaining the "why" (not the "what")
- Docstring/comment language: **English**
- New tests: choose unit / integration / manual E2E — see `docs/reference/testing.md`.
- **Module size**: soft warning at 800 non-blank LOC, hard ceiling 1000 LOC. Run `python3 scripts/check-module-size.py` (also wired into `make check`). Advisory in 0.9.0; promoted to hard block in 0.10.0.

### Phase Gate Checklist (MANDATORY before every phase gate commit)

Every `chore(scope): phase N gate` commit MUST pass all of:

1. **`make lint`** — ruff + mypy (both wired in Makefile). Zero errors.
2. **`make test`** — all 2642+ tests pass. Check the summary line: `NNNN passed` with 0 failed/errors.
3. **`make check`** — lint + test + module-size + typed-api guardrails.
4. **Residual import grep** — for every module deleted in this phase, grep both `personalscraper/` AND `tests/` for the old import path. Zero matches.
5. **`python -c "import personalscraper"`** — smoke test.

**If `make test` shows any ERROR (not just FAILED)**: the test COLLECTION crashed — all tests after that point are skipped. Fix imports before proceeding.

**After any module deletion**: grep `tests/` for the old path. `rg "old.module.path" tests/` must return zero matches.

**After any constructor signature change**: grep `tests/` for the old call pattern and update all test fixtures/mocks.

### Implementation Workflow (feature-oriented)

10 `implement:*` skills managing the full feature lifecycle with Opus/Sonnet/Haiku allocation. See details in `docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md`.

**Entry point**: `/implement:feature` — archive prev, brainstorm, derive codename + SemVer type, create branch, generate plan.

**Per phase**: `/implement:phase` — loop on sub-phases, dispatching `/implement:sub-phase` + `/implement:check` (verification). Auto-invokes `/implement:feature-pr` at last phase (gate + push + PR + CI poll), then `/implement:pr-review` (review + max-3 fix cycles + squash merge).

**Branches**: `feat/{codename}` or `fix/{codename}`
**Commits**: Conventional Commits with `(codename)` scope
**SemVer bump** (at create-branch): bugfix → Z+1, minor → Y+1, major → X+1
**Merge**: squash, mode chosen at feature start (manual / auto)

### Move Rules (dispatch)

- **Movies** (category IDs: `movies`, `movies_animation`, `movies_documentary`, `standup`, `theater`): if a folder with the same name already exists on a disk, **replace it** with the new version from the staging area.
- **TV Shows** (category IDs: `tv_shows`, `tv_shows_animation`, `tv_shows_documentary`, `anime`, `tv_programs`): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

### Security & Paths

- **Never include API keys** in documentation or brainstorming files — use `.env` references only.
- Storage/staging paths may contain spaces (e.g. `/Volumes/<disk>/<staging-dir>/`) — always quote paths in shell commands.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails, use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`.

### Language

The user communicates in French or English. Code comments are in English only. Respond in French when the user writes in French.

## Reference Index (lazy-load when relevant)

Load these docs on-demand based on your task — they are **not** auto-loaded:

| When working on...                                                                                                  | Read                                    |
| ------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| CLI commands, pipeline invocation, scheduling (launchd), make targets                                               | `docs/reference/commands.md`            |
| Disks, NTFS/macFUSE, rsync flags, disk space rules, move rules details                                              | `docs/reference/storage.md`             |
| Directory layout, module map, shared utilities, dependencies                                                        | `docs/reference/architecture.md`        |
| Movie/TV folder naming, episode patterns, filename sanitization                                                     | `docs/reference/naming.md`              |
| Unit tests, E2E, roundtrip, golden files, test markers, timeouts                                                    | `docs/reference/testing.md`             |
| TMDB/TVDB APIs, NFO invariants, artwork, ffprobe language codes                                                     | `docs/reference/scraping.md`            |
| rapidfuzz, tenacity, structlog, rich, guessit gotchas                                                               | `docs/reference/libraries.md`           |
| Circuit breaker, fast-skip, dispatch/verify internals, idempotence                                                  | `docs/reference/pipeline-internals.md`  |
| Logging conventions, event-name style, structlog vs CLI vs typer channels                                           | `docs/reference/logging.md`             |
| Trailer discovery, download, state, CLI, Plex-conformant placement (movies flat, TV shows in `Trailers/` subfolder) | `docs/reference/trailers.md`            |
| Media indexer DB, scanner modes, query parser, outbox, cron setup, failure recovery                                 | `docs/reference/indexer.md`             |
| JSON column shapes (artwork_json, payload_json, stats_json) — Pydantic model references and examples                | `docs/reference/indexer-json-shapes.md` |

Also check archived alpha versions under `docs/archive/legacy-alpha/` and archived features under `docs/archive/features/`.

## Current Feature

**Feature**: arch-cleanup
**Branch**: refactor/arch-cleanup
**Design**: docs/features/arch-cleanup/DESIGN.md
**Plan**: docs/features/arch-cleanup/plan/
