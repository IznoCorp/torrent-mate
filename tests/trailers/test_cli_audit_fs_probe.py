"""Filesystem-probe audit tests — F6 (trailers audit reports EXISTING trailers).

Constitution P26: the filesystem is the single truth for trailer existence and
§8 requires the audit to *show what exists*, not only what is missing. The
legacy ``trailers audit`` was built on the items-WITHOUT-trailer query
(``find_items_without_trailer`` → items lacking a ``trailer_found`` attribute,
further filtered to those with no trailer file on disk), so an item whose
trailer *exists* was invisible to the audit. These tests seed a real indexer DB
with a dispatched item that already has its trailer on disk and assert the audit
surfaces it (F6 — test-first).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_OPEN_DB = "personalscraper.indexer.db.open_db"

_TRAILER_BYTES = b"x" * 200_000  # comfortably above the 100 KiB min_file_size


def _fake_config(tmp_path: Path) -> MagicMock:
    """Build a minimal mock config sufficient to drive ``trailers audit``.

    Args:
        tmp_path: Pytest tmp_path fixture (state-file location).

    Returns:
        A ``MagicMock`` satisfying the attribute access the audit performs.
    """
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.filters.min_file_size_bytes = 102400
    cfg.trailers.filters.allowed_extensions = {"mp4", "mkv", "webm"}
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.seasons.enabled = False
    cfg.paths.staging_dir = tmp_path
    cfg.disks = []
    # No torrent client configured — a bare MagicMock makes ``torrent.active``
    # truthy and trips the boot fail-fast in _build_app_context.
    cfg.torrent.active = ""
    return cfg


def _open_seeded_db() -> sqlite3.Connection:
    """Open an in-memory SQLite connection with the full indexer schema applied.

    Returns:
        An open connection carrying every table the query layer needs.
    """
    from personalscraper.indexer.db import apply_migrations

    conn = sqlite3.connect(":memory:")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _seed_dispatched_movie(
    conn: sqlite3.Connection,
    tmp_path: Path,
    *,
    title: str = "Fight Club",
    with_trailer_on_disk: bool = True,
) -> Path:
    """Insert one dispatched movie and (optionally) place its trailer on disk.

    The item deliberately has NO ``trailer_found`` attribute so the legacy
    without-trailer query would surface it only when the trailer is *absent* —
    exactly the blind spot F6 closes.

    Args:
        conn: Open seeded connection.
        tmp_path: Base temp directory for the fake media dir.
        title: Movie title.
        with_trailer_on_disk: When True, write a valid-size ``-trailer.mp4``.

    Returns:
        Path to the created media directory.
    """
    movie_dir = tmp_path / f"{title} (1999)"
    movie_dir.mkdir(parents=True, exist_ok=True)
    external_ids_json = json.dumps({"tmdb": {"series_id": "550", "episode_id": None}})
    conn.execute(
        "INSERT INTO media_item (id, kind, title, title_sort, year, category_id, "
        "external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES (1, 'movie', ?, ?, 1999, 'movies', ?, NULL, NULL, 'valid', NULL, 0, 0, 0, 'fr')",
        (title, title, external_ids_json),
    )
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (1, 'dispatch_path', ?)",
        (str(movie_dir),),
    )
    conn.commit()
    if with_trailer_on_disk:
        (movie_dir / f"{movie_dir.name}-trailer.mp4").write_bytes(_TRAILER_BYTES)
    return movie_dir


class TestTrailersAuditFsProbe:
    """F6 — ``trailers audit`` must report trailers that EXIST on disk."""

    def test_trailers_audit_fs_probe_reports_existing_trailer(self, tmp_path: Path) -> None:
        """An on-disk trailer is surfaced by the audit (not only missing ones).

        The legacy audit was built on the without-trailer query, so an item that
        already has its trailer never appeared in the output. This pins that the
        FS-probe audit lists the existing trailer by title.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        conn = _open_seeded_db()
        _seed_dispatched_movie(conn, tmp_path, with_trailer_on_disk=True)

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_OPEN_DB, return_value=conn),
        ):
            result = runner.invoke(app, ["trailers", "audit"])

        assert result.exit_code == 0, result.output
        # F6: the existing trailer must be visible in the audit output.
        assert "Fight Club" in result.output, result.output
        assert "existing" in result.output.lower(), result.output

    def test_trailers_audit_fs_probe_still_flags_missing(self, tmp_path: Path) -> None:
        """A dispatched item with no trailer on disk is still reported as missing.

        Guards against the FS-probe rebuild silently dropping the missing-trailer
        signal (exit code 2) while adding the existing listing.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        conn = _open_seeded_db()
        _seed_dispatched_movie(conn, tmp_path, title="Heat", with_trailer_on_disk=False)

        with (
            patch(_PATCH_LOAD_CONFIG, return_value=_fake_config(tmp_path)),
            patch(_PATCH_OPEN_DB, return_value=conn),
        ):
            result = runner.invoke(app, ["trailers", "audit"])

        assert result.exit_code == 2, result.output
        assert "Heat" in result.output, result.output
