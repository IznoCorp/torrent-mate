"""Locator-block assertion for Sub-phase 4.2a.

Pins the canonical disk-guard module path so any future refactor that
moves :func:`handle_disk_full` back into ``indexer/db.py`` (or anywhere
else) breaks loudly, preserving the Phase 4 disk-guard locator contract
recorded in ``docs/features/event-bus/plan/phase-04-cross-cutting-events.md``.
"""

from __future__ import annotations


def test_handle_disk_full_lives_in_disk_guard_module() -> None:
    """``handle_disk_full`` is importable from the canonical module and is callable."""
    from personalscraper.indexer._disk_guard import handle_disk_full

    assert callable(handle_disk_full)


def test_handle_disk_full_no_longer_lives_in_db_module() -> None:
    """``indexer/db.py`` must NOT re-export ``handle_disk_full``.

    The 4.2a sweep removed it; this test pins the post-sweep state so the
    Phase 5.2 cleanup audit can rely on a clean import surface.
    """
    import personalscraper.indexer.db as db_module

    assert not hasattr(db_module, "handle_disk_full")
