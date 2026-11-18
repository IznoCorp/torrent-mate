"""Tests for personalscraper.indexer.deletion — the one folder-deletion primitive."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import personalscraper.indexer.deletion as deletion
import personalscraper.indexer.migrations as _migrations_pkg
from personalscraper.core.delete_permit import PermitDecision, veto
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.deletion import DeleteOutcome, delete_media_folder
from personalscraper.indexer.destructive_journal import OP_DELETE, list_recent, record_destruction


class _Veto:
    """Permit that refuses every deletion."""

    def may_delete(self, path: Path) -> PermitDecision:
        return veto("seeding")


def _folder(tmp_path: Path) -> Path:
    folder = tmp_path / "Movie (2024)"
    folder.mkdir()
    (folder / "a.nfo").write_bytes(b"12345")
    return folder


def test_dry_run_measures_and_keeps_folder(tmp_path: Path) -> None:
    """A dry run measures the folder and deletes nothing."""
    folder = _folder(tmp_path)
    res = delete_media_folder(folder, db_path=tmp_path / "x.db", actor="t", label="l", dry_run=True)
    assert res.outcome is DeleteOutcome.DELETED
    assert (res.size_bytes, res.deleted_count) == (5, 1)
    assert folder.exists()


def test_delete_removes_folder_without_journal_db(tmp_path: Path) -> None:
    """A missing journal DB never blocks the deletion."""
    folder = _folder(tmp_path)
    res = delete_media_folder(folder, db_path=tmp_path / "missing.db", actor="t", label="l")
    assert res.outcome is DeleteOutcome.DELETED
    assert not folder.exists()


def test_veto_keeps_folder(tmp_path: Path) -> None:
    """A vetoed deletion leaves the folder in place."""
    folder = _folder(tmp_path)
    res = delete_media_folder(folder, db_path=tmp_path / "x.db", actor="t", label="l", permit=_Veto())
    assert res.outcome is DeleteOutcome.VETOED
    assert folder.exists()


def test_failure_reports_error(tmp_path: Path) -> None:
    """A removal that raises is reported as FAILED with its error."""
    res = delete_media_folder(tmp_path / "absent", db_path=tmp_path / "x.db", actor="t", label="l")
    assert res.outcome is DeleteOutcome.FAILED
    assert res.error


def _journal_db(tmp_path: Path) -> Path:
    """Create a migrated library.db (the schema the destructive journal uses)."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    apply_migrations(conn, Path(_migrations_pkg.__file__).parent)
    conn.close()
    return db_path


class _Spies:
    """Records every journal write and outbox publish the primitive makes."""

    def __init__(self) -> None:
        self.journal: list[dict[str, object]] = []
        self.published: list[tuple[Path, str, Path]] = []


@pytest.fixture
def spies(monkeypatch: pytest.MonkeyPatch) -> _Spies:
    """Spy on the journal (still writing for real) and the outbox publish."""
    spy = _Spies()

    def journal(db_path: Path, **kwargs: object) -> None:
        spy.journal.append(kwargs)
        record_destruction(db_path, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(deletion, "record_destruction", journal)
    monkeypatch.setattr(deletion, "_publish_deleted", lambda *args: spy.published.append(args))
    return spy


def test_deleted_writes_one_journal_row(tmp_path: Path, spies: _Spies) -> None:
    """A real deletion appends one destructive_op row with op, actor, detail, label and run_uid."""
    folder = _folder(tmp_path)
    db_path = _journal_db(tmp_path)
    res = delete_media_folder(folder, db_path=db_path, actor="disk-clean", label=".actors", run_uid="run-1")
    assert res.outcome is DeleteOutcome.DELETED
    rows = list_recent(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["op"] == OP_DELETE
    assert row["actor"] == "disk-clean"
    assert row["path"] == str(folder)
    assert row["run_uid"] == "run-1"
    assert ".actors" in str(row["detail"])


def test_deleted_publishes_outbox_event(tmp_path: Path, spies: _Spies) -> None:
    """A real deletion publishes exactly one outbox event for the removed path."""
    folder = _folder(tmp_path)
    db_path = _journal_db(tmp_path)
    delete_media_folder(folder, db_path=db_path, actor="t", label="l")
    assert spies.published == [(folder, "l", db_path)]


def test_dry_run_neither_journals_nor_publishes(tmp_path: Path, spies: _Spies) -> None:
    """A dry run leaves no journal row and publishes nothing."""
    db_path = _journal_db(tmp_path)
    delete_media_folder(_folder(tmp_path), db_path=db_path, actor="t", label="l", dry_run=True)
    assert spies.journal == []
    assert spies.published == []
    assert list_recent(db_path) == []


def test_veto_neither_journals_nor_publishes(tmp_path: Path, spies: _Spies) -> None:
    """A vetoed deletion leaves no journal row and publishes nothing."""
    db_path = _journal_db(tmp_path)
    delete_media_folder(_folder(tmp_path), db_path=db_path, actor="t", label="l", permit=_Veto())
    assert spies.journal == []
    assert spies.published == []
    assert list_recent(db_path) == []


def test_failure_neither_journals_nor_publishes(tmp_path: Path, spies: _Spies) -> None:
    """A failed removal leaves no journal row and publishes nothing."""
    db_path = _journal_db(tmp_path)
    res = delete_media_folder(tmp_path / "absent", db_path=db_path, actor="t", label="l")
    assert res.outcome is DeleteOutcome.FAILED
    assert spies.journal == []
    assert spies.published == []
    assert list_recent(db_path) == []


def test_staging_refuses_a_folder_outside_the_preprod_roots(
    tmp_path: Path, spies: _Spies, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under staging a folder outside every preprod root is refused: nothing deleted, journaled or published."""
    from personalscraper.conf import sandbox_guard
    from personalscraper.conf.sandbox_guard import SandboxGuardError
    from tests.conf.test_sandbox_guard import _config, _root

    disk, stage = _root(tmp_path, "disk"), _root(tmp_path, "stage")
    config = _config(tmp_path, disk, stage)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    folder = _folder(tmp_path)
    db_path = _journal_db(tmp_path)
    with pytest.raises(SandboxGuardError):
        delete_media_folder(folder, db_path=db_path, actor="t", label="l", config=config)
    assert folder.exists()
    assert list_recent(db_path) == []
    assert spies.journal == []
    assert spies.published == []


def test_staging_deletes_a_folder_inside_a_preprod_root(
    tmp_path: Path, spies: _Spies, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under staging a folder inside a marked, mounted root is deleted as usual."""
    from personalscraper.conf import sandbox_guard
    from tests.conf.test_sandbox_guard import _config, _root

    disk, stage = _root(tmp_path, "disk"), _root(tmp_path, "stage")
    config = _config(tmp_path, disk, stage)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    folder = disk / "Movie (2024)"
    folder.mkdir()
    res = delete_media_folder(folder, db_path=_journal_db(tmp_path), actor="t", label="l", config=config)
    assert res.outcome is DeleteOutcome.DELETED
    assert not folder.exists()


def test_dev_refuses_a_folder_outside_the_dev_roots(
    tmp_path: Path, spies: _Spies, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under dev a folder outside every dev root is refused: nothing deleted, journaled or published."""
    from personalscraper.conf import sandbox_guard
    from personalscraper.conf.sandbox_guard import SandboxGuardError
    from tests.conf.test_sandbox_guard import _config, _marked

    disk, stage = _marked(tmp_path, "disk", ".tm-dev-root"), _marked(tmp_path, "stage", ".tm-dev-root")
    config = _config(tmp_path, disk, stage)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    folder = _folder(tmp_path)
    db_path = _journal_db(tmp_path)
    with pytest.raises(SandboxGuardError):
        delete_media_folder(folder, db_path=db_path, actor="t", label="l", config=config)
    assert folder.exists()
    assert list_recent(db_path) == []
    assert spies.journal == []
    assert spies.published == []


def test_prod_unchanged_deletes_without_a_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """In prod, a folder is deleted with no config and no marker, as before."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "prod")
    folder = _folder(tmp_path)
    res = delete_media_folder(folder, db_path=_journal_db(tmp_path), actor="t", label="l")
    assert res.outcome is DeleteOutcome.DELETED
    assert not folder.exists()


def test_staging_without_a_config_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Under staging the roots are unknown without a config: the deletion fails closed."""
    from personalscraper.conf.sandbox_guard import SandboxGuardError

    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    folder = _folder(tmp_path)
    with pytest.raises(SandboxGuardError):
        delete_media_folder(folder, db_path=tmp_path / "x.db", actor="t", label="l")
    assert folder.exists()
