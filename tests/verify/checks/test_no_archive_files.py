"""Tests for the ``no_archive_files`` dispatch check (DEV #1 safety net).

A media item that still holds un-extracted archive parts (extraction failed)
must be blocked from dispatch so a RAR set is never shipped to the library.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checks.base import CheckContext, CheckStage, Severity
from personalscraper.verify.checks.structure import NoArchiveFiles


def _ctx(media_dir: Path, media_type: str, test_config) -> CheckContext:
    """Build a minimal DISPATCH-stage CheckContext."""
    return CheckContext(
        media_dir=media_dir,
        media_type=media_type,
        stage=CheckStage.DISPATCH,
        config=test_config,
        patterns=NamingPatterns(),
    )


class TestNoArchiveFiles:
    """``no_archive_files`` blocks items that still hold archives."""

    def test_passes_when_no_archives(self, tmp_path: Path, test_config) -> None:
        """A clean, archive-free show passes the check."""
        (tmp_path / "Saison 01").mkdir()
        (tmp_path / "Saison 01" / "S01E01 - Pilot.mkv").write_bytes(b"\0" * 64)

        results = NoArchiveFiles().run(_ctx(tmp_path, "tvshow", test_config))

        assert len(results) == 1
        assert results[0].passed is True

    def test_fails_on_leftover_rar(self, tmp_path: Path, test_config) -> None:
        """A retained .rar (failed extraction) blocks dispatch with ERROR."""
        rel = tmp_path / "Rafa.S01E01.DOC-Penrose"
        rel.mkdir()
        (rel / "release.rar").write_bytes(b"RAR")
        (rel / "release.r00").write_bytes(b"VOL")

        results = NoArchiveFiles().run(_ctx(tmp_path, "tvshow", test_config))

        assert results[0].passed is False
        assert results[0].severity is Severity.ERROR
        assert "archives" in results[0].message.lower()

    def test_fails_on_movie_archive(self, tmp_path: Path, test_config) -> None:
        """A movie holding a .7z archive is blocked."""
        (tmp_path / "movie.2026.7z").write_bytes(b"7Z")

        results = NoArchiveFiles().run(_ctx(tmp_path, "movie", test_config))

        assert results[0].passed is False
