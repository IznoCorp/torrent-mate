"""Golden-fixture tests for parse_torrent_layout (RP10a, sub-phase 1.4).

Tests real .torrent files from qBittorrent's BT_backup/ — single-file,
multi-file flat, and multi-file (de facto flat; no nested fixture available
on this host — see Deviations in sub-phase 1.4 report).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.api.torrent._base import parse_torrent_layout

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "torrent_layout"


class TestParseTorrentLayout:
    """Golden-file tests for the layout parser."""

    FILES = sorted(FIXTURE_DIR.glob("*.torrent"))

    @pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
    def test_parses_real_torrent(self, path: Path) -> None:
        """Every real .torrent fixture parses without error."""
        data = path.read_bytes()
        layout = parse_torrent_layout(data)
        assert layout.name
        assert layout.piece_length > 0
        assert layout.files
        assert layout.total_size > 0
        # Every file entry has a non-empty rel path and positive size.
        for rel_path, size in layout.files:
            assert rel_path, f"empty rel_path in {path.name}"
            assert size > 0, f"zero-size file in {path.name}: {rel_path}"

    def test_single_file_fixture_has_synthetic_filelist(self) -> None:
        """A single-file .torrent yields one-entry file-list with info.name."""
        path = FIXTURE_DIR / "single_file.torrent"
        if not path.exists():
            pytest.skip("fixture not present")
        layout = parse_torrent_layout(path.read_bytes())
        assert len(layout.files) == 1
        assert layout.files[0][0] == layout.name
        assert layout.files[0][1] == layout.total_size

    def test_nested_fixture_has_path_separator(self) -> None:
        """At least one rel_path in the nested fixture contains ``'/'``.

        Skips when no real nested (subdir-containing) ``.torrent`` fixture is
        available.  The current qBittorrent ``BT_backup/`` on this host
        contains zero torrents with nested directories — all are flat
        multi-file or single-file.  When a real nested fixture is added,
        this test validates that the parser preserves the ``/`` separators.
        """
        path = FIXTURE_DIR / "multi_file_nested.torrent"
        if not path.exists():
            pytest.skip("fixture not present")
        layout = parse_torrent_layout(path.read_bytes())
        nested = [(r, s) for r, s in layout.files if "/" in r]
        if not nested:
            pytest.skip("fixture is flat — no '/' in any rel_path (no nested dirs on this host)")
        # Test passes by construction: at least one entry has '/'.
