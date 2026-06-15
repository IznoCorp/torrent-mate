# ROADMAP

Deferred items from DESIGN §13. These are out of scope for v1.0 but are recognised as
desirable future enhancements.

## Optional webhook ingress adapter

For anyone wanting sub-second latency, a `kanban serve` webhook receiver could slot in
behind the same `BoardReader` boundary. It would receive GitHub webhook events, translate
them into the same `Transition` objects the poll loop produces, and feed them to
`decide → execute`. Polling is the default and only supported ingress in v1 — the webhook
adapter is an optional acceleration layer, not a replacement for the polling model.

## GitHub App upgrade

Currently KanbanMate uses a **user PAT** (fine-grained, scoped `project` + `repo`). A GitHub
App would provide:

- **Identity-keyed anti-loop** — the bot's own identity rather than the user's, making it
  easier to distinguish bot moves from human moves in the GitHub UI.
- **Clean attribution** — comments and commits appear as the App, not the user.
- **Short-lived scoped tokens** — per-installation tokens with automatic expiry, removing the
  long-lived PAT from `~/.kanban/token`.

## Multi-org support

Currently `kanban init` registers projects keyed by project node id in a flat
`projects.json`. Multi-org would add org-level namespacing and the ability to run one daemon
per org with separate configs.

## MCP helpers

The current agent helpers (`kanban-comment`, `kanban-move`, etc.) use the urllib GitHub
client directly. Future MCP (Model Context Protocol) helpers could expose the board as a
rich MCP resource, letting the agent reason about the board state without shelling out to
helper bins.

## Auto-merge

Permanently forbidden. Merge is always a human action. This item is listed for completeness
— it will never be implemented.
