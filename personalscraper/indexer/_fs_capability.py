"""FilesystemCapability strategy table — per-FS behaviour knobs.

Pure data module: no I/O, no subprocess calls.  Fully unit-testable in
isolation.  The capability table is the single source of truth for all
filesystem-conditional behaviour in the pipeline (rsync flags, Unix-perms
tolerance, AppleDouble exclusions, NTFS name restrictions, drift tunables).

Canonical fs-type keys (produced by
:func:`personalscraper.indexer._fs_probe.canonical_fs_type`):

- ``"ntfs_macfuse"`` — NTFS via macFUSE (Tuxera ufsd_NTFS, fuse_osxfuse, …)
- ``"unknown"``      — Unrecognised; falls back to the NTFS-safe superset
- ``"apfs"``         — Apple APFS (macOS native, full POSIX)
- ``"hfsplus"``      — HFS+ / HFS Plus (macOS legacy, full POSIX, 1s mtime)
- ``"exfat"``        — exFAT (no ctime, 2s mtime granularity)
- ``"ext4"``         — Linux ext4 (data-only; FsProbe parser is macOS-oriented)

CRITICAL INVARIANT: The ``ntfs_macfuse`` ``rsync_flags`` tuple reproduces
today's hardcoded flag list in ``dispatch/_transfer.py`` lines 103–115
byte-for-byte.  Any change here must be reflected there and vice-versa.
``unknown`` MUST equal ``ntfs_macfuse`` — a permissive default on an
unrecognised FS could write Unix perms / AppleDouble files to a real NTFS
disk and trigger EPERM / journal problems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# NTFS illegal-filename pattern (same source as text_utils._FILENAME_ILLEGAL)
# ---------------------------------------------------------------------------

_NTFS_ILLEGAL: re.Pattern[str] = re.compile(r'[<>:"/\\|?*]')

# ---------------------------------------------------------------------------
# FilesystemCapability dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FilesystemCapability:
    """Per-filesystem behaviour strategy.

    Pure data; fully unit-testable without I/O.  Consumed by the transfer
    layer (:mod:`personalscraper.dispatch._transfer`) and the indexer drift
    detector (:mod:`personalscraper.indexer.drift`).

    Attributes:
        fs_type: Canonical key this entry serves (matches output of
            :func:`personalscraper.indexer._fs_probe.canonical_fs_type`).
            Excluded from equality (``compare=False``) so the ``"unknown"``
            entry — a byte-identical *behavioural* clone of ``ntfs_macfuse``
            that keeps its own readable ``"unknown"`` label — still satisfies
            AC-02: ``capability_for("unknown") == capability_for("ntfs_macfuse")``.
            Equality therefore reflects behaviour (rsync flags, perms/metadata
            policy, name regex, drift tunables), not the cosmetic key.
        rsync_flags: Complete rsync flag prefix tuple (excluding source/dest
            paths).  Single source of truth replacing the two hardcoded literal
            lists in ``_transfer.py``.
        forbids_unix_perms: When ``True``, ``--no-perms --no-owner --no-group``
            are present in ``rsync_flags`` to suppress EPERM on FUSE volumes.
        forbids_apple_metadata: When ``True``, ``--exclude=.DS_Store`` and
            ``--exclude=._*`` are present to avoid rsync errors on FS types
            that reject AppleDouble files.
        illegal_name_regex: Compiled pattern for filesystem-illegal filename
            characters, or ``None`` when the FS imposes no name restrictions.
        tier1_uses_ctime: When ``False``, ctime is dropped from the tier-1
            drift tuple (exFAT has no ctime; ext4 ctime mutates on metadata ops).
        mtime_granularity_ns: Round mtime to this many nanoseconds before
            comparing (1 = exact; 1_000_000_000 = 1s precision for HFS+;
            2_000_000_000 = 2s for exFAT).
        dir_mtime_reliable_default: ``True`` / ``False`` to hard-wire the
            dir-mtime probe result; ``None`` to run the runtime probe
            (:func:`personalscraper.indexer.scanner._walker._verify_dir_mtime_reliable`).
    """

    fs_type: str = field(compare=False)
    rsync_flags: tuple[str, ...]
    forbids_unix_perms: bool
    forbids_apple_metadata: bool
    illegal_name_regex: Optional[re.Pattern[str]]
    tier1_uses_ctime: bool
    mtime_granularity_ns: int
    dir_mtime_reliable_default: Optional[bool]


# ---------------------------------------------------------------------------
# Capability table (6 entries)
# ---------------------------------------------------------------------------

# NTFS-via-macFUSE rsync flag prefix — byte-identical to _transfer.py:103-115.
# DO NOT reorder or add flags without updating _transfer.py simultaneously.
_NTFS_RSYNC_FLAGS: tuple[str, ...] = (
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

# Flags for POSIX-capable filesystems (APFS, HFS+, ext4).
# --inplace and --partial are FS-agnostic cache-pressure decisions — kept
# regardless of FS type.  --no-times / --no-perms / AppleDouble excludes
# are NTFS-specific and are intentionally absent here.
_POSIX_RSYNC_FLAGS: tuple[str, ...] = (
    "-a",
    "--inplace",
    "--partial",
)

# exFAT: POSIX perms work, but AppleDouble files are junk on exFAT.
_EXFAT_RSYNC_FLAGS: tuple[str, ...] = (
    "-a",
    "--inplace",
    "--partial",
    "--exclude=.DS_Store",
    "--exclude=._*",
)

_CAPABILITY_TABLE: dict[str, FilesystemCapability] = {}


def _register(cap: FilesystemCapability) -> FilesystemCapability:
    """Register a capability entry and return it."""
    _CAPABILITY_TABLE[cap.fs_type] = cap
    return cap


NTFS_MACFUSE = _register(
    FilesystemCapability(
        fs_type="ntfs_macfuse",
        rsync_flags=_NTFS_RSYNC_FLAGS,
        forbids_unix_perms=True,
        forbids_apple_metadata=True,
        illegal_name_regex=_NTFS_ILLEGAL,
        tier1_uses_ctime=True,
        mtime_granularity_ns=1,
        dir_mtime_reliable_default=None,  # runtime probe
    )
)

# "unknown" MUST equal ntfs_macfuse — restrictive superset, never permissive.
UNKNOWN = _register(
    FilesystemCapability(
        fs_type="unknown",
        rsync_flags=_NTFS_RSYNC_FLAGS,
        forbids_unix_perms=True,
        forbids_apple_metadata=True,
        illegal_name_regex=_NTFS_ILLEGAL,
        tier1_uses_ctime=True,
        mtime_granularity_ns=1,
        dir_mtime_reliable_default=None,
    )
)

APFS = _register(
    FilesystemCapability(
        fs_type="apfs",
        rsync_flags=_POSIX_RSYNC_FLAGS,
        forbids_unix_perms=False,
        forbids_apple_metadata=False,
        illegal_name_regex=None,
        tier1_uses_ctime=True,
        mtime_granularity_ns=1,
        dir_mtime_reliable_default=True,
    )
)

# HFS+: full POSIX, reliable ~1s mtime (the AppleRAID target).
# mtime_granularity_ns=1_000_000_000 so sub-second jitter never triggers drift.
HFSPLUS = _register(
    FilesystemCapability(
        fs_type="hfsplus",
        rsync_flags=_POSIX_RSYNC_FLAGS,
        forbids_unix_perms=False,
        forbids_apple_metadata=False,
        illegal_name_regex=None,
        tier1_uses_ctime=True,
        mtime_granularity_ns=1_000_000_000,
        dir_mtime_reliable_default=True,
    )
)

# exFAT: no ctime (tier1_uses_ctime=False), 2s mtime granularity.
# AppleDouble excludes kept — exFAT stores them but they are macOS junk.
EXFAT = _register(
    FilesystemCapability(
        fs_type="exfat",
        rsync_flags=_EXFAT_RSYNC_FLAGS,
        forbids_unix_perms=False,
        forbids_apple_metadata=True,
        illegal_name_regex=None,
        tier1_uses_ctime=False,
        mtime_granularity_ns=2_000_000_000,
        dir_mtime_reliable_default=None,
    )
)

# ext4: data-only entry; FsProbe parser is macOS-oriented.
# ctime=True with caveat: ctime mutates on metadata ops — candidate for
# granularity widening once a real ext4 target exists (DESIGN §8.4).
EXT4 = _register(
    FilesystemCapability(
        fs_type="ext4",
        rsync_flags=_POSIX_RSYNC_FLAGS,
        forbids_unix_perms=False,
        forbids_apple_metadata=False,
        illegal_name_regex=None,
        tier1_uses_ctime=True,
        mtime_granularity_ns=1,
        dir_mtime_reliable_default=None,
    )
)


# ---------------------------------------------------------------------------
# Public lookup
# ---------------------------------------------------------------------------


def capability_for(fs_type: str) -> FilesystemCapability:
    """Return the :class:`FilesystemCapability` for a canonical fs-type key.

    Falls back to ``"unknown"`` (NTFS-safe restrictive superset) for any
    unrecognised key.

    Args:
        fs_type: Canonical fs-type string as returned by
            :func:`personalscraper.indexer._fs_probe.canonical_fs_type`.

    Returns:
        The matching :class:`FilesystemCapability`, or the ``"unknown"`` entry
        when *fs_type* is not in the table.
    """
    return _CAPABILITY_TABLE.get(fs_type, UNKNOWN)
