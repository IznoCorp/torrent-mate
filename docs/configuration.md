# Configuration & parametering

This is the reference for **every knob** that shapes how KanbanMate drives a board: the per-project
registry, the three per-repo YAML files (`columns.yml`, `transitions.yml`, `sensitive.yml`), the
permission profiles, the poll cadence, and the operator CLI surface. Each section gives a concrete
example and how to change it.

> **Mental model (since `keel` / `skiff`).** Placement authority is a **local `board.json`** per
> project, not GitHub. The daemon writes `board.json` first, then mirrors that placement **one-way**
> to the GitHub Status field. A drag made on the GitHub board is ingested back through the webhook
> receiver. Monitoring and the board view read the local store (sub-second). So GitHub is a
> **secondary mirror**, not the source of truth. Each ticket is classified at **Triage** into one of
> three lanes — FULL, LITE, EXPRESS — which differ only in how much of the front of the flow runs
> before the build. **Merge is human-only in every lane.**

Everything below lives **outside the repo**, under the runtime root `~/.kanban/` (the live prod
deployment uses `~/.kanban-km/`). The per-repo YAML files live **inside each project's clone** at
`<clone>/.claude/kanban/`.

```
~/.kanban/                          # runtime root (prod: ~/.kanban-km)
├── projects.json                   # the registry — one entry per board (§1)
├── token                           # the shared GitHub PAT (mode 0600)
├── tokens/<token_ref>              # per-org PATs (multi-org; §1, token_ref)
├── webhook_secret                  # HMAC secret for `kanban serve` (0600)
├── PAUSE                           # kill-switch sentinel (§5)
├── intents/ … .nudge               # operator-move queue + daemon-wake sentinel
└── projects/<safe(project_id)>/    # per-project state sub-root (board.json, heartbeats, …)

<clone>/.claude/kanban/
├── columns.yml                     # the board's column set (§2)
├── transitions.yml                 # the (from,to) whitelist + prompts + defaults (§3)
└── sensitive.yml                   # paths/keywords forcing the FULL lane (§4)
```

---

## 1. The registry — `~/.kanban/projects.json`

The registry is a JSON object keyed by **Project v2 node id**, with one `ProjectEntry` per board.
`kanban init` writes it; the daemon, the CLI, the bin helpers, and the webhook receiver all read it.
It is the authoritative source code for `ProjectEntry` (`src/kanbanmate/cli/init.py`).

### Example (the live prod registry, abridged)

```json
{
  "PVT_kwDOB3abh84BZiPJ": {
    "repo": "IznoCorp/kanban-mate",
    "clone": "/Users/izno/deploy/kanban-mate",
    "project_id": "PVT_kwDOB3abh84BZiPJ",
    "status_field_node_id": "PVTSSF_lADOB3abh84BZiPJzhUgNb8",
    "option_map": {
      "Backlog": "f75ad846",
      "Triage": "…",
      "In Progress": "47fc9ee4",
      "Done": "98236657"
    },
    "config_dir": "/Users/izno/deploy/kanban-mate/.claude",
    "dev_repo_path": "",
    "org": "IznoCorp",
    "enabled": true,
    "ingress": "polling",
    "token_ref": "",
    "board_backend": "native",
    "board_mirror": true
  }
}
```

### Every field

| Field                  | Type   | Default (new board)  | What it does                                                                                                                                                                                                                                           |
| ---------------------- | ------ | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `repo`                 | string | (required)           | The `owner/name` slug. Drives clone resolution, issue comments, branch protection, the org fallback for webhook routing.                                                                                                                               |
| `clone`                | string | the cwd at `init`    | Absolute path to the local clone — the base of the ticket worktrees and the source of `columns.yml`.                                                                                                                                                   |
| `project_id`           | string | (resolved by `init`) | The Project v2 node id. Same as the registry **key**; what the daemon routes by.                                                                                                                                                                       |
| `status_field_node_id` | string | (resolved by `init`) | The Status single-select field node id — what a Status mirror writes / a webhook event is matched against.                                                                                                                                             |
| `option_map`           | object | (resolved by `init`) | `{column display-name → GitHub option id}` for the Status field. Lets the engine mirror a native column key to the right GitHub option.                                                                                                                |
| `config_dir`           | string | `<clone>/.claude`    | The project's `.claude` dir — the launcher **copies** `skills/`/`commands/`/`agents/` from here into each worktree so the agent can resolve the `/implement:*` skills its prompt invokes. `""` disables provisioning.                                  |
| `dev_repo_path`        | string | `""`                 | The operator's dev-clone path; the post-merge ff-only `main` update target. `""` = no dev-clone update.                                                                                                                                                |
| `org`                  | string | the repo owner       | The owning org/user login (informational + webhook-routing fallback). Blank ⇒ derived from `repo`.                                                                                                                                                     |
| `enabled`              | bool   | `true`               | Whether the daemon drives this project. Set `false` to **pause one board** in a multi-project root without de-registering it.                                                                                                                          |
| `ingress`              | string | `"polling"`          | Per-project ingress: `"polling"` (tight 10 s cadence — right for a native board) or `"webhook"` (slow safety-sweep + sub-second nudge — for a github-backed board). A **blank** value resolves backend-aware (native→polling, github→webhook). See §6. |
| `token_ref`            | string | `""`                 | Multi-org token selector. `""` ⇒ the shared `<root>/token`. A name ⇒ `<root>/tokens/<token_ref>` (mode 0600), so two orgs can use distinct PATs without a GitHub App.                                                                                  |
| `board_backend`        | string | `"native"`           | `native` (default, one-way: local store is authority, mirrors native→GitHub), `hybrid` (legacy bidirectional reconcile — being retired, ticket #112), or `github` (pure GitHub authority).                                                             |
| `board_mirror`         | bool   | `true`               | Whether the native one-way mirror keeps the GitHub Status in sync. `false` ⇒ native is the sole authority and the GitHub board drifts.                                                                                                                 |

> **`kanban init` always writes `board_backend: "native"` + `ingress` from `--ingress` (default
> `polling`).** There is **no `--board-backend` flag** — to put a board on `hybrid` or `github` you
> edit `projects.json` by hand. Old-shaped entries (missing newer keys) load with the defaults
> above, so the file is backward-compatible — no migration needed.

### How to change it

- **Add a board** — run `kanban init --repo owner/name` (§7). Never hand-author a first entry: `init`
  resolves the `project_id`, `status_field_node_id`, and `option_map` from GitHub for you.
- **Pause one board** — set its `"enabled": false` and the daemon skips it on the next tick.
- **Per-org token** — drop the PAT in `~/.kanban/tokens/<name>` (mode 0600) and set
  `"token_ref": "<name>"` on the entries for that org.
- **Disable the GitHub mirror** — set `"board_mirror": false` (the GitHub board then drifts; only
  KanbanMateUI / `board.json` is correct).

After editing `projects.json`, the daemon picks it up on its next tick — no restart needed for most
fields, but restart `kanban-km` to be safe after a backend/ingress change.

---

## 2. `columns.yml` — the board column set

`columns.yml` (in `<clone>/.claude/kanban/`) declares **only** the board's columns. It carries **no**
launch configuration — every prompt, profile, and advance directive lives in `transitions.yml`,
because an agent launches **at a transition**, never at a column.

### The name / key seam

Every column has two identifiers:

- **`key`** — the stable machine-readable id (no spaces): `InProgress`, `PRCI`, `ReadyToDev`.
- **`name`** — the human-readable GitHub Projects v2 column label: `In Progress`, `PR/CI`, `Ready to dev`.

The daemon resolves a column reference by **name first** (the GitHub adapter emits the option _name_),
then **key** (config / engine / your CLI moves). So `kanban move 5 InProgress` and a GitHub drag to
"In Progress" both land on the same model column. **Keep `key`s stable** — `transitions.yml` and the
engine reference columns by key.

### Example (shipped template)

```yaml
columns:
  - key: Backlog
    name: Backlog
  - key: Triage
    name: Triage # skiff classifier stage
  - key: Brainstorming
    name: Brainstorming # FULL-lane head (interactive)
  - key: Spec
    name: Spec
  - key: Plan
    name: Plan
  - key: Scope
    name: Scope # LITE-lane head (design+plan in one pass)
  - key: ReadyToDev
    name: Ready to dev # the SINGLE pre-build human gate (FULL lane)
  - key: PrepareFeature
    name: Prepare feature # EXPRESS-lane head
  - key: InProgress
    name: In Progress
  - key: PRCI
    name: PR/CI
  - key: Review
    name: Review
  - key: ReadyToMerge
    name: Ready to merge # the human merge gate
  - key: Merge
    name: Merge
  - key: Cancel
    name: Cancel
    action: teardown # the ONLY non-key/name flag
  - key: Done
    name: Done
  - key: Blocked
    name: Blocked
```

The only optional flag is `action: teardown`, which marks a **reactive** column (the Cancel teardown —
no agent, a mechanical dispatcher side-effect). Every other column is **inert** (a human gate or
terminal). A `defaults:` block is parsed here as a documented **fallback only**; the authoritative
concurrency/rate-limit knobs live in `transitions.yml` (§3) and the template leaves them commented out
so the two can never silently disagree.

### How to change it

Edit the `columns` list **and** make the GitHub board's Status options match, **then run
`kanban board import`** (§8 — this is the gotcha). Renaming a `name` is safe as long as the GitHub
option name matches; renaming a `key` means updating every reference in `transitions.yml`.

---

## 3. `transitions.yml` — the (from,to) whitelist

`transitions.yml` is the heart of the flow: it whitelists each `(from, to)` move and attaches the
launch behaviour to it. It is **rendered** per-project by `init` (it carries the project slug) from
`core/transitions_defaults.py` — that renderer is the source of truth for the shipped table.

### Per-transition fields

| Field             | What it does                                                                                                                                                                                                            |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `from` / `to`     | The column **keys** of the move. `from` may be a list (cartesian-expanded) or `*` (wildcard).                                                                                                                           |
| `profile`         | The permission profile materialised into the worktree (`docs`/`prepare`/`dev`/`check`/`merge`/`triage` — §5).                                                                                                           |
| `prompt`          | The agent's launch instruction (a `/implement:*` stage). A transition **with** a prompt launches an agent; one without is an allowed **no-op** (a human gate landing or a recovery edge).                               |
| `permission_mode` | The `claude --permission-mode` for the session (`auto` default — headless-safe, still enforces deny). `bypassPermissions` is **never** allowed.                                                                         |
| `advance`         | What the engine does after a clean `kanban-done`: `auto:<col>` (move the card to `<col>`, firing the next stage), `route` (read the triage breadcrumb and move to the lane entry), or `stop` (the agent routes itself). |
| `script`          | A bot gate script (e.g. `bin/check-pr-ready.sh`) run before/at the transition instead of an agent.                                                                                                                      |
| `on_fail`         | Where a failed `script` bounces the card (e.g. `move:InProgress` — the fix-CI loop).                                                                                                                                    |

### The lanes (shipped table)

Each lane is just a path through these transitions. **Triage** (`Backlog → Triage`) classifies the
ticket and `advance: route`s it to the lane head:

```
FULL    Triage→Brainstorming→Spec→Plan→[Ready to dev = HUMAN GATE]→Prepare feature→In Progress→PR/CI→Review→[Ready to merge = HUMAN]→Merge→Done
LITE    Triage→Scope (design+plan in one pass; NO pre-build gate)→Prepare feature→In Progress→ … (same tail)
EXPRESS Triage→Prepare feature (straight to build)→In Progress→ … (same tail)
```

`advance:auto:<col>` carries the autonomy: e.g. `Brainstorming → Spec` is `advance:auto:Plan`, so when
the design agent finishes cleanly the engine moves the card to `Plan` and the next tick fires the plan
stage. The two human gates have **no** advance directive (`Plan → ReadyToDev` and `Review →
ReadyToMerge` are inert no-op landings). The CI gate (`InProgress → PRCI`, a script) auto-promotes to
`Review` **only on green CI**; red bounces back to `InProgress` (the fix-CI loop). **Merge is always a
human drag** (`ReadyToMerge → Merge`), even though the merge agent itself then runs autonomously under
the `merge` profile.

```yaml
project: owner/repo
defaults:
  concurrency_cap: 3
  move_rate_limit_per_hour: 10
transitions:
  - from: Backlog
    to: Triage
    profile: triage
    prompt: |
      You are the skiff TRIAGE classifier …
    advance: route
    permission_mode: auto
  - from: Spec
    to: Plan
    profile: docs
    prompt: |
      Run /implement:plan …
    advance: auto:ReadyToDev
    permission_mode: auto
  - from: InProgress
    to: PRCI
    profile: check
    script: bin/check-pr-ready.sh
    on_fail: move:InProgress
    advance: auto:Review
  - from: Plan # allowed no-op (the human review gate landing)
    to: ReadyToDev
```

### The `defaults:` block

This is the **authoritative** surface for two board-wide knobs (`columns.yml`'s copy is a fallback
only):

| Knob                       | Default | What it does                                                                                                        |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| `concurrency_cap`          | `3`     | Max concurrent agent sessions. Over-cap launches **queue** rather than fire.                                        |
| `move_rate_limit_per_hour` | `10`    | Max AUTO/bot moves **per ticket per hour**. Over-limit parks the ticket in **Blocked** (the runaway-loop backstop). |

### How to change it

Edit `<clone>/.claude/kanban/transitions.yml` directly. To **regenerate** the shipped table from
scratch (e.g. after an engine upgrade changed the default flow), re-render it from
`core.transitions_defaults.render_transitions_yaml` and **restart the daemon**. A board that has
stopped auto-advancing is almost always running a stale `transitions.yml` — regenerate + restart is
the fix.

---

## 4. `sensitive.yml` — forcing the FULL lane

`sensitive.yml` (in `<clone>/.claude/kanban/`) lists the **paths, keywords, and labels** that force a
ticket onto the **FULL** lane at Triage, no matter how small it looks. The **Triage agent reads this
file** (the engine never loads it): any hit is a hard "never fast-track" — a small mechanical edit to a
high-regression-risk surface still gets the full brainstorm→design→plan→human-gate treatment.

### Example (shipped template)

```yaml
paths: # globs matched against the ticket's probable scope
  - "**/auth/**"
  - "**/billing/**"
  - "src/kanbanmate/core/decide.py"
  - "src/kanbanmate/adapters/perms.py"
  - "src/kanbanmate/adapters/github/client.py" # the ONLY board-write path
  - "src/kanbanmate/adapters/store/**" # runtime state persistence
keywords: # case-insensitive substrings in the ticket text
  - security
  - credential
  - secret
  - migration
  - rate-limit
  - idempoten
  - concurrency
  - hmac
labels: # GitHub labels that force full regardless of size
  - sensitive
  - security
```

A **missing or empty** `sensitive.yml` does **not** mean "nothing is sensitive" — the Triage prompt
leans to `full` for anything it cannot confidently classify as safe. The Triage sizing logic runs the
safety check **first**, so a `sensitive.yml` hit cannot be down-overridden by a `track:*` label.

### How to change it

Edit the lists to fit the project. Add the modules where a thin lane would be dangerous (anything
touching autonomy, idempotency, persistence, board-writes, auth/billing, or signature verification).

---

## 5. Permission profiles — `docs` / `prepare` / `dev` / `check` (+ `merge`, `triage`)

Every launched agent reads `<worktree>/.claude/settings.json`, which the engine **materialises** from
the transition's `profile` (`src/kanbanmate/adapters/perms.py`). A profile pins
`permissions.defaultMode`, a concrete `permissions.allow` list, and the universal `permissions.deny`
ban set. **Deny wins over allow.**

| Profile   | Used by                              | Allows                                                                                                                                                                            |
| --------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs`    | brainstorm / design / plan / scope   | `Read` + `Edit` + a minimal shell (`mkdir`/`ls`/`cat`) + git read + **local commit** + `gh issue` + kanban helpers. **No push, no PR ops, no broad Bash.** This is the **floor**. |
| `prepare` | create-branch (Prepare feature)      | code edits + **full git incl. push** (create/maintain a branch) + kanban helpers. **No `gh`.**                                                                                    |
| `dev`     | implement / fix-CI / review / rework | code edits + full git (push to open/maintain a PR) + `gh` (**never merge**) + `make` + broad `Bash` for build/test + kanban helpers.                                              |
| `check`   | the script gates (no agent)          | read-only-ish: `Read` + git read + `gh` read + `kanban-done`.                                                                                                                     |
| `merge`   | the autonomous Review→Merge agent    | a `dev`-like surface — and the **sole** profile whose deny lifts exactly `gh pr merge` so it can squash-merge a green, mergeable PR.                                              |
| `triage`  | the skiff classifier                 | read-only: `Read` + code-search verbs (`cat`/`ls`/`grep`/`rg`/`git log`/`gh issue view`) + the route/decision/terminal kanban helpers. No `Edit`, no push, no broad Bash.         |

### What is banned **everywhere** (the universal deny-list)

These stay denied for **all** profiles (the `merge` profile lifts only the single `gh pr merge` path):

- **Merge** — `gh pr merge` (and every reachable path: `gh api …/merge`, the GraphQL
  `mergePullRequest`, the github-curl `pr-merge` helper). **Merge is human-only.** Even `merge`
  keeps `--admin`, `--merge`, `--rebase`, and the `-m`/`-r` short aliases banned — only `--squash`.
- **Force-push** — `git push --force` / `-f` / `+refspec` / `--mirror` / `--force-with-lease`.
- **Direct push to the default branch** — any push whose destination ref is `main`.
- **Branch / ref deletion** — `git push --delete` / `-d` / `:refspec`, `git branch -D`,
  `git update-ref -d`.
- **History rewrite** — `git rebase`, `git reset --hard`, `git commit --amend`, `filter-branch` /
  `filter-repo`, `reflog expire`, `gc --prune`.
- **`bypassPermissions`** — refused outright (it would skip the deny layer), and `materialise_settings`
  **refuses to run as root**.
- **Runtime-root secrets** — reading `launch_secret` / `webhook_secret` via `Read` or `cat`/`head`/…

> Defense-in-depth: a string-prefix Bash deny-list **cannot** be made airtight (a same-OS-user agent
> has equivalents). The **authoritative** boundary is **GitHub branch protection** (require status
> checks; block force-push, deletion, and direct push on the default branch). Configure it on every
> orchestrated repo.

### The `~/.kanban/PAUSE` kill-switch

`kanban pause` writes a `PAUSE` sentinel under the runtime root. While present, the daemon **launches
no agents** and downgrades every profile to the `docs` floor. The daemon reads the sentinel fresh each
tick, so pause/resume takes effect on the next poll — no restart.

```bash
kanban pause     # engage the kill-switch (no launches)
kanban resume    # clear it
```

### How to change a profile

The profiles are defined in code (`_PROFILE_ALLOW` / `_DENY` in `adapters/perms.py`) — they are **not**
a config file you edit per board. You change which profile a stage uses by setting `profile:` on the
transition in `transitions.yml`. An unknown profile name degrades safe to `docs`.

---

## 6. Cadence tuning — why native boards want polling

The daemon runs one inter-tick sleep after sweeping all projects, so the cadence is the **tightest**
any enabled project requires (`core/interval.py`):

| Effective ingress | Base cadence           | Reaction                                                                                                                                                                                  |
| ----------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `polling`         | **10 s** (fixed)       | A move is detected within ~10 s.                                                                                                                                                          |
| `webhook`         | **120 s** safety-sweep | The webhook **nudge** (`.nudge` sentinel) collapses the wait to **<1 s**; the slow sweep is the always-on fallback that reconciles even if the receiver is down or GitHub drops an event. |

**A native one-way board wants `polling`.** Its primary input is **local** (KanbanMateUI writes
`board.json`; a local drag fires **no** webhook), so an all-webhook daemon would make every operator
action wait out the slow 120 s sweep. That is why `init` defaults `ingress` to `polling` for the
default native backend, and a **blank** ingress resolves backend-aware (native→polling, github→webhook,
in `core/registry_resolve.effective_ingress`).

The 10 s poll costs ~7 %/h of the GitHub GraphQL 5000 pt/h budget — negligible. The geometric idle
back-off is **opt-in** (an operator sets `idle_max > base` in an `IntervalConfig`); the shipped default
is a flat 10 s.

### How to change it

Set `"ingress": "webhook"` (or `"polling"`) on the registry entry (§1) and restart the daemon. Use
`webhook` only for a `github`-backed board fronted by `kanban serve` behind a TLS proxy.

---

## 7. Adding a board — `kanban init`

```bash
kanban init --repo owner/name
# optional:
#   --clone /path/to/clone       (default: cwd; the worktree base)
#   --title "Board title"        (default: the repo name)
#   --ingress polling|webhook    (default: polling)
#   --dev-repo-path /path        (post-merge ff-only update target; default: none)
#   --root ~/.kanban             (the runtime root holding projects.json)
```

`init` is idempotent. It: (1) finds-or-creates a fresh org Project v2, (2) reshapes its Status field to
exactly the `columns.yml` columns (preserving existing option ids — no card is orphaned), (3) ensures
the `wave:*`/`prio:*` routing labels, (4) bootstraps the clone in place (`git init` + credential
helper — the long-lived PAT is never written into `.git/config`), (5) copies `columns.yml` +
`sensitive.yml` and renders `transitions.yml` into `<clone>/.claude/kanban/`, and (6) registers the
project in `projects.json` (keyed by the node id) with `board_backend: native`, `ingress` from the
flag, and `board_mirror: true`. With `--ingress webhook` it also seeds the `webhook_secret`
placeholder.

Then seed and run:

```bash
kanban seed ROADMAP.md --repo owner/name   # creates issues + adds them to Backlog
kanban run --root ~/.kanban                # start the daemon (PM2: kanban-km)
```

---

## 8. Changing columns — the `board import` gotcha

> **After changing the board's columns, you MUST run `kanban board import`.**

A native board keeps a **local `board.json` mirror** of placement. `board.json` records the set of
columns it knows about; it is **not** refreshed by the normal GitHub Sync / poll loop. So if you:

1. add or rename a column on the GitHub board, and
2. update `columns.yml` to match,

…the native store **still doesn't know the new column**, and native placement **cannot reconcile a
card into a column it doesn't know about** — the daemon won't fire a launch for a move into it.

`kanban board import` re-seeds `board.json` from the live GitHub snapshot (placement + the full column
set), closing the gap:

```bash
kanban board import --root ~/.kanban --project <project-id>   # --project required when N>1
kanban board import --dry-run                                  # preview, no write
kanban board status                                            # show the native store summary
```

Do this any time you touch the board's column set. (It is also the recovery if `board.json` ever drifts
from GitHub.)

---

## 9. The CLI surface

All commands take `--root ~/.kanban` (default; prod is `~/.kanban-km`) and, on a multi-project root,
`--project <node-id>` or `--repo owner/name` to select the board (they **fail loud** with the candidate
list when ambiguous — never silently pick the wrong board).

### Daemon & ingress

| Command                          | What it does                                                                                                                                                                  |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kanban run`                     | Start the long-running poll daemon (PM2 app `kanban-km`). Blocks until SIGTERM.                                                                                               |
| `kanban serve`                   | Start the webhook receiver (PM2 app `kanban-km-serve`). Verifies the HMAC, identifies the project, nudges the daemon. Refuses root / privileged ports / a placeholder secret. |
| `kanban poll --once`             | Run a single reconciliation tick and exit (debug dry-run, no daemon, no lock).                                                                                                |
| `kanban pause` / `kanban resume` | Engage / release the `PAUSE` kill-switch (§5).                                                                                                                                |

### Board placement

| Command                        | What it does                                                                                                                                                                                                 |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `kanban move <issue> <column>` | Enqueue an operator move (the daemon — the **sole** board writer — applies it next tick, advancing the diff baseline so it never re-fires a launch). `--wait` blocks on the result. `<column>` is a **key**. |
| `kanban board import`          | Re-seed the native `board.json` from GitHub (§8).                                                                                                                                                            |
| `kanban board status`          | Show the native store summary (placement + version).                                                                                                                                                         |
| `kanban cancel <issue>`        | Tear down a ticket's agent (kill tmux, remove worktree, release the slot, post a recap) — the same `TeardownAction` a Cancel-column move runs.                                                               |

### Tickets & pills

| Command                                   | What it does                                                                                      |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `kanban ticket create` / `edit` / `close` | Create / edit / close a ticket (issue + project item).                                            |
| `kanban pill set-health <health>`         | Set the dashboard health pill (domain names: `INACTIVE`/`BLOCKED`/`WAITING`/`ACTIVE`/`COMPLETE`). |
| `kanban pill note` / `clear`              | Set / clear the status-update note.                                                               |

### Read-only & health

| Command                 | What it does                                                                                                                                                                          |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kanban state`          | The unified board + agents + queue + recent-events + health-pill pane. `--json` for scripts.                                                                                          |
| `kanban status`         | The board summary + operator signals.                                                                                                                                                 |
| `kanban sessions`       | List live agent tmux sessions; flags reaper candidates (running ticket, dead session).                                                                                                |
| `kanban logs [<issue>]` | Read the structured JSONL daemon log; `--tail N`, optional issue filter.                                                                                                              |
| `kanban doctor`         | The 3-tier health check (engine importable, PM2 daemon up + heartbeat fresh, plugin present, token scoped, branch protection on, non-root, tmux socket ownership). Exit 0 = all pass. |

### Setup & lifecycle

| Command                        | What it does                                                                                       |
| ------------------------------ | -------------------------------------------------------------------------------------------------- |
| `kanban install` / `uninstall` | Create `~/.kanban`, write the PM2 ecosystem, install the `/kanban` plugin.                         |
| `kanban init`                  | Bootstrap a board (§7).                                                                            |
| `kanban seed`                  | Seed the board from a `ROADMAP.md`.                                                                |
| `kanban reset`                 | Archive the runtime root aside to a timestamped backup (non-destructive — the token is preserved). |
| `kanban config serve`          | Serve KanbanMateUI (the config builder + monitoring SPA; PM2 app `kanban-km-config`).              |

---

## See also

- [how-it-works.md](how-it-works.md) — the poll loop, the tick, the agent lifecycle.
- [columns.md](columns.md) — the column flow in depth.
- [install.md](install.md) — the three install tiers.
- Design records: `docs/features/{anchor,ensign,lucid,ingress-multiproject}/`,
  `docs/superpowers/plans/2026-06-22-fast-track-lanes.md`.
