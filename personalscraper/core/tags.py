"""Centralized tag vocabulary for the triage pipeline (seed-pure feature).

All layers — ``api/torrent``, ``ingest``, ``sorter``, ``process``,
``commands``, and a future Watcher — import tag constants from here
rather than using string literals, so a rename touches one file only.
``core/`` is the bottom layer: this module imports nothing project-internal.
"""

SEED_PURE = "seed-pure"
"""Tag applied to a torrent downloaded only for ratio seeding.

A torrent carrying this tag must be skipped by the triage pipeline
(ingest, sort, process) and by the Watcher before triggering a pipeline
run. The tag is set manually via ``personalscraper seed mark <hash>``
or automatically by Follow D3 / Ratio (future).
"""

__all__ = ["SEED_PURE"]
