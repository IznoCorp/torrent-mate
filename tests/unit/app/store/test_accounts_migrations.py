"""Unit tests for the accounts migrations of ``app.db`` — ``002_accounts.sql`` to ``006_account_language.sql``.

A fresh file reaches version 7 with the five seeded roles; an existing file keeps its push
subscriptions through ``003``'s rebuild, and a subscription naming no account makes the
migration fail loud, the runner restoring the file as it stood before ``003``. ``004`` gives
every account, existing or new, ``sign_in_allowed = 1``; ``005`` leaves every account not demoted;
``006`` gives every existing account French, the language the household always read it in.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.store.errors import AppMigrationError
from personalscraper.app.store.store import _MIGRATIONS_DIR, AppStore
from personalscraper.core.sqlite import apply_migrations, open_db

_PUSH_COLUMNS = (
    "id, account_id, token, platform, user_agent, created_at, refreshed_at,"
    " last_sent_at, last_outcome, failure_count, revoked_at, revoked_reason"
)
_PUSH_ROW = (7, "account-alice", "tok-1", "ios", "UA", 1.0, 2.0, 3.0, "delivered", 1, None, None)


def _file_at(tmp_path: Path, version: int) -> Path:
    """Build an ``app.db`` migrated up to *version* only, with the shipped scripts.

    Args:
        tmp_path: The test's temporary directory.
        version: The last migration to apply.

    Returns:
        The database path; no connection is left open.
    """
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for script in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if int(script.stem.split("_")[0]) <= version:
            shutil.copy(script, scripts / script.name)
    db_path = tmp_path / "data" / "app.db"
    db_path.parent.mkdir()
    conn = open_db(db_path)
    try:
        apply_migrations(conn, scripts)
    finally:
        conn.close()
    return db_path


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open *db_path* with the canonical PRAGMAs (``foreign_keys=ON``).

    Args:
        db_path: The database.

    Returns:
        The connection.
    """
    return open_db(db_path)


def _user_version(db_path: Path) -> int:
    """Read ``PRAGMA user_version`` of *db_path*.

    Args:
        db_path: The database.

    Returns:
        The schema version.
    """
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


@pytest.fixture
def fresh(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A fresh ``app.db`` opened (and migrated) through :class:`AppStore`.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        A connection to the migrated file.
    """
    db_path = tmp_path / "app.db"
    store = AppStore(db_path)
    try:
        store.push.live_for("nobody")
    finally:
        store.close()
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


class TestFreshFile:
    """A file created today holds the whole schema and the five seeded roles."""

    def test_reaches_version_nine(self, fresh: sqlite3.Connection) -> None:
        """Every migration applied."""
        assert fresh.execute("PRAGMA user_version").fetchone()[0] == 9

    def test_seeds_the_five_roles_with_their_kinds_and_no_name(self, fresh: sqlite3.Connection) -> None:
        """The maquette's five roles; a seeded role carries no name (its id is translated by the interface)."""
        rows = fresh.execute("SELECT id, name, kind FROM role ORDER BY rowid").fetchall()
        assert rows == [
            ("admin", None, "admin"),
            ("household", None, "ordinary"),
            ("plex-guest", None, "ordinary"),
            ("requester", None, "ordinary"),
            ("local-guest", None, "ordinary"),
        ]

    def test_seeds_the_seed_rights_and_admin_holds_none(self, fresh: sqlite3.Connection) -> None:
        """``admin`` has no ``role_right`` row; the others carry the seed's rights exactly."""
        rights: dict[str, set[str]] = {}
        for role_id, right in fresh.execute("SELECT role_id, right_name FROM role_right"):
            rights.setdefault(role_id, set()).add(right)
        own = {
            "library.read",
            "acquisition.request",
            "acquisition.follow",
            "acquisition.todo.view",
            "acquisition.pilot.own",
            "acquisition.pause.own",
        }
        assert rights == {
            "household": own,
            "plex-guest": {"library.read"},
            "requester": own,
            "local-guest": {"library.read"},
        }

    def test_seeds_one_role_per_start_kind(self, fresh: sqlite3.Connection) -> None:
        """Plex Home → household, Plex guest → plex-guest; a local account's role is chosen at its creation."""
        starts = dict(fresh.execute("SELECT start, role_id FROM role_start").fetchall())
        assert starts == {"plexHome": "household", "plexGuest": "plex-guest"}

    def test_a_second_admin_role_is_refused(self, fresh: sqlite3.Connection) -> None:
        """One role of kind ``admin``, enforced by the base."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute("INSERT INTO role VALUES ('role-x', 'X', 'admin', 1, 1)")

    def test_an_unknown_role_kind_is_refused(self, fresh: sqlite3.Connection) -> None:
        """No ``default`` kind any more: two kinds only."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute("INSERT INTO role VALUES ('role-x', 'X', 'default', 1, 1)")

    def test_a_second_role_for_one_start_is_refused(self, fresh: sqlite3.Connection) -> None:
        """One role per start kind."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute("INSERT INTO role_start VALUES ('plexGuest', 'requester')")

    @pytest.mark.parametrize("start", ["plexFriend", "local"])
    def test_an_unknown_start_kind_is_refused(self, fresh: sqlite3.Connection, start: str) -> None:
        """Two start kinds only: a local account starts on the role chosen at its creation.

        Any row of that kind is removed first, so only the CHECK can refuse it.
        """
        fresh.execute("DELETE FROM role_start WHERE start = ?", (start,))
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute("INSERT INTO role_start VALUES (?, 'requester')", (start,))

    def test_a_role_named_as_a_start_cannot_be_deleted(self, fresh: sqlite3.Connection) -> None:
        """``role_start``'s foreign key holds the role."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute("DELETE FROM role WHERE id = 'plex-guest'")

    def test_a_role_no_start_names_can_be_deleted(self, fresh: sqlite3.Connection) -> None:
        """``requester`` is no start's role: it goes, and its rights with it."""
        fresh.execute("DELETE FROM role WHERE id = 'requester'")
        assert fresh.execute("SELECT count(*) FROM role_right WHERE role_id = 'requester'").fetchone()[0] == 0

    def test_email_is_unique_case_insensitively(self, fresh: sqlite3.Connection) -> None:
        """``A@x`` then ``a@X`` → refused."""
        fresh.execute(
            "INSERT INTO account (id, name, email, role_id, created_at, updated_at)"
            " VALUES ('a1', 'A', 'A@x', 'local-guest', 1, 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute(
                "INSERT INTO account (id, name, email, role_id, created_at, updated_at)"
                " VALUES ('a2', 'B', 'a@X', 'local-guest', 1, 1)"
            )

    def test_a_new_account_may_sign_in(self, fresh: sqlite3.Connection) -> None:
        """``004``: an account inserted without the column is allowed to sign in."""
        fresh.execute(
            "INSERT INTO account (id, name, email, role_id, created_at, updated_at)"
            " VALUES ('a1', 'A', 'a@x', 'local-guest', 1, 1)"
        )
        assert fresh.execute("SELECT sign_in_allowed FROM account WHERE id = 'a1'").fetchone()[0] == 1

    def test_sign_in_allowed_is_zero_or_one(self, fresh: sqlite3.Connection) -> None:
        """``004``: any other value is refused."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute(
                "INSERT INTO account (id, name, email, role_id, created_at, updated_at, sign_in_allowed)"
                " VALUES ('a1', 'A', 'a@x', 'local-guest', 1, 1, 2)"
            )

    def test_a_language_outside_fr_and_en_is_refused(self, fresh: sqlite3.Connection) -> None:
        """``006``: the two languages the interface speaks, and no other."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute(
                "INSERT INTO account (id, name, email, role_id, created_at, updated_at, language)"
                " VALUES ('a1', 'A', 'a@x', 'local-guest', 1, 1, 'de')"
            )

    @pytest.mark.parametrize(
        "insert",
        [
            "INSERT INTO account_notice (account_id, code, params_json, created_at) VALUES ('nobody', 'c', '{}', 1)",
            "INSERT INTO notification_preference (account_id, type, enabled, updated_at) VALUES ('nobody', 't', 1, 1)",
        ],
        ids=["notice", "preference"],
    )
    def test_a_notice_and_a_switch_must_name_an_account(self, fresh: sqlite3.Connection, insert: str) -> None:
        """``009``: the notice's and the switch's account is a foreign key."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute(insert)

    def test_a_switch_is_zero_or_one(self, fresh: sqlite3.Connection) -> None:
        """``009``: ``enabled`` holds no other value."""
        fresh.execute(
            "INSERT INTO account (id, name, email, role_id, created_at, updated_at)"
            " VALUES ('a1', 'A', 'a@x', 'local-guest', 1, 1)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute(
                "INSERT INTO notification_preference (account_id, type, enabled, updated_at) VALUES ('a1', 't', 2, 1)"
            )

    def test_a_push_subscription_must_name_an_account(self, fresh: sqlite3.Connection) -> None:
        """``003``: the subscription's account is a foreign key."""
        with pytest.raises(sqlite3.IntegrityError):
            fresh.execute(
                f"INSERT INTO push_subscription ({_PUSH_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", _PUSH_ROW
            )

    def test_deleting_an_account_cascades_its_rows(self, fresh: sqlite3.Connection) -> None:
        """Its Plex link, its sessions and its push subscriptions go with it."""
        fresh.execute(
            "INSERT INTO account (id, name, email, role_id, created_at, updated_at)"
            " VALUES ('account-alice', 'Alice', 'alice@x', 'household', 1, 1)"
        )
        fresh.execute(
            "INSERT INTO plex_link (account_id, plex_id, plex_uuid, plex_username, server_access, linked_at)"
            " VALUES ('account-alice', 42, 'uuid', 'alice', 'shared', 1)"
        )
        fresh.execute(
            "INSERT INTO session (account_id, token_hash, created_at, expires_at, last_seen_at)"
            " VALUES ('account-alice', 'h', 1, 2, 1)"
        )
        fresh.execute(f"INSERT INTO push_subscription ({_PUSH_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", _PUSH_ROW)
        fresh.execute(
            "INSERT INTO account_notice (account_id, code, params_json, created_at)"
            " VALUES ('account-alice', 'account.sign_in.unknown_device', '{}', 1)"
        )
        fresh.execute(
            "INSERT INTO notification_preference (account_id, type, enabled, updated_at)"
            " VALUES ('account-alice', 'account.sign_in', 0, 1)"
        )

        fresh.execute("DELETE FROM account WHERE id = 'account-alice'")

        for table in ("plex_link", "session", "push_subscription", "account_notice", "notification_preference"):
            assert fresh.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, table  # noqa: S608 — fixed names


class TestExistingFile:
    """``003`` on a file that already holds push subscriptions."""

    def test_a_subscription_with_its_account_survives_with_every_column(self, tmp_path: Path) -> None:
        """A version-2 file holding an account and its subscription: the row survives ``003`` unchanged."""
        db_path = _file_at(tmp_path, 2)
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO account (id, name, email, role_id, created_at, updated_at)"
                " VALUES ('account-alice', 'Alice', 'alice@x', 'household', 1, 1)"
            )
            conn.execute(f"INSERT INTO push_subscription ({_PUSH_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", _PUSH_ROW)
        finally:
            conn.close()

        store = AppStore(db_path)
        try:
            store.push.live_for("account-alice")
        finally:
            store.close()

        assert _user_version(db_path) == 9
        conn = _connect(db_path)
        try:
            rows = conn.execute(f"SELECT {_PUSH_COLUMNS} FROM push_subscription").fetchall()  # noqa: S608 — fixed names
            foreign_keys = conn.execute("PRAGMA foreign_key_list(push_subscription)").fetchall()
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(push_subscription)")}
        finally:
            conn.close()
        assert rows == [_PUSH_ROW]
        assert [(fk[2], fk[3], fk[4], fk[6]) for fk in foreign_keys] == [("account", "account_id", "id", "CASCADE")]
        assert "push_subscription_account" in indexes

    def test_a_subscription_naming_no_account_fails_loud_and_restores(self, tmp_path: Path) -> None:
        """A version-1 subscription whose account does not exist: ``AppMigrationError``, the row kept.

        ``002`` commits, then ``003``'s copy fails; the runner restores the snapshot taken
        before ``003``, so the file stands at version 2 with its row, never with the row dropped.
        """
        db_path = _file_at(tmp_path, 1)
        conn = _connect(db_path)
        try:
            conn.execute(f"INSERT INTO push_subscription ({_PUSH_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", _PUSH_ROW)
        finally:
            conn.close()

        store = AppStore(db_path)
        try:
            with pytest.raises(AppMigrationError) as raised:
                _ = store.push
        finally:
            store.close()

        assert raised.value.version == 3
        assert _user_version(db_path) == 2
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(f"SELECT {_PUSH_COLUMNS} FROM push_subscription").fetchall()  # noqa: S608 — fixed names
            foreign_keys = conn.execute("PRAGMA foreign_key_list(push_subscription)").fetchall()
        finally:
            conn.close()
        assert rows == [_PUSH_ROW]
        assert foreign_keys == []


class TestAccountAccessMigration:
    """``004`` on a file that already holds accounts."""

    def test_an_existing_account_may_sign_in(self, tmp_path: Path) -> None:
        """A version-3 file's account comes out of ``004`` allowed to sign in, every other column unchanged."""
        db_path = _file_at(tmp_path, 3)
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO account (id, name, email, role_id, password_hash, created_at, updated_at)"
                " VALUES ('account-alice', 'Alice', 'alice@x', 'household', 'h', 1, 2)"
            )
        finally:
            conn.close()

        store = AppStore(db_path)
        try:
            account = store.accounts.account("account-alice")
        finally:
            store.close()

        assert _user_version(db_path) == 9
        assert account is not None
        assert account.sign_in_allowed is True
        assert (account.name, account.email, account.role_id, account.password_hash) == (
            "Alice",
            "alice@x",
            "household",
            "h",
        )


class TestAccountDemotionMigration:
    """``005`` on a file that already holds accounts."""

    def test_an_existing_account_is_not_demoted(self, tmp_path: Path) -> None:
        """A version-4 file's account comes out of ``005`` with no demotion, every other column unchanged."""
        db_path = _file_at(tmp_path, 4)
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO account (id, name, email, role_id, password_hash, created_at, updated_at, sign_in_allowed)"
                " VALUES ('account-alice', 'Alice', 'alice@x', 'household', 'h', 1, 2, 0)"
            )
        finally:
            conn.close()

        store = AppStore(db_path)
        try:
            account = store.accounts.account("account-alice")
        finally:
            store.close()

        assert _user_version(db_path) == 9
        assert account is not None
        assert account.demoted_from is None
        assert (account.role_id, account.password_hash, account.sign_in_allowed) == ("household", "h", False)


class TestAccountLanguageMigration:
    """``006`` on a file that already holds accounts."""

    def test_an_existing_account_speaks_french(self, tmp_path: Path) -> None:
        """A version-5 file's account comes out of ``006`` in French, every other column unchanged.

        The operator, 2026-10-05: « Compte existants en fr ».
        """
        db_path = _file_at(tmp_path, 5)
        conn = _connect(db_path)
        try:
            conn.execute(
                "INSERT INTO account (id, name, email, role_id, password_hash, created_at, updated_at,"
                " sign_in_allowed, demoted_from) VALUES ('account-alice', 'Alice', 'alice@x', 'household', 'h',"
                " 1, 2, 0, 'requester')"
            )
        finally:
            conn.close()

        store = AppStore(db_path)
        try:
            account = store.accounts.account("account-alice")
        finally:
            store.close()

        assert _user_version(db_path) == 9
        assert account is not None
        assert account.language == "fr"
        assert (account.role_id, account.password_hash, account.sign_in_allowed, account.demoted_from) == (
            "household",
            "h",
            False,
            "requester",
        )
