"""Indexer schema migrations — applied in numeric order by ``apply_migrations``.

Each ``NNN_*.sql`` script is the canonical source for one schema version.
The script must:

1. Apply its DDL changes (``CREATE TABLE``, ``ALTER TABLE``, ``CREATE INDEX``).
2. ``INSERT INTO schema_version(version) VALUES (N);`` (use ``INSERT OR IGNORE``
   when the migration is also safe to re-run on a partially-upgraded DB).
3. ``PRAGMA user_version = N;`` in lockstep — the runtime gates further
   migrations on this PRAGMA.

See ``personalscraper/indexer/db.py:apply_migrations`` for the applier and
``tests/indexer/test_migrations.py`` for the contract assertions
(every version 1..N must appear in ``schema_version``; PRAGMA user_version
must equal the latest version after a fresh apply).
"""
