# Install — 3-tier walkthrough

KanbanMate installs in three idempotent tiers, all driven by a single entry point:
`kanban install`. Re-running any tier is safe — it upgrades or no-ops.

## Tier 1 — Host (`kanban install`)

Creates the runtime root `~/.kanban/` (mode `700`), seeds the `token` skeleton (mode `600` —
a comment placeholder, never a real secret), and writes the PM2 ecosystem file
`ecosystem.config.js` at the repo root. The kill-switch sentinel (`~/.kanban/PAUSE`) is
**not** created — the default is unpaused.

PM2 is driven automatically unless you pass `--no-pm2`:

```bash
kanban install          # full: skeleton + ecosystem + pm2 start/save/startup
kanban install --no-pm2 # skeleton + ecosystem only, no PM2 subprocess calls
```

### PM2 supervision

The daemon (`kanban run`) is supervisor-agnostic — it knows nothing about PM2. PM2 is the
ops layer: it restarts the daemon on exit (not on hang — the daemon has its own per-tick
watchdog, DESIGN §5). Useful PM2 commands:

```bash
pm2 list                    # see kanban app status
pm2 logs kanban             # tail daemon stdout/stderr
pm2 restart kanban          # restart after upgrade
pm2 delete kanban           # manual stop (kanban uninstall does this)
```

The ecosystem file is a plain CommonJS module at the repo root; `kanban install` writes it
idempotently.

### Non-root requirement

`kanban install` refuses to run as root (DESIGN §10). The daemon must run as the same user
that owns the tmux socket — otherwise agent sessions can't be discovered or killed by the
reaper.

## Tier 2 — Claude (`claude plugin marketplace add` + `install`)

`kanban install` drives the Claude plugin manager CLI directly (no manual `/plugin` step):

```
claude plugin marketplace add <repo-path> --scope user
claude plugin install kanban@kanbanmate --scope user
```

- `marketplace add` accepts a **local path** (the KanbanMate repo) as source.
- `install` enables the `/kanban` skill in one shot.
- `kanban uninstall` runs `claude plugin uninstall` + `marketplace remove`.
- `kanban doctor` verifies the plugin is present via `claude plugin list`.

### Token scope (PAT)

The GitHub token lives in `~/.kanban/token` (mode `600`, off-git). It must be a
**fine-grained user PAT** scoped to `project` + `repo` only — enough for the daemon's
GraphQL board reads/writes and issue/PR ops. `kanban doctor` checks the token scope is
not over-broad.

> **Webhook ingestion is optional and out-of-band of this token.** Polling is the
> sole ingress required for the default native board (a local KanbanMateUI/CLI move
> writes `board.json` directly). If you also want a card dragged _on the GitHub board_
> to be re-ingested, run the `kanban serve` receiver (it verifies an HMAC against
> `~/.kanban/webhook_secret`) and register a GitHub webhook pointing at it — that
> webhook is created/managed on GitHub separately and does **not** require the daemon's
> PAT to carry `admin:org_hook`. See [how-it-works.md](how-it-works.md) and
> [configuration.md](configuration.md).

## Tier 3 — Per-repo (`kanban init` + `kanban seed`)

### `kanban init --repo owner/name`

```bash
kanban init --repo iznocorp/my-project
# Optionally specify a clone path and project title:
kanban init --repo iznocorp/my-project --clone ~/dev/my-project --title "My Board"
```

This command:

1. Creates (or finds) a GitHub Project v2 for the target repo.
2. Materialises the 11-column default from the bundled `columns.yml` template into the
   project's auto Status field.
3. Ensures the `wave:*` / `prio:*` labels exist on the repo.
4. Copies `columns.yml` into `<clone>/.claude/kanban/columns.yml` for agent use.
5. Registers the project in `~/.kanban/projects.json` (keyed by project node id).

Save the project node id printed by `init` — you need it for `seed`.

### `kanban seed ROADMAP.md`

```bash
kanban seed ROADMAP.md --repo iznocorp/my-project --project-id "PVT_xxx"
```

Parses the roadmap, creates issues in dependency order, rewrites `Depends on RPx` references
to real `#N` issue numbers, and adds each issue to the project (they land in Backlog).
Idempotent — re-running skips already-created issues.

## Uninstall

```bash
kanban uninstall            # pm2 delete + claude plugin uninstall + marketplace remove
kanban uninstall --no-pm2   # skip PM2 (host teardown only)
kanban reset                # archive entire ~/.kanban to ~/.kanban.bak-<timestamp>
```

`uninstall` is idempotent and leaves the `token` file in place (it may hold a real PAT).
Use `kanban reset` to archive the whole root.

## `kanban doctor` — health check reference

`kanban doctor` runs a 3-tier health check. Exits 0 when all pass, 1 when any fail.

| Check                  | Tier     | What it verifies                                       | Pass means                                |
| ---------------------- | -------- | ------------------------------------------------------ | ----------------------------------------- |
| Engine importable      | Host     | `import kanbanmate` succeeds                           | Package installed, no broken imports      |
| Daemon up              | Host     | PM2 process `kanban` is `online`                       | Polling loop is running                   |
| Daemon heartbeat fresh | Host     | Last daemon heartbeat < 2× poll interval               | Daemon is not wedged                      |
| Plugin present         | Claude   | `claude plugin list` includes `kanban`                 | `/kanban` skill available                 |
| Token reachable        | Per-repo | Token file exists + auth test succeeds                 | GitHub API calls work                     |
| Token scope            | Per-repo | Token has `project` + `repo`, **not** `admin:org_hook` | Least-privilege                           |
| Branch protection      | Per-repo | Default branch has protection rules                    | `kanban-move` can't force-push to main    |
| Non-root               | Host     | `os.geteuid() != 0`                                    | Daemon/agents run as the user             |
| Tmux socket ownership  | Host     | Socket belongs to current user                         | Agent sessions are killable/re-attachable |
