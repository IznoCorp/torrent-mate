-- The accounts of app.db: roles and their rights, the start kinds' roles, accounts, Plex links,
-- sessions, Plex PINs and the application's own settings. Additive: nothing existing changes.
--
-- Two role kinds: ``admin`` (the one system role, holding every right without a rights list) and
-- ``ordinary``. ``role_start`` names, per start kind, the role a new account starts on: a Plex
-- Home member, a Plex guest. A local account starts on the role chosen at its creation, so it has
-- no start kind. A role named there cannot be deleted (its foreign
-- key has no ON DELETE, and every connection runs with ``foreign_keys=ON``).
--
-- The seeds are the five roles of the maquette's ``mocks/seeds/accounts.json`` (ids, kinds, rights,
-- start kinds). A seeded role carries NO name: until an Admin renames it, the interface shows the
-- translation of its id, so no interface text lives in the database; a rename stores its text.

BEGIN TRANSACTION;

CREATE TABLE role (
    id          TEXT PRIMARY KEY,                -- the seeds' ids, or 'role-<uuid4 hex>'
    name        TEXT,                            -- NULL = never renamed: the interface shows its id's translation
    kind        TEXT NOT NULL CHECK (kind IN ('admin', 'ordinary')),
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE UNIQUE INDEX role_admin_kind ON role(kind) WHERE kind = 'admin';

CREATE TABLE role_right (
    role_id     TEXT NOT NULL REFERENCES role(id) ON DELETE CASCADE,
    right_name  TEXT NOT NULL,                   -- a Right member; checked by the service, not by SQL
    PRIMARY KEY (role_id, right_name)
);

CREATE TABLE role_start (
    start       TEXT PRIMARY KEY CHECK (start IN ('plexHome', 'plexGuest')),
    role_id     TEXT NOT NULL REFERENCES role(id)
);

CREATE TABLE account (
    id             TEXT PRIMARY KEY,             -- 'account-<uuid4 hex>'
    name           TEXT NOT NULL,
    email          TEXT NOT NULL,
    avatar         TEXT NOT NULL DEFAULT '',
    role_id        TEXT NOT NULL REFERENCES role(id),
    password_hash  TEXT,                         -- scrypt$N$r$p$salt$hash; NULL = no password
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);
CREATE UNIQUE INDEX account_email ON account(lower(email));

CREATE TABLE plex_link (
    account_id        TEXT PRIMARY KEY REFERENCES account(id) ON DELETE CASCADE,
    plex_id           INTEGER NOT NULL UNIQUE,   -- plex.tv's stable id: the identity, never the e-mail
    plex_uuid         TEXT NOT NULL,
    plex_username     TEXT NOT NULL,
    server_access     TEXT NOT NULL CHECK (server_access IN ('owner', 'shared')),
    token_ciphertext  BLOB,                      -- Fernet; NULL = not kept, forgotten, or revoked
    token_stored_at   REAL,
    linked_at         REAL NOT NULL,
    last_sign_in_at   REAL
);

CREATE TABLE session (
    id            INTEGER PRIMARY KEY,
    account_id    TEXT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    token_hash    TEXT NOT NULL UNIQUE,          -- sha256 hex of the cookie value; the value is never stored
    created_at    REAL NOT NULL,
    expires_at    REAL NOT NULL,
    last_seen_at  REAL NOT NULL,
    revoked_at    REAL,
    user_agent    TEXT
);
CREATE INDEX session_account ON session(account_id) WHERE revoked_at IS NULL;

CREATE TABLE plex_pin (
    pin_id           INTEGER PRIMARY KEY,
    code             TEXT NOT NULL,
    nonce_hash       TEXT NOT NULL,              -- binds the PIN to the browser that started it
    created_at       REAL NOT NULL,
    expires_at       REAL,
    last_checked_at  REAL,
    consumed_at      REAL
);

CREATE TABLE app_setting (
    key    TEXT PRIMARY KEY,                     -- e.g. 'plex.client_identifier'
    value  TEXT NOT NULL
);

INSERT INTO role (id, name, kind, created_at, updated_at) VALUES
    ('admin', NULL, 'admin', 0, 0),
    ('household', NULL, 'ordinary', 0, 0),
    ('plex-guest', NULL, 'ordinary', 0, 0),
    ('requester', NULL, 'ordinary', 0, 0),
    ('local-guest', NULL, 'ordinary', 0, 0);

INSERT INTO role_right (role_id, right_name) VALUES
    ('household', 'library.read'),
    ('household', 'acquisition.request'),
    ('household', 'acquisition.follow'),
    ('household', 'acquisition.todo.view'),
    ('household', 'acquisition.pilot.own'),
    ('household', 'acquisition.pause.own'),
    ('plex-guest', 'library.read'),
    ('requester', 'library.read'),
    ('requester', 'acquisition.request'),
    ('requester', 'acquisition.follow'),
    ('requester', 'acquisition.todo.view'),
    ('requester', 'acquisition.pilot.own'),
    ('requester', 'acquisition.pause.own'),
    ('local-guest', 'library.read');

INSERT INTO role_start (start, role_id) VALUES
    ('plexHome', 'household'),
    ('plexGuest', 'plex-guest');

PRAGMA user_version = 2;

COMMIT;
