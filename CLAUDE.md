# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage pipeline** ("A TRIER" = "to sort"). Downloaded media files
land in the staging area (defined by `paths.staging_dir` in `config.json5`, outside
the repository by default), get renamed, cleaned of junk files/folders, scraped for
metadata (via TMDB/TVDB APIs, with MediaElch as manual fallback), then moved to
permanent storage on one of 4 disks.

The staging subdirectory layout (`001-MOVIES/`, `002-TVSHOWS/`, etc.) is configured
via the `staging_dirs` section of `config.json5` — not hardcoded or tracked by git.

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.
See `docs/reference/architecture.md` for the module map and package layout.

All storage paths, staging layout, and category names are in `config.json5`.
Run `personalscraper init-config` to create `config.json5` from the example template (interactive prompts, or `--yes` to accept defaults).

## Critical Rules

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

### Implementation Workflow (feature-oriented)

10 `implement:*` skills managing the full feature lifecycle with Opus/Sonnet/Haiku allocation. See details in `docs/superpowers/specs/2026-04-22-implement-skills-refactor-design.md`.

**Entry point**: `/implement:feature` — archive prev, brainstorm, derive codename + SemVer type, create branch, generate plan.

**Per phase**: `/implement:phase` — loop on sub-phases, dispatching `/implement:sub-phase` (Sonnet) + `/implement:check` (Opus verification). Auto-invokes `/implement:feature-pr` at last phase (gate + push + PR + CI poll), then `/implement:pr-review` (review + max-3 fix cycles + squash merge).

**Branches**: `feat/{codename}` or `fix/{codename}`
**Commits**: Conventional Commits with `(codename)` scope
**SemVer bump** (at create-branch): bugfix → Z+1, minor → Y+1, major → X+1
**Merge**: squash, mode chosen at feature start (manual / auto)

### Move Rules (dispatch)

- **Movies** (category IDs: `movies`, `movies_animation`, `movies_documentary`, `standup`, `theater`): if a folder with the same name already exists on a disk, **replace it** with the new version from A TRIER.
- **TV Shows** (category IDs: `tv_shows`, `tv_shows_animation`, `tv_shows_documentary`, `anime`, `tv_programs`): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

### Security & Paths

- **Never include API keys** in documentation or brainstorming files — use `.env` references only.
- Paths contain spaces (`/Volumes/IznoServer SSD/A TRIER/`) — always quote paths in shell commands.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails, use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`.

### Language

The user communicates in **French**. Code comments are a mix of French and English. Respond in French when the user writes in French.

## Reference Index (lazy-load when relevant)

Load these docs on-demand based on your task — they are **not** auto-loaded:

| When working on...                                                     | Read                                   |
| ---------------------------------------------------------------------- | -------------------------------------- |
| CLI commands, pipeline invocation, scheduling (launchd), make targets  | `docs/reference/commands.md`           |
| Disks, NTFS/macFUSE, rsync flags, disk space rules, move rules details | `docs/reference/storage.md`            |
| Directory layout, module map, shared utilities, dependencies           | `docs/reference/architecture.md`       |
| Movie/TV folder naming, episode patterns, filename sanitization        | `docs/reference/naming.md`             |
| Unit tests, E2E, roundtrip, golden files, test markers, timeouts       | `docs/reference/testing.md`            |
| TMDB/TVDB APIs, NFO invariants, artwork, ffprobe language codes        | `docs/reference/scraping.md`           |
| rapidfuzz, tenacity, structlog, rich, guessit gotchas                  | `docs/reference/libraries.md`          |
| Circuit breaker, fast-skip, dispatch/verify internals, idempotence     | `docs/reference/pipeline-internals.md` |

Also check archived alpha versions under `docs/archive/legacy-alpha/` and archived features under `docs/archive/features/`.

## Current Feature

**Feature**: ext-staging — external staging directories
**Branch**: `feat/ext-staging`
**Design**: `docs/features/ext-staging/DESIGN.md`
**Plan**: `docs/features/ext-staging/plan/`
