# Documentation Set Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a consolidated, English, GitHub-rendered documentation set for KanbanMate, organised into a user/operator track and a developer/architecture track, with the web management console recorded as a single roadmap entry.

**Architecture:** Plain markdown under `docs/` plus root `README.md` / `CONTRIBUTING.md` / `ROADMAP.md`, rendered by GitHub (no docs-site build tool). Existing scattered docs are rewritten and consolidated into a single source of truth; the `/implement:*` lifecycle artifacts are left untouched.

**Tech Stack:** Markdown (CommonMark / GitHub-flavored). No code changes. Verification uses `rg`, `git`, and reading `src/kanbanmate/`.

**Source spec:** `docs/superpowers/specs/2026-06-05-documentation-set-design.md`.

---

## Preflight (execution start, before Task 1)

- [ ] **Create the working branch.** This work should NOT land in the open genesis PR #1. From the current `feat/genesis` tip (the branch where the documented engine actually exists), create a dedicated branch:

```bash
git switch -c docs/documentation-set
```

If the operator prefers to fold the docs into genesis instead, skip this step — but the default is a dedicated branch. Confirm the choice before continuing.

## Conventions for every task

These rules apply to all tasks below; each task lists only its file, content spec, and task-specific checks.

- **Search safety (MANDATORY):** every `rg` invocation includes a glob filter (`-g '*.md'`, `-g '*.py'`). Never run unfiltered `rg`.
- **Code accuracy (MANDATORY):** before stating any CLI command, file path, config key, or default value, verify it against `src/kanbanmate/` (read the relevant module or run `--help`). Never paraphrase from memory.
- **Commit convention:** Conventional Commits, type `docs`, no codename scope. No AI attribution / `Co-Authored-By` (blocked by `hooks/block_ai_attribution.py`).
- **gitignore:** the global `~/.gitignore` ignores `docs/`, so stage doc files with `git add -f`.
- **English** for all artifacts.
- **Standard per-task step sequence** (each task instantiates these with its own content):
  1. Gather accurate source facts (read the cited code/doc; note exact commands, paths, defaults).
  2. Write the file per the content spec.
  3. Verify links resolve and references are code-accurate (task-specific commands).
  4. Commit with `git add -f <files>` + the task's commit message.

---

## File Structure

| File                          | Responsibility                                               | Replaces                               |
| ----------------------------- | ------------------------------------------------------------ | -------------------------------------- |
| `docs/index.md`               | Documentation hub: TOC + "start here" per audience           | —                                      |
| `README.md`                   | Front door: what + why + quickstart + doc map                | trim current `README.md`               |
| `CONTRIBUTING.md`             | Contribution process                                         | —                                      |
| `docs/introduction.md`        | Description + Interest + Principles                          | —                                      |
| `docs/how-it-works.md`        | Shared concepts (polling, classes, actions, heartbeats)      | rewrite current `docs/how-it-works.md` |
| `docs/guide/installation.md`  | 3-tier install + doctor                                      | `docs/install.md` (removed)            |
| `docs/guide/configuration.md` | columns.yml + global config + token + profiles + kill-switch | `docs/columns.md` (removed)            |
| `docs/guide/operating.md`     | Day-to-day operation                                         | —                                      |
| `docs/architecture.md`        | Hexagonal internals, module map, ports, patterns             | distil `DESIGN §3`                     |
| `docs/development.md`         | Dev setup, gates, tests, CI, conventions                     | —                                      |
| `ROADMAP.md`                  | Deferred items + web-console entry                           | rewrite current `ROADMAP.md`           |

---

## Phase 1 — Scaffold + front door

### Task 1: Documentation hub

**Files:**

- Create: `docs/index.md`

- [ ] **Step 1: Gather facts.** Note the final file list above (the hub links to all of them).
- [ ] **Step 2: Write `docs/index.md`.** Required content:
  - `# KanbanMate documentation` + one-sentence orientation.
  - **"Start here"** block with two entry paths:
    - _Operators_ → `introduction.md` → `guide/installation.md` → `guide/configuration.md` → `guide/operating.md`.
    - _Developers_ → `introduction.md` → `how-it-works.md` → `architecture.md` → `development.md`.
  - A **table of contents** linking every page in `docs/` plus root `README.md`, `CONTRIBUTING.md`, `ROADMAP.md` (relative links, e.g. `[Installation](guide/installation.md)`, `[Roadmap](../ROADMAP.md)`).
  - A one-line note that `docs/features/` and `docs/superpowers/` are internal lifecycle artifacts, not part of this set.
- [ ] **Step 3: Verify** every relative link target exists (the files in later tasks may not exist yet — that's fine; the final sweep in Task 12 re-checks). For now just confirm paths match the File Structure table exactly.
- [ ] **Step 4: Commit.**

```bash
git add -f docs/index.md
git commit -m "docs: add documentation hub"
```

### Task 2: README front door (rewrite)

**Files:**

- Modify: `README.md` (full rewrite)

- [ ] **Step 1: Gather facts.** Read the current `README.md` (keep the accurate quickstart). Verify each quickstart command against `src/kanbanmate/cli/` (commands: `install`, `init`, `seed`, `run`, `status`, `sessions`, `doctor`, `poll`). Confirm `pm2 start ecosystem.config.js --only kanban`.
- [ ] **Step 2: Write `README.md`.** Required structure:
  - Title + one-paragraph "what" (reusable Kanban orchestrator on GitHub Projects v2; agent-column move fires an autonomous Claude Code agent in a tmux + git-worktree workspace; single polling daemon; no webhook/n8n).
  - **Why KanbanMate** — 4-6 bullets of value: autonomy (board reacts with no open Claude session), resumability (`tmux attach` / `claude --resume`), polling idempotence (crash-safe recovery, no public endpoint/HMAC), clean per-repo isolation, human-only merge safety.
  - **Two artifacts, one repo** — keep the existing engine/plugin table.
  - **5-minute quickstart** — keep the current four-step block (verified in Step 1).
  - **Documentation** — a map table linking into the new set: `docs/index.md`, `docs/introduction.md`, `docs/guide/installation.md`, `docs/guide/configuration.md`, `docs/guide/operating.md`, `docs/how-it-works.md`, `docs/architecture.md`, `docs/development.md`, `CONTRIBUTING.md`, `ROADMAP.md`.
  - Remove deep mechanics paragraphs (they live in `how-it-works.md` now).
  - **Do NOT** link to `docs/install.md` / `docs/columns.md` (removed in Phase 3) — link the new `guide/` paths.
- [ ] **Step 3: Verify.** Run, expecting zero hits:

```bash
rg -n 'docs/install\.md|docs/columns\.md' README.md -g '*.md'
```

Expected: no matches.

- [ ] **Step 4: Commit.**

```bash
git add -f README.md
git commit -m "docs: rewrite README as documentation front door"
```

### Task 3: Contribution guide

**Files:**

- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Gather facts.** Read `CLAUDE.md` (commit convention, code conventions, phase-gate checklist) and `Makefile` (targets). Confirm `make lint` / `make test` / `make check` exist.
- [ ] **Step 2: Write `CONTRIBUTING.md`.** Required content:
  - **How to propose a change** (issue → branch → PR; small focused diffs).
  - **Commit convention** — Conventional Commits types (`feat | fix | chore | refactor | style | docs | test | perf | build | ci`); forbidden version prefixes and AI attribution; the milestone-commit format `chore(<codename>): phase N gate — …`.
  - **Branch naming** — `feat/{codename}` / `fix/{codename}`.
  - **Local quality gate** — run `make check` (ruff + mypy + tests + module-size guards) before pushing; what green means.
  - **Merge policy** — **merge is human-only**; agents/PRs never `gh pr merge`, never `git push --force`.
  - **Larger features** — pointer to the `/implement:*` lifecycle (one line).
  - **Environment setup** — pointer to `docs/development.md` (do not duplicate it here).
- [ ] **Step 3: Verify** the three make targets named actually exist:

```bash
rg -n '^(lint|test|check):' Makefile
```

Expected: all three present.

- [ ] **Step 4: Commit.**

```bash
git add -f CONTRIBUTING.md
git commit -m "docs: add contribution guide"
```

---

## Phase 2 — Shared concepts

### Task 4: Introduction (Description + Interest + Principles)

**Files:**

- Create: `docs/introduction.md`

- [ ] **Step 1: Gather facts.** Read `docs/features/genesis/DESIGN.md` §1–§3 and §10 for the description, motivation, and principles. Do not copy verbatim — distil into public-facing prose.
- [ ] **Step 2: Write `docs/introduction.md`.** Three sections:
  - **What it is** — orchestrator on GitHub Projects v2; ticket = roadmap item; column-by-column flow; agent-column move fires an autonomous agent; single polling daemon; the repo is its own Claude plugin marketplace; two artifacts (engine + plugin).
  - **Why / use-cases** — the problem it solves (autonomous, board-driven dev), who it's for (multi-repo solo/operator use), why polling over webhooks (no public endpoint, no HMAC, no n8n; idempotent recovery), the value of resumable agents and per-repo isolation.
  - **Principles** — bullet list: (1) polling + diff-against-persisted-state idempotence; (2) hexagonal / functional-core / imperative-shell, downward-only imports; (3) generic engine vs per-repo `columns.yml`; (4) autonomy with **human-only merge**; (5) non-root operation; (6) kill-switch + unattended-hours; (7) two-artifact model.
  - Footer: "See also" → `how-it-works.md`, `architecture.md`.
- [ ] **Step 3: Verify** links resolve (`how-it-works.md`, `architecture.md` are same-dir relative).
- [ ] **Step 4: Commit.**

```bash
git add -f docs/introduction.md
git commit -m "docs: add introduction (description, value, principles)"
```

### Task 5: How it works (consolidate)

**Files:**

- Modify: `docs/how-it-works.md` (rewrite in place)

- [ ] **Step 1: Gather facts.** Read the current `docs/how-it-works.md` and `DESIGN §3.1`, §5, §8.2, §8.3. Verify the heartbeat TTL default (`1800` s) and poll interval default (`10` s) against `src/kanbanmate/` (search `core/interval.py`, and the reaper/heartbeat constants):

```bash
rg -n 'HEARTBEAT_TTL|1800|interval' src/kanbanmate -g '*.py'
```

- [ ] **Step 2: Write `docs/how-it-works.md`.** Keep/refine these sections (already present, verify accuracy):
  - The polling loop diagram + the 8 tick steps (cheap_probe → snapshot → diff → decide → execute → reap → drain → heartbeat).
  - The three **column classes** table (agent / reactive / inert).
  - The four **action kinds** table (Launch / Teardown / Reset / Block).
  - The **two heartbeats** (agent PostToolUse hook vs daemon per-tick) — keep the distinction explicit.
  - Kill-switch (`~/.kanban/PAUSE`), adaptive poll interval, resumability.
  - Fix any link that points to `../ROADMAP.md` (still valid).
- [ ] **Step 3: Verify** internal command/path references:

```bash
rg -n 'tmux attach|claude --resume|~/.kanban/PAUSE' docs/how-it-works.md -g '*.md'
```

Expected: present and correct.

- [ ] **Step 4: Commit.**

```bash
git add -f docs/how-it-works.md
git commit -m "docs: consolidate how-it-works concepts"
```

---

## Phase 3 — User / Operator track

### Task 6: Installation guide (consolidate, retire install.md)

**Files:**

- Create: `docs/guide/installation.md`
- Remove: `docs/install.md`

- [ ] **Step 1: Gather facts.** Read `docs/install.md` and `DESIGN §4`. Verify the `kanban doctor` check set and the install flags against `src/kanbanmate/cli/install.py` and `cli/doctor.py` (e.g. `--no-pm2`, `--kanban-command`).
- [ ] **Step 2: Write `docs/guide/installation.md`.** Required content (carry over from `install.md`, verified):
  - The three idempotent tiers (host / Claude plugin / per-repo).
  - PM2 supervision commands; non-root requirement; `--no-pm2` and `--kanban-command <abs>` flags.
  - Claude plugin tier (`claude plugin marketplace add` / `install`).
  - Token scope (`project` + `repo`, not `admin:org_hook`).
  - `kanban init --repo` and `kanban seed ROADMAP.md` (with `--project-id`).
  - Uninstall / reset.
  - The `kanban doctor` health-check table.
- [ ] **Step 3: Remove the old file and verify no dangling links remain:**

```bash
git rm docs/install.md
rg -n 'docs/install\.md|\(install\.md\)|\.\./install\.md' -g '*.md'
```

Expected: zero matches (README already points to the new path; fix any stragglers).

- [ ] **Step 4: Commit.**

```bash
git add -f docs/guide/installation.md
git commit -m "docs: move install guide under guide/ and consolidate"
```

### Task 7: Configuration guide (consolidate, retire columns.md)

**Files:**

- Create: `docs/guide/configuration.md`
- Remove: `docs/columns.md`

- [ ] **Step 1: Gather facts.** Read `docs/columns.md`, `DESIGN §8`/§9, and verify: column-class resolution in `src/kanbanmate/core/columns.py`; the agent-column fields and permission profiles in the assets template and `adapters/perms.py`; the global config knobs (poll interval, unattended-hours, `HEARTBEAT_TTL`) wherever the daemon reads config.

```bash
rg -n 'triggers_agent|permission_profile|interactive_only|teardown|defaultMode|auto|trusted|safe' src/kanbanmate -g '*.py'
```

- [ ] **Step 2: Write `docs/guide/configuration.md`.** Required content:
  - **`columns.yml` reference** — `key`/`name`, the three column classes and how `load_columns()` resolves them, the agent-column extra fields (`prompt`, `permission_profile`, `interactive_only`).
  - **Default 11-column template** table + the flow diagram (carry over from `columns.md`).
  - **Permission profiles** — `safe` vs `trusted`; the pinned `defaultMode: auto` (headless-safe); both ban `gh pr merge` / `git push --force` / history rewrite.
  - **Global config** (`~/.kanban/config.yml`) — poll interval (default 10 s), adaptive back-off, unattended-hours, `HEARTBEAT_TTL` (default 1800 s).
  - **Token file** (`~/.kanban/token`, mode 600).
  - **Kill-switch** (`~/.kanban/PAUSE`).
  - **Customising columns** + config hot-reload (mtime-based, top of a tick).
- [ ] **Step 3: Remove the old file and verify:**

```bash
git rm docs/columns.md
rg -n 'docs/columns\.md|\(columns\.md\)|\.\./columns\.md' -g '*.md'
```

Expected: zero matches.

- [ ] **Step 4: Commit.**

```bash
git add -f docs/guide/configuration.md
git commit -m "docs: consolidate configuration reference under guide/"
```

### Task 8: Operating guide

**Files:**

- Create: `docs/guide/operating.md`

- [ ] **Step 1: Gather facts.** Enumerate the operator-facing CLI commands and verify each exists:

```bash
rg -n 'def (status|sessions|logs|cancel|reset|run|poll)\b|app\.command' src/kanbanmate/cli -g '*.py'
```

Also confirm the `~/.kanban/` runtime layout members (token, PAUSE, config.yml, projects.json, daemon.lock, log/, state/).

- [ ] **Step 2: Write `docs/guide/operating.md`.** Required content:
  - **Running the daemon** — `kanban run` (foreground) vs PM2 (`pm2 start ecosystem.config.js --only kanban`, `pm2 logs/restart kanban`).
  - **Observing** — `kanban status`, `kanban sessions`, `kanban logs`, `kanban doctor`.
  - **Intervening** — `kanban cancel <issue>`, attach/resume (`tmux attach -t ticket-<n>`, `claude --resume <uuid>`), `kanban poll --once` (debug single tick).
  - **Kill-switch** — create/remove `~/.kanban/PAUSE`; unattended-hours.
  - **Upgrade** — `pm2 restart kanban`; **uninstall/reset** — `kanban uninstall`, `kanban reset`.
  - **Runtime layout** — a short table of `~/.kanban/` members and what each holds.
  - Footer: "See also" → `installation.md`, `configuration.md`, `how-it-works.md`.
- [ ] **Step 3: Verify** every command named maps to a real CLI module (re-run the Step 1 grep; each `status/sessions/logs/cancel/reset/run/poll` must appear).
- [ ] **Step 4: Commit.**

```bash
git add -f docs/guide/operating.md
git commit -m "docs: add operating guide"
```

---

## Phase 4 — Developer / Architecture track

### Task 9: Architecture

**Files:**

- Create: `docs/architecture.md`

- [ ] **Step 1: Gather facts.** Read `DESIGN §3.2`/§3.3 and confirm the actual module layout:

```bash
rg --files src/kanbanmate -g '*.py'
```

Cross-check the module map (core/ports/adapters/app/daemon/cli/bin) against the real files.

- [ ] **Step 2: Write `docs/architecture.md`.** Required content:
  - **Hexagonal layering** + the downward-only import rule (+ the layering guard).
  - **Module map** — list `core/` (domain, diff, decide, columns, antiloop, dependency_gate, interval, stage_comment), `ports/` (board, store, workspace, clock), `adapters/` (github urllib, workspace tmux/git, store fs, perms), `app/` (tick, actions, wiring, stage_signal), `daemon/` (loop, jsonl_log), `cli/`, `bin/`. Verify each name against Step 1 output.
  - **Data flow** — the `tick` pipeline as the imperative shell calling pure core + ports.
  - **Design patterns** — command (actions), strategy (interval), functional-core/imperative-shell, Protocols as injectable seams.
  - **Ports catalogue** — short table: BoardReader/Writer, Seeder, Workspace, Sessions, StateStore, Clock.
  - **Agent helper bins** — `kanban-comment`, `kanban-move`, `kanban-heartbeat`, `kanban-progress`, `kanban-session-end`, `kanban-update-main`.
  - Footer: "See also" → `development.md`, `how-it-works.md`.
- [ ] **Step 3: Verify** every module named exists:

```bash
rg -n 'diff|decide|antiloop|dependency_gate|interval|stage_comment' --files-with-matches src/kanbanmate/core -g '*.py'
```

Expected: the core modules resolve.

- [ ] **Step 4: Commit.**

```bash
git add -f docs/architecture.md
git commit -m "docs: add architecture guide"
```

### Task 10: Development

**Files:**

- Create: `docs/development.md`

- [ ] **Step 1: Gather facts.** Read `pyproject.toml` (deps, `requires-python = ">=3.12"`, scripts, markers), `Makefile`, and `CLAUDE.md` (module-size guards, layering guard, testing). Confirm pytest markers `local_real` and `integration`.
- [ ] **Step 2: Write `docs/development.md`.** Required content:
  - **Setup** — `pip install -e ".[dev]"`; pyenv 3.12 (`.python-version` = 3.12.4).
  - **Quality gate** — `make lint` (ruff + mypy strict), `make test`, `make check` (adds module-size guards).
  - **Layering guard** — downward-only imports enforced.
  - **Module size** — soft warning ~800 LOC, hard ceiling 1000 LOC.
  - **Testing strategy** — three levels: unit (offline, pure `core/`), local-real (`local_real` marker; real tmux + git, `claude`=`echo`), integration (`integration` marker; real GitHub Projects v2, gated on a CI secret). How to run each.
  - **CI split** — PR = unit + local-real + `claude plugin validate` ; nightly = integration.
  - **Conventions** — Google-style docstrings (Args/Returns/Raises), why-comments in English, downward-only imports.
  - Footer: "See also" → `architecture.md`, `../CONTRIBUTING.md`.
- [ ] **Step 3: Verify** the claimed facts:

```bash
rg -n 'requires-python|local_real|integration|target-version' pyproject.toml
```

Expected: `>=3.12`, both markers, `py312`.

- [ ] **Step 4: Commit.**

```bash
git add -f docs/development.md
git commit -m "docs: add development guide"
```

---

## Phase 5 — Roadmap + cross-link / accuracy sweep

### Task 11: Roadmap rewrite + web-console entry

**Files:**

- Modify: `ROADMAP.md` (rewrite)

- [ ] **Step 1: Gather facts.** Read the current `ROADMAP.md` (keep all existing deferred items) and the web-console entry text from the spec §8.
- [ ] **Step 2: Write `ROADMAP.md`.** Required content:
  - Keep existing deferred items: optional webhook ingress adapter (`kanban serve`), GitHub App upgrade, multi-org, MCP helpers, auto-merge (permanently forbidden).
  - **Add a new section "Web management console (`kanban web`)"** with the concise high-level entry from spec §8: optional opt-in console bundled with the engine; control & observability plane, not a board replacement; reuses `core`/`ports` + reads `~/.kanban`; scope sketch (daemon/server status + per-project workflow viz; connected-projects registry from `projects.json`; global `config.yml` editing + per-project `columns.yml` editing for prompts/transition-classes/workflow, hot-reloaded; read+write controls pause/resume/cancel/restart but **never merge**); name kept distinct from the deferred `kanban serve` webhook adapter; stack/auth deferred to the feature's own design.
- [ ] **Step 3: Verify** the two `kanban serve` vs `kanban web` names are both present and not conflated:

```bash
rg -n 'kanban serve|kanban web' ROADMAP.md -g '*.md'
```

Expected: both appear, in different sections.

- [ ] **Step 4: Commit.**

```bash
git add -f ROADMAP.md
git commit -m "docs: rewrite roadmap and add web-console entry"
```

### Task 12: Cross-link + accuracy sweep (final gate)

**Files:**

- Modify: any doc needing a "See also" footer or link fix (touch only what's needed).

- [ ] **Step 1: Dangling-reference check.** No references to removed files anywhere:

```bash
rg -n 'install\.md|columns\.md' -g '*.md' | rg -v 'guide/installation\.md|guide/configuration\.md'
```

Expected: zero lines. Fix any hit by repointing to the `guide/` path.

- [ ] **Step 2: Link-resolution check.** Extract every relative markdown link in the new docs and confirm each target file exists. For each link `](path)`, verify `path` resolves from its file's directory. List of files to check: `README.md`, `CONTRIBUTING.md`, `ROADMAP.md`, `docs/index.md`, `docs/introduction.md`, `docs/how-it-works.md`, `docs/guide/*.md`, `docs/architecture.md`, `docs/development.md`. Fix any broken target.
- [ ] **Step 3: Code-accuracy spot-check.** Confirm every CLI command named across the docs maps to a real command:

```bash
rg -oN 'kanban [a-z-]+' -g '*.md' README.md CONTRIBUTING.md ROADMAP.md docs | sort -u
```

Cross-check each against `src/kanbanmate/cli/` and the `pyproject.toml` `[project.scripts]` (`kanban`, `kanban-comment`, `kanban-heartbeat`, `kanban-move`, `kanban-progress`, `kanban-session-end`, `kanban-update-main`). Flag any command that does not exist.

- [ ] **Step 4: "See also" footers.** Ensure each track page links its siblings and back to `docs/index.md` (add where missing). Keep edits minimal.
- [ ] **Step 5: Commit.**

```bash
git add -f README.md CONTRIBUTING.md ROADMAP.md docs
git commit -m "docs: cross-link pass and reference accuracy sweep"
```

---

## Self-Review (completed during authoring)

**1. Spec coverage:** every spec volet maps to a task — Description/Interest/Principles → Task 4; Architecture → Task 9; Development → Task 10; Contributions → Task 3; Installations → Task 6; Roadmap/web → Task 11; consolidation of how-it-works/columns/install → Tasks 5/7/6; hub + README → Tasks 1/2; configuration + operating → Tasks 7/8. The two-track split (spec §3) is realised by `guide/` (Tasks 6-8) vs `architecture.md`/`development.md` (Tasks 9-10). The "leave lifecycle artifacts untouched" rule (spec §9) is honoured — no task edits `docs/features/` or `IMPLEMENTATION.md`.

**2. Placeholder scan:** no "TBD/TODO/handle edge cases" — each task lists concrete sections, exact facts (defaults: poll 10 s, TTL 1800 s; flags: `--no-pm2`, `--kanban-command`; markers: `local_real`, `integration`), and exact verification commands.

**3. Consistency:** file paths are identical across the File Structure table, the per-task headers, and the verification greps. Removed files (`docs/install.md`, `docs/columns.md`) are git-rm'd in the same task that creates their replacement, and Task 12 re-verifies no dangling references survive.
