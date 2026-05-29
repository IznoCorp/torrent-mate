"""Tests for personalscraper.indexer._fs_probe.

Regression test for the ufsd_NTFS dead-branch bug: _spotlight.py used exact-token
matching, so the real production token "ufsd_NTFS" returned "ufsd_ntfs" (not
"macfuse"), causing try_attach() to fall through to the wrong branch.
FsProbe uses substring matching, fixing this at the root.
"""

import pytest

from personalscraper.indexer._fs_probe import (
    _build_mount_table,
    _parse_mount_line,
    canonical_fs_type,
    probe_mount,
)

pytestmark = pytest.mark.multifs

# ---------------------------------------------------------------------------
# canonical_fs_type
# ---------------------------------------------------------------------------


class TestCanonicalFsType:
    """Unit tests for canonical_fs_type()."""

    def test_ufsd_ntfs_maps_to_ntfs_macfuse(self) -> None:
        """Regression: the real production token ufsd_NTFS must map to ntfs_macfuse.

        This is the root cause of the _spotlight.py dead-branch bug: exact-token
        matching returned 'ufsd_ntfs', which never equalled 'macfuse'.
        """
        assert canonical_fs_type("ufsd_NTFS") == "ntfs_macfuse"

    def test_ufsd_ntfs_lowercase(self) -> None:
        """The lowercase ``ufsd_ntfs`` token also maps to ntfs_macfuse."""
        assert canonical_fs_type("ufsd_ntfs") == "ntfs_macfuse"

    def test_macfuse_token(self) -> None:
        """The bare ``macfuse`` driver token maps to ntfs_macfuse."""
        assert canonical_fs_type("macfuse") == "ntfs_macfuse"

    def test_fuse_osxfuse_token(self) -> None:
        """The ``fuse_osxfuse`` driver token maps to ntfs_macfuse."""
        assert canonical_fs_type("fuse_osxfuse") == "ntfs_macfuse"

    def test_osxfuse_token(self) -> None:
        """The ``osxfuse`` driver token maps to ntfs_macfuse."""
        assert canonical_fs_type("osxfuse") == "ntfs_macfuse"

    def test_ntfs_bare_token(self) -> None:
        """The bare ``ntfs`` token maps to ntfs_macfuse."""
        assert canonical_fs_type("ntfs") == "ntfs_macfuse"

    def test_fuse_t_token(self) -> None:
        """The ``fuse-t`` driver token maps to ntfs_macfuse."""
        assert canonical_fs_type("fuse-t") == "ntfs_macfuse"

    def test_apfs(self) -> None:
        """An ``apfs`` token maps to the apfs canonical key."""
        assert canonical_fs_type("apfs") == "apfs"

    def test_apfs_uppercase(self) -> None:
        """Canonicalisation is case-insensitive for apfs."""
        assert canonical_fs_type("APFS") == "apfs"

    def test_hfs(self) -> None:
        """The legacy ``hfs`` token maps to hfsplus."""
        assert canonical_fs_type("hfs") == "hfsplus"

    def test_hfsplus(self) -> None:
        """An ``hfsplus`` token maps to hfsplus."""
        assert canonical_fs_type("hfsplus") == "hfsplus"

    def test_exfat(self) -> None:
        """An ``exfat`` token maps to the exfat canonical key."""
        assert canonical_fs_type("exfat") == "exfat"

    def test_ext4(self) -> None:
        """An ``ext4`` token maps to the ext4 canonical key."""
        assert canonical_fs_type("ext4") == "ext4"

    def test_unknown_token(self) -> None:
        """An unrecognised token falls back to unknown."""
        assert canonical_fs_type("tmpfs") == "unknown"

    def test_empty_string(self) -> None:
        """An empty fs-type token falls back to unknown."""
        assert canonical_fs_type("") == "unknown"


# ---------------------------------------------------------------------------
# _parse_mount_line
# ---------------------------------------------------------------------------


class TestParseMountLine:
    """Unit tests for _parse_mount_line()."""

    def test_real_ntfs_line(self) -> None:
        """Parse a real-world macFUSE-NTFS mount line."""
        line = "/dev/disk2s1 on /Volumes/Disk1 (ufsd_NTFS, local, noatime)"
        info = _parse_mount_line(line)
        assert info is not None
        assert info.mount_point == "/Volumes/Disk1"
        assert info.fs_type == "ntfs_macfuse"
        assert info.raw_fs_type == "ufsd_ntfs"
        assert "local" in info.flags
        assert "noatime" in info.flags

    def test_apfs_line(self) -> None:
        """Parse a root APFS mount line."""
        line = "/dev/disk1s1 on / (apfs, local, journaled)"
        info = _parse_mount_line(line)
        assert info is not None
        assert info.mount_point == "/"
        assert info.fs_type == "apfs"

    def test_auto_home_line(self) -> None:
        """An autofs map line parses with an unknown canonical fs-type."""
        line = "map auto_home on /home (autofs, automounted, nobrowse)"
        info = _parse_mount_line(line)
        assert info is not None
        assert info.mount_point == "/home"
        assert info.fs_type == "unknown"

    def test_malformed_line_returns_none(self) -> None:
        """A line without the expected structure returns None."""
        assert _parse_mount_line("not a mount line") is None

    def test_trailing_slash_stripped(self) -> None:
        """A non-root mount point has its trailing slash stripped."""
        line = "/dev/disk3s1 on /Volumes/HFS/ (hfs, local)"
        info = _parse_mount_line(line)
        assert info is not None
        assert not info.mount_point.endswith("/")

    def test_root_mount_point_preserved(self) -> None:
        """Regression: a bare root mount ("/") must NOT collapse to "".

        Blindly ``rstrip("/")``-ing the mount point turns "/" into "", which
        then prefix-matches every absolute path in :func:`probe_mount`. The
        lone root slash is preserved instead.
        """
        line = "/dev/disk1s1 on / (apfs, local, journaled)"
        info = _parse_mount_line(line)
        assert info is not None
        assert info.mount_point == "/"


# ---------------------------------------------------------------------------
# _build_mount_table
# ---------------------------------------------------------------------------


class TestBuildMountTable:
    """Unit tests for _build_mount_table()."""

    SAMPLE_MOUNT = """\
/dev/disk1s1 on / (apfs, local, journaled)
/dev/disk2s1 on /Volumes/Disk1 (ufsd_NTFS, local, noatime)
map auto_home on /home (autofs, automounted, nobrowse)
"""

    def test_parses_all_lines(self) -> None:
        """Every well-formed mount line is keyed into the table."""
        table = _build_mount_table(self.SAMPLE_MOUNT)
        assert "/" in table
        assert "/Volumes/Disk1" in table
        assert "/home" in table

    def test_ntfs_entry_canonical(self) -> None:
        """The NTFS entry carries the ntfs_macfuse canonical fs-type."""
        table = _build_mount_table(self.SAMPLE_MOUNT)
        assert table["/Volumes/Disk1"].fs_type == "ntfs_macfuse"

    def test_apfs_entry(self) -> None:
        """The root entry carries the apfs canonical fs-type."""
        table = _build_mount_table(self.SAMPLE_MOUNT)
        assert table["/"].fs_type == "apfs"


# ---------------------------------------------------------------------------
# probe_mount (with injected mount output)
# ---------------------------------------------------------------------------


class TestProbeMount:
    """Tests for probe_mount() using monkeypatched _run_mount."""

    SAMPLE_MOUNT = """\
/dev/disk1s1 on / (apfs, local, journaled)
/dev/disk2s1 on /Volumes/Disk1 (ufsd_NTFS, local, noatime)
"""

    def test_probe_ntfs_volume(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A path under an NTFS volume probes to that volume's MountInfo."""
        import personalscraper.indexer._fs_probe as mod

        monkeypatch.setattr(mod, "_run_mount", lambda: self.SAMPLE_MOUNT)
        info = probe_mount("/Volumes/Disk1/Movies/Foo")
        assert info is not None
        assert info.fs_type == "ntfs_macfuse"
        assert info.mount_point == "/Volumes/Disk1"

    def test_probe_returns_most_specific_mount(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The longest matching mount point wins over a shorter prefix."""
        mount_out = """\
/dev/disk1s1 on / (apfs, local)
/dev/disk2s1 on /Volumes/Disk1 (ufsd_NTFS, local)
"""
        import personalscraper.indexer._fs_probe as mod

        monkeypatch.setattr(mod, "_run_mount", lambda: mount_out)
        info = probe_mount("/Volumes/Disk1/deep/path")
        assert info is not None
        assert info.mount_point == "/Volumes/Disk1"

    def test_probe_returns_none_when_no_match(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A path under no listed volume returns None.

        The mount table here deliberately omits the root ("/") entry: a root
        mount is a catch-all that prefix-matches every absolute path, so a
        genuine "no match" can only occur when no listed mount point (root
        included) contains the path.
        """
        mount_out = "/dev/disk2s1 on /Volumes/Disk1 (ufsd_NTFS, local, noatime)\n"
        import personalscraper.indexer._fs_probe as mod

        monkeypatch.setattr(mod, "_run_mount", lambda: mount_out)
        info = probe_mount("/nonexistent/path")
        assert info is None

    def test_probe_returns_none_on_empty_mount_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty mount output (FsProbe failure signal) probes to None."""
        import personalscraper.indexer._fs_probe as mod

        monkeypatch.setattr(mod, "_run_mount", lambda: "")
        info = probe_mount("/Volumes/Disk1/foo")
        assert info is None
