"""Unit tests for personalscraper.indexer.scanner._spotlight.

Focused regression coverage for the ``try_attach`` macFUSE dead-branch bug.
``detect_fs_type`` previously returned the raw token ``"macfuse"`` (or, for the
real production ``ufsd_NTFS`` token, ``"ufsd_ntfs"``), but ``try_attach``
compared against the literal ``"macfuse"``.  Real macFUSE-NTFS mounts therefore
never matched the macFUSE guard.  After consolidation onto FsProbe,
``detect_fs_type`` returns the canonical ``"ntfs_macfuse"`` key and
``try_attach`` matches that key.
"""

import logging

import pytest

from personalscraper.indexer.scanner._spotlight import SpotlightChangeDetector


class TestTryAttachMacfuseBranch:
    """``try_attach`` recognises the canonical ``"ntfs_macfuse"`` fs-type."""

    def test_ntfs_macfuse_fs_type_refuses_attach(self) -> None:
        """A ``ntfs_macfuse`` mount must take the macFUSE branch and refuse to attach.

        Regression: this branch was dead before consolidation because
        ``try_attach`` compared ``fs_type == "macfuse"`` while ``detect_fs_type``
        returned a different token for real ``ufsd_NTFS`` mounts.
        """
        detector = SpotlightChangeDetector()
        attached = detector.try_attach(
            "/Volumes/Disk1",
            spotlight_enabled=True,
            fs_type_fn=lambda _path: "ntfs_macfuse",
            # probe_fn must never be reached on the macFUSE branch.
            probe_fn=lambda _path: pytest.fail("probe_fn must not run on macFUSE"),
        )
        assert attached is False
        assert detector.is_attached() is False

    def test_ntfs_macfuse_emits_skipped_macfuse(self, caplog: pytest.LogCaptureFixture) -> None:
        """The macFUSE branch emits ``indexer.spotlight.skipped_macfuse``."""
        detector = SpotlightChangeDetector()
        with caplog.at_level(logging.INFO, logger="indexer.spotlight"):
            detector.try_attach(
                "/Volumes/Disk1",
                spotlight_enabled=False,
                fs_type_fn=lambda _path: "ntfs_macfuse",
            )
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipped_macfuse" in messages

    def test_ntfs_macfuse_with_flag_emits_flag_ignored(self, caplog: pytest.LogCaptureFixture) -> None:
        """``spotlight_enabled=True`` on a macFUSE mount warns the flag is ignored."""
        detector = SpotlightChangeDetector()
        with caplog.at_level(logging.WARNING, logger="indexer.spotlight"):
            detector.try_attach(
                "/Volumes/Disk1",
                spotlight_enabled=True,
                fs_type_fn=lambda _path: "ntfs_macfuse",
            )
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "flag_ignored_macfuse" in messages

    def test_legacy_macfuse_token_no_longer_takes_branch(self) -> None:
        """The pre-fix raw token ``"macfuse"`` must NOT take the macFUSE branch.

        ``detect_fs_type`` no longer returns ``"macfuse"``; it returns the
        canonical ``"ntfs_macfuse"``.  Feeding the legacy value falls through to
        the not-APFS branch (returns False without emitting skipped_macfuse),
        which proves the guard now keys on the canonical token, not the old one.
        """
        detector = SpotlightChangeDetector()
        attached = detector.try_attach(
            "/Volumes/Disk1",
            spotlight_enabled=True,
            fs_type_fn=lambda _path: "macfuse",
            probe_fn=lambda _path: pytest.fail("probe_fn must not run on non-APFS"),
        )
        assert attached is False
        assert detector.is_attached() is False

    def test_apfs_reaches_probe(self) -> None:
        """An APFS mount with the flag enabled reaches the mdutil probe and attaches."""
        detector = SpotlightChangeDetector()
        attached = detector.try_attach(
            "/Volumes/Internal",
            spotlight_enabled=True,
            fs_type_fn=lambda _path: "apfs",
            probe_fn=lambda _path: True,
        )
        assert attached is True
        assert detector.is_attached() is True
