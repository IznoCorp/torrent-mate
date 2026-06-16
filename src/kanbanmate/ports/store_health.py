"""Per-card "Health" single-select field state port (the health-field custom chip).

Extracted from :mod:`kanbanmate.ports.store` (LOC-ceiling headroom — store.py sat at 996/1000, so
adding the Candidate-3 ``prune_item_health`` stub there would have breached the hard ceiling). The
:class:`~kanbanmate.ports.store.StateStore` composes this Protocol (``StateStore(HealthStateStore,
IntentStore, Protocol)``), so the concrete filesystem adapter
(:mod:`kanbanmate.adapters.store.fs_health_state`) satisfies the SAME surface as before — only its
declaration moved here.

The Health field carries the operator's own vocabulary
(``INACTIVE / BLOCKED / WAITING / ACTIVE / COMPLETE``) as native chips on each card, maintained by
the daemon ON CHANGE (a workaround for GitHub's fixed status-update pill enum). These markers cache
the board-wide field id / options + each card's last-written value so the on-change step writes only
on a real change.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class HealthStateStore(Protocol):
    """Persisted per-card Health field markers (board-wide ids + per-card last-written values)."""

    def get_health_project_id(self) -> str | None:
        """Return the project id the persisted Health field markers belong to, or ``None``.

        The board-wide field-id/options markers carry no project binding; this records
        WHICH project they belong to so the Health step can detect a registry re-point and
        drop the stale ids (the rebind guard). ``None`` means never-bound (degrade →
        treated as a project change → markers cleared + a fresh ensure).
        """
        ...

    def set_health_project_id(self, project_id: str | None) -> None:
        """Persist the project id the Health field markers belong to, or clear it (``None``)."""
        ...

    def get_health_field_id(self) -> str | None:
        """Return the persisted Health single-select field node id, or ``None`` when absent.

        Backs the cross-restart cache: when present (with :meth:`get_health_options`) the
        Health step reuses the field WITHOUT a network read; when absent it re-ensures the
        field via the reporter. Degrades to ``None`` on an unreadable marker.
        """
        ...

    def set_health_field_id(self, field_id: str | None) -> None:
        """Persist the Health field node id atomically, or clear it (``None`` → UNLINK)."""
        ...

    def get_health_options(self) -> dict[str, str]:
        """Return the persisted ``{HEALTH_NAME: option_id}`` map, or ``{}`` when absent.

        The option ids needed to set a card's Health value. Degrades to ``{}`` on an
        absent/corrupt map — a poison file must never wedge the Health step.
        """
        ...

    def set_health_options(self, options: dict[str, str]) -> None:
        """Persist the ``{HEALTH_NAME: option_id}`` map atomically.

        Args:
            options: The option-name → option-id map to persist.
        """
        ...

    def get_item_health(self, item_id: str) -> str | None:
        """Return the LAST-WRITTEN Health value for card ``item_id``, or ``None``.

        The on-change diff key: the Health step writes a card only when its computed value
        DIFFERS from this. ``None`` means none has been written yet (or the marker is
        unreadable — degrade → the next compute is treated as a change).

        Args:
            item_id: The ``ProjectV2Item`` node id whose last-written value to read.
        """
        ...

    def set_item_health(self, item_id: str, value: str | None) -> None:
        """Persist card ``item_id``'s last-written Health value atomically, or clear it.

        Args:
            item_id: The ``ProjectV2Item`` node id whose marker to write.
            value: The Health value to record, or ``None`` to UNLINK the marker.
        """
        ...

    def clear_health_markers(self) -> None:
        """Drop the Health field id + options + ALL per-card last-written markers.

        Called on a project rebind (the registry re-pointed at a new board): the
        board-wide field id/options and every per-card last-written marker belong to the
        OLD project and must not leak into the new one. The ``project_id`` marker itself is
        re-bound separately by the caller.
        """
        ...

    def prune_item_health(self, live_item_ids: Iterable[str]) -> None:
        """Garbage-collect per-card Health markers for cards no longer on the board (Candidate 3).

        The on-change Health step writes a per-card ``health/last/<item>`` marker for every
        snapshot card and never removed one when a card LEFT the board — only a project rebind
        (:meth:`clear_health_markers`) dropped them ALL, so the marker directory grew unbounded.
        This bounded GC unlinks any per-card marker whose item id is NOT in ``live_item_ids`` (the
        current snapshot), keeping the directory proportional to the live board. FAIL-SOFT: a
        missing directory is a no-op and any per-file unlink error is swallowed — the GC must never
        raise into the tick.

        Args:
            live_item_ids: The ``ProjectV2Item`` node ids currently on the board (the snapshot).
        """
        ...
