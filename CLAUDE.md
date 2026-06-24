# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

**KanbanMate** is a reusable Kanban orchestrator on **GitHub Projects v2**. Each roadmap item is a
**ticket** moved column by column on a board; moving a card into a triggering column fires an
autonomous **Claude Code agent** in an isolated **tmux + git-worktree** workspace. The agent
comments on the ticket, may re-move the card (only to non-triggering columns), and its session is
**resumable** (`tmux attach` / `claude --resume <uuid>`).

The board runs **native one-way** (codename _keel_): placement authority is a per-project local
`board.json`, GitHub Status is a **one-way mirror**, and operators work primarily through
KanbanMateUI. A single background daemon (`kanban run`, PM2-supervised) reconciles the board each
tick; a `.nudge` sentinel wakes it &lt;1s on an operator action. Secondary GitHub-side drags are
ingested by a **webhook receiver** (`kanban serve`) — there is **no n8n**. (The legacy
GitHub-primary polling / hybrid bidirectional model is retired; see `docs/how-it-works.md`.)

Package name: `kanbanmate`. CLI entry point: `kanban <command>`. Runtime state lives outside the
repo — in production `~/.kanban-km/` (the multi-project root; `~/.kanban/` is the legacy
single-project default).

The web SPA in `web/` (config builder + monitoring tab, served by `kanban config serve`, built into
`src/kanbanmate/webui/`) is called **KanbanMateUI**. In production it is the PM2 app
`kanban-km-config` (loopback `127.0.0.1:8796`), fronted by Caddy at `https://km.iznogoudatall.xyz`.

This repo is also its own **Claude plugin marketplace** (`.claude-plugin/marketplace.json`): the
`/kanban` skill is a thin wrapper that shells out to the `kanban` CLI. All logic lives in the engine.

## Current State

On **`main` at v0.21.1**, fully **native one-way** (codename _keel_): KanbanMateUI is the primary
surface, per-project `board.json` is the placement authority, GitHub Status is a **one-way mirror**,
secondary GitHub-side drags are ingested via the webhook receiver, and monitoring reads local state
(sub-second via SSE). The **skiff** fast-track routes every ticket through a Triage classifier into
one of three lanes — **full** (Brainstorming→Spec→Plan→Ready-to-dev human gate→…), **lite** (Scope→…,
no pre-build gate), **express** (straight to build). **Merge is human-only on every lane.**

**Read the docs** (refreshed + grounded in code): [`docs/how-it-works.md`](docs/how-it-works.md)
(native one-way runtime), [`docs/lanes.md`](docs/lanes.md) (skiff lanes + Triage + gates),
[`docs/configuration.md`](docs/configuration.md) (registry / columns / transitions / sensitive /
profiles / cadence), [`docs/kanbanmateui.md`](docs/kanbanmateui.md) (the SPA).

> Shipped + merged to `main`: genesis (0.0.0→0.1.0, PR #1, archived), cockpit (PR #2), helm, tiller,
> conduit, ingress-multiproject, anchor (native repatriation), **skiff** (3-lane fast-track),
> **keel** (native one-way migration through step 5.5), tug (sub-second operator-action latency),
> lucid (self-documenting tooltips), ensign (closed-issue indicator).
> **keel step 6 — retire the hybrid bidirectional-reconcile code — is ticket #112 (_jettison_)**,
> resting in Ready to dev pending a soak.

## Architecture (at a glance)

Hexagonal (ports & adapters), functional-core / imperative-shell. Import direction is **downward only**:

```
cli/ · daemon/  ──▶  app/ (tick, actions, wiring)  ──▶  core/ (pure: domain, diff, decide, …)
                                                     └─▶  ports/ (Protocols)
                                                          ▲
                                            adapters/ ────┘  (github urllib · workspace tmux/git · store fs)
```

The unified poll loop (`tick`): `cheap_probe → snapshot → diff(persisted, snapshot) → decide →
LaunchAction | TeardownAction | ResetAction | BlockAction`, then reap stale agents + drain queue +
heartbeat. See DESIGN §3 for the full module map.

## Critical Rules

### Search Safety (MANDATORY)

Every `rg` command MUST include a type/glob filter (`--type py`, `-g '*.py'`, etc.). Unfiltered `rg`
can scan large binary fixtures and exhaust RAM.

### Network Timeout Safety (MANDATORY)

Every network command (curl/wget) MUST include `--connect-timeout N` and `--max-time N`. The urllib
GitHub client MUST set connect + read timeouts on every request — the daemon must never hang on I/O.

### Commit Convention

[Conventional Commits](https://www.conventionalcommits.org/) — globally enforced.

```
<type>[(<scope>)]: <description>
```

Types: `feat | fix | chore | refactor | style | docs | test | perf | build | ci`

**Forbidden**: version prefixes (`vX.Y.Z: …`); AI attribution (`Co-Authored-By`, `Claude`,
`Anthropic`) — enforced by `hooks/block_ai_attribution.py`.

**Milestone commits** (used by `/implement:phase`) carry the codename as scope:
`chore(genesis): phase 1 gate — bootstrap engine + polling core`.

### Code Conventions

- **Google-style docstrings** on all modules, classes, functions, methods (`Args:`/`Returns:`/`Raises:`).
- Inline comments explain the **why**, in English.
- New code respects the hexagonal layering: `core/` imports nothing with I/O; `adapters/` implement
  `ports/` Protocols; the layering guard enforces downward-only imports.
- Module size: soft warning ~800 LOC, hard ceiling 1000 LOC.

### Autonomy & Safety (orchestrated agents)

- **Merge = human only.** Agents push + open PRs but NEVER merge. Ban `gh pr merge`, `git push
--force`, history rewrite across all permission profiles.
- Permission profiles (`docs` / `prepare` / `dev` / `check`) are materialised into each worktree's
  `.claude/settings.json` with a pinned `defaultMode`, plus the PostToolUse heartbeat hook. `docs`
  is the minimal floor (an unknown profile name degrades to it); the `merge` profile is gone
  (merge = human-only).
- Kill-switch `~/.kanban/PAUSE` downgrades all to the `docs` floor and stops launches.
- The daemon and agents run **non-root** (tmux socket ownership; `bypassPermissions` refuses under root).

### Phase Gate Checklist (before every `chore(genesis): phase N gate`)

1. `make lint` (ruff + mypy) — zero errors.
2. `make test` — all pass (check the summary line; any ERROR = collection crash, fix imports first).
3. `make check` — lint + test + module-size guards.
4. Residual-import grep for any deleted module, in `src/` AND `tests/` — zero matches.
5. `python -c "import kanbanmate"` smoke test.
6. Tracker row updated + DESIGN delta present (a phase that changed behaviour must not close without
   the matching `IMPLEMENTATION.md` row and a `DESIGN.md` edit — phases 25/27/28 all drifted).

### Implementation Workflow

Feature lifecycle via `/implement:*` skills (brainstorm → create-branch → plan → phase → feature-pr →
pr-review). Branch `feat/{codename}`, commits scoped `(codename)`, squash merge (mode chosen at start).

### Language

User communicates in French or English. Code comments and report/doc artifacts in **English**.
Respond in French when the user writes in French.

## Setup (per clone)

```bash
pip install -e ".[dev]"   # once the package exists (phase 1)
```

The portable Claude config lives in `.claude/` (its own git repo, gitignored by this repo).

## Deployment, Staging & CD

**Only `main` is ever served in prod.** The `webui/` SPA build is gitignored, so a manual
`npm run build` from a dirty/non-main tree once silently deployed — then lost — uncommitted UI work.
Guardrails make that impossible. Three SSH clones of this repo:

- `~/dev/KanbanMate` — **development** (branches, worktrees). PM2 NEVER serves from here.
- `~/deploy/kanban-mate` — **prod**, pinned to `main`. PM2 serves from here: `kanban-km` (daemon),
  `kanban-km-serve` (webhook `:8765`), `kanban-km-config` (UI `:8796` → `km.iznogoudatall.xyz`).
- `~/staging/kanban-mate` — **staging**, tracks branch `staging`. PM2 `kanban-staging-config`
  (`:8797` → `km-staging.iznogoudatall.xyz`).

**Continuous deployment** — PM2 `kanban-autodeploy` (`scripts/autodeploy-poll.sh`, ~60 s poll):
push to **`main`** → prod auto-redeploys; push to **`staging`** → staging auto-redeploys. The poller
**hard-resets** each clone to its tracked remote tip, so a **force-pushed** `staging` (rebased feature
branch) deploys cleanly. (Historical bug, fixed 2026-06-21: the old poller used `git pull --ff-only`,
which aborted on a diverged/force-pushed `staging` — `ff-only pull failed (diverged) — skipping` —
and silently never updated staging; now `git reset --hard origin/<branch>`. The fix ships in
`autodeploy-poll.sh`; the **running** poller executes the **prod clone's** copy, so it only takes
effect once the fix is on `main` and the poller is restarted.)

**To test not-yet-merged work on staging** — staging runs against the **REAL prod board** (no test
board: a card move / config edit there applies for real). Push your branch onto the `staging` branch:

```bash
git push origin <your-branch>:staging --force-with-lease
```

Within ~60 s, open `https://km-staging.iznogoudatall.xyz` (same login as prod) and **confirm** the
served asset hash (`curl -s https://km-staging.iznogoudatall.xyz/ | grep -o 'index-[A-Za-z0-9_-]*\.js'`)
or `/api/health` version changed. An amber **STAGING** frame marks it.

**Reliable manual staging deploy** — use when the poller is mid-rollout or stale (e.g. its `reset
--hard` fix is on a branch not yet merged to `main`), or when you want a deterministic, immediate
deploy. Deploy straight from the staging clone:

```bash
cd ~/staging/kanban-mate \
  && git remote update --prune origin \
  && git reset --hard origin/staging \
  && PATH="$HOME/staging/venv/bin:$PATH" bash scripts/deploy-staging.sh
```

(`git remote update`, **not** `git fetch` — the repo's network-timeout hook flags the bare word
`fetch`.) This touches only the staging clone + `kanban-staging-config`, never prod. Keep on-disk
state/config **backward-compatible** so the feature build (staging) and the prod daemon (`main`)
share `~/.kanban-km` safely.

**Never** run `npm run build` + `pm2 restart` by hand — use `scripts/deploy.sh` (prod; refuses unless
clean `main` synced with origin) or `scripts/deploy-staging.sh`. **Always commit** (nothing lives only
in a working tree). **Never delete a local branch** that isn't pushed AND merged to `main` (enforced by
`hooks/reference-transaction`; activate per clone with `scripts/install-git-guards.sh`). Full detail:
`docs/reference/deployment.md` + `docs/reference/repo-safety.md`.
