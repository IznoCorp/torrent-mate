# KanbanMate — Extraction & Hardening — Design Spec

> **Status**: brainstormed & approved (2026-06-03), pending final spec review.
> **Repo**: `~/dev/KanbanMate` → `git@github.com:IznoCorp/kanban-mate.git` (fresh, empty).
> **Source of the code being extracted**: the PoC at
> `PersonalScraper/.claude/skills/kanban/` (portable-config repo, branch `personal-scraper`).
> **⚠️ Pre-implementation gate**: two PoC features are still landing upstream
> (sticky comments per step; Cancel-column teardown + Cancel→Backlog resume).
> The extraction MUST re-sync the latest PoC code before implementation starts — see §10.

## 1. Purpose & motivation

KanbanMate is a **reusable Kanban orchestrator**: each roadmap item is a **ticket** moved
column by column on a **GitHub Projects v2** board; moving a card into a triggering column
fires an autonomous **Claude Code agent** in an isolated **tmux + git-worktree** workspace.
The agent comments on the ticket, may re-move the card (only to non-triggering columns), and
its session is **resumable** (`tmux attach` / `claude --resume <uuid>`). The runtime listener
is **n8n** (24/7); no open Claude session is required for the board to react.

Today this lives buried inside `PersonalScraper/.claude/skills/kanban/` (~18 kLOC incl. tests).
It is **transverse infrastructure** that has nothing to do with the media pipeline. This effort
extracts it into its own autonomous project and **hardens it**.

**Motivation, in priority order** (user-stated):

1. **Harden the PoC** — wave-2 hardening (15 should-fix) was never done; integration tests are
   gated/skipped and have never actually run.
2. **Clean personal multi-repo use** — make it properly tooled for the user's own repos.
3. **Publishable** — distributable to others (open-source / Claude plugin marketplace).
4. **Decouple from the media repo** — get it out of PersonalScraper for good.

Decoupling is the through-line; hardening is the dominant driver; publishability is a goal but
not the primary optimisation target (we optimise reliability and personal use first).

## 2. Identity & artifacts

One repo, **two distributable artifacts**:

| Artifact          | What                                                                                                                                                                                         | Install channel                                           |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **Engine**        | Python package `kanbanmate` + console script `kanban` + bundled assets (`kanban-dispatch.sh`, n8n `workflow.json`, launchd reaper plist template, `columns.yml` template, agent helper bins) | `pip install` (editable for dev; pipx for runtime)        |
| **Claude plugin** | `.claude-plugin/marketplace.json` at repo root → skill `/kanban` (thin: shells to the `kanban` CLI) + agent helper commands                                                                  | `claude plugin marketplace add` + `claude plugin install` |

The repo **is** its own Claude plugin marketplace. **All logic lives in the engine**; the
plugin/skill only invokes `kanban …`. This is the key correction vs the PoC, where logic and
skill packaging were intermixed.

Naming: package `kanbanmate`, console entry `kanban`, plugin `kanban`, marketplace `kanbanmate`
(GitHub repo `IznoCorp/kanban-mate`). Fresh git history — a clean initial extraction commit; the
PoC commit history stays in the config repo.

## 3. Architecture (unchanged runtime flow)

```
Drag a card (Status field) — Projects v2 board, org IznoCorp
   │ ORG webhook projects_v2_item (action=edited, Status field)
   ▼
n8n [Webhook Raw Body ON] → [Code: base64(rawBody)+sig+delivery] → [Execute Command (nohup detached)]
   ▼
kanban-dispatch.sh  (server, non-root user)
   1) base64-decode + HMAC on decoded bytes (secret off-git)       → reject if invalid (FIRST)
   2) anti-loop + idempotence: bot-moves to triggering cols refused; dedup (item,to);
      dedup X-GitHub-Delivery; in-flight lock (issue,column)
   3) filter: action=edited AND field == Status (by NODE ID); the column is NOT in the payload
   4) resolve (narrow GraphQL): content_node_id → Issue{number, repo} + current Status value
      (fieldValueByName → new column); old column from persisted Store.get_state
   5) route: ~/.kanban/projects.json (keyed by project node id) → local clone (flock) → git fetch
   6) config: <clone>/.claude/kanban/columns.yml → column class (agent / reactive / inert)
   7) dependency gate: "Depends on #N" not Done → comment + move Blocked + stop
   8) atomic cap (count+reserve under flock) else → queue ~/.kanban/queue/
   9) worktree (on main, idempotent) + tmux ticket-<n> + claude --session-id <uuid> <perms>
      send-keys: trust-dialog poll → filled prompt; write state + audit
   ▼
Agent (claude, tmux): works · kanban-comment (sticky) · kanban-move (push/PR OK, NEVER merge)
   ▲
You: ssh + tmux attach -t ticket-<n> · iTerm2 -CC · claude --resume <uuid> · /kanban (management)
```

Separation: listener = **n8n** (24/7); skill `/kanban` = **occasional management** (off-runtime);
agent = fresh independent `claude` process. The full PoC design detail is carried over verbatim
from `2026-06-02-kanbanmate-design.md` (frozen decisions D1–D9) and is not re-litigated here.

## 4. Install model — self-bootstrapping ("everything via the project")

Single entry point `kanban install`, in **three idempotent tiers**:

### 4.1 Host tier (1×/machine)

Creates `~/.kanban/` skeleton (secret `600`, token, `n8n_key`), imports **and activates** the n8n
workflow via the **public API** (`POST /api/v1/workflows/{id}/activate`, `X-N8N-API-KEY`), installs
the **launchd reaper** plist **re-pointed at the new repo path** (the PoC plist points at the old
`…/PersonnalScaper/.claude/skills/kanban/bin/kanban-reaper` and must be replaced), seeds the
kill-switch primitives.

### 4.2 Claude tier (1×/machine) — fully automatic ✅

The Claude plugin manager exposes a **non-interactive CLI** (`claude` v2.1.156, verified), so
`kanban install` drives it directly — no manual `/plugin` step, no hand-editing of internal JSON:

```
claude plugin marketplace add <repo-path> --scope user
claude plugin install kanban@kanbanmate --scope user [--config engine_path=…]
```

- `marketplace add` accepts a **local path** source (no GitHub round-trip needed for local dev).
- `install` installs **and** enables in one shot, non-interactively; `--config key=value` passes
  userConfig validated against the plugin manifest.
- `kanban doctor` verifies presence via `claude plugin list` + `claude plugin validate <path> --strict`.
- `kanban uninstall` runs `claude plugin uninstall` + `marketplace remove`, plus host-tier teardown.

> Persistence is file-based (`~/.claude/plugins/{known_marketplaces,installed_plugins}.json`,
> `settings.json:enabledPlugins`) but we **never write those directly** — we go through the
> supported CLI, which is upgrade-stable.

### 4.3 Per-repo tier (per target project)

`kanban init --repo org/repo` (fresh org Project v2, reuse auto Status field, ensure columns,
`wave:*`/`prio:*` labels, write `<clone>/.claude/kanban/columns.yml`, register in `projects.json`
keyed by project node id) + `kanban seed <ROADMAP.md>` (issues + `Depends on` rewrite, in Backlog).

`kanban doctor` validates **all three tiers** end-to-end (engine importable, host services up,
plugin present, n8n reachable + Execute Command enabled, token scopes not over-broad, branch
protection on, non-root, tmux socket).

## 5. Hardening fused (the 15 should-fix → design requirements)

This effort does **not** defer hardening. Each item below is in scope.

| #   | Requirement                                                                                                                                                                                                                                                   |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| H1  | Hard idempotence: `processed/` dedup via **atomic `O_EXCL` create** + **TTL/pruning**; **in-flight lock `(issue, column)`** so a duplicate delivery never double-launches                                                                                     |
| H2  | Bot-move dedup with **TTL** (bounded timing window; stale entries pruned)                                                                                                                                                                                     |
| H3  | **Pagination**: org webhook listing + `projectItems` GraphQL (cursor-follow; an issue in many projects / a project with many items must not silently truncate)                                                                                                |
| H4  | Permission profiles **materialised** into the worktree's `.claude/settings.json` (`defaultMode` pinned — mitigates mid-session reset #39057); `safe` (concrete `permissions.allow`) vs `trusted`; both ban `gh pr merge`, `git push --force`, history rewrite |
| H5  | **Kill-switch** `~/.kanban/PAUSE` → downgrade all profiles to `safe` + **unattended-hours** window → zero launches                                                                                                                                            |
| H6  | Replace synthetic fixtures with **real captured** `projects_v2_item.edited` payloads + real GraphQL responses (resolves the open question of exact shape)                                                                                                     |
| H7  | **Real GitHub/n8n integration tests** actually executed (no longer gated-and-skipped-forever) — see §6                                                                                                                                                        |

## 6. Testing & CI strategy (the core of "harden")

Three levels:

1. **Unit** (offline, deterministic) — carried over (~255 tests), kept green throughout.
2. **Local-real** (real tmux + real git; GitHub & `claude` faked) — `test_e2e_local.py`. Runs in
   **CI** (GitHub Actions runners have tmux/git). This is the anti-hollow proof: a real card-move
   spawns a real tmux session in a real worktree.
3. **Integration-real** (real GitHub Projects v2 + real n8n) — gated on secrets:
   - A **dedicated test org/Project** + `KANBAN_TOKEN` CI secret.
   - n8n is self-hosted → spin an **ephemeral n8n container** in a **nightly** CI job.
   - **PR CI** = levels 1+2 + `claude plugin validate .claude-plugin --strict` (free, no secrets).
   - **Nightly CI** = level 3.

This converts "gated/skipped, never run" into "actually verified".

## 7. Column contract — three column classes

The PoC had two implicit classes (agent-triggering vs inert). The two in-progress features
introduce a **third**: **reactive-action columns** that run a side-effect, not an agent.

| Class        | `columns.yml` shape                                                           | Behaviour                                                       |
| ------------ | ----------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **agent**    | `triggers_agent: true` (+ `prompt`, `permission_profile`, `interactive_only`) | launch agent in worktree                                        |
| **reactive** | `action: teardown` (NEW)                                                      | run a dispatcher side-effect (no agent), e.g. Cancel teardown   |
| **inert**    | neither                                                                       | human-gate / terminal; dispatcher comments-and-stops or ignores |

`kanban-move` still **refuses agent-triggering targets** (anti-loop); reactive and inert targets
are permitted for bot/agent moves.

### 7.1 Sticky comments per step (agent→ticket signalling) — NEW

`kanban-comment` gains a **sticky mode**: one comment per _(ticket, step)_ updated in place rather
than appended. Implementation: an HTML marker (`<!-- kanban:step=<column-key> -->`) embedded in the
comment body; the helper lists the issue's comments, matches the marker, and **edits** the existing
one (`gh issue comment --edit-last` is insufficient — match by marker, not recency) or **creates**
it if absent. Append mode stays available for free-form notes. This is the durable agent→ticket
signal surface (progress, phase summaries) that doesn't spam the timeline.

### 7.2 Cancel column — teardown + resume — NEW

A **`Cancel`** reactive column. Moving a card into it triggers **full teardown** of the ticket:
kill the tmux session, `worktree remove` (no `--force`), release the slot, drop the in-flight lock

- relevant `processed/` marks, clear/transition the persisted state, and post a final sticky
  comment. This **promotes** the existing `kanban cancel` CLI (`cli/plan_cancel.py`) from a manual
  command into a column-reactive action sharing the same teardown core.

**Resume path**: moving **Cancel → Backlog** resets the ticket to a clean, re-startable state
(state purge so a later move into a triggering column starts fresh — fresh uuid, fresh worktree).
Cancel and Backlog are both non-agent columns, so neither move relaunches an agent; the teardown is
keyed on the _destination_ (`Cancel`) and the reset on the _transition_ (`Cancel→Backlog`).

## 8. Default columns & triggering (carried from PoC, + Cancel)

| Column          | Class                  | Note                                         |
| --------------- | ---------------------- | -------------------------------------------- |
| Backlog         | inert                  | manual; also the reset target from Cancel    |
| Spec            | inert (human-gate)     | brainstorm = interactive                     |
| Planned         | inert                  | create-branch = interactive                  |
| Ready to dev    | inert                  | human gate                                   |
| **In Progress** | **agent**              | `/implement:phase` (unattended-safe)         |
| **PR/CI**       | **agent**              | `/implement:feature-pr`                      |
| **Review**      | **agent**              | `/implement:pr-review` (no auto-merge)       |
| Merge           | inert (human only)     | bot cannot reach it; merge is human          |
| **Cancel**      | **reactive: teardown** | full teardown; Cancel→Backlog = resume reset |
| Done            | inert                  | terminal                                     |
| Blocked         | inert                  | agent/reaper parks here                      |

The `implement:*` defaults live **only** in the `columns.yml` template (per-repo, user-editable) —
the engine stays generic, so a third party uses their own prompts without touching code.

## 9. Security & autonomy (carried from PoC §10)

Merge = human only (agents push + open PR, never merge); ban `gh pr merge` / `--force` / history
rewrite across all profiles. `safe` profile = concrete `permissions.allow` + pinned `defaultMode`.
Token in `~/.kanban/token` (600, off-git/n8n); v1 = user PAT (anti-loop is target-keyed, not
identity-keyed). Kill-switch (H5). Non-root process. GitHub App = optional future upgrade (§12).

## 10. Cutover & decommission (rule: no back-compat before v1.0)

- **No migration script** (project rule: <1.0 ⇒ no migrations). Existing `~/.kanban/` PoC state
  (disposable test tickets) is dropped; `kanban install` starts a fresh `~/.kanban/`; `kanban reset`
  archives the old one.
- **Pre-implementation re-sync gate (⚠️ blocking)**: before extraction begins, pull the latest PoC
  code from `.claude/skills/kanban/` **with the two in-progress features landed** (sticky comments,
  Cancel column). The spec's §7.1/§7.2 describe target behaviour; the actual code is the source of
  truth and must be synced first. Do not extract a half-landed tree.
- **Decommission old location** (after the new repo is green): remove `skills/kanban/` from the
  portable-config repo, **uninstall the old launchd plist**, replace it with the new repo's plist,
  clean references in `.claude/CLAUDE.md`.

## 11. Repository layout (target)

```
~/dev/KanbanMate/
├── README.md                      # what/why + quickstart
├── pyproject.toml                 # package kanbanmate, console_scripts: kanban
├── .claude-plugin/marketplace.json
├── plugin/                        # the Claude plugin payload (skill /kanban, agent helpers)
│   └── skills/kanban/SKILL.md
├── src/kanbanmate/                # engine: dispatch, payload, github/, engine/, cli/, state, ...
├── assets/
│   ├── n8n/workflow.json
│   ├── launchd/xyz.iznogoudatall.kanban-reaper.plist.tmpl
│   └── columns.yml.tmpl
├── bin/                           # kanban-dispatch.sh, kanban-reaper, kanban-comment, kanban-move
├── tests/                         # unit + local-real + gated integration
├── docs/
│   ├── install.md                 # 3 tiers
│   ├── how-it-works.md            # flow diagram + components
│   ├── columns.md                 # columns.yml contract (3 classes)
│   └── superpowers/specs/…        # this file
├── ROADMAP.md                     # deferred items (§12)
└── .github/workflows/             # pr.yml (L1+L2+validate), nightly.yml (L3)
```

## 12. Out of scope / ROADMAP (deferred)

n8n-alternative lightweight receiver (reduce the n8n dependency for publishability); GitHub App
upgrade (identity-keyed anti-loop + clean attribution + short scoped tokens); multi-org; MCP helpers
(Bash helpers in v1); auto-merge (permanently forbidden by design).

## 13. Implementation phasing (for the plan)

- **P1** — bootstrap repo + packaging (`pyproject`, layout §11) + port engine + CI green on existing
  unit + local-real tests.
- **P2** — installer 3 tiers (`kanban install/uninstall/doctor`) + plugin marketplace + `validate` gate.
- **P3** — hardening H1–H5.
- **P4** — real fixtures H6 + integration CI H7 (test org + ephemeral n8n nightly).
- **P5** — sticky comments (§7.1) + Cancel column (§7.2) wired to the column-class model; docs;
  cutover + decommission of the old location.

> Phasing note: §7.1/§7.2 land in P5 **only if** they arrive via the §10 re-sync as finished PoC
> code. If still in flux at extraction time, P1 ports them as-is and P5 only does the wiring/tests.
