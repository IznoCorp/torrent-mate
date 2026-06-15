---
name: kanban
description: Invoke the KanbanMate orchestrator CLI — manage the Kanban board, daemon, and agent sessions from the command line.
---

# /kanban — KanbanMate CLI

This skill is a **thin wrapper** around the `kanban` CLI. **All logic lives in the engine.**
Invoke this skill with arguments that map directly to `kanban <subcommand> [options]`.

## Commands

| Command                                 | Purpose                                                                          |
| --------------------------------------- | -------------------------------------------------------------------------------- |
| `kanban install [host\|claude]`         | Idempotent 2-tier setup (host skeleton + PM2 daemon; Claude plugin registration) |
| `kanban uninstall`                      | Remove PM2 daemon + Claude plugin + host skeleton                                |
| `kanban init --repo <org/repo>`         | Create a fresh GitHub Projects v2 board for a repo                               |
| `kanban seed <ROADMAP.md>`              | Parse a roadmap file, create issues in dependency order, add to Backlog          |
| `kanban doctor`                         | 3-tier health check (engine / PM2 daemon / Claude plugin + GitHub token)         |
| `kanban run`                            | Start the polling daemon (PM2-supervised, non-root)                              |
| `kanban status`                         | Board summary — columns and ticket positions                                     |
| `kanban state [--json]`                 | Unified read-only view — board + agents + queue + recent events + health pill    |
| `kanban sessions`                       | List active tmux agent sessions                                                  |
| `kanban move <issue> <column> [--wait]` | Enqueue an operator move of a card to <column> (daemon applies it; cockpit)      |
| `kanban ticket create\|edit\|close`        | Enqueue operator ticket CRUD (daemon applies it; cockpit)                        |
| `kanban cancel <issue>`                 | Teardown an agent for a specific issue                                           |
| `kanban logs [issue]`                   | Structured JSONL agent logs                                                      |
| `kanban reset`                          | Archive old `~/.kanban/` state                                                   |
| `kanban poll --once`                    | Single tick (no loop) — useful for debugging                                     |

## Usage

When a user invokes `/kanban <args>`, run:

```bash
kanban <args>
```

The `kanban` CLI is installed via the engine package (`pip install kanbanmate`). It must be on `$PATH`.
If `kanban` is not found, advise the user to run `kanban install` first or verify their Python environment.
