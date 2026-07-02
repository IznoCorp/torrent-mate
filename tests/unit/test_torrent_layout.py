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

    # --- Golden exact-value pins for the 3 committed fixtures (sub-phase 10.10a) ---

    def test_single_file_golden_pin(self) -> None:
        """Pinned from fixture ground truth: single_file.torrent."""
        path = FIXTURE_DIR / "single_file.torrent"
        if not path.exists():
            pytest.skip("fixture not present")
        layout = parse_torrent_layout(path.read_bytes())
        # pinned from fixture ground truth
        assert layout.name == "House.of.the.Dragon.S03E01.MULTi.1080p.WEB.H265-TyHD.mkv"
        assert layout.piece_length == 2_097_152
        assert len(layout.files) == 1
        assert layout.total_size == 1_709_268_712
        assert layout.meta_version == 1

    def test_multi_file_golden_pin(self) -> None:
        """Pinned from fixture ground truth: multi_file.torrent."""
        path = FIXTURE_DIR / "multi_file.torrent"
        if not path.exists():
            pytest.skip("fixture not present")
        layout = parse_torrent_layout(path.read_bytes())
        # pinned from fixture ground truth
        assert layout.name == ("Rafa.S01.MULTI.AD.1080p.WEB.NF.DV.HDR.H265.EAC3.5.1.Atmos-Amen")
        assert layout.piece_length == 4_194_304
        assert len(layout.files) == 4
        assert layout.total_size == 5_522_454_799
        assert layout.meta_version == 1

    def test_multi_file_13_golden_pin(self) -> None:
        """Pinned from fixture ground truth: multi_file_13.torrent."""
        path = FIXTURE_DIR / "multi_file_13.torrent"
        if not path.exists():
            pytest.skip("fixture not present")
        layout = parse_torrent_layout(path.read_bytes())
        # pinned from fixture ground truth
        assert layout.name == "Les.Groos.2026.S01.VFF.1080p.WEBRip.AAC.2.0.x264-LOLOPC"
        assert layout.piece_length == 16_777_216
        assert len(layout.files) == 13
        assert layout.total_size == 1_004_276_088
        assert layout.meta_version == 1

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


class TestParseTorrentLayoutAdversarial:
    """Adversarial and edge-case tests for the layout parser (sub-phase 1.5)."""

    def test_truncated_bencode_raises_valueerror(self) -> None:
        """A truncated bencode (dict start with integer but no closing ``e``) raises ValueError."""
        with pytest.raises(ValueError):
            parse_torrent_layout(b"di1e")

    def test_empty_bytes_raises_valueerror(self) -> None:
        """Empty byte string raises ValueError (not a bencoded dict)."""
        with pytest.raises(ValueError):
            parse_torrent_layout(b"")

    def test_missing_info_name_raises_valueerror(self) -> None:
        """Info dict without a ``name`` key raises ValueError."""
        with pytest.raises(ValueError):
            parse_torrent_layout(b"d4:infod12:piece lengthi262144e6:lengthi1000eee")

    def test_missing_piece_length_raises_valueerror(self) -> None:
        """Info dict without a ``piece length`` key raises ValueError."""
        with pytest.raises(ValueError):
            parse_torrent_layout(b"d4:infod4:name3:foo6:lengthi1000eee")

    def test_missing_both_files_and_length_raises_valueerror(self) -> None:
        """Info dict with neither ``files`` nor ``length`` raises ValueError."""
        with pytest.raises(ValueError):
            parse_torrent_layout(b"d4:infod4:name3:foo12:piece lengthi262144eee")

    def test_empty_files_list_raises_valueerror(self) -> None:
        """Info dict with an empty ``files`` list raises ValueError."""
        with pytest.raises(ValueError):
            parse_torrent_layout(b"d4:infod4:name3:foo12:piece lengthi262144e5:filesleee")

    def test_deep_nesting_raises_valueerror(self) -> None:
        """Bencode nesting beyond ``_MAX_BENCODE_DEPTH`` (100) raises ValueError.

        Builds a deeply nested list (101 levels) inside the info dict under an
        unknown key so that ``_bencode_end`` recursion trips the depth guard.
        """
        # Build 101 nested lists around a terminal value: l(l(...l(0:)e...)e)e
        inner = b"0:"
        for _ in range(101):
            inner = b"l" + inner + b"e"
        # Embed under an unknown key inside info → _parse_info_walk skips it via
        # _bencode_end, which recurses past _MAX_BENCODE_DEPTH.
        data = b"d4:infod1:x" + inner + b"ee"
        with pytest.raises(ValueError):
            parse_torrent_layout(data)

    def test_v2_hybrid_detected(self) -> None:
        """A single-file v2/hybrid torrent has ``meta_version == 2``.

        The phase file's example bytes are fixed to include a ``length`` key
        (required by the parser even for v2 torrents).
        """
        data = b"d4:infod4:name5:test412:piece lengthi262144e6:lengthi1000000e12:meta versioni2e6:pieces0:ee"
        layout = parse_torrent_layout(data)
        assert layout.meta_version == 2
        assert layout.name == "test4"
        assert layout.files == (("test4", 1_000_000),)


class TestTorrentLayoutValidation:
    """Adversarial tests for :class:`TorrentLayout.__post_init__` (sub-phase 10.10c)."""

    def test_empty_files_raises_valueerror(self) -> None:
        """``TorrentLayout(files=())`` raises ValueError."""
        from personalscraper.api.torrent._layout import TorrentLayout

        with pytest.raises(ValueError, match="files must not be empty"):
            TorrentLayout(
                name="test",
                piece_length=262144,
                files=(),
                total_size=0,
            )

    def test_piece_length_zero_raises_valueerror(self) -> None:
        """``TorrentLayout(piece_length=0)`` raises ValueError."""
        from personalscraper.api.torrent._layout import TorrentLayout

        with pytest.raises(ValueError, match="piece_length must be > 0"):
            TorrentLayout(
                name="test",
                piece_length=0,
                files=(("f.mkv", 1000),),
                total_size=1000,
            )

    def test_piece_length_negative_raises_valueerror(self) -> None:
        """``TorrentLayout(piece_length=-1)`` raises ValueError."""
        from personalscraper.api.torrent._layout import TorrentLayout

        with pytest.raises(ValueError, match="piece_length must be > 0"):
            TorrentLayout(
                name="test",
                piece_length=-1,
                files=(("f.mkv", 1000),),
                total_size=1000,
            )

    def test_negative_file_size_raises_valueerror(self) -> None:
        """A file entry with negative size raises ValueError."""
        from personalscraper.api.torrent._layout import TorrentLayout

        with pytest.raises(ValueError, match="File size must be >= 0"):
            TorrentLayout(
                name="test",
                piece_length=262144,
                files=(("f.mkv", -1),),
                total_size=-1,
            )

    def test_total_size_lie_raises_valueerror(self) -> None:
        """``TorrentLayout(total_size != sum(sizes))`` raises ValueError."""
        from personalscraper.api.torrent._layout import TorrentLayout

        with pytest.raises(ValueError, match="total_size.*does not match"):
            TorrentLayout(
                name="test",
                piece_length=262144,
                files=(("f.mkv", 1000),),
                total_size=9999,  # lie
            )
