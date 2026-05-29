"""Tests for personalscraper.indexer._fs_capability.

Verifies the FilesystemCapability table: field values per fs_type, the
unknown==ntfs_macfuse invariant, and the byte-identical NTFS rsync-flags pin.
"""

import pytest

from personalscraper.indexer._fs_capability import (
    APFS,
    EXFAT,
    EXT4,
    HFSPLUS,
    NTFS_MACFUSE,
    UNKNOWN,
    FilesystemCapability,
    capability_for,
    resolve_capability,
)

pytestmark = pytest.mark.multifs

# ---------------------------------------------------------------------------
# Golden pin: NTFS rsync flags must be byte-identical to _transfer.py:103-115
# ---------------------------------------------------------------------------


class TestNtfsRsyncFlagsPin:
    """Pinned golden test — any change here must also change _transfer.py."""

    EXPECTED_FLAGS = (
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
    )

    def test_ntfs_rsync_flags_byte_identical_to_legacy(self) -> None:
        """NTFS rsync flags must match the former hardcoded list in _transfer.py."""
        assert NTFS_MACFUSE.rsync_flags == self.EXPECTED_FLAGS

    def test_unknown_rsync_flags_identical_to_ntfs(self) -> None:
        """Unknown falls back to NTFS-safe superset."""
        assert UNKNOWN.rsync_flags == self.EXPECTED_FLAGS


# ---------------------------------------------------------------------------
# AC-02: unknown == ntfs_macfuse (every field)
# ---------------------------------------------------------------------------


class TestUnknownFallback:
    """AC-02: capability_for('unknown') must equal capability_for('ntfs_macfuse')."""

    def test_unknown_equals_ntfs_macfuse_full(self) -> None:
        """The unknown entry must equal ntfs_macfuse on every behavioural field."""
        assert capability_for("unknown") == capability_for("ntfs_macfuse")

    def test_unknown_forbids_unix_perms(self) -> None:
        """Unknown inherits the NTFS Unix-perms suppression."""
        assert UNKNOWN.forbids_unix_perms is True

    def test_unknown_forbids_apple_metadata(self) -> None:
        """Unknown inherits the NTFS AppleDouble exclusions."""
        assert UNKNOWN.forbids_apple_metadata is True

    def test_unknown_has_ntfs_illegal_regex(self) -> None:
        """Unknown inherits the NTFS illegal-filename regex."""
        assert UNKNOWN.illegal_name_regex is not None

    def test_unrecognised_key_returns_unknown(self) -> None:
        """Any unrecognised fs-type key resolves to the unknown fallback."""
        cap = capability_for("nfs")
        assert cap == UNKNOWN


# ---------------------------------------------------------------------------
# AC-03: NTFS rsync flags (via capability_for)
# ---------------------------------------------------------------------------


class TestNtfsMacfuse:
    """AC-03: the ntfs_macfuse entry's fields."""

    def test_fs_type_key(self) -> None:
        """The fs_type key is 'ntfs_macfuse'."""
        assert NTFS_MACFUSE.fs_type == "ntfs_macfuse"

    def test_forbids_unix_perms(self) -> None:
        """NTFS forbids Unix perms (suppressed via --no-perms et al.)."""
        assert NTFS_MACFUSE.forbids_unix_perms is True

    def test_forbids_apple_metadata(self) -> None:
        """NTFS forbids AppleDouble metadata files."""
        assert NTFS_MACFUSE.forbids_apple_metadata is True

    def test_illegal_name_regex_matches_colon(self) -> None:
        """The NTFS illegal-name regex flags a colon character."""
        assert NTFS_MACFUSE.illegal_name_regex is not None
        assert NTFS_MACFUSE.illegal_name_regex.search("file:name") is not None

    def test_tier1_uses_ctime(self) -> None:
        """NTFS keeps ctime in the tier-1 drift tuple."""
        assert NTFS_MACFUSE.tier1_uses_ctime is True

    def test_mtime_granularity_exact(self) -> None:
        """NTFS uses exact (1 ns) mtime comparison granularity."""
        assert NTFS_MACFUSE.mtime_granularity_ns == 1

    def test_capability_for_lookup(self) -> None:
        """capability_for('ntfs_macfuse') returns the NTFS_MACFUSE singleton."""
        assert capability_for("ntfs_macfuse") is NTFS_MACFUSE


# ---------------------------------------------------------------------------
# AC-04: APFS drops NTFS-only flags
# ---------------------------------------------------------------------------


class TestApfs:
    """AC-04: APFS drops the NTFS-only rsync flags."""

    def test_no_no_perms_flag(self) -> None:
        """APFS does not carry --no-perms."""
        assert "--no-perms" not in APFS.rsync_flags

    def test_no_no_times_flag(self) -> None:
        """APFS does not carry --no-times."""
        assert "--no-times" not in APFS.rsync_flags

    def test_no_omit_dir_times(self) -> None:
        """APFS does not carry --omit-dir-times."""
        assert "--omit-dir-times" not in APFS.rsync_flags

    def test_no_appledouble_excludes(self) -> None:
        """APFS does not carry the AppleDouble exclude flags."""
        assert "--exclude=.DS_Store" not in APFS.rsync_flags
        assert "--exclude=._*" not in APFS.rsync_flags

    def test_does_not_forbid_unix_perms(self) -> None:
        """APFS permits Unix perms."""
        assert APFS.forbids_unix_perms is False

    def test_does_not_forbid_apple_metadata(self) -> None:
        """APFS permits AppleDouble metadata."""
        assert APFS.forbids_apple_metadata is False

    def test_dir_mtime_reliable_true(self) -> None:
        """APFS hard-wires dir-mtime reliability to True."""
        assert APFS.dir_mtime_reliable_default is True


# ---------------------------------------------------------------------------
# AC-05: APFS has no NTFS illegal-name restriction
# ---------------------------------------------------------------------------


class TestApfsNamePolicy:
    """AC-05: APFS imposes no NTFS illegal-name restriction."""

    def test_illegal_name_regex_is_none(self) -> None:
        """APFS has no illegal-name regex."""
        assert APFS.illegal_name_regex is None

    def test_colon_not_illegal_on_apfs(self) -> None:
        """A name with ':' must NOT be flagged as illegal on APFS (AC-05)."""
        r = APFS.illegal_name_regex
        assert r is None or r.search("a:b") is None


# ---------------------------------------------------------------------------
# AC-06: exFAT — no ctime, 2s mtime granularity
# ---------------------------------------------------------------------------


class TestExfat:
    """AC-06: exFAT has no ctime and a 2s mtime granularity."""

    def test_tier1_uses_ctime_false(self) -> None:
        """ExFAT drops ctime from the tier-1 drift tuple."""
        assert EXFAT.tier1_uses_ctime is False

    def test_mtime_granularity_2s(self) -> None:
        """ExFAT rounds mtime to 2s before comparing."""
        assert EXFAT.mtime_granularity_ns == 2_000_000_000

    def test_appledouble_excluded(self) -> None:
        """ExFAT keeps the AppleDouble exclude flags (macOS junk on exFAT)."""
        assert "--exclude=.DS_Store" in EXFAT.rsync_flags

    def test_does_not_forbid_unix_perms(self) -> None:
        """ExFAT permits Unix perms."""
        assert EXFAT.forbids_unix_perms is False


# ---------------------------------------------------------------------------
# AC-07: HFS+ (AppleRAID target) — full POSIX, no NTFS restrictions
# ---------------------------------------------------------------------------


class TestHfsplus:
    """AC-07: HFS+ (AppleRAID target) has full POSIX and no NTFS restrictions."""

    def test_does_not_forbid_unix_perms(self) -> None:
        """HFS+ permits Unix perms."""
        assert HFSPLUS.forbids_unix_perms is False

    def test_illegal_name_regex_is_none(self) -> None:
        """HFS+ has no illegal-name regex."""
        assert HFSPLUS.illegal_name_regex is None

    def test_mtime_granularity_1s(self) -> None:
        """HFS+ rounds mtime to 1s (documents HFS+ 1s precision)."""
        assert HFSPLUS.mtime_granularity_ns == 1_000_000_000

    def test_dir_mtime_reliable_true(self) -> None:
        """HFS+ hard-wires dir-mtime reliability to True."""
        assert HFSPLUS.dir_mtime_reliable_default is True

    def test_no_appledouble_excludes(self) -> None:
        """HFS+ does not carry the AppleDouble exclude flags."""
        assert "--exclude=.DS_Store" not in HFSPLUS.rsync_flags


# ---------------------------------------------------------------------------
# ext4 (data-only entry)
# ---------------------------------------------------------------------------


class TestExt4:
    """The ext4 data-only entry's fields."""

    def test_tier1_uses_ctime(self) -> None:
        """ext4 keeps ctime in the tier-1 drift tuple (with documented caveat)."""
        assert EXT4.tier1_uses_ctime is True

    def test_mtime_granularity_exact(self) -> None:
        """ext4 uses exact (1 ns) mtime comparison granularity."""
        assert EXT4.mtime_granularity_ns == 1

    def test_does_not_forbid_unix_perms(self) -> None:
        """ext4 permits Unix perms."""
        assert EXT4.forbids_unix_perms is False


# ---------------------------------------------------------------------------
# capability_for: all 6 keys return a FilesystemCapability
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fs_type",
    ["ntfs_macfuse", "unknown", "apfs", "hfsplus", "exfat", "ext4"],
)
def test_capability_for_all_keys(fs_type: str) -> None:
    """Every canonical key returns a FilesystemCapability bearing that key."""
    cap = capability_for(fs_type)
    assert isinstance(cap, FilesystemCapability)
    assert cap.fs_type == fs_type


# ---------------------------------------------------------------------------
# resolve_capability: the single shared resolver (transfer + scan consistency)
# ---------------------------------------------------------------------------


class TestResolveCapability:
    """``resolve_capability`` — override beats probe; probe drives auto-detect."""

    def test_override_beats_probe_and_skips_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An explicit override returns its capability and never invokes the probe."""
        from unittest.mock import MagicMock

        probe = MagicMock()
        monkeypatch.setattr("personalscraper.indexer._fs_probe.probe_mount", probe)

        cap = resolve_capability("/Volumes/Disk1", "apfs")

        assert cap is APFS
        probe.assert_not_called()  # override short-circuits before the lazy import

    def test_override_exfat_on_path_that_probes_ntfs_returns_exfat(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-NEW-3 shape: override 'exfat' wins even when the path probes NTFS."""
        from personalscraper.indexer._fs_probe import MountInfo

        ntfs_info = MountInfo(
            mount_point="/Volumes/Disk1",
            fs_type="ntfs_macfuse",
            raw_fs_type="ufsd_ntfs",
            flags=frozenset(),
        )
        # Even with a probe that would return NTFS, the override must win — and
        # since the override short-circuits, the probe is never consulted at all.
        monkeypatch.setattr("personalscraper.indexer._fs_probe.probe_mount", lambda _: ntfs_info)

        cap = resolve_capability("/Volumes/Disk1", "exfat")

        assert cap is EXFAT

    def test_no_override_uses_probe_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no override, the FsProbe-detected fs-type drives the capability."""
        from personalscraper.indexer._fs_probe import MountInfo

        exfat_info = MountInfo(
            mount_point="/Volumes/Card",
            fs_type="exfat",
            raw_fs_type="exfat",
            flags=frozenset(),
        )
        monkeypatch.setattr("personalscraper.indexer._fs_probe.probe_mount", lambda _: exfat_info)

        cap = resolve_capability("/Volumes/Card", None)

        assert cap is EXFAT

    def test_unprobeable_path_falls_back_to_ntfs_safe_unknown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``None`` probe result (unmounted / non-Darwin) yields the NTFS-safe unknown."""
        monkeypatch.setattr("personalscraper.indexer._fs_probe.probe_mount", lambda _: None)

        cap = resolve_capability("/Volumes/Gone", None)

        # UNKNOWN behaviourally equals NTFS_MACFUSE (restrictive superset).
        assert cap is UNKNOWN
        assert cap == NTFS_MACFUSE

    def test_unrecognised_override_falls_back_to_unknown(self) -> None:
        """An unrecognised override token falls back to the NTFS-safe unknown."""
        cap = resolve_capability("/Volumes/Paragon", "some_driver_token")

        assert cap == NTFS_MACFUSE
