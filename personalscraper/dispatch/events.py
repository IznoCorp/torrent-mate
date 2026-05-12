"""Dispatch event catalog.

Hosts :class:`ItemDispatched`, emitted by
:mod:`personalscraper.dispatch._movie` and
:mod:`personalscraper.dispatch._tv` after every successful real transfer
(``moved`` / ``merged`` / ``replaced``). Dry-run dispatches never emit —
the action enum has no ``"skipped"`` value precisely because the event
catalog only records completed real transfers (DESIGN §Event catalog
Notes).

The module is eagerly imported by :mod:`personalscraper.events` so
``Event.__init_subclass__`` registers ``ItemDispatched`` before any
consumer calls ``event_from_envelope``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from personalscraper.core.event_bus import Event


@dataclass(frozen=True, kw_only=True)
class ItemDispatched(Event):
    """Emitted by the dispatcher after a successful move / merge / replace.

    Attributes:
        item: Source folder basename (e.g. ``"Inception (2010)"``).
        target_disk: Storage disk root for the destination (the disk's
            mount point, NOT the per-category sub-folder).
        category_id: Config category id (``"movies"``, ``"tv_shows"``, …).
        action: ``"moved"`` (new placement), ``"merged"`` (TV merge into
            existing folder), or ``"replaced"`` (movie overwrite of an
            existing folder).
    """

    item: str
    target_disk: Path
    category_id: str
    action: Literal["moved", "merged", "replaced"]


__all__ = ["ItemDispatched"]
