# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

A **media triage pipeline**: downloaded media land in the staging area, get renamed, cleaned of
junk, scraped for metadata (TMDB/TVDB, MediaElch as manual fallback), then moved to permanent
storage on one of the configured disks. Package `personalscraper`; CLI `torrentmate` (alias
`personalscraper`), same Typer app. All storage paths, the staging layout and the categories are
config-driven, never hardcoded (`personalscraper init-config` seeds `config/` from
`config.example/`). Layout: `docs/production/config-overlay-layout.md`; module map:
`docs/production/architecture.md`.

## Setup (per clone)

```bash
pip install -e ".[dev]"
./hooks/install.sh   # one-time per clone — sets core.hooksPath to hooks/ (never ~/.gitconfig)
```

## How we work

One page: `docs/reference/method.md`. The generic lifecycle lives in the skills — `implement:*`
(feature → phase → check → close), `orchestrator:*` (dispatching agents),
`pr-review-toolkit:review-pr` (the lot's reading), `github:*`. Where the frontend work stands:
`IMPLEMENTATION.md`. The operator's principles and rulings, verbatim:
`docs/reference/operator-method.md` (§ 1 and § 3 are amended by him alone).

## Gates

The implement skills read these two lines.

- **Phase gate**: `make lint`; `cd frontend/maquette/design && npm run typecheck && npm test`; pytest of
  the touched modules.
- **Lot-close gate**: `make check`.

The full pytest and every harness rule run in CI (`.github/workflows/ci.yml`, `harness-full.yml` on a
pull request touching the maquette), not on this machine. `make harness` runs the rules by hand.

## Authority — the operator's word (BINDING)

- `docs/reference/product-intent.md` is the product constitution: an implementation that conflicts
  with it is wrong. A web PR cites the §§ it serves; a pure conversion (nothing observable changes)
  cites none.
- The maquette `frontend/maquette/design/` is the next version of the app and REPLACES it; it is not
  transposed into the app surface by surface. Its reference is the tokens and the component
  catalogue: `design/src/styles/theme.css`, `design/src/styles/base.css`, and the `variants.ts` of
  `design/src/ui/` and of each surface. It is changed FIRST, a surface is drawn (named states, a
  rule that bites) before it is coded, and nothing ships that it does not show.
- **The mission, dictated 2026-08-19**: EVERY screen is redrawn. (1) No surface is out of scope — a
  production screen with no maquette page is a page still to draw; `/control` and `/pipeline` are
  owed. (2) What the maquette already holds is VALIDATED; do not relitigate it. (3) What remains is
  also the UX, the interaction language and the prototype's architecture — the interface is frozen
  when that is done. (4) The backend follows the interface, after the freeze: a backend limitation
  is recorded, never a reason to draw less.
- What the maquette must become technically, and the lot order: `docs/reference/frontend-architecture.md`
  (BINDING). Developer reference of the prototype: `frontend/maquette/README.md`.

## The machine (IznoServer)

- `rg` ALWAYS with `--type py` or a `-g '*.ext'` glob: `tests/e2e/perf/.fixture/` is 14 GB of binary
  media and an unfiltered `rg` crashes the machine.
- qBittorrent: NEVER enable « Bypass authentication for clients on localhost » (nor any whitelist
  variant) — behind the reverse proxy it exposes the WebUI to the Internet (`docs/reference/qbittorrent-api.md`).
- NEVER start a server on 8710/8711 (Caddy routes `tm.`/`tm-staging.` there), nor on 8712/8899 by
  hand (design host, harness host). Test the frontend via `tm-staging.iznogoudatall.xyz` / `tm-design`.
- A heavy local run goes through `scripts/heavy.sh`, one at a time; `make test` and `run.sh` default
  to half the processors. Kill what you start, delete what you build. The machine reboots every
  Monday at 05:00.
- `personalscraper run` and any long pipeline command: foreground only, `timeout=600000` (hook-enforced);
  create TODO tasks before launching; show output step by step; kill on 2 identical consecutive
  errors, then check for orphans, lock files and temp dirs. Or run the steps one by one
  (`personalscraper ingest`, `sort`, …). `-v` only to debug one step.
- Never an API key in documentation. Storage paths may contain spaces — quote them. The filesystem
  is case-insensitive: `git mv FILE.md tmp.md && git mv tmp.md file.md`.

## Commits and pull requests

- Conventional Commits `<type>[(<scope>)]: <description>` (`feat|fix|chore|refactor|style|docs|test|perf|build|ci`);
  no version prefix; no AI attribution (`hooks/commit-msg` refuses both; it cannot reach a message
  composed on GitHub). Branches `feat/<codename>` / `fix/<codename>`, scope = codename, squash merge.
- Every PR bumps the patch version (CI `version-bump`), or carries the label `no-version-bump` when it
  touches no code under `personalscraper/`, `frontend/maquette/design/src/`, `frontend/maquette/harness/`,
  `scripts/` or `.github/workflows/`.
- A DRAFT PR runs no CI: open it READY (or add `run-ci-on-draft`, never both transitions at once).
  Once its diff is verified, arm `gh pr merge <n> --auto --squash --match-head-commit <sha>` (re-arm if
  the head moves). After `main` moves, `gh pr update-branch`.
- Claim a KanbanMate ticket that ALREADY EXISTS (`/kanban-work <ticket>`) before coding it; never
  create one for work this session is about to do.
- A worktree is removed once its PR is merged (local branch deleted, then `ExitWorktree` remove).

## Code

- Google-style docstrings on every module, class, function and method (`Args:`, `Returns:`,
  `Raises:`); comments explain the why; English.
- A bug fix carries a regression test shown to FAIL against the code before the fix.
- Tests: unit / integration / manual E2E — `docs/reference/testing.md`.
- `scripts/rename-identifiers.py` exists for identifier renames (optional); re-read the diff.

## Language

The operator writes French or English — answer in French when he writes French. Everything
durable is English (code, comments, docstrings, maquette and harness sources, `docs/`, `BUGS.md`,
`IMPLEMENTATION.md`, this file), except his two documents, `docs/reference/product-intent.md` and
`docs/reference/operator-method.md`, and the frozen `docs/production/`. Never mix languages in a
document; French inside an English one only quotes UI copy, media titles or the operator verbatim.

- The code has no French and no interface text. Names are English everywhere (identifiers, CSS
  classes, file names, `data-*` attribute names, route paths, named-state ids, tool messages).
- Every UI string lives in `frontend/maquette/design/src/i18n/fr.json` (the `server` namespace for
  `serve.py`'s pages). Extract strings, never retype them.
- A literal that must stay French (rendered output a harness asserts, i18n placeholders, form field
  names, settings config keys) carries `# french-ok: <reason>` / `// french-ok: <reason>`; a pragma
  with no reason is a violation.
- `frontend/src` is exempt (no i18n layer, dies at switchover), under a ratchet
  (`scripts/french-exemption-baseline.json`).
- Enforced in CI by `scripts/check-no-french.py` (fourteen arms, listed in its docstring).

## Domain rules

- **Move rules (dispatch)** — Movies (`movies`, `movies_animation`, `movies_documentary`, `standup`,
  `theater`): an existing folder on a disk is REPLACED by the staging version. TV shows (`tv_shows`,
  `tv_shows_animation`, `tv_shows_documentary`, `anime`, `tv_programs`): new episodes are MERGED into
  the existing folder, replacing any that exist. New media go to the disk with the most free space.
- **Web environments** — three checkouts share `library.db`, `.data/` and the disks: dev
  `~/dev/PersonalScraper` (no PM2 daemons), prod `~/deploy/torrentmate` (tracks `main`, 8710),
  staging `~/staging/torrentmate` (tracks `staging`, 8711, read-only role → 403 on writes).
  Canonical config: `~/.torrentmate/config`. Topology and deploy: `docs/production/web-ui.md`.
- **Web invariants (tests enforce)** — every mutating endpoint is `require_not_staging` and typed
  (Pydantic `response_model`; a route change ⇒ `make openapi` and commit the generated files); the
  auth perimeter is the single `guarded_api` dependency (never a per-route `Depends(require_session)`);
  maintenance write actions hold `pipeline.lock` for their runner's lifetime; `pipeline_run`
  timestamps are epoch `time.time()`; `GET /api/version` serves the boot-cached BUILD_COMMIT.

## Reference index (lazy-load)

`docs/production/` describes the version in production, frozen until the switchover;
`docs/reference/` describes the next version or what is true whatever the version. History is
git: a path cited `path@sha` is read with `git show sha:path`.

| Topic | Read |
| --- | --- |
| The method | `docs/reference/method.md` |
| CLI, scheduling (PM2 crons), make targets | `docs/production/commands.md` |
| Disks, NTFS/macFUSE, rsync, move rules detail | `docs/production/storage.md` |
| Module map, api/ contracts | `docs/production/architecture.md` |
| Media folder naming, episode patterns | `docs/reference/naming.md` |
| Tests, markers, golden files, feature map | `docs/reference/testing.md` |
| TMDB/TVDB, NFO, artwork | `docs/production/scraping.md` |
| Library gotchas (rapidfuzz, tenacity, structlog…) | `docs/reference/libraries.md` |
| Circuit breaker, dispatch/verify internals | `docs/production/pipeline-internals.md` |
| Event bus | `docs/production/event-bus.md` |
| Logging | `docs/production/logging.md` |
| Trailers | `docs/production/trailers.md` |
| Indexer, JSON column shapes | `docs/production/indexer.md`, `docs/production/indexer-json-shapes.md` |
| Cross-provider IDs, ratings | `docs/production/external-ids-flow.md` |
| Providers and clients | `docs/reference/<provider>-api.md` (tmdb, tvdb, omdb, trakt, qbittorrent, transmission, c411, tr4ker, plex, telegram, healthchecks, ffprobe) |
| Insights | `docs/production/insights.md` |
| Maintenance ops | `docs/production/maintenance.md` |
| Config overlay | `docs/production/config-overlay-layout.md` |
| Post-merge operator checklist | `docs/production/runbook-post-merge.md` |
| Web UI in production | `docs/production/web-ui.md` |
| Constitution and its surface map | `docs/reference/product-intent.md`, `docs/reference/product-intent-map.md` |
| Maquette (prototype reference) | `frontend/maquette/README.md` |
| Frontend target and lots | `docs/reference/frontend-architecture.md` |
| Frame model and survey | `docs/reference/frame-model.md`, `docs/reference/frame-survey.md` |
| Backend demands, and the backend brief (draft) | `docs/reference/backend-demands-architecture.md`, `docs/reference/frontend-backend-demands.md`, `docs/reference/backend-brief.md` |
