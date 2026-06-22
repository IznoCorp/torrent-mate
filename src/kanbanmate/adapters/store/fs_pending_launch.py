"""Restart-durable pending-launch breadcrumb for the filesystem state store (#55).

The daemon's diff baseline (``columns_by_item`` in :class:`~kanbanmate.app.tick.PersistedState`) is
IN-MEMORY only and wiped on a restart (#20 — the board is the source of truth, the baseline rebuilds
from it). That makes a card already sitting in a column look first-contact (``from=None``) after a
restart, which ``decide`` treats as a recording NOOP, never a launch. A launch-bearing operator move
(e.g. ``ReadyToDev → PrepareFeature``) is detected by ``diff`` on the tick AFTER the move drains, so
a restart in that window silently DROPS the launch (the live #55 bug).

This mixin persists a tiny ``pending_launch/<item_id>`` marker = ``{"from", "to", "ts"}`` for exactly
such an edge. The tick OVERLAYS the recorded ``from`` column back onto the wiped baseline (only for
an item still parked in ``to``), re-creating the genuine transition so the existing
``diff → decide → LAUNCH`` path fires unchanged — for ONLY the items with an explicit breadcrumb,
never all cards (no restart storm; the #20 in-memory baseline decision stands).

Keyed by the ``item_id`` (the diff-baseline key) — a deliberate divergence from the issue-keyed
agent breadcrumbs in :mod:`kanbanmate.adapters.store.fs_breadcrumbs` (item_id-as-filename is already
established by the ``health/last/<item_id>`` markers). Layering: imports only the standard library +
the :class:`~kanbanmate.ports.store.PendingLaunch` value type.
"""

from __future__ import annotations

import json
from pathlib import Path

from kanbanmate.ports.store import PendingLaunch

# A pending-launch breadcrumb is honoured for this long. Generous on purpose: it must outlive a
# daemon restart + deploy (seconds–minutes) AND brief launch blocks (PAUSE / the 3600 s move
# rate-limit window) so the launch still fires when the block clears, yet age out an abandoned
# breadcrumb. DISTINCT from the advance/done breadcrumb TTLs (300 s / 1800 s) and the reaper
# ``HEARTBEAT_TTL`` (1800 s) — these govern different subsystems and must stay separate knobs.
_PENDING_LAUNCH_TTL = 3600.0


class PendingLaunchMixin:
    """Restart-durable pending-launch breadcrumbs (mixed into the fs state store, #55).

    Operates on the host store's ``root`` directory. The ``pending_launch/`` directory is created by
    the host store's ``__init__`` (so an empty store tree is well-formed); reads degrade gracefully
    on a missing/poison marker.

    Attributes:
        root: The state-store root directory (set by the host store's ``__init__``).
    """

    root: Path

    @staticmethod
    def _unlink(path: Path) -> None:  # pragma: no cover - provided by the host store
        """Remove *path* if it exists; no-op otherwise (host-store helper).

        Declared here only so mypy sees the member the mixin relies on; the concrete implementation
        is :meth:`~kanbanmate.adapters.store.fs_store.FsStateStore._unlink`.
        """
        raise NotImplementedError

    def _pending_launch_path(self, item_id: str) -> Path:
        """Return the filesystem path for ``item_id``'s pending-launch breadcrumb (item_id-keyed)."""
        return self.root / "pending_launch" / item_id

    def record_pending_launch(
        self, item_id: str, *, from_col: str, to_col: str, now: float
    ) -> None:
        """Persist ``<root>/pending_launch/<item_id>`` = ``{"from", "to", "ts"}`` (#55).

        See :meth:`~kanbanmate.ports.store.StateStore.record_pending_launch`.

        Args:
            item_id: The ``ProjectV2Item`` node id (the diff-baseline / breadcrumb key).
            from_col: The transition origin column key, re-created on the baseline post-restart.
            to_col: The launch-bearing destination column key.
            now: The wall-clock timestamp written into the breadcrumb (the TTL anchor).
        """
        self._pending_launch_path(item_id).write_text(
            json.dumps({"from": from_col, "to": to_col, "ts": now})
        )

    def pending_launches(self, *, now: float) -> dict[str, PendingLaunch]:
        """Return the live (non-expired) pending-launch breadcrumbs keyed by ``item_id`` (#55).

        See :meth:`~kanbanmate.ports.store.StateStore.pending_launches`. Corrupt markers and entries
        older than :data:`_PENDING_LAUNCH_TTL` are skipped (degrade, never raise — a poison file must
        never wedge the tick).

        Args:
            now: The wall-clock timestamp the TTL is measured against.

        Returns:
            ``{item_id: PendingLaunch}`` for every live breadcrumb.
        """
        out: dict[str, PendingLaunch] = {}
        directory = self.root / "pending_launch"
        if not directory.is_dir():
            return out
        for path in directory.iterdir():
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text())
                ts = float(data["ts"])
                from_col = str(data["from"])
                to_col = str(data["to"])
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue  # poison marker → skip (a corrupt file must never wedge the tick)
            if (now - ts) > _PENDING_LAUNCH_TTL:
                continue
            out[path.name] = PendingLaunch(
                item_id=path.name, from_col=from_col, to_col=to_col, ts=ts
            )
        return out

    def clear_pending_launch(self, item_id: str) -> None:
        """Unlink ``<root>/pending_launch/<item_id>``; no-op when absent (#55).

        See :meth:`~kanbanmate.ports.store.StateStore.clear_pending_launch`.

        Args:
            item_id: The ``ProjectV2Item`` node id whose breadcrumb to clear (the key).
        """
        self._unlink(self._pending_launch_path(item_id))
