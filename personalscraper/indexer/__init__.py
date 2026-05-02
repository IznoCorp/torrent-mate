"""Media indexer sub-package.

Provides the SQLite-backed library index that replaces the legacy JSON files
(``media_index.json``, ``library_scan.json``, ``library_analysis.json``).

Layout:

- ``db`` — connection, PRAGMAs, ``indexer_lock``, migration applier.
- ``schema`` — typed ``MediaItemRow`` / ``MediaFileRow`` / etc. dataclasses
  and the JSON-shape Pydantic models (see ``docs/reference/indexer-json-shapes.md``
  for the runtime payload contracts; the Pydantic classes are mostly
  documentation today).
- ``migrations/`` — ``*.sql`` schema versions, applied in order by ``apply_migrations``.
- ``repos/`` — table-scoped repository functions (one module per table).
- ``scanner/`` — disk-walking modes (full / quick / incremental / enrich /
  verify / repair) with concurrent per-disk workers.
- ``drift`` — per-file reconciliation, OSHash collision handling, soft-delete
  + tombstone, ``purge_old_tombstones``.
- ``merkle`` — per-disk Merkle root for fast-skip on quick scans.
- ``outbox`` — write-through event drainer (DESIGN §9).
- ``release_linker`` — Stage B linker that pairs ``media_file`` rows to a
  ``media_release`` after Stage A discovers them with ``release_id IS NULL``.
- ``reconcile`` — DB-only divergence detectors (DESIGN §17.2).
- ``query`` — flex-attr query language compiler used by ``library-search``.
- ``cli`` — ``library-{index,status,verify,search,repair,reconcile,show}``
  command implementations.
"""
