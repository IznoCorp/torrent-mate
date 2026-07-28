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
        target_path: The exact destination FOLDER of the transfer (e.g.
            ``/Volumes/Disk2/medias/films/Inception (2010)``), as opposed to
            ``target_disk`` which is only the mount point. Additive with a
            ``None`` default (D1): every existing emitter and consumer keeps
            working, and the dispatcher fills it. A consumer that needs to act
            on the media itself — the Plex refresh trigger, which must scan ONE
            folder rather than a whole section — cannot reconstruct this path
            from disk + category + item name without re-deriving the naming
            rules, so the event carries what the dispatcher already knows.
    """

    item: str
    target_disk: Path
    category_id: str
    action: Literal["moved", "merged", "replaced"]
    target_path: Path | None = None


__all__ = ["ItemDispatched"]
