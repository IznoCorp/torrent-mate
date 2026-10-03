"""Tests for personalscraper.indexer.deletion — the one folder-deletion primitive."""

from __future__ import annotations

from pathlib import Path

from personalscraper.core.delete_permit import PermitDecision, veto
from personalscraper.indexer.deletion import DeleteOutcome, delete_media_folder


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
