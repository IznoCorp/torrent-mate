# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage staging area** ("A TRIER" = "to sort"). Downloaded media files land here, get renamed, cleaned of junk files/folders, scraped for metadata (via TMDB/TVDB APIs, with MediaElch as manual fallback), then moved to permanent storage on one of 4 disks.

Package name: `personalscraper`. CLI entry point: `personalscraper <command>`.
V0-V15 implemented — see `docs/reference/architecture.md` for version history and module map.

**V15 (config-driven):** All storage paths and category names are now in `config.json5`.
Run `personalscraper init-config --from-current` to migrate from V14. See `MIGRATION.md`.

## Critical Rules

### Commit Convention

- Format: `vX.Y.Z: Description` (X=version, Y=phase, Z=sub-phase)
- NEVER include `Co-Authored-By`, Claude, Anthropic, or AI references in commits
- A PreToolUse hook (`block_ai_attribution.py`) enforces this — commit will be blocked

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

### Implementation Workflow

ALL planning (brainstorming → design → plan) must be complete for ALL versions before ANY code is written.
Use `/model-version` for planning, `/implement-version` to start coding (blocks if planning incomplete).
Coherence check between every phase — verify interfaces match design before continuing.

**Per sub-phase discipline:**

- **Commit** after every sub-phase (`vX.Y.Z: Description`)
- **Update progress** (IMPLEMENTATION.md + plan/INDEX.md) after every sub-phase — never batch
- **Check context** after every sub-phase — if ≥80% full, compact before continuing

**Continuous flow:**

- **Never ask for confirmation** to continue between sub-phases, phases, or versions
- **Always continue automatically** — phase done → next phase, version done → next version
- **Only stop** if: a blocking error requires a user decision, or context needs compaction
- Do NOT ask "On continue ?", "Shall I proceed?", or present options to continue — just do it

### Move Rules (V5 dispatch)

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

| When working on...                                                            | Read                                   |
| ----------------------------------------------------------------------------- | -------------------------------------- |
| CLI commands, pipeline invocation, scheduling (launchd), make targets         | `docs/reference/commands.md`           |
| Disks, NTFS/macFUSE, rsync flags, disk space rules, move rules details        | `docs/reference/storage.md`            |
| Directory layout, module map, versions V0-V14, shared utilities, dependencies | `docs/reference/architecture.md`       |
| Movie/TV folder naming, episode patterns, filename sanitization               | `docs/reference/naming.md`             |
| Unit tests, E2E, roundtrip, golden files, test markers, timeouts              | `docs/reference/testing.md`            |
| TMDB/TVDB APIs, NFO invariants, artwork, ffprobe language codes               | `docs/reference/scraping.md`           |
| rapidfuzz, tenacity, structlog, rich, guessit gotchas                         | `docs/reference/libraries.md`          |
| Circuit breaker, fast-skip, dispatch/verify internals, idempotence            | `docs/reference/pipeline-internals.md` |

Also check version-specific planning docs under `docs/v{N}-*/` and archived versions under `docs/archive/`.

## Current Version

**v15** — COMPLETE. Config-driven architecture. All 10 phases done. 1702 tests pass.

- Archive v14: `docs/archive/v14/IMPLEMENTATION.md`
- Completed plan: `docs/IMPLEMENTATION.md`
- Design spec: `docs/v15-config-driven/DESIGN.md`
- Plans: `docs/v15-config-driven/plan/`
- Migration guide: `MIGRATION.md`

**Config-driven key points:**

- `config.json5` (gitignored) holds all paths, disks, categories — run `init-config` to create
- Category IDs: `movies`, `tv_shows`, `anime`, etc. — see `personalscraper/conf/ids.py`
- `personalscraper init-config --from-current` migrates from V14 `.env`
