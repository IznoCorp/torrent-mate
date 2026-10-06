"""Guards of the core migration runner, ``personalscraper.core.sqlite._migrate.apply_migrations``.

Covers:
- A store whose ``PRAGMA user_version`` is HIGHER than the code's highest migration is refused:
  a typed error, nothing migrated, nothing written, ``store.schema_newer_than_code`` logged.
- A script that fails inside its transaction leaves the schema, ``user_version`` and the
  pre-migration ``.bak`` as they were before it.
- Every migration script of the three stores runs inside one explicit transaction, the
  version bump included (legacy scripts already applied everywhere are listed by name).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from personalscraper.core.sqlite import SqliteMigrationError, SqliteSchemaNewerError, apply_migrations, open_db

_PACKAGE_DIR = Path(__file__).parent.parent.parent / "personalscraper"

#: The migration directories of the three stores (library.db, acquire.db, app.db).
_MIGRATION_DIRS = {
    "indexer": _PACKAGE_DIR / "indexer" / "migrations",
    "acquire": _PACKAGE_DIR / "acquire" / "migrations",
    "app": _PACKAGE_DIR / "app" / "store" / "migrations",
}

#: Scripts written before the one-transaction rule, applied on every live store: editing them
#: changes nothing that exists, so they stay as they are. Every other script follows the rule.
_LEGACY_NON_TRANSACTIONAL = {
    "acquire/001_init.sql",
    "acquire/002_cross_seed.sql",
    "acquire/003_watch_state.sql",
    "acquire/004_followed_unique.sql",
    "acquire/005_followed_metadata.sql",
    "acquire/006_followed_kind.sql",
    "acquire/007_aired_episode.sql",
    "acquire/014_download_marks.sql",
    "app/001_baseline.sql",
}


def _write_scripts(dir_: Path, scripts: dict[str, str]) -> Path:
    """Write migration scripts into *dir_*.

    Args:
        dir_: The directory to create.
        scripts: File name → SQL text.

    Returns:
        The directory.
    """
    dir_.mkdir()
    for name, sql in scripts.items():
        (dir_ / name).write_text(sql, encoding="utf-8")
    return dir_


def _schema(conn: sqlite3.Connection) -> list[tuple[str, str, str | None]]:
    """Return the store's schema as sorted ``(type, name, sql)`` rows.

    Args:
        conn: An open connection.

    Returns:
        Every non-internal ``sqlite_master`` row.
    """
    return conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()


def _user_version(conn: sqlite3.Connection) -> int:
    """Return the store's ``PRAGMA user_version``.

    Args:
        conn: An open connection.

    Returns:
        The schema version in the header.
    """
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _statements(sql: str) -> list[str]:
    """Split a migration script into its top-level statements, comments stripped.

    Args:
        sql: The script text.

    Returns:
        Each complete statement, whitespace-normalised and upper-cased.
    """
    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            text = " ".join(re.sub(r"--[^\n]*", "", buffer).split())
            if text:
                statements.append(text.upper())
            buffer = ""
    return statements


class TestSchemaNewerThanCode:
    """A store written by a newer code is refused before anything touches it."""

    def _newer_store(self, tmp_path: Path) -> tuple[Path, Path]:
        """Build a store at version 5 and a migration directory that knows up to 3.

        Args:
            tmp_path: The test's temporary directory.

        Returns:
            ``(db_path, migrations_dir)``.
        """
        db_path = tmp_path / "store.db"
        with sqlite3.connect(db_path) as seed:
            seed.execute("CREATE TABLE kept (id INTEGER PRIMARY KEY)")
            seed.execute("PRAGMA user_version = 5")
        seed.close()
        migrations = _write_scripts(
            tmp_path / "migrations",
            {
                "001_a.sql": "CREATE TABLE a (id INTEGER);\nPRAGMA user_version = 1;\n",
                "002_b.sql": "CREATE TABLE b (id INTEGER);\nPRAGMA user_version = 2;\n",
                "003_c.sql": "CREATE TABLE c (id INTEGER);\nPRAGMA user_version = 3;\n",
            },
        )
        return db_path, migrations

    def test_refused_with_a_typed_error(self, tmp_path: Path) -> None:
        """A store at 5 under a code that knows 3 raises ``SqliteSchemaNewerError``."""
        db_path, migrations = self._newer_store(tmp_path)
        conn = sqlite3.connect(db_path, isolation_level=None)

        with pytest.raises(SqliteSchemaNewerError) as raised:
            apply_migrations(conn, migrations)

        assert isinstance(raised.value, SqliteMigrationError)
        assert "5" in str(raised.value) and "3" in str(raised.value)

    def test_the_typed_error_wins_over_the_error_factory(self, tmp_path: Path) -> None:
        """A store's ``error_factory`` builds « migration N failed »; a newer schema is not that."""
        db_path, migrations = self._newer_store(tmp_path)
        conn = sqlite3.connect(db_path, isolation_level=None)

        with pytest.raises(SqliteSchemaNewerError):
            apply_migrations(conn, migrations, error_factory=lambda version: ValueError(version))

    def test_nothing_is_migrated_nor_written(self, tmp_path: Path) -> None:
        """The file's bytes are unchanged, no table was added and no ``.bak`` was taken."""
        db_path, migrations = self._newer_store(tmp_path)
        before = db_path.read_bytes()
        conn = sqlite3.connect(db_path, isolation_level=None)

        with pytest.raises(SqliteSchemaNewerError):
            apply_migrations(conn, migrations)

        assert db_path.read_bytes() == before
        assert list(tmp_path.glob("*.bak")) == []
        with sqlite3.connect(db_path) as check:
            assert _user_version(check) == 5
            assert [row[1] for row in _schema(check)] == ["kept"]
        check.close()

    def test_the_connection_is_closed(self, tmp_path: Path) -> None:
        """The refused connection is closed, like on every other failure path of the runner."""
        db_path, migrations = self._newer_store(tmp_path)
        conn = sqlite3.connect(db_path, isolation_level=None)

        with pytest.raises(SqliteSchemaNewerError):
            apply_migrations(conn, migrations)

        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_the_refusal_is_logged(self, tmp_path: Path, logged_events) -> None:  # type: ignore[no-untyped-def]
        """``store.schema_newer_than_code`` names the path, the found and the known versions."""
        db_path, migrations = self._newer_store(tmp_path)
        conn = sqlite3.connect(db_path, isolation_level=None)

        with logged_events() as events, pytest.raises(SqliteSchemaNewerError):
            apply_migrations(conn, migrations)

        refusals = [event for event in events if event["event"] == "store.schema_newer_than_code"]
        assert len(refusals) == 1
        assert refusals[0]["path"] == str(db_path.resolve())
        assert refusals[0]["found"] == 5
        assert refusals[0]["known"] == 3
        assert refusals[0]["log_level"] == "error"

    def test_a_store_at_the_code_version_opens(self, tmp_path: Path) -> None:
        """Equal versions are the steady state: a no-op, no refusal."""
        db_path, migrations = self._newer_store(tmp_path)
        (migrations / "005_e.sql").write_text("PRAGMA user_version = 5;\n", encoding="utf-8")
        conn = sqlite3.connect(db_path, isolation_level=None)

        apply_migrations(conn, migrations)

        assert _user_version(conn) == 5
        conn.close()


class TestFailedScriptLeavesTheStoreAsBefore:
    """A script that fails mid-way inside its transaction changes nothing, its ``.bak`` included."""

    def test_schema_version_and_bak_intact(self, tmp_path: Path) -> None:
        """The failing 002 leaves schema and version at 001, and its ``.bak`` is the state before it."""
        migrations = _write_scripts(
            tmp_path / "migrations",
            {"001_a.sql": "BEGIN TRANSACTION;\nCREATE TABLE a (id INTEGER);\nPRAGMA user_version = 1;\nCOMMIT;\n"},
        )
        db_path = tmp_path / "store.db"
        conn = open_db(db_path)
        apply_migrations(conn, migrations)
        before_schema = _schema(conn)
        (migrations / "002_b.sql").write_text(
            "BEGIN TRANSACTION;\nCREATE TABLE b (id INTEGER);\nALTER TABLE a ADD COLUMN x TEXT;\n"
            "INSERT INTO missing_table VALUES (1);\nPRAGMA user_version = 2;\nCOMMIT;\n",
            encoding="utf-8",
        )

        with pytest.raises(SqliteMigrationError):
            apply_migrations(conn, migrations)

        bak_path = tmp_path / "store.db.pre-migration-2.bak"
        assert bak_path.exists()
        reopened = open_db(db_path)
        assert _user_version(reopened) == 1
        assert _schema(reopened) == before_schema
        reopened.close()
        with sqlite3.connect(bak_path) as bak:
            assert _user_version(bak) == 1
            assert _schema(bak) == before_schema
        bak.close()


@pytest.mark.parametrize(
    "script",
    [
        pytest.param(path, id=f"{store}/{path.name}")
        for store, dir_ in _MIGRATION_DIRS.items()
        for path in sorted(dir_.glob("*.sql"))
        if f"{store}/{path.name}" not in _LEGACY_NON_TRANSACTIONAL
    ],
)
def test_every_migration_runs_inside_one_transaction(script: Path) -> None:
    """Every statement but the ``foreign_keys`` toggles sits between one BEGIN and its COMMIT.

    ``executescript`` auto-commits each statement outside an explicit transaction: a crash
    mid-script leaves a half-applied schema, which the next attempt snapshots into its ``.bak``.
    ``PRAGMA foreign_keys`` is a no-op inside a transaction, so its toggles sit outside it.

    Args:
        script: A migration script of one of the three stores.
    """
    statements = [
        statement
        for statement in _statements(script.read_text(encoding="utf-8"))
        if not statement.startswith("PRAGMA FOREIGN_KEYS") and not statement.startswith("PRAGMA FOREIGN_KEY_CHECK")
    ]

    assert statements[0] in {"BEGIN;", "BEGIN TRANSACTION;", "BEGIN IMMEDIATE;", "BEGIN IMMEDIATE TRANSACTION;"}
    assert statements[-1] in {"COMMIT;", "COMMIT TRANSACTION;", "END;", "END TRANSACTION;"}
    assert statements[-2].startswith("PRAGMA USER_VERSION")
