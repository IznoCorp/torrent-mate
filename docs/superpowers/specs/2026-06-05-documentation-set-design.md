# KanbanMate — Documentation Set — Design Spec

> **Status**: brainstormed & approved (2026-06-05), pending spec review.
> **Topic**: build a consolidated, English, GitHub-rendered documentation set for KanbanMate.
> **Deliverable**: markdown docs only — no engine code changes.

## 1. Purpose & motivation

KanbanMate has good content scattered across `README.md`, `docs/how-it-works.md`,
`docs/install.md`, `docs/columns.md`, and `ROADMAP.md`, plus a deep feature spec under
`docs/features/genesis/DESIGN.md`. The content is **internally oriented** (organised around the
genesis feature) rather than presented as a coherent, public-facing documentation set.

This effort **consolidates and rewrites** that content into a single source of truth, organised for
two clearly separated audiences, and adds the missing top-level material the project needs to read
as a properly documented open-source project: a description/value/principles introduction, a
contribution guide, and a roadmap that records the future **web management console** as one entry.

**No engine behaviour changes.** This is documentation only.

## 2. Decisions of record

Captured from the brainstorm (2026-06-05):

| Decision                                     | Choice                                                                               |
| -------------------------------------------- | ------------------------------------------------------------------------------------ |
| Output form                                  | `docs/` markdown + refreshed `README` (GitHub-rendered; no docs-site build tool)     |
| Existing docs                                | **Consolidate / rewrite** into the new set — one source of truth                     |
| Web interface depth                          | **High-level roadmap entry** only; full design deferred to its own feature           |
| Audience                                     | **Two separated tracks**: user/operator vs developer/architecture                    |
| Web console role (for the roadmap entry)     | Central **management console** (read + write control plane), not a board replacement |
| Web console delivery (for the roadmap entry) | Optional component of the engine (`kanban web`), reusing `core`/`ports`              |
| Language                                     | English for all doc artifacts                                                        |

## 3. Audience & tracks

- **User / Operator track** — people who install, configure, and operate KanbanMate against their
  own repos. They want: install, configure (columns/profiles/global), and day-to-day operation.
- **Developer / Architecture track** — people who want to understand the internals or contribute to
  the engine. They want: architecture, development workflow, tooling, tests, conventions.
- **Shared conceptual layer** — "what it is / why" and "how it works" are linked from both tracks.

## 4. Output form & conventions

- Plain markdown under `docs/` (+ root `README.md`, `CONTRIBUTING.md`, `ROADMAP.md`), rendered
  directly by GitHub. No MkDocs/Docusaurus build dependency.
- **English** throughout (project rule: doc artifacts in English).
- Every doc cross-links its siblings (a small "See also" footer where useful) and links back to the
  hub (`docs/index.md`).
- Content must be **code-accurate**: CLI commands, file paths, config keys, and defaults are verified
  against `src/kanbanmate/` at writing time, not paraphrased from memory.
- Diagrams reuse the existing ASCII style (the polling-loop diagram in `how-it-works.md` /
  `DESIGN §3.1` is the reference aesthetic).
- Mind the global `~/.gitignore` rules: `docs/` and `CLAUDE.md` are ignored — use `git add -f` for
  files under `docs/`.

## 5. Information architecture (target tree)

```
README.md                      # front door: what + why/value + 5-min quickstart + doc map
CONTRIBUTING.md                # contribution process (GitHub-surfaced)
ROADMAP.md                     # deferred items + the web-console roadmap entry
docs/
  index.md                     # documentation hub: TOC, "start here", links to both tracks
  introduction.md              # Description + Interest/use-cases + Principles
  how-it-works.md              # shared concepts: polling tick, column classes, action model,
                               #   the two heartbeats, kill-switch, adaptive interval, resumability
  guide/                       # ── USER / OPERATOR TRACK ──
    installation.md            #   3-tier install + kanban doctor
    configuration.md           #   columns.yml + global config.yml + token + permission profiles
                               #   + kill-switch / unattended-hours
    operating.md               #   run/PM2, status, sessions, logs, cancel, resume, upgrade, uninstall
  architecture.md              # ── DEVELOPER / ARCHITECTURE TRACK ──
                               #   hexagonal layering, module map, data flow (tick), patterns, ports
  development.md               #   dev setup, make targets, layering guard, module-size guards,
                               #   test strategy (unit / local-real / integration), CI, conventions
```

11 files total. `CONTRIBUTING.md` covers **process** (Conventional Commits, PR flow, merge=human,
`/implement:*` lifecycle pointer) and defers the **technical** setup to `docs/development.md`.
`how-it-works.md` is shared and linked from both tracks.

**Approach rationale**: two-track sub-grouping (`guide/` + dev-track files) over a flat `docs/`,
because the user explicitly asked for separated audiences and the tree should make that split
visible. A flat layout was considered and rejected (simpler, but blurs the two tracks).

## 6. Per-file content specification

### `README.md` (rewrite)

One-paragraph "what", a short **Why KanbanMate** value block (autonomy + resumability + no
webhook/n8n), the 5-minute quickstart (kept from today), and a **documentation map** table linking
into `docs/`. Trimmed of deep mechanics (those move into `how-it-works.md`).

### `CONTRIBUTING.md` (new)

How to propose changes; Conventional Commits (types, forbidden version prefixes + AI attribution,
the milestone-commit convention); branch naming (`feat/{codename}` · `fix/{codename}`); the
local quality gate (`make check`); **merge is human-only**; a pointer to `docs/development.md` for
environment setup and to the `/implement:*` lifecycle for larger features.

### `ROADMAP.md` (rewrite)

Keeps the existing deferred items (optional webhook ingress adapter, GitHub App upgrade, multi-org,
MCP helpers, auto-merge=forbidden) and **adds the web-console entry** (§8). Style matches the
current bullet/section format.

### `docs/index.md` (new)

The hub: a short orientation, a "Start here" path for each audience, and a linked table of contents
for every page.

### `docs/introduction.md` (new — volets Description + Interest + Principles)

- **Description**: reusable Kanban orchestrator on GitHub Projects v2; ticket = roadmap item moved
  column by column; agent-column move fires an autonomous Claude Code agent in a tmux + git-worktree
  workspace; single polling daemon; the repo is its own Claude plugin marketplace.
- **Interest / use-cases**: who it's for, what problem it solves, why polling beats webhooks here
  (no public endpoint, no HMAC, no n8n; idempotent recovery), the value of resumable autonomous
  agents and clean per-repo isolation.
- **Principles**: polling + diff-against-persisted-state idempotence; hexagonal / functional-core
  / imperative-shell with downward-only imports; generic engine vs per-repo `columns.yml`;
  autonomy with **human-only merge**; non-root operation; kill-switch & unattended-hours;
  two-artifact model (engine + plugin).

### `docs/how-it-works.md` (consolidate from existing)

The polling loop (`tick`: cheap_probe → snapshot → diff → decide → execute → reap → drain →
heartbeat), the three column classes, the four action kinds, the **two distinct heartbeats** (agent
PostToolUse hook vs daemon per-tick), the kill-switch, adaptive poll interval, and resumability.
Reconciled with the diagram from `DESIGN §3.1`.

### `docs/guide/installation.md` (consolidate from `install.md`)

The three idempotent tiers (host / Claude plugin / per-repo), PM2 supervision, non-root requirement,
token scope, `kanban init` + `kanban seed`, uninstall/reset, and the `kanban doctor` check table.

### `docs/guide/configuration.md` (consolidate from `columns.md` + scattered)

`columns.yml` reference (keys/names, the three column classes, agent-column extra fields: `prompt`,
`permission_profile`, `interactive_only`), the **default 11-column template** + flow diagram, the
global `~/.kanban/config.yml` knobs (poll interval, adaptive back-off, unattended-hours,
`HEARTBEAT_TTL`), the token file, permission profiles (`safe`/`trusted`) and the pinned
`defaultMode` (`auto`, headless-safe), and the kill-switch (`~/.kanban/PAUSE`). Customisation flow.

### `docs/guide/operating.md` (new — assembled from scattered ops content)

Day-to-day: starting the daemon (`kanban run` foreground vs PM2), `status`, `sessions`,
`logs`, `cancel`, attach/resume (`tmux attach` / `claude --resume`), kill-switch usage, config
hot-reload, upgrade (`pm2 restart`), and uninstall. The `~/.kanban/` runtime layout
(`token`, `PAUSE`, `config.yml`, `projects.json`, `daemon.lock`, `log/`, `state/`).

### `docs/architecture.md` (new — volet Architecture)

Hexagonal layering and downward-only import rule; the full module map
(`core` · `ports` · `adapters` · `app` · `daemon` · `cli` · `bin`); the data flow through `tick`;
design patterns (command = actions, strategy = interval, functional-core/imperative-shell); the
ports catalogue (BoardReader/Writer, Seeder, Workspace, Sessions, StateStore, Clock); the agent
helper bins. Grounded in `DESIGN §3`.

### `docs/development.md` (new — volet Development)

Setup (`pip install -e ".[dev]"`, pyenv 3.12); `make lint` / `make test` / `make check`; the
layering guard and module-size guards (soft ~800 / hard 1000 LOC); the three test levels
(unit offline · local-real with real tmux+git · integration against a test org/Project, with the
`local_real` / `integration` markers); CI split (PR = L1+L2+plugin validate; nightly = L3); code
conventions (Google-style docstrings, why-comments, English).

## 7. Consolidation mapping (existing → new)

| Existing source                                          | Destination                                         |
| -------------------------------------------------------- | --------------------------------------------------- |
| `README.md` (deep mechanics)                             | trimmed; mechanics → `docs/how-it-works.md`         |
| `docs/how-it-works.md`                                   | `docs/how-it-works.md` (rewritten/expanded)         |
| `docs/install.md`                                        | `docs/guide/installation.md`                        |
| `docs/columns.md`                                        | `docs/guide/configuration.md`                       |
| `ROADMAP.md`                                             | `ROADMAP.md` (rewritten + web entry)                |
| scattered ops notes (status/sessions/logs/cancel/resume) | `docs/guide/operating.md`                           |
| `DESIGN §3` (architecture)                               | `docs/architecture.md` (public-facing distillation) |

The old `docs/install.md`, `docs/columns.md`, and `docs/how-it-works.md` (current flat versions) are
**replaced** by their new homes; no stale duplicate is left behind. `README.md` and `ROADMAP.md` are
rewritten in place.

## 8. Web management console — roadmap entry (concise)

Recorded in `ROADMAP.md` as a single forward-looking item; **full design is deferred to its own
feature**. Entry text (high-level):

> **Web management console (`kanban web`)** — an optional, opt-in web console bundled with the
> engine: a control & observability plane for the orchestrator, **not** a replacement for the
> GitHub Projects board. It would reuse the same `core`/`ports` and read the same `~/.kanban` store.
> Scope sketch: daemon/server status + per-project workflow visualization; a connected-projects
> registry (today `projects.json`) with connect/disconnect and drill-in; global config editing
> (`config.yml`) and per-project config editing (`columns.yml` — prompts, transition classes,
> workflow), hot-reloaded by the daemon; read+write controls (pause/resume, cancel, restart) — but
> **never merge** (human-only). Delivered as `kanban web`, a name kept distinct from the deferred
> `kanban serve` webhook adapter. Stack and auth model are left to the feature's own design.

## 9. Out of scope

- No docs-site tooling (MkDocs/Docusaurus), no GitHub Pages workflow.
- No engine code changes; no new CLI commands actually implemented (`kanban web` stays roadmap text).
- The `/implement:*` lifecycle artifacts (`docs/features/genesis/DESIGN.md`,
  `docs/superpowers/specs/*`, `IMPLEMENTATION.md`) are **left untouched** — they are working
  artifacts of the in-flight genesis feature, not part of the public set.
- No detailed web-console design (deferred to its own feature/brainstorm).

## 10. Execution-time decisions

- **Branch strategy**: recommend a dedicated branch (e.g. `docs/documentation-set`) so this work does
  not bloat the still-open genesis PR #1 (whose phase-11 operator cutover is pending). Folding into
  genesis is possible but discouraged. Final call at execution start.

## 11. Implementation phasing (hint for writing-plans)

1. **Scaffold + front door** — `docs/index.md`, rewrite `README.md`, `CONTRIBUTING.md`.
2. **Shared concepts** — `docs/introduction.md`, `docs/how-it-works.md`.
3. **User/operator track** — `docs/guide/installation.md`, `configuration.md`, `operating.md`
   (consolidating + retiring the old flat files).
4. **Developer track** — `docs/architecture.md`, `docs/development.md`.
5. **Roadmap + cross-linking pass** — rewrite `ROADMAP.md` (web entry), add See-also footers, verify
   every link resolves and every CLI/command/config reference is code-accurate.
