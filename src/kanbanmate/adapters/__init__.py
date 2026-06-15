"""Adapters: concrete implementations of the ``ports`` Protocols.

This layer performs the actual I/O — the GitHub urllib client, the tmux +
git-worktree workspace, and the filesystem state store. Adapters may import
``core`` and ``ports`` but must not import ``app``, ``daemon``, or ``cli``
(DESIGN §3.2 downward-only import rule).
"""
