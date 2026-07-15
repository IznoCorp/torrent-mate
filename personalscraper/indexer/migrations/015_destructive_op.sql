-- Schema migration 015 — append-only journal of destructive filesystem ops.
--
-- Background (constitution §7 / the Star City incident):
--
-- Media payloads were deleted by an unknown actor and no audit trail existed to
-- innocent or accuse the pipeline — the investigation had to reconstruct events
-- from scratch. This table is the durable trail: every destructive filesystem
-- operation the app performs on library content (an overwrite that supersedes a
-- previous folder, a disk-clean deletion) records who/what/when/where/why.
--
-- Append-only by discipline: rows are INSERTed, never UPDATEd; only a bounded
-- retention GC may DELETE old rows. Independent of ``index_outbox`` (a work
-- queue, status-mutated + purged) and ``deleted_item`` (scanner-drift
-- tombstones only) — neither recorded dispatch/clean destructions.

CREATE TABLE destructive_op (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL    NOT NULL,          -- Unix epoch (time.time()) of the op
    op       TEXT    NOT NULL,          -- 'overwrite' | 'delete'
    path     TEXT    NOT NULL,          -- absolute path that was destroyed
    actor    TEXT    NOT NULL,          -- 'dispatch' | 'disk-clean' | ...
    detail   TEXT    NULL,              -- human context / decision (French)
    run_uid  TEXT    NULL               -- correlating pipeline_run, when known
);

CREATE INDEX idx_destructive_op_ts ON destructive_op(ts);

INSERT INTO schema_version (version) VALUES (15);
PRAGMA user_version = 15;
