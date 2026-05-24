# Design — Legacy Cleanup "Goodbye V0-V15"

> **⚠ STATUS** : This DESIGN.md is an archived as-designed snapshot. Some claims are
> superseded by later features. Original scope was alpha-version cleanup. Doc rot remains in
> non-scope `docs/*.md` top-level (~43 VX hits). Resolved in tech-debt 10.2.b sweep.
>
> **Old → New mapping** :
>
> | Old (DESIGN.md)                    | New (current)                                             | Replaced by                    |
> | ---------------------------------- | --------------------------------------------------------- | ------------------------------ |
> | Scope = alpha-version cleanup only | Scope extended to all `docs/*.md` top-level VX references | tech-debt 10.2.b (in progress) |
> | `MANUAL.md` V3 mentions            | Rewritten without VX token                                | tech-debt 10.2.b               |

**Date** : 2026-04-22
**Codename** : `legacy-cleanup`
**Type** : minor (feat)
**Version bump** : 0.2.0 → 0.3.0
**Branch** : `feat/legacy-cleanup`

## Context

The project went through 16 alpha iterations labelled V0 through V15. Each iteration
produced its own `docs/vX-*/` directory with BRAINSTORMING + DESIGN + plan phases,
and its own milestone commits. Many Python modules carry VX tags in docstrings and
inline comments ("V8 circuit breaker", "V9 sequential pipeline", etc.).

Since the switch to SemVer (currently `0.2.0`), these VX tags are obsolete history:

- They obscure the current state of the project (what _is_ vs what _was built when_)
- They confuse new contributors / future sessions reading `CLAUDE.md`
- They scatter historical context across 16 directories, an obsolete `MIGRATION.md`,
  and dozens of Python comments

This refactor erases all visible traces of the alpha versioning scheme, without
losing the history (git log + a preserved archive directory remain the source of truth).

## Goal

Present the project as a mature `0.x` SemVer codebase. No VX references in
any "live" file (code, root docs, reference docs). Historical artifacts are
preserved under a single archive root.

## Scope

### In scope

- **Root docs** : `MIGRATION.md`, `ROADMAP.md`, `CLAUDE.md`, `CONFIGURATION.md`, `MANUAL.md`, `INSTALLATION.md`, `docs/IMPLEMENTATION.md`
- **Legacy feature archive** : 16 `docs/v*-*/` directories + existing `docs/archive/v13/`, `docs/archive/v14/`
- **Reference docs** : `docs/reference/*.md` (8 files)
- **Source code** : 41 Python files in `personalscraper/` with VX refs in comments and docstrings

### Out of scope

- `README.md` — already clean (no VX refs)
- `IMPLEMENTATION.md` at root — current feature tracker (info-cmd), kept as-is
- `docs/features/` and `docs/archive/features/` — post-refactor feature workflow, untouched
- `docs/superpowers/` — unchanged
- Git commit history — past is past
- `VERSION` — bumped separately via `/implement:create-branch`
- Runtime migration contracts (`.v14.bak` file extensions created by `conf/migration.py`) — preserved; only the **comments/docstrings** around them are reformulated

## Non-Goals

- **No functional change.** Zero modification to logic, imports, names, control flow.
- **No documentation rewrite beyond VX removal.** If a paragraph in `architecture.md` becomes awkward after removing "V0-V14 implemented", it's reformulated to an intemporal equivalent — but we don't audit for technical accuracy beyond that.
- **No test changes.** If a test fixture references "V14 label" in a string, the fixture stays (runtime contract).
- **No git history rewrite.** No rebase, no filter-branch.

## Architecture — 5 Sequential Phases

### Phase 1 — Archive legacy docs

**Intent** : move all alpha version directories to a single archive root.

Operations :

- Create `docs/archive/legacy-alpha/`
- `git mv docs/v0-project-setup/` → `docs/archive/legacy-alpha/v0-project-setup/`
- Repeat for `v1-ingest`, `v2-sort-clean`, `v3-scrape`, `v4-verify`, `v5-dispatch`, `v6-log-notify`, `v7-e2e-tests`, `v7x-test-audit`, `v8-robustness`, `v9-pipeline-integrity`, `v10-pipeline-resilience`, `v11-code-quality`, `v12-pipeline-hardening`, `v13-pipeline-correctness`, `v15-config-driven` (16 directories total)
- `git mv docs/archive/v13/` → `docs/archive/legacy-alpha/v13/`
- `git mv docs/archive/v14/` → `docs/archive/legacy-alpha/v14/`
- `git rm docs/IMPLEMENTATION.md` (legacy tracker, 30 KB, redundant with git log + archived dirs)

Gate :

- `ls docs/ | grep -E '^v[0-9]'` returns nothing
- `ls docs/archive/` contains `legacy-alpha/`, `features/`, and nothing matching `v[0-9]*`
- No `docs/IMPLEMENTATION.md`

Commit : `chore(legacy-cleanup): archive v0-v15 alpha docs`

### Phase 2 — Rewrite root docs

**Intent** : strip VX references from user-facing documentation at the project root.

Operations :

- `git rm MIGRATION.md` (V14 → V15 migration, obsolete at 0.2.x)
- Rewrite `ROADMAP.md` : drop "Implemented V0-V14" table, keep only "Future Ideas" (Auto-Download, Watcher, YoutubeTrailerScraper, Config System Overhaul, Decouple Staging, Library Indexer)
- Clean `CLAUDE.md` : remove "V0-V15 implemented", "V15 (config-driven)", "Config-driven key points (v15 baseline)", "V14 → V15 migration" mentions. Keep the functional description + rules + reference index
- Scan `CONFIGURATION.md`, `MANUAL.md`, `INSTALLATION.md` for VX refs, apply strategy A (sharp removal + reformulate where sense is lost)

Gate :

- `grep -rn "V[0-9]" *.md` returns nothing meaningful (ignore CI badges, Python version refs)
- `ls *.md` : no `MIGRATION.md`
- `ROADMAP.md` contains only future ideas
- `CLAUDE.md` reads as a description of the current 0.x project, not an alpha history

Commit : `chore(legacy-cleanup): rewrite root docs without VX refs`

### Phase 3 — Clean `docs/reference/*.md`

**Intent** : make the lazy-loaded reference docs intemporal.

Files (8) :

- `architecture.md` — "V0-V14 implemented" header, pipeline compositions like "V9+V10+V13"
- `commands.md`, `storage.md`, `naming.md`, `testing.md`, `scraping.md`, `libraries.md`, `pipeline-internals.md`

Strategy "A + common sense" :

- Sharp mechanical removal of `V[0-9]+` tokens
- When a sentence loses meaning, reformulate intemporally
  - Example : `Full pipeline (V9+V10+V13) executes 8 steps sequentially` → `Full pipeline executes 8 steps sequentially`
  - Example : `V1: qBittorrent → staging` → `Ingest module: qBittorrent → staging`

Gate :

- `grep -n "V[0-9]\b" docs/reference/*.md` returns nothing
- Visual pass on each file — no orphan fragments ("ex. after removing version", "based on the V8 spec")

Commit : `chore(legacy-cleanup): clean reference docs of VX refs`

### Phase 4 — Clean source code

**Intent** : remove VX tags from Python comments and docstrings.

Scope : 41 files (listed below under "File inventory").

Approach :

- Per-module sweeps (ingest, sorter, scraper, verify, dispatch, enforce, library, conf, commands, plus top-level files)
- Each sweep : one commit per module to keep diffs reviewable and revert-friendly
- **Strict invariants** :
  - Modifications only inside comments (`# …`) and docstrings (`"""…"""`)
  - No change to variable / function / class names
  - No change to imports or control flow
  - `git diff --stat` per commit shows only comment/docstring lines
  - `make test` after each module sweep → green
  - `make lint` after each module sweep → green

Edge case — `personalscraper/conf/migration.py` :

- The code creates `.v14.bak` files as a runtime contract — **that code stays**
- The **comments** around it reformulate V14/V15 as "legacy format" / "current format" or similar

Gate :

- `grep -rn "V[0-9]\b" personalscraper/ --include="*.py"` returns nothing
- Full `make test && make lint` → green

Commits : per module, e.g. :

- `chore(legacy-cleanup): strip VX refs from ingest module`
- `chore(legacy-cleanup): strip VX refs from sorter module`
- etc.

### Phase 5 — Final validation

**Intent** : verify the whole codebase is clean; final commit.

Operations :

- Full sweep check :
  ```
  grep -rn "\bV[0-9]+\b" \
    --include="*.md" --include="*.py" \
    --exclude-dir=archive --exclude-dir=.venv
  ```
- `make lint && make test` → green
- Refresh test count in `README.md` / `CLAUDE.md` if stale (`pytest --collect-only -q | tail -1`)
- Final commit : `chore(legacy-cleanup): final sweep and validation`

### Detection rules (grep patterns)

| Pattern                       | Meaning                     | Action                         |
| ----------------------------- | --------------------------- | ------------------------------ |
| `\bV[0-9]+\b`                 | "V3", "V12", "V14" isolated | remove                         |
| `\bv[0-9]+\b`                 | "v3", "v12" lowercase       | remove (context check)         |
| `V[0-9]+\.x`                  | "V7.x"                      | remove                         |
| `V[0-9]+\+V[0-9]+`            | "V9+V10+V13" composition    | reformulate                    |
| `V15 \(config-driven\)`       | explicit feature title      | remove label, keep description |
| `\.v14\.bak`                  | runtime backup filename     | **KEEP** (runtime contract)    |
| `\.personalscraper\.v14\.bak` | runtime backup              | **KEEP**                       |
| `Python 3\.10\+`, `V3\.10`    | Python version              | **KEEP**                       |
| `TMDB v3 API`, `TVDB v4 API`  | external API version        | **KEEP**                       |
| CI badges, `VERSION=0.x.y`    | semver reference            | **KEEP**                       |

### Decision rule per occurrence

```
For each grep match:
├─ Is it a project version ref (V0-V15) ?
│  ├─ YES → remove it
│  │        └─ Does the sentence still make sense ?
│  │           ├─ YES → sharp removal
│  │           └─ NO  → reformulate, preserving the "why" if meaningful
│  │                    (e.g. "# NTFS safety check — filenames corrupted on reboot")
│  └─ NO (external API, Python, runtime file) → leave as-is
```

## File inventory (source code)

41 files identified by `grep "V[0-9]"` in `personalscraper/` :

```
personalscraper/cli.py
personalscraper/config.py
personalscraper/models.py
personalscraper/naming_patterns.py
personalscraper/pipeline.py
personalscraper/text_utils.py
personalscraper/commands/init_config.py
personalscraper/conf/__init__.py
personalscraper/conf/classifier.py
personalscraper/conf/migration.py
personalscraper/conf/models.py
personalscraper/conf/resolver.py
personalscraper/dispatch/dispatcher.py
personalscraper/dispatch/disk_scanner.py
personalscraper/dispatch/media_index.py
personalscraper/dispatch/run.py
personalscraper/enforce/coherence_checker.py
personalscraper/enforce/run.py
personalscraper/ingest/__init__.py
personalscraper/library/analyzer.py
personalscraper/library/disk_cleaner.py
personalscraper/library/models.py
personalscraper/library/rescraper.py
personalscraper/library/scanner.py
personalscraper/library/validator.py
personalscraper/scraper/__init__.py
personalscraper/scraper/episode_manager.py
personalscraper/scraper/mediainfo.py
personalscraper/scraper/nfo_generator.py
personalscraper/scraper/providers.py
personalscraper/scraper/run.py
personalscraper/scraper/scraper.py
personalscraper/sorter/__init__.py
personalscraper/sorter/cleaner.py
personalscraper/sorter/matcher.py
personalscraper/sorter/run.py
personalscraper/sorter/sorter.py
personalscraper/sorter/strategies.py
personalscraper/verify/checker.py
personalscraper/verify/run.py
personalscraper/verify/verifier.py
```

Module grouping for commits :

- `commands/`, `conf/`, `ingest/`, `sorter/`, `scraper/`, `verify/`, `enforce/`, `dispatch/`, `library/`
- Plus top-level : `cli.py`, `config.py`, `models.py`, `naming_patterns.py`, `pipeline.py`, `text_utils.py`

## Testing strategy

- **Zero new tests**, zero modified tests for this refactor — logic doesn't change
- After each phase : `make test && make lint` must stay green
- If any test fails during Phase 4 : the grep sweep was too aggressive (caught a live string), fix immediately
- End of Phase 5 : run the full E2E suite if affordable

## Risk analysis

| Risk                                                                 | Mitigation                                                                                                             |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Grep catches a live user-facing string (CLI message, log text)       | Review each match visually before editing; trigger `make test` after each module sweep                                 |
| Sentence in reference docs becomes incomprehensible after VX removal | Strategy "A + common sense" : reformulate intemporally, preserve the "why"                                             |
| Runtime migration code breaks (`.v14.bak` handling)                  | Touch only comments/docstrings in `conf/migration.py`; logic stays intact                                              |
| Archive path breaks cross-references in live docs                    | Phase 2 cleans live docs of any `docs/v*-*/` path mention; check with `grep -n "docs/v[0-9]" *.md docs/reference/*.md` |
| Merge conflict if other features start in parallel                   | Single-purpose branch, merge (squash) before starting next feature                                                     |

## Deliverables

**Deleted** :

- `MIGRATION.md`
- `docs/IMPLEMENTATION.md`

**Moved (git mv, history preserved)** :

- `docs/v0-project-setup/` … `docs/v15-config-driven/` → `docs/archive/legacy-alpha/`
- `docs/archive/v13/`, `docs/archive/v14/` → `docs/archive/legacy-alpha/`

**Rewritten** :

- `ROADMAP.md`, `CLAUDE.md`, `CONFIGURATION.md`, `MANUAL.md`, `INSTALLATION.md`
- `docs/reference/*.md` (8 files)
- 41 Python files — comments/docstrings only

**Unchanged** :

- `README.md`, `IMPLEMENTATION.md` (root), `VERSION`
- `docs/features/`, `docs/archive/features/`, `docs/superpowers/`
- All Python logic, imports, names, tests, fixtures

## Success criteria

1. `grep -rn "\bV[0-9]+\b" --include="*.md" --include="*.py" --exclude-dir=archive --exclude-dir=.venv` returns zero significant matches
2. `make lint && make test` green
3. `ls docs/` contains no `v[0-9]*` directory
4. `CLAUDE.md` reads as a description of the current 0.x project
5. All 5 phases committed on `feat/legacy-cleanup`, ready for PR + squash merge

## Version bump

- Current : 0.2.0
- Target : 0.3.0 (minor)
- Rationale : project-visible cleanup significant enough to warrant a minor bump — the docs and codebase presentation change substantially for any contributor or future agent reading the project.

## Next step

Invoke `superpowers:writing-plans` to produce the per-phase implementation plan
(`docs/features/legacy-cleanup/plan/INDEX.md` + one file per phase).
