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

    def test_synthetic_nested_path_join(self) -> None:
        """Multi-file info dict with multi-component path lists joins with ``'/'``.

        Synthetic bencode covering the nested-directory code path (no real
        nested ``.torrent`` fixture is available on this host — all qBittorrent
        torrents are flat multi-file or single-file).  Craft a minimal info
        dict with two files whose ``path`` lists have depth 2 (e.g.
        ``["Season 01", "ep1.mkv"]``) and assert the parser joins components
        with ``/`` and preserves sizes.
        """
        # Top-level dict → info dict with:
        #   name="Show.S01", piece length=262144,
        #   files=[ {length:1000, path:["Season 01","ep1.mkv"]},
        #           {length:2000, path:["Season 02","ep1.mkv"]} ]
        data = (
            b"d4:infod4:name8:Show.S0112:piece lengthi262144e5:filesl"
            b"d6:lengthi1000e4:pathl9:Season 017:ep1.mkvee"
            b"d6:lengthi2000e4:pathl9:Season 027:ep1.mkvee"
            b"eeee"
        )
        layout = parse_torrent_layout(data)
        assert layout.name == "Show.S01"
        assert len(layout.files) == 2
        assert layout.files[0] == ("Season 01/ep1.mkv", 1000)
        assert layout.files[1] == ("Season 02/ep1.mkv", 2000)
        assert layout.total_size == 3000
