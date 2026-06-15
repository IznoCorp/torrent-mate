"""Rolling project status-update state for the filesystem state store (phase-24).

Extracted from :mod:`kanbanmate.adapters.store.fs_store` (phase-24 §24.2 LOC
budget — ``fs_store.py`` had reached the 1000-LOC hard ceiling, so the new
status-update markers could not land there without lifting a self-contained
concern out; mirrors the earlier
:mod:`kanbanmate.adapters.github._transport` transport extraction). This is a
behaviour-preserving move: the markers, their atomic-write discipline, and the
poison-file degrade are byte-identical to the rest of the store.

The board carries ONE *rolling* GitHub Project status update (the live
dashboard, see :mod:`kanbanmate.core.status_update`). This module persists the
three pieces of state the on-change reporter needs, all BOARD-WIDE (not
per-issue) under ``<root>/status/``:

* ``project_id``   — the project node id the persisted ``update_id`` /
  ``body_hash`` belong to (phase-33). The markers are BOARD-WIDE, not
  per-project, so after the operator re-points the registry at a NEW project the
  stale id (pointing at the OLD board) and stale hash (suppressing the post) must
  be ignored; the reporter compares this against the live project id and treats a
  mismatch as a first post.
* ``update_id``    — the rolling status update's node id (so a later refresh
  ``update``s it rather than creating a new pill).
* ``body_hash``    — a hash of the last-posted body (on-change diffing: the
  reporter renders every tick but only mutates GitHub when the body changes).
* ``last_status``  — the GitHub status ENUM last posted. GitHub only refreshes a
  project's denormalised status PILL on a *create*, never on an in-place
  ``update``; the reporter re-creates the rolling update when the enum changes,
  and this marker records the last-posted enum so a change is detectable.
* ``events.json``  — a bounded ring of the ≤10 most recent significant events,
  oldest-first, rendered newest-first by the dashboard.

Every read degrades to ``None`` / ``()`` on a poison file (the
:meth:`kanbanmate.adapters.store.fs_store.FsStateStore.load` pattern) so a bad
marker can never wedge the dashboard, and every write is atomic (temp-file +
:func:`os.replace`) so a concurrent reader never observes a torn marker.

Layering: this module sits in ``adapters/store`` (same layer as the store) and
imports only the standard library, so :mod:`.fs_store` can mix it in without a
cycle.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

# The status-update dashboard keeps a bounded ring of the most recent significant
# events (phase-24 §24.2). Appending past this cap drops the oldest events, so
# only the newest ``_STATUS_EVENT_RING_CAP`` are ever persisted/rendered.
_STATUS_EVENT_RING_CAP = 10


class StatusUpdateStateMixin:
    """Board-wide rolling status-update state (mixed into the fs state store).

    Operates on the host store's ``root`` directory (declared below). The host
    (:class:`~kanbanmate.adapters.store.fs_store.FsStateStore`) creates the
    ``<root>/status/`` directory in its ``__init__`` and inherits these methods,
    so the public ``StateStore`` surface is unchanged by the extraction.

    Attributes:
        root: The state-store root directory (set by the host store's ``__init__``).
    """

    root: Path

    def get_status_update_id(self) -> str | None:
        """Return the persisted rolling status-update node id, or ``None``.

        Returns:
            The stored ``ProjectV2StatusUpdate`` node id, or ``None`` when the
            marker is absent or unreadable (degrade → a fresh ``create``).
        """
        return self._read_status_marker(self._status_update_id_path())

    def set_status_update_id(self, status_update_id: str | None) -> None:
        """Persist the rolling status-update node id atomically, or clear it.

        Args:
            status_update_id: The node id to persist, or ``None`` to UNLINK the
                marker (the stale-id re-create path).
        """
        self._write_status_marker(self._status_update_id_path(), status_update_id)

    def get_status_project_id(self) -> str | None:
        """Return the project id the persisted rolling status state belongs to, or ``None``.

        The board-wide ``update_id`` / ``body_hash`` markers carry no project
        binding of their own; this marker records WHICH project they belong to so
        the reporter can detect a registry re-point (a new project) and ignore the
        stale id+hash (phase-33).

        Returns:
            The stored project node id, or ``None`` when the marker is absent or
            unreadable (degrade → treated as a project change → a fresh post).
        """
        return self._read_status_marker(self._status_project_id_path())

    def set_status_project_id(self, project_id: str | None) -> None:
        """Persist the project id the rolling status state belongs to, or clear it.

        Args:
            project_id: The project node id to bind the status markers to, or
                ``None`` to UNLINK the marker.
        """
        self._write_status_marker(self._status_project_id_path(), project_id)

    def get_status_body_hash(self) -> str | None:
        """Return the hash of the last-posted status-update body, or ``None``.

        Returns:
            The stored body hash, or ``None`` when the marker is absent or
            unreadable (degrade → the next render re-posts).
        """
        return self._read_status_marker(self._status_body_hash_path())

    def set_status_body_hash(self, body_hash: str | None) -> None:
        """Persist the last-posted status-update body hash atomically, or clear it.

        Args:
            body_hash: The body hash to persist, or ``None`` to UNLINK the marker.
        """
        self._write_status_marker(self._status_body_hash_path(), body_hash)

    def get_status_last_enum(self) -> str | None:
        """Return the GitHub status ENUM last posted for the rolling update, or ``None``.

        Returns:
            The last-posted ``ProjectV2StatusUpdateStatus`` value, or ``None``
            when the marker is absent or unreadable (degrade → the next post is
            treated as an enum change → a re-create that moves the project pill).
        """
        return self._read_status_marker(self._status_last_enum_path())

    def set_status_last_enum(self, status: str | None) -> None:
        """Persist the last-posted status ENUM atomically, or clear it.

        Args:
            status: The ``ProjectV2StatusUpdateStatus`` value to persist, or
                ``None`` to UNLINK the marker (e.g. on a project rebind).
        """
        self._write_status_marker(self._status_last_enum_path(), status)

    def get_status_override_enum(self) -> str | None:
        """Return the OPERATOR pill override enum (cockpit ``pill set-health``), or ``None``.

        When set, the rolling-dashboard render forces this enum (winning over the computed health)
        until the operator clears it — letting an operator pin the pill (e.g. ``WAITING`` during an
        incident) regardless of orchestration state.
        """
        return self._read_status_marker(self._status_override_enum_path())

    def set_status_override_enum(self, status: str | None) -> None:
        """Persist the operator pill override enum atomically, or clear it (``pill clear``)."""
        self._write_status_marker(self._status_override_enum_path(), status)

    def get_status_override_note(self) -> str | None:
        """Return the OPERATOR dashboard note (cockpit ``pill note``), or ``None``."""
        return self._read_status_marker(self._status_override_note_path())

    def set_status_override_note(self, note: str | None) -> None:
        """Persist the operator dashboard note atomically, or clear it."""
        self._write_status_marker(self._status_override_note_path(), note)

    def append_status_event(self, event: Mapping[str, object]) -> None:
        """Append one event to the bounded recent-events ring (≤10 newest kept).

        Reads the current ring, appends ``event``, truncates to the
        :data:`_STATUS_EVENT_RING_CAP` newest entries, then writes atomically — so
        the ring never grows past the cap and always keeps the most recent events.

        Args:
            event: A JSON-serialisable mapping (typically ``ts`` / ``kind`` /
                ``issue`` / ``detail``).
        """
        ring = list(self.read_status_events())
        ring.append(dict(event))
        # Keep only the newest cap entries (drop the oldest from the front).
        if len(ring) > _STATUS_EVENT_RING_CAP:
            ring = ring[-_STATUS_EVENT_RING_CAP:]
        self._atomic_write(self._status_events_path(), json.dumps(ring))

    def read_status_events(self) -> tuple[dict[str, object], ...]:
        """Return the recent-events ring, oldest-first (≤ the 10-event cap).

        Returns:
            An immutable tuple of the stored event dicts (≤10), oldest-first, or
            ``()`` when the ring is absent, corrupt, or not a JSON list (degrade,
            with a named breadcrumb on a corrupt file — never wedges the dashboard).
        """
        path = self._status_events_path()
        if not path.exists():
            return ()
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as err:
            # A poison ring file must not wedge the dashboard — degrade to empty but
            # name it on stderr so the corruption is visible (the state-file pattern).
            print(f"kanban: skipping corrupt status events ring {path}: {err}", file=sys.stderr)
            return ()
        if not isinstance(data, list):
            return ()
        # Keep only dict-shaped entries (defensive against a hand-edited ring).
        return tuple(item for item in data if isinstance(item, dict))

    # ------------------------------------------------------------------
    # Marker paths (board-wide, under <root>/status/) + atomic primitives.
    # ------------------------------------------------------------------

    def _status_project_id_path(self) -> Path:
        """Return the marker binding the status state to a project (``status/project_id``)."""
        return self.root / "status" / "project_id"

    def _status_update_id_path(self) -> Path:
        """Return the rolling status-update node-id marker path (``status/update_id``)."""
        return self.root / "status" / "update_id"

    def _status_body_hash_path(self) -> Path:
        """Return the last-posted-body hash marker path (``status/body_hash``)."""
        return self.root / "status" / "body_hash"

    def _status_last_enum_path(self) -> Path:
        """Return the last-posted status-enum marker path (``status/last_status``)."""
        return self.root / "status" / "last_status"

    def _status_override_enum_path(self) -> Path:
        """Return the operator pill-override enum marker path (``status/override_status``)."""
        return self.root / "status" / "override_status"

    def _status_override_note_path(self) -> Path:
        """Return the operator dashboard-note marker path (``status/override_note``)."""
        return self.root / "status" / "override_note"

    def _status_events_path(self) -> Path:
        """Return the bounded recent-events ring path (``status/events.json``)."""
        return self.root / "status" / "events.json"

    @staticmethod
    def _read_status_marker(path: Path) -> str | None:
        """Read a board-wide status text marker, degrading to ``None``.

        Args:
            path: The marker file (``update_id`` or ``body_hash``).

        Returns:
            The marker's text, or ``None`` when absent, empty, or unreadable.
        """
        if not path.exists():
            return None
        try:
            return path.read_text() or None
        except OSError:
            return None

    def _write_status_marker(self, path: Path, value: str | None) -> None:
        """Persist a board-wide status text marker atomically, or clear it.

        Args:
            path: The marker file (``update_id`` or ``body_hash``).
            value: The text to persist, or ``None`` to UNLINK the marker.
        """
        if value is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            return
        self._atomic_write(path, value)

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        """Write *text* to *path* atomically via temp-file + ``os.replace``.

        A concurrent reader never observes a torn write — the same atomicity
        discipline the rest of the store uses. The temp file is created beside the
        target (same directory) so the rename stays on one filesystem.

        Args:
            path: The destination file.
            text: The text to write.
        """
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(text)
        os.replace(tmp, path)
