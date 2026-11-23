-- 027: the acquisition model's store (K3 P2): requesters, scope, removal, trigger, candidates.
--
-- Additive and inert: nothing reads or writes these columns beyond the store's own
-- sub-stores until the phases that give them behaviour (the follow service, the engine's
-- scope rule, the search pass). Every timestamp is an INTEGER epoch, acquire's convention.
--
-- ``acquisition_requester``: who asked for a follow. One row per (follow, account); the
-- follow's row is the subject, shared by every account that asked, and it is removed with
-- its last requester (``followed_series.removed_at``). ``floor`` is the requester's own
-- quality floor (a vertical resolution; NULL = none set), ``paused`` the requester's own
-- pause, ``via`` how the account asked (a follow, or a one-off request). The engine never
-- learns of rights: ``account_id`` is an opaque id. Existing follows get no requester row
-- (no backfill: K9's reprise writes the owner for real).
--
-- ``followed_series.scope``: 'follow' (every existing row) or 'request' (a one-off request
-- is a followed_series row with this scope, DESIGN O-2 A). ``removed_at``: set when the last
-- requester left, NULL while the follow stands.
--
-- ``wanted.trigger``: what put the row in the queue, 'manual' (a person's ask) or
-- 'automatic' (detect, the search conversions); NULL = unknown, which every existing row
-- and v0's frozen season route keep.
--
-- ``wanted_candidate``: the ranked candidates a concluded search found for a wanted row,
-- replaced wholesale by the next concluded search (DESIGN O-7 A); a row's candidates go
-- with it (ON DELETE CASCADE, which needs ``foreign_keys=ON``: the canonical pragma set).
--
-- Wrapped in one transaction (008/009/024/025/026 pattern) so the DDL and the
-- user_version bump commit together.

BEGIN TRANSACTION;

CREATE TABLE acquisition_requester (
    followed_id INTEGER NOT NULL REFERENCES followed_series(id) ON DELETE CASCADE,
    account_id  TEXT    NOT NULL,
    via         TEXT    NOT NULL CHECK (via IN ('follow', 'request')),
    floor       INTEGER CHECK (floor IN (720, 1080, 2160)),
    paused      INTEGER NOT NULL DEFAULT 0 CHECK (paused IN (0, 1)),
    since       INTEGER NOT NULL,
    PRIMARY KEY (followed_id, account_id)
);

ALTER TABLE followed_series ADD COLUMN scope TEXT NOT NULL DEFAULT 'follow' CHECK (scope IN ('follow', 'request'));
ALTER TABLE followed_series ADD COLUMN removed_at INTEGER;

ALTER TABLE wanted ADD COLUMN trigger TEXT CHECK (trigger IN ('manual', 'automatic'));

CREATE TABLE wanted_candidate (
    wanted_id   INTEGER NOT NULL REFERENCES wanted(id) ON DELETE CASCADE,
    rank        INTEGER NOT NULL,
    provider    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    info_hash   TEXT,
    size_bytes  INTEGER NOT NULL,
    seeders     INTEGER NOT NULL,
    resolution  TEXT,
    source      TEXT,
    language    TEXT,
    score       INTEGER NOT NULL,
    season      INTEGER,
    episode     INTEGER,
    searched_at INTEGER NOT NULL,
    PRIMARY KEY (wanted_id, rank)
);

INSERT OR IGNORE INTO schema_version(version) VALUES (27);
PRAGMA user_version = 27;

COMMIT;
