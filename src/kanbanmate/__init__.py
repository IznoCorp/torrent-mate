"""KanbanMate: a reusable Kanban orchestrator on GitHub Projects v2.

A single background daemon polls one or more GitHub Projects boards (across one or
more orgs) and reconciles each against persisted state, firing autonomous Claude
Code agents in isolated tmux + git-worktree workspaces. Polling is the always-on
fallback; an optional ``kanban serve`` webhook receiver (a plain shared-secret HMAC
front-door — no GitHub App) nudges the daemon for sub-second reaction. There is no
external workflow engine.
"""

__version__ = "0.20.1"
