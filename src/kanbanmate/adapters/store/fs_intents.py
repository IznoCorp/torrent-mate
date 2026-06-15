"""Intent-queue persistence for the filesystem state store (cockpit PR2).

The cockpit skill mutates the board through an **intent queue** whose only writer is the daemon
(eliminating the daemon-vs-CLI board-write race). The CLI enqueues an :class:`~kanbanmate.core.intent.Intent`
as ``<root>/intents/<id>.json``; the daemon's ``drain_intents`` tick step loads it, validates +
executes it, writes ``<root>/intents/<id>.result.json`` (which the CLI ``--wait`` polls), then clears
the pending file. Both writes are atomic (temp-file + ``os.replace``) and every read degrades to
``None``/``()`` on a poison file — a bad marker never wedges the drain or the tick.

This mixin is **self-contained** (its own atomic-write + a lazy ``intents/`` mkdir on first write) so
mixing it into :class:`~kanbanmate.adapters.store.fs_store.FsStateStore` adds only one import line
there (keeping ``fs_store.py`` under the 1000-LOC ceiling without an extraction). Layering: imports
only the standard library.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path


class IntentsStateMixin:
    """Board-mutation intent queue (mixed into the fs state store).

    Operates on the host store's ``root`` directory. The ``intents/`` directory is created lazily on
    the first write (no ``__init__`` change in the host), and reads tolerate its absence.

    Attributes:
        root: The state-store root directory (set by the host store's ``__init__``).
    """

    root: Path

    def enqueue_intent(self, intent_id: str, payload: Mapping[str, object]) -> None:
        """Persist a pending intent atomically as ``intents/<id>.json``.

        Args:
            intent_id: The intent's id (its filename stem; the result file mirrors it).
            payload: The JSON-serialisable intent mapping (kind / issue / args / requested_at / caller).
        """
        self._ensure_intents_dir()
        self._atomic_write_intent(self._intent_path(intent_id), json.dumps(dict(payload)))

    def load_intent(self, intent_id: str) -> dict[str, object] | None:
        """Return the pending intent payload, or ``None`` when absent/corrupt (poison-tolerant)."""
        return self._read_intent_json(self._intent_path(intent_id))

    def clear_intent(self, intent_id: str) -> None:
        """Remove the pending intent marker (the drain clears it after writing the result)."""
        self._unlink_intent(self._intent_path(intent_id))

    def list_pending_intents(self) -> tuple[str, ...]:
        """Return the ids of all pending intents (result files excluded), sorted for stable order.

        Sorted lexicographically here for determinism; the drain re-orders by ``requested_at``.
        Degrades to ``()`` when the directory is absent.
        """
        directory = self._intents_dir()
        if not directory.exists():
            return ()
        ids = [
            path.stem
            for path in directory.glob("*.json")
            # ``*.json`` also matches ``<id>.result.json`` — exclude result files (their stem ends
            # in ``.result``); only ``<id>.json`` pending markers are returned.
            if not path.name.endswith(".result.json")
        ]
        return tuple(sorted(ids))

    def save_intent_result(self, intent_id: str, payload: Mapping[str, object]) -> None:
        """Persist an intent's result atomically as ``intents/<id>.result.json`` (CLI ``--wait`` reads it)."""
        self._ensure_intents_dir()
        self._atomic_write_intent(self._intent_result_path(intent_id), json.dumps(dict(payload)))

    def load_intent_result(self, intent_id: str) -> dict[str, object] | None:
        """Return an intent's result payload, or ``None`` when not yet written/corrupt."""
        return self._read_intent_json(self._intent_result_path(intent_id))

    # ------------------------------------------------------------------
    # Paths + atomic primitives (self-contained — mirror fs_status_state).
    # ------------------------------------------------------------------

    def _intents_dir(self) -> Path:
        """Return the intent-queue directory (``intents/``)."""
        return self.root / "intents"

    def _intent_path(self, intent_id: str) -> Path:
        """Return the pending-intent marker path (``intents/<id>.json``)."""
        return self._intents_dir() / f"{intent_id}.json"

    def _intent_result_path(self, intent_id: str) -> Path:
        """Return the intent-result marker path (``intents/<id>.result.json``)."""
        return self._intents_dir() / f"{intent_id}.result.json"

    def _ensure_intents_dir(self) -> None:
        """Create ``intents/`` on first write (lazy — keeps the host ``__init__`` untouched)."""
        self._intents_dir().mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _read_intent_json(path: Path) -> dict[str, object] | None:
        """Read a JSON intent/result file, degrading to ``None`` on absence or corruption.

        A poison file must never wedge the drain — it degrades to ``None`` (treated as
        absent/unparseable) with a named breadcrumb on stderr (the state-file pattern).

        Args:
            path: The intent or result file to read.

        Returns:
            The parsed mapping, or ``None`` when absent, unreadable, or not a JSON object.
        """
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as err:
            print(f"kanban: skipping corrupt intent file {path}: {err}", file=sys.stderr)
            return None
        return data if isinstance(data, dict) else None

    def _unlink_intent(self, path: Path) -> None:
        """Remove an intent/result marker, tolerating its prior absence."""
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def _atomic_write_intent(path: Path, text: str) -> None:
        """Write ``text`` to ``path`` atomically via temp-file + ``os.replace`` (no torn reads)."""
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(text)
        os.replace(tmp, path)
