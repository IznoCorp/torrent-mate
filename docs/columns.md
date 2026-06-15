# `columns.yml` reference

The board layout is defined by a per-repo `columns.yml` file, copied by `kanban init` into
`<clone>/.claude/kanban/columns.yml`. The engine is generic — the column definitions below
live **only** in the template and can be edited per project.

## Field reference

Each entry in the `columns` sequence is a mapping. Required fields:

| Field  | Type     | Description                                                                                              |
| ------ | -------- | -------------------------------------------------------------------------------------------------------- |
| `key`  | `string` | Stable machine-readable identifier, no spaces (e.g. `InProgress`). Used internally by diff/decide/state. |
| `name` | `string` | Human-readable label shown in GitHub Projects v2 (e.g. `In Progress`).                                   |

Optional flags that determine the **column class** (DESIGN §8):

| Flag             | Value      | Effect                                                                                   |
| ---------------- | ---------- | ---------------------------------------------------------------------------------------- |
| `triggers_agent` | `true`     | **Agent column** — moving a card here launches a Claude Code agent (`LaunchAction`)      |
| `action`         | `teardown` | **Reactive column** — moving a card here runs a side-effect (`TeardownAction`), no agent |
| (neither)        | —          | **Inert column** — human gate or terminal; no automatic action                           |

The column class is resolved by `load_columns()` in `kanbanmate.core.columns`:

1. If `triggers_agent` is truthy → `ColumnClass.AGENT` (the agent flag wins — an agent column
   is the strongest contract).
2. Else if `action == "teardown"` → `ColumnClass.REACTIVE`.
3. Otherwise → `ColumnClass.INERT`.

### Agent-column extra fields

When `triggers_agent: true`, these additional fields configure the agent launch:

| Field                | Type      | Default | Description                                                                                                                                                                                           |
| -------------------- | --------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prompt`             | `string`  | —       | The Claude Code prompt invoked when the agent starts (e.g. `/implement:phase`).                                                                                                                       |
| `permission_profile` | `string`  | `safe`  | Permission profile materialised into the worktree's `.claude/settings.json`. `safe` = concrete `permissions.allow`; `trusted` = broader. Both ban `gh pr merge`, `git push --force`, history rewrite. |
| `interactive_only`   | `boolean` | `false` | When `true`, the agent only launches if the daemon detects an attached terminal (interactive columns like brainstorming). When `false`, the agent fires unattended.                                   |

## Default template — the 11 shipped columns

The bundled template at `src/kanbanmate/assets/columns.yml.tmpl` (copied by `kanban init`)
defines these columns. The `implement:*` prompts are defaults — edit them to match your
project's skill set.

| #   | Key          | Name         | Class        | Details                                                                                      |
| --- | ------------ | ------------ | ------------ | -------------------------------------------------------------------------------------------- |
| 1   | `Backlog`    | Backlog      | inert        | Manual entry point. Also the reset target from Cancel (`Cancel → Backlog` is `ResetAction`). |
| 2   | `Spec`       | Spec         | inert        | Human-gate: brainstorming is interactive.                                                    |
| 3   | `Planned`    | Planned      | inert        | Human-gate: create-branch is interactive.                                                    |
| 4   | `ReadyToDev` | Ready to dev | inert        | Human-gate: final go/no-go before development.                                               |
| 5   | `InProgress` | In Progress  | **agent**    | Unattended-safe. Prompt: `/implement:phase`. Profile: `trusted`.                             |
| 6   | `PRCI`       | PR/CI        | **agent**    | Prompt: `/implement:feature-pr`. Profile: `trusted`.                                         |
| 7   | `Review`     | Review       | **agent**    | Prompt: `/implement:pr-review`. Profile: `trusted`. No auto-merge.                           |
| 8   | `Merge`      | Merge        | inert        | **Human only** — the bot cannot reach it. Merge is always a human action.                    |
| 9   | `Cancel`     | Cancel       | **reactive** | `action: teardown`. Moving here kills the session. Cancel → Backlog = resume reset.          |
| 10  | `Done`       | Done         | inert        | Terminal column for completed work.                                                          |
| 11  | `Blocked`    | Blocked      | inert        | The daemon or reaper parks stalled/broken tickets here.                                      |

### Flow diagram

```
Backlog → Spec → Planned → ReadyToDev → InProgress → PRCI → Review → Merge → Done
                                              ↓
                                           Cancel ──→ Backlog (reset)
                                              ↓
                                          Blocked
```

- Agent columns (5-7) are the **only** columns that trigger agent launches.
- `Cancel` is the only reactive column — it tears down the running agent.
- All other columns are inert — human gates or terminal states.
- `kanban-move` (agent helper) refuses moves to agent columns (anti-loop guard).
- `Merge` is inert so the bot can never move a card there — merge is always human.

## Customising columns

1. Edit `<clone>/.claude/kanban/columns.yml`.
2. Sync the GitHub Project columns to match (rename/add/remove via GitHub UI — the engine
   matches by `name`).
3. Restart the daemon (`pm2 restart kanban`) or wait for the next config reload (mtime-based,
   at the top of a tick).

The engine's `load_columns()` validates that every entry has a non-empty `key` and `name`.
Duplicate keys are an error (the last wins in YAML but the engine raises).
