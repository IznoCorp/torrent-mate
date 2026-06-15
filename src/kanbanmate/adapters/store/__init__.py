"""Filesystem state-store adapter.

Implements the :class:`kanbanmate.ports.store.StateStore` Protocol with atomic
``O_EXCL`` + ``flock`` writes to a configurable root directory (default
``~/.kanban/``). Ported from the PoC ``state.py`` persistence layer (DESIGN §6).
"""
