"""Per-card Health field state for the filesystem state store (health-field).

Extracted from :mod:`kanbanmate.adapters.store.fs_store` (LOC budget — the store had
reached the 1000-LOC hard ceiling, so the Health markers could not land there without
lifting a self-contained concern out; mirrors the earlier
:mod:`kanbanmate.adapters.store.fs_status_state` extraction). The markers, their atomic
write discipline, and the poison-file degrade are byte-identical to the rest of the
store.

The daemon maintains a per-card "Health" single-select field (the custom chip carrying
the operator's own vocabulary, see :mod:`kanbanmate.core.health`). This module persists,
all BOARD-WIDE under ``<root>/health/`` plus one marker per card:

* ``project_id``   — the project node id the persisted field-id/options belong to (the
  rebind guard, mirroring :mod:`.fs_status_state`); drops stale ids when the registry is
  re-pointed at a new board.
* ``field_id``     — the resolved/created Health single-select field node id, so a restart
  re-reads it without a second create attempt.
* ``options.json`` — ``{HEALTH_NAME: option_id}``; the option ids needed to set a card's
  value (the cross-restart cache the daemon reuses every tick).
* ``last/<item_id>`` — the LAST-WRITTEN Health value for that card, so the tick only
  issues a set mutation when a card's computed value CHANGES (the on-change discipline —
  no per-tick API spam).

Every read degrades to ``None`` / ``{}`` on a poison file and every write is atomic
(temp-file + :func:`os.replace`) so a concurrent reader never observes a torn marker —
the same discipline :mod:`.fs_status_state` uses.

Layering: this module sits in ``adapters/store`` (same layer as the store) and imports
only the standard library, so :mod:`.fs_store` can mix it in without a cycle.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


class HealthStateMixin:
    """Per-card Health field state (mixed into the fs state store).

    Operates on the host store's ``root`` directory. The host
    (:class:`~kanbanmate.adapters.store.fs_store.FsStateStore`) creates the
    ``<root>/health/`` + ``<root>/health/last/`` directories in its ``__init__`` and
    inherits these methods, so the public ``StateStore`` surface is unchanged by the
    extraction.

    Attributes:
        root: The state-store root directory (set by the host store's ``__init__``).
    """

    root: Path

    # ------------------------------------------------------------------
    # Board-wide field metadata (project binding + field id + option map).
    # ------------------------------------------------------------------

    def get_health_project_id(self) -> str | None:
        """Return the project id the persisted Health field markers belong to, or ``None``.

        The field-id/options markers carry no project binding of their own; this records
        WHICH project they belong to so the reporter can detect a registry re-point and
        drop the stale ids (the rebind guard, mirroring the status markers).

        Returns:
            The stored project node id, or ``None`` when absent/unreadable (degrade →
            treated as a project change → markers cleared + a fresh field ensure).
        """
        return self._read_health_marker(self._health_project_id_path())

    def set_health_project_id(self, project_id: str | None) -> None:
        """Persist the project id the Health field markers belong to, or clear it.

        Args:
            project_id: The project node id to bind the markers to, or ``None`` to UNLINK.
        """
        self._write_health_marker(self._health_project_id_path(), project_id)

    def get_health_field_id(self) -> str | None:
        """Return the persisted Health single-select field node id, or ``None``.

        Returns:
            The stored field node id, or ``None`` when absent/unreadable (degrade → the
            reporter re-ensures the field via the network).
        """
        return self._read_health_marker(self._health_field_id_path())

    def set_health_field_id(self, field_id: str | None) -> None:
        """Persist the Health field node id atomically, or clear it.

        Args:
            field_id: The field node id to persist, or ``None`` to UNLINK the marker.
        """
        self._write_health_marker(self._health_field_id_path(), field_id)

    def get_health_options(self) -> dict[str, str]:
        """Return the persisted ``{HEALTH_NAME: option_id}`` map, or ``{}`` when absent.

        Returns:
            The stored option map, or ``{}`` when the marker is absent, corrupt, or not a
            JSON object (degrade — a poison map must never wedge the Health step).
        """
        path = self._health_options_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as err:
            # A poison options file must not wedge the Health step — degrade to empty but
            # name it on stderr so the corruption is visible (the state-file pattern).
            print(f"kanban: skipping corrupt health options {path}: {err}", file=sys.stderr)
            return {}
        if not isinstance(data, dict):
            return {}
        # Coerce to {str: str} defensively against a hand-edited map.
        return {str(k): str(v) for k, v in data.items()}

    def set_health_options(self, options: dict[str, str]) -> None:
        """Persist the ``{HEALTH_NAME: option_id}`` map atomically.

        Args:
            options: The option-name → option-id map to persist.
        """
        self._atomic_write_health(self._health_options_path(), json.dumps(options))

    # ------------------------------------------------------------------
    # Per-card last-written Health value (the on-change diff key).
    # ------------------------------------------------------------------

    def get_item_health(self, item_id: str) -> str | None:
        """Return the LAST-WRITTEN Health value for card ``item_id``, or ``None``.

        Args:
            item_id: The ``ProjectV2Item`` node id whose last-written value to read.

        Returns:
            The stored Health value, or ``None`` when none has been written yet (or the
            marker is unreadable — degrade → the next compute is treated as a change).
        """
        return self._read_health_marker(self._health_item_path(item_id))

    def set_item_health(self, item_id: str, value: str | None) -> None:
        """Persist card ``item_id``'s last-written Health value atomically, or clear it.

        Args:
            item_id: The ``ProjectV2Item`` node id whose marker to write.
            value: The Health value to record, or ``None`` to UNLINK the marker.
        """
        self._write_health_marker(self._health_item_path(item_id), value)

    def clear_health_markers(self) -> None:
        """Drop the Health field id + options + ALL per-card last-written markers.

        Called on a project rebind (the registry re-pointed at a new board): the
        board-wide field id/options and every ``last/<item>`` marker belong to the OLD
        project and must not leak into the new one. The ``project_id`` marker itself is
        left for the caller to re-bind. Poison-tolerant: a missing file is ignored.
        """
        self._write_health_marker(self._health_field_id_path(), None)
        self._write_health_marker(self._health_options_path(), None)
        last_dir = self._health_last_dir()
        if last_dir.exists():
            for marker in last_dir.iterdir():
                try:
                    marker.unlink()
                except FileNotFoundError:
                    pass

    # ------------------------------------------------------------------
    # Marker paths (board-wide + per-card, under <root>/health/) + primitives.
    # ------------------------------------------------------------------

    def _health_project_id_path(self) -> Path:
        """Return the marker binding the Health markers to a project (``health/project_id``)."""
        return self.root / "health" / "project_id"

    def _health_field_id_path(self) -> Path:
        """Return the Health field node-id marker path (``health/field_id``)."""
        return self.root / "health" / "field_id"

    def _health_options_path(self) -> Path:
        """Return the Health option-map marker path (``health/options.json``)."""
        return self.root / "health" / "options.json"

    def _health_last_dir(self) -> Path:
        """Return the per-card last-written-value directory (``health/last/``)."""
        return self.root / "health" / "last"

    def _health_item_path(self, item_id: str) -> Path:
        """Return the per-card last-written-value marker path for ``item_id``.

        **Sanitisation INVARIANT.** GraphQL node ids (``PVTI_...``) are base64-ish and
        already filesystem-safe, but the id is sanitised defensively with the same
        alphanumeric/``._-`` filter :meth:`FsStateStore._retry_path` uses (any other
        character → ``_``), so a pathological id can never escape ``health/last/``. An
        empty/all-replaced id defaults to ``"_"``.

        Args:
            item_id: The ``ProjectV2Item`` node id to compute a marker path for.

        Returns:
            The marker path under ``health/last/``.
        """
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in item_id) or "_"
        return self._health_last_dir() / safe

    @staticmethod
    def _read_health_marker(path: Path) -> str | None:
        """Read a Health text marker, degrading to ``None``.

        Args:
            path: The marker file.

        Returns:
            The marker's text, or ``None`` when absent, empty, or unreadable.
        """
        if not path.exists():
            return None
        try:
            return path.read_text() or None
        except OSError:
            return None

    def _write_health_marker(self, path: Path, value: str | None) -> None:
        """Persist a Health text marker atomically, or clear it.

        Args:
            path: The marker file.
            value: The text to persist, or ``None`` to UNLINK the marker.
        """
        if value is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            return
        self._atomic_write_health(path, value)

    @staticmethod
    def _atomic_write_health(path: Path, text: str) -> None:
        """Write ``text`` to ``path`` atomically via temp-file + ``os.replace``.

        A concurrent reader never observes a torn write — the same atomicity discipline
        the rest of the store uses. The temp file is created beside the target so the
        rename stays on one filesystem.

        Args:
            path: The destination file.
            text: The text to write.
        """
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(text)
        os.replace(tmp, path)
