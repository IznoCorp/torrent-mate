"""Centralized tag vocabulary for the triage pipeline (seed-pure feature).

All layers — ``api/torrent``, ``ingest``, ``sorter``, ``process``,
``commands``, and a future Watcher — import tag constants from here
rather than using string literals, so a rename touches one file only.
``core/`` is the bottom layer: this module imports nothing project-internal.

Which tag a reader honours depends on the instance: an unscoped one (the v0
prod) skips :data:`SEED_PURE`; a scoped one (a v1 instance sharing the client)
triages the torrents carrying its instance tag and skips :data:`SEED_ONLY`
(``api.torrent._base.triage_skip_reason`` holds the rule).
"""

SEED_PURE = "seed-pure"
"""v0 tag: a torrent downloaded only for ratio seeding, never triaged.

The v0 rule, kept while v0 runs in prod: an unscoped instance's triage
(ingest, sort, watcher, cross-seed) skips every torrent carrying it. The tag
is set manually via ``personalscraper seed mark <hash>``, on an unscoped
cross-seed, and — while ``TorrentScope.v0_seed_pure`` is on — on every torrent
a scoped instance adds, so v0 prod leaves it alone. A scoped instance never
reads it.
"""

SEED_ONLY = "seed-only"
"""v1 tag: keep seeding, never triage.

A scoped instance tags its cross-seeds with it beside its instance tag, and
its triage skips any of its own torrents carrying it.
"""

__all__ = ["SEED_ONLY", "SEED_PURE"]
