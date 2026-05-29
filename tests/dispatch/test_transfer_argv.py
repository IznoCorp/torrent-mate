"""Golden argv tests for _transfer.rsync and _transfer.rsync_merge.

Phase 3 baseline — authored against the PRE-refactor code to serve as the
equivalence anchor.  After the capability refactor, these tests must still
pass with ntfs_macfuse capability injected (the default), proving NTFS
behaviour is byte-identical.

The real current argv produced by ``_transfer.rsync`` is::

    ["rsync", "-a", "--no-perms", "--no-owner", "--no-group", "--no-times",
     "--omit-dir-times", "--inplace", "--partial", "--exclude=.DS_Store",
     "--exclude=._*", ...]

so ``argv[0] == "rsync"`` and the NTFS flag prefix begins at index 1.  The
assertions below therefore pin ``called_cmd[0] == "rsync"`` and
``called_cmd[1 : 1 + len(NTFS_FLAGS_PREFIX)] == NTFS_FLAGS_PREFIX``.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import personalscraper.dispatch._transfer as _transfer
from personalscraper.indexer._fs_capability import APFS, NTFS_MACFUSE

NTFS_FLAGS_PREFIX = [
    "-a",
    "--no-perms",
    "--no-owner",
    "--no-group",
    "--no-times",
    "--omit-dir-times",
    "--inplace",
    "--partial",
    "--exclude=.DS_Store",
    "--exclude=._*",
]

APFS_FLAGS_PREFIX = [
    "-a",
    "--inplace",
    "--partial",
]


class TestRsyncArgvNtfs:
    """Golden pin: rsync() argv for NTFS dest (byte-identical to legacy)."""

    def test_rsync_ntfs_argv_no_delete(self, tmp_path: Path) -> None:
        """rsync() with no delete pins the full NTFS flag prefix and paths."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync(source, dest)

        called_cmd = mock_run.call_args[0][0]
        # argv[0] is the rsync binary; the NTFS flag prefix starts at index 1.
        assert called_cmd[0] == "rsync"
        assert called_cmd[1 : 1 + len(NTFS_FLAGS_PREFIX)] == NTFS_FLAGS_PREFIX
        # source/dest are appended last, in order.
        assert called_cmd[-2] == f"{source}/"
        assert called_cmd[-1] == str(dest)
        assert "--delete" not in called_cmd

    def test_rsync_ntfs_argv_with_delete(self, tmp_path: Path) -> None:
        """rsync(delete=True) keeps the NTFS prefix and appends --delete."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync(source, dest, delete=True)

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "rsync"
        assert called_cmd[1 : 1 + len(NTFS_FLAGS_PREFIX)] == NTFS_FLAGS_PREFIX
        assert "--delete" in called_cmd
        # --delete sits between the flag prefix and the source/dest pair.
        assert called_cmd[-3] == "--delete"
        assert called_cmd[-2] == f"{source}/"
        assert called_cmd[-1] == str(dest)

    def test_rsync_ntfs_argv_full_equivalence(self, tmp_path: Path) -> None:
        """Byte-identical equivalence: the entire argv equals the legacy list."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync(source, dest)

        called_cmd = mock_run.call_args[0][0]
        expected = ["rsync", *NTFS_FLAGS_PREFIX, f"{source}/", str(dest)]
        assert called_cmd == expected


class TestRsyncMergeArgvNtfs:
    """Golden pin: rsync_merge() argv for NTFS dest (byte-identical to legacy)."""

    def test_rsync_merge_ntfs_argv(self, tmp_path: Path) -> None:
        """rsync_merge() pins the NTFS prefix plus --backup/--backup-dir ordering."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        backup = tmp_path / "backup"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync_merge(source, dest, backup)

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "rsync"
        assert called_cmd[1 : 1 + len(NTFS_FLAGS_PREFIX)] == NTFS_FLAGS_PREFIX
        assert "--backup" in called_cmd
        assert f"--backup-dir={backup}" in called_cmd

    def test_rsync_merge_ntfs_argv_full_equivalence(self, tmp_path: Path) -> None:
        """Byte-identical equivalence for the merge argv (exact ordering)."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        backup = tmp_path / "backup"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync_merge(source, dest, backup)

        called_cmd = mock_run.call_args[0][0]
        expected = [
            "rsync",
            *NTFS_FLAGS_PREFIX,
            "--backup",
            f"--backup-dir={backup}",
            f"{source}/",
            str(dest),
        ]
        assert called_cmd == expected


class TestRsyncArgvApfs:
    """APFS capability drops NTFS-only flags."""

    def test_rsync_apfs_no_no_perms(self, tmp_path: Path) -> None:
        """rsync(capability=APFS) drops perms/metadata/AppleDouble flags."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync(source, dest, capability=APFS)

        called_cmd = mock_run.call_args[0][0]
        assert "--no-perms" not in called_cmd
        assert "--no-owner" not in called_cmd
        assert "--no-group" not in called_cmd
        assert "--no-times" not in called_cmd
        assert "--omit-dir-times" not in called_cmd
        assert "--exclude=.DS_Store" not in called_cmd
        assert "--exclude=._*" not in called_cmd
        # Core FS-agnostic flags still present.
        assert "-a" in called_cmd
        assert "--inplace" in called_cmd
        assert "--partial" in called_cmd

    def test_rsync_apfs_full_equivalence(self, tmp_path: Path) -> None:
        """The full APFS argv equals the POSIX flag prefix plus paths."""
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync(source, dest, capability=APFS)

        called_cmd = mock_run.call_args[0][0]
        expected = ["rsync", *APFS_FLAGS_PREFIX, f"{source}/", str(dest)]
        assert called_cmd == expected


class TestHasNtfsIllegalNamesPosix:
    """On a POSIX-capable FS (illegal_name_regex=None), colon names are allowed."""

    def test_colon_name_not_flagged_on_apfs(self, tmp_path: Path) -> None:
        """APFS has no illegal-name regex — a colon filename is not flagged."""
        colon_dir = tmp_path / "show"
        colon_dir.mkdir()
        (colon_dir / "Episode S01E01: Pilot.mkv").touch()

        # APFS has no illegal-name regex — must return False.
        result = _transfer.has_ntfs_illegal_names(colon_dir, pattern=APFS.illegal_name_regex)
        assert result is False

    def test_colon_name_flagged_on_ntfs(self, tmp_path: Path) -> None:
        """NTFS regex flags a colon filename (the default restrictive set)."""
        colon_dir = tmp_path / "show"
        colon_dir.mkdir()
        (colon_dir / "Episode S01E01: Pilot.mkv").touch()

        result = _transfer.has_ntfs_illegal_names(colon_dir, pattern=NTFS_MACFUSE.illegal_name_regex)
        assert result is True
