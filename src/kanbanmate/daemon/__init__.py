"""Daemon entrypoint: the long-running background poll loop.

This layer hosts the blocking ``kanban run`` loop (single-instance flock,
SIGTERM-aware, config hot-reload). As an entrypoint it sits at the top of the
import hierarchy and may import lower layers freely (DESIGN §3.2).
"""
