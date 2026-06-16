"""KanbanMate: a reusable Kanban orchestrator on GitHub Projects v2.

A single background daemon polls a GitHub Projects board and reconciles it
against persisted state, firing autonomous Claude Code agents in isolated
tmux + git-worktree workspaces. There is no webhook and no external workflow
engine.
"""

__version__ = "0.1.1"
