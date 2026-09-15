# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This is a **media triage pipeline**. Downloaded media files land in the staging area, get
renamed, cleaned of junk, scraped for metadata (TMDB/TVDB, MediaElch as manual fallback),
then moved to permanent storage on one of the configured disks.

Package name: `personalscraper`. CLI entry points: `torrentmate` (public command name) and
`personalscraper` (back-compat alias) — same Typer app.

All storage paths, staging layout (`001-MOVIES/`, `002-TVSHOWS/`, …) and category names are
config-driven, never hardcoded; `personalscraper init-config` seeds `config/` from
`config.example/`. Layout: `docs/production/config-overlay-layout.md`. Module map:
`docs/production/architecture.md`.

## Setup (per clone)

```bash
pip install -e ".[dev]"
./hooks/install.sh   # one-time per clone — sets core.hooksPath to hooks/ (never ~/.gitconfig)
```

The pre-commit hook regenerates `tests/feature_map/<codename>.json`; CI catches drift if it
is bypassed. Details: `docs/reference/testing.md` §Feature Map.

## Critical Rules

### Product Intent — product constitution (web-UI — BINDING)

- Every web-UI evolution must conform to `docs/reference/product-intent.md` — the application's raison d'être, dictated by the operator; when an implementation conflicts with the constitution, the implementation is wrong.
- Every web PR cites the §§ it serves, except a CONVERSION PR (nothing observable changes), which cites none (operator, 2026-09-14). Story: `CLAUDE.md@6a47304a4` § Product Intent.

### Design Reference — the maquette is authoritative (web-UI — BINDING)

- `frontend/maquette/design/` is the visual reference of the web UI (constitution §15); every design evolution starts from the maquette, never from the code.
- The reference is the tokens and the component catalogue, and only those: `design/src/styles/theme.css`, `design/src/styles/base.css`, and the `variants.ts` of `design/src/ui/` and of each surface. `legacy.css` dies with the engine at L13; `harness.css` is the harness's own measuring apparatus, ships in no production build, and dies at switchover.
- The maquette is the NEXT version of the app and REPLACES it; it is not transposed, translated, or merged into the app surface by surface — every page and mechanism must eventually be re-created IN the maquette. A maquette/production difference is never a bug to repair by pointing a tool at the other side. Story: `CLAUDE.md@6a47304a4` § Design Reference.
- When a decision changes, the implementation directives change IN THE SAME MOVE; what loses its subject is removed, not kept "just in case".
- The method: (1) the maquette is modified first, verified with its harness (`frontend/maquette/harness/`) — nothing about a surface is decided elsewhere; (2) a surface is drawn before it is coded, with named states and a rule that bites; (3) the harness is the proof — a change lands with its rule, and the rule is mutation-tested.
- The rule suite runs on a schedule, not on a hunch: `frontend/maquette/harness/run.sh --contracts` runs in CI on every PR touching the maquette (a rule reading the operator's live databases cannot be among them); `make check` entire is not among them either. The full suite (no flag) is the gate before a wave is merged, and it is not optional. `run.sh` builds and re-copies the prototype first — the harness reads a manual copy at `/tmp/tm-refonte/wrapped.html`. Story: `CLAUDE.md@6a47304a4` § Design Reference.
- What the maquette must become technically, and in what order, is `docs/reference/frontend-architecture.md`, and it is BINDING. Read it before any frontend work beyond drawing a surface; the state of that work — which lot landed, which is next — is `IMPLEMENTATION.md` § « Where the frontend work stands », and lives nowhere else.

#### The mission — dictated by the operator, 2026-08-19 (SUPERSEDES any narrower reading)

**The maquette is a NEW VERSION of the app, and EVERY screen is to be redrawn. All of them.**
It is not a reskin of the shipped surfaces and it is not bounded by what production happens to
have today. Its purpose is a new, COHERENT user experience, and the first objective is to
**freeze that interface**.

Four consequences, and none of them is optional:

1. **No surface is out of scope.** Any production screen with no page in the maquette is a page
   still to be drawn — never an arbitration to leave it out. This explicitly REVERSES the
   earlier ruling that `/control` (« Contrôle ») and `/pipeline` were deliberately page-less:
   the operator overturned it. Their redistribution into Arrivées / Système / Maintenance /
   Configuration remains a valid UX proposal, but it does not exempt anything from being drawn.
2. **What is already in the maquette is VALIDATED** by the operator. Do not relitigate it.
3. **What remains is not only pages.** The UX, the interaction language, the architecture of the
   prototype and the missing pages all have to be finished and consolidated. The interface is
   frozen when that work is done, not when the last page exists.
4. **The backend follows the interface, not the reverse.** The engine will be adapted to what
   the new interface needs. So a backend limitation is not a reason to draw less — record it and
   draw what the experience requires. Backend work comes AFTER the interface is frozen.

- Read `frontend/maquette/README.md` before any design change — method, named states, verified rule set, and the traps already paid for.

### Search Safety (MANDATORY — machine crash prevention)

- `rg` without type filters WILL consume all RAM and crash the machine (`tests/e2e/perf/.fixture/` alone is 14 GB of binary media). Every `rg` command MUST include `--type py`, or a `-g '*.ext'` glob filter for non-Python targets. `.rgignore` is defense-in-depth only — the type filter is the primary safeguard, since new fixtures can appear. Story: `CLAUDE.md@6a47304a4` § Search Safety.

### Network Timeout Safety (MANDATORY — machine hang prevention)

- curl, wget, and fetch can hang indefinitely when a server accepts the TCP connection but never sends a response. Every network command MUST include both `--connect-timeout N` (recommended 10s) and `--max-time N` (recommended 30s); a `block_curl_without_timeout` PreToolUse hook enforces this. WebFetch has no configurable timeout — prefer `Bash(curl)` with explicit timeouts for hosts that may be slow or unreachable. Story: `CLAUDE.md@6a47304a4` § Network Timeout Safety.

### Commit Convention

- [Conventional Commits](https://www.conventionalcommits.org/), format `<type>[(<scope>)]: <description>` (`feat|fix|chore|refactor|style|docs|test|perf|build|ci`) — globally enforced for all projects using this `.claude/` config.
- Forbidden: version prefixes (`vX.Y.Z: …`) — version traceability lives in `IMPLEMENTATION.md` and subagent reports, not commit messages; AI attribution (`Co-Authored-By`, `Claude`, `Anthropic`) — `hooks/commit-msg` refuses it and holds the Conventional-Commit format and the version-prefix ban, on every commit in this clone, but it cannot reach the squash-merge message composed on GitHub. Milestone-commit format and the codename-as-scope rule: `docs/reference/feature-lifecycle.md` §7.
- Every PR bumps the version, patch by default — the `version-bump` CI job enforces it. A pull request that touches no code — pure documentation, a directive correction, a bug-register entry — carries the label `no-version-bump` instead, added any time before or after opening (CI reruns on `labeled`/`unlabeled`); this never exempts a PR that also changes any file `personalscraper/`, `frontend/maquette/design/src/`, `frontend/maquette/harness/`, `scripts/`, or `.github/workflows/` touches in its logic. Story: `CLAUDE.md@6a47304a4` § Commit Convention.
- A DRAFT pull request runs NO CI, since 2026-09-08 by the operator's decision. CI is read after `ready_for_review`, or on a draft by adding the `run-ci-on-draft` label; a job added to the workflow without the shared draft condition silently re-enables draft runs, and `tests/scripts/test_ci_skips_draft_pull_requests.py` refuses it. Open a pull request READY when it is ready, or add `run-ci-on-draft` and read the run that label dispatches — never both transitions in one breath (a draft-then-ready-within-seconds run reads as `skipped`, not failed, and a waiter on it waits forever). After a merge lands on `main`, an open PR behind it needs `gh pr update-branch` before its ruleset check passes. Story: `CLAUDE.md@6a47304a4` § Commit Convention.

### Pipeline Monitoring Rules

- Running `personalscraper run` or any long-running command with user observation: NEVER run in background — foreground only, `timeout=600000` (a `block_background_pipeline.py` hook enforces this); create TODO tasks (bugs, inconsistencies, improvements) BEFORE launching, updated in real-time; show output after each step, incrementally, don't wait for the end; kill on 2 identical consecutive errors — systemic failure = STOP immediately; state limitations upfront, before agreeing; after a kill, check the filesystem (orphans, lock files, temp dirs) and clean or report what can't be cleaned. Alternative: run steps individually (`personalscraper ingest`, then `personalscraper sort`, etc.) to keep control between steps. Use `-v` only for debugging a specific step (100× more output).

### Code Conventions

- **Google-style docstrings** mandatory on all modules, classes, functions, and methods (description, `Args:`, `Returns:`, `Raises:`); **inline comments** for non-trivial logic explaining the "why"; docstring/comment language: **English**.
- **No French in the code, and no interface text in the code** — see §Language below. Enforced by `python3 scripts/check-no-french.py` (in `make check` and in CI).
- New tests: choose unit / integration / manual E2E — see `docs/reference/testing.md`.
- **Renaming an identifier goes through `scripts/rename-identifiers.py`** — never by hand, never with an ad-hoc regex. The tool's read-back check is skipped for `--values` runs and for Python files, so every rename batch is verified by an oracle OUTSIDE the tool: re-read the diff, and re-run the harness rule suite. Story: `CLAUDE.md@6a47304a4` § Code Conventions.
- **A bug fix carries a regression test**, and the test is shown to FAIL against the code as it stands before the fix.
- **Names are written out in full — no abbreviations.** The rule, its blacklist, what is NOT an abbreviation, and the ratchet that freezes the existing debt: `docs/reference/code-naming.md`. It covers `personalscraper/`, `scripts/` and `frontend/maquette/`, parameters and locals included.
- **Module size**: soft warning at 800 non-blank LOC, hard ceiling 1000 LOC (exit 1). Run `python3 scripts/check-module-size.py` (also wired into `make check`).

### Phase Gate Checklist (MANDATORY before every phase gate commit)

- Every `chore(scope): phase N gate` commit MUST pass: **`make lint`** (ruff + mypy, zero errors); **`make test`** (all pass, summary line `NNNN passed` with 0 failed/errors — an ERROR, not FAILED, means test COLLECTION crashed and everything after was skipped); **`make check`** (lint + test + module-size + typed-api guardrails), EXCEPT a maquette wave's own pull request (trial, auditor order 26) where CI's `test` job is the authority instead, and the pre-PR gate is `make lint` + the harness full suite + `--a11y` + `--compare` + the pre-push pytest; a **residual import grep** — for every module deleted in this phase, grep both `personalscraper/` AND `tests/` for the old import path, zero matches; and `python -c "import personalscraper"` as a smoke test. Post-deletion and post-signature-change grep rules: `docs/reference/feature-lifecycle.md` §7.

### Implementation Workflow (feature-oriented)

- The feature lifecycle is the plugin `implement@lounisbou`'s, five skills: `/implement:feature`, `/implement:phase`, `/implement:check`, `/implement:close`, `/implement:prepare`. The pull request, its CI reading and the squash merge come after `/implement:close`, by the operator or the orchestrator. Sonnet is no longer forbidden as a dispatch target — the orchestrator routes by the class of work. Branches `feat/{codename}` / `fix/{codename}`, commits scoped with the codename, squash merge. Full flow, milestone commits and the KanbanMate claim procedure: `docs/reference/feature-lifecycle.md` §7.
- **Claim a ticket that ALREADY EXISTS on the board before coding it** — `/kanban-work <ticket>`, so the autonomous KanbanMate daemon stays out of the way. **Do NOT create a ticket for work you are about to do in this session** — the claim procedure keeps this session and the daemon off each other's cards, it is not a bookkeeping ritual.
- **A worktree is ALWAYS removed once its PR is merged.** The local branch is deleted, then `ExitWorktree` with `action: "remove"` (`discard_changes: true` for superseded pre-merge commits).

### Move Rules (dispatch)

- **Movies** (category IDs: `movies`, `movies_animation`, `movies_documentary`, `standup`, `theater`): if a folder with the same name already exists on a disk, **replace it** with the new version from the staging area.
- **TV Shows** (category IDs: `tv_shows`, `tv_shows_animation`, `tv_shows_documentary`, `anime`, `tv_programs`): if a folder already exists, **merge** new episode files into it, replacing any that already exist.
- **New media** (no existing folder on any disk): move to the **disk with the most free space**.

### Security & Paths

- **qBittorrent: NEVER enable "Bypass authentication for clients on localhost"** (nor any "trust localhost" / IP-whitelist variant). qBittorrent sits behind the reverse proxy, so Internet traffic reaches it seen as localhost — the bypass would expose the qBittorrent WebUI to the whole world, passwordless. Details: `docs/reference/qbittorrent-api.md` (Auth).
- **Never include API keys** in documentation or brainstorming files — use `.env` references only.
- Storage/staging paths may contain spaces (e.g. `/Volumes/<disk>/<staging-dir>/`) — always quote paths in shell commands.
- macOS filesystem is case-insensitive — `git mv FILE.md file.md` fails, use intermediate rename: `git mv FILE.md tmp.md && git mv tmp.md file.md`.

### Web-UI Environments (ENV-SEP) & Binding Invariants

Three checkouts share `library.db`, `.data/` and the storage disks: **dev** = `~/dev/PersonalScraper`
(feature branches, no PM2 daemons) · **prod** = `~/deploy/torrentmate` (tracks `main`, `torrentmate-web`
on 8710) · **staging** = `~/staging/torrentmate` (tracks `staging`, 8711, read-only role → 403 on
writes). Canonical config lives at `~/.torrentmate/config`, outside every working tree. Full topology
and deploy runbook: `docs/production/web-ui.md`.

- **NEVER start a local server on 8710/8711** (Caddy routes `tm.`/`tm-staging.` there) — test the frontend via `tm-staging.iznogoudatall.xyz`.

Invariants enforced by tests (do not regress; details in `docs/production/web-ui.md` + `maintenance.md`):

- Every mutating web endpoint is staging-guarded (`require_not_staging`) and typed (Pydantic `response_model` → OpenAPI → `schema.d.ts`; any route change ⇒ `make openapi` + commit the regenerated files).
- The web auth perimeter is the **single** `guarded_api` dependency (web-ui.md §6) — never add per-route `Depends(require_session)`.
- Write/destructive maintenance actions hold `pipeline.lock` for their runner's whole lifetime (maintenance.md §Pipeline lock).
- `pipeline_run` timestamps (run-level AND per-step `steps_json`) are Unix-epoch `time.time()`.
- `GET /api/version` serves the **boot-cached** BUILD_COMMIT; `scripts/deploy.sh` hard-asserts the running process serves the deployed sha.

### Language

The operator communicates in French or English — respond in French when they write in French.
Everything durable is **English only**: code comments, docstrings, maquette/harness sources, and
all engineering documentation (`docs/`, `BUGS.md`, `CHANGELOG.md`,
`IMPLEMENTATION.md`, this file). **Never mix languages within a document.**

- **Two documents stay French, by name**: `docs/reference/product-intent.md`, the constitution, and `docs/reference/operator-method.md`, his method — both dictated by the operator and amended by the operator alone. The documents describing the version in production (`docs/production/`, `README.md`) keep the language they were written in — they are frozen and die at the switchover. The rule, the three families and their fates: `docs/reference/documentation-model.md`.
- French inside an English document is allowed **only** to quote UI copy / app screens and sections named in French (in « guillemets »), media titles, or the operator verbatim. Maquette/harness comments carry no reference to a session, a phase or a dated decision — they must still read years from now, out of context.

**The code itself contains NO French, and no interface text.** Two halves of one rule,
enforced by `scripts/check-no-french.py` (fifteen arms, in `make check` and in CI):

- **English names, everywhere and always**: identifiers, function/type/**class** names (code AND CSS), **file and directory names**, and every message the tools print.
- **No UI string lives in the code.** The French a reader of the interface sees lives in the i18n resources: `frontend/maquette/design/src/i18n/fr.json` for the shell, and the same file's `server` namespace for the pages `serve.py` serves. Extract strings, never retype them.
- **`frontend/src` is EXEMPT from that rule, deliberately** — the production React app has no i18n layer, and moving its copy into resources would be work thrown away with the app that holds it. **It is a RATCHET**: `check_app_interface_text` reads that whole tree and **refuses the count going UP**, against the baseline pinned in `scripts/french-exemption-baseline.json`. Story: `CLAUDE.md@6a47304a4` § Language.
- **`data-*` attribute NAMES are code and follow the rule.** A `data-*` name is a name someone chose, so it is written in English like any other. Their VALUES are not — a page id or a stored/displayed datum is data, not a name; a NAMED STATE id (`window.__go("acq-now-idle")`) IS a name someone chose. Route paths are NOT exempt either — a route and a parameter are names, not data.
- **What is NOT French-in-the-code**, and must stay as it is: the French a harness hold ASSERTS (the app's rendered output), i18n interpolation placeholders, form field names, and the config keys the settings dictionaries are keyed by. Each such literal carries a `# french-ok: <reason>` / `// french-ok: <reason>` pragma; a pragma with no reason is itself a violation. The frozen CSS-class exceptions live in `frontend/maquette/regions.json`'s `$vocabulary`.
- **The guard asks « is this word one we use? », not « is this word French? »** `scripts/code-vocabulary.txt` holds the words this codebase's names are built from; a name built from a word nobody wrote down is refused, whatever language it comes from. Adding a word is one line, and that is the point.
- **A vocabulary SEEDED from the codebase certifies the status quo.** The dying engine's French debt (`design/src/engine/legacy.js`) lives below a banner, named as French on purpose; `check_french_debt` refuses it to every file but that one, so the debt cannot spread. **When the engine goes, that section goes with it.**
- **Every rule in this section has an ARM, or it is a sentence in a file.** Story: `CLAUDE.md@6a47304a4` § Language.

## Reference Index (lazy-load when relevant)

Load these docs on-demand based on your task — they are **not** auto-loaded:

**Three families, one rule** — `docs/reference/documentation-model.md`: a row pointing into
`docs/production/` describes the version IN PRODUCTION, frozen, dying at the switchover; a row
pointing into `docs/reference/` describes the next version or what is true whatever the version.
History is not in the tree: a path cited as `` `path@sha` `` is read with `git show sha:path`.

| When working on... | Read |
| --- | --- |
| **The documentation model — which version a document may describe, where it lives, how history is cited (BINDING)** | `docs/reference/documentation-model.md` |
| CLI commands, pipeline invocation, scheduling (PM2 crons), make targets | `docs/production/commands.md` |
| Disks, NTFS/macFUSE, rsync flags, disk space rules, move rules details | `docs/production/storage.md` |
| Directory layout, module map, shared utilities, dependencies, api/ contracts (HttpTransport, Protocols) | `docs/production/architecture.md` |
| Movie/TV folder naming, episode patterns, filename sanitization | `docs/reference/naming.md` |
| Code names — the no-abbreviation rule, its blacklist, exemptions and ratchet | `docs/reference/code-naming.md` |
| Unit tests, E2E, roundtrip, golden files, test markers, timeouts, feature map | `docs/reference/testing.md` |
| TMDB/TVDB APIs, NFO invariants, artwork, ffprobe language codes | `docs/production/scraping.md` |
| rapidfuzz, tenacity, structlog, rich, guessit gotchas | `docs/reference/libraries.md` |
| Circuit breaker, fast-skip, dispatch/verify internals, idempotence | `docs/production/pipeline-internals.md` |
| EventBus internals, event catalog, subscriber recipes, AppContext boundary rule, ContextVar pattern | `docs/production/event-bus.md` |
| Logging conventions, event-name style, structlog vs CLI vs typer channels | `docs/production/logging.md` |
| Trailer discovery, download, state, CLI, Plex-conformant placement | `docs/production/trailers.md` |
| Media indexer DB, scanner modes, query parser, outbox, cron setup, failure recovery | `docs/production/indexer.md` |
| JSON column shapes (artwork_json, payload_json, stats_json) — Pydantic models and examples | `docs/production/indexer-json-shapes.md` |
| Cross-provider IDs flow, ratings JSON, backfill mode, capability protocols | `docs/production/external-ids-flow.md` |
| Any provider or client — TMDB/TVDB/OMDB/Trakt, qBittorrent/Transmission, C411/Tr4ker + Torznab, Telegram/healthchecks | `docs/reference/<provider>-api.md` |
| Plex refresh after dispatch (X-Plex-Token, partial scan, longest-prefix section, fail-soft) | `docs/reference/plex-api.md` |
| Provider naming — `ProviderName` Enum (transport) vs `RegistryProviderName` NewType (registry) | `docs/archive/features/registry/DESIGN.md@79ccebe2` §5.3 |
| Insights layer — analytics, reporting, recommendations over the indexer DB | `docs/production/insights.md` |
| Maintenance ops — disk cleaning, targeted re-scrape repairs, web-UI action catalog + runner | `docs/production/maintenance.md` |
| ffprobe stream extraction, codec/language → Kodi NFO mapping | `docs/reference/ffprobe-api.md` |
| Config split layout, JSON5 overlay composition, per-file key ownership | `docs/production/config-overlay-layout.md` |
| Config home relocation — canonical location, migration runbook | `docs/archive/features/config-home/DESIGN.md@79ccebe2` |
| Feature lifecycle — ACCEPTANCE format, phase gates, implement:\* flow, KanbanMate claim | `docs/reference/feature-lifecycle.md` |
| Module-size budget tracking, BLOCK-threshold promise status | `docs/production/promises.md` |
| Post-merge operator checklist (DB schema, config/CLI migrations, ACC re-exercise) | `docs/production/runbook-post-merge.md` |
| TorrentMate web UI — architecture, auth, WS protocol, Redis relay, PWA, deploy runbook, REST conventions | `docs/production/web-ui.md` |
| **Product intent — the product constitution (BINDING): §1–§15 + DOIT/NE-DOIT-PAS + §méthode** | `docs/reference/product-intent.md` |
| **Maquette — the VISUAL reference of the web UI (BINDING): it is modified BEFORE the code** | `frontend/maquette/README.md` |
| **Frontend architecture — what the maquette must BECOME, and in what order (BINDING)** | `docs/reference/frontend-architecture.md` |
| The frame's model — its thirteen parts under invariant 10, the 30 mobile-application properties, the survey of what the engine still draws | `docs/reference/frame-model.md` · `docs/reference/frame-survey.md` |
| Product intent → surface map — every DOIT / NE-DOIT-PAS clause, the surface serving it, its verdict and owner (the operator amends it) | `docs/reference/product-intent-map.md` |
| Backend demands of ARCHITECTURE — the tunnel per media (§20), the requester and rights (§17), the ratio write, cross-seed — inputs of the future backend brief, unscheduled by design | `docs/reference/backend-demands-architecture.md` |
| Frontend steward — the standing audit of that plan. **NOT for the agent implementing a lot**: it is the operator's and the steward's | `docs/reference/frontend-steward.md` |

Everything a merged wave wrote is in git, not in the tree: `git log --all --oneline -- <path>`
finds the commit, `git show <sha>:<path>` reads it.

## Current Feature

Tracked in `IMPLEMENTATION.md` at the repo root — feature, branch, phases, PR and next
action. Read that file, not this section: a copy here goes stale and contradicts it.
