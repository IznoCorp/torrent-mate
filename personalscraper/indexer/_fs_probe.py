"""Filesystem-type probe — single source of truth for mount-point detection.

Consolidates the three independent ``mount`` parsers that previously lived in
``db.py``, ``scanner/_spotlight.py``, and ``scanner/__init__.py``.  A single
10-second ``mount`` shell-out is cached for the process lifetime (mounts do not
change mid-run).

Intentional behaviour change vs the pre-consolidation code:
- ``db.py`` used a 5-second timeout; this module uses 10 seconds (matching the
  two scanner parsers).  The difference only matters on a hung ``mount`` binary
  — acceptable trade-off for a single, shared shell-out.
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from personalscraper.logger import get_logger

log = get_logger("indexer.fs_probe")

# ---------------------------------------------------------------------------
# Known macFUSE/NTFS driver tokens (substring match — see canonical_fs_type).
# ---------------------------------------------------------------------------

_NTFS_TOKENS: frozenset[str] = frozenset({"ufsd_ntfs", "fuse_osxfuse", "osxfuse", "macfuse", "ntfs", "fuse-t"})


@dataclass(frozen=True)
class MountInfo:
    """One mounted filesystem as parsed from ``mount``.

    Attributes:
        mount_point: Normalised mount-point path (trailing slash stripped).
        fs_type: Canonical filesystem type key (see :func:`canonical_fs_type`).
        raw_fs_type: Original first token, lowercased, before canonicalisation.
        flags: Frozenset of parenthesised option-block tokens.
    """

    mount_point: str
    fs_type: str
    raw_fs_type: str
    flags: frozenset[str]


def canonical_fs_type(raw: str) -> str:
    """Normalise a raw ``mount`` fs-type token to a canonical capability key.

    Recognises NTFS-via-macFUSE under every known driver spelling
    (``ufsd_ntfs``, ``ntfs``, ``fuse_osxfuse``, ``osxfuse``, ``macfuse``,
    ``fuse-t``) via **substring** matching so that ``ufsd_NTFS`` (the real
    production token) is correctly detected.  This fixes the exact-token
    asymmetry that caused the ``_spotlight.py`` dead branch.

    Canonical keys:
    - ``"ntfs_macfuse"`` — NTFS via macFUSE (any of the known driver spellings)
    - ``"apfs"``         — Apple APFS
    - ``"hfsplus"``      — HFS+ / HFS Plus (``hfs``, ``hfsplus``)
    - ``"exfat"``        — exFAT
    - ``"ext4"``         — Linux ext4 (data-only; no Linux parser in FsProbe)
    - ``"unknown"``      — Anything else (falls back to NTFS-safe superset)

    Args:
        raw: Raw fs-type string from ``mount`` output (any casing).

    Returns:
        One of the canonical key strings listed above.
    """
    lowered = raw.lower()

    # NTFS-via-macFUSE: GREEDY substring match across all known driver spellings.
    # This is deliberately asymmetric with the exact ``==`` matches below: only
    # the NTFS/fuse family over-matches. Over-classifying an unknown token toward
    # NTFS is the SAFE direction (NTFS is the restrictive superset — suppress
    # perms, exclude AppleDouble), whereas over-matching toward a permissive FS
    # could write Unix perms / AppleDouble to a real NTFS disk. Pinned by
    # test_ntfs_substring_is_deliberately_greedy / test_apfs_superstring_stays_unknown.
    if any(token in lowered for token in _NTFS_TOKENS):
        return "ntfs_macfuse"

    # Exact match for every non-NTFS key: a superstring like ``apfs_encrypted``
    # must fall through to the NTFS-safe ``unknown`` superset, never collapse to
    # a permissive capability.
    if lowered == "apfs":
        return "apfs"

    if lowered in ("hfs", "hfsplus"):
        return "hfsplus"

    if lowered == "exfat":
        return "exfat"

    if lowered == "ext4":
        return "ext4"

    return "unknown"


def _parse_mount_line(line: str) -> Optional[MountInfo]:
    """Parse one macOS ``mount`` output line into a :class:`MountInfo`.

    macOS format::

        /dev/disk2s1 on /Volumes/Disk1 (ufsd_NTFS, local, noatime)
        map auto_home on /home (autofs, automounted, nobrowse)

    Args:
        line: Single line from ``mount`` stdout.

    Returns:
        :class:`MountInfo` on success, ``None`` if the line does not match
        the expected format.
    """
    on_idx = line.find(" on ")
    if on_idx == -1:
        return None

    rest = line[on_idx + 4 :]
    paren_open = rest.rfind("(")
    paren_close = rest.rfind(")")
    if paren_open == -1 or paren_close == -1 or paren_open >= paren_close:
        return None

    # Strip a trailing slash so mount points compare uniformly, but preserve a
    # bare root mount ("/") which would otherwise collapse to an empty string
    # and then prefix-match every path in probe_mount().
    mount_point = rest[:paren_open].strip()
    if mount_point != "/":
        mount_point = mount_point.rstrip("/")
    flags_str = rest[paren_open + 1 : paren_close]
    tokens = [t.strip() for t in flags_str.split(",") if t.strip()]

    if not tokens:
        return None

    raw_fs_type = tokens[0].lower()
    flags = frozenset(tokens[1:])

    return MountInfo(
        mount_point=mount_point,
        fs_type=canonical_fs_type(raw_fs_type),
        raw_fs_type=raw_fs_type,
        flags=flags,
    )


@lru_cache(maxsize=1)
def _run_mount() -> str:
    """Run ``mount`` and return raw stdout, cached for the process lifetime.

    Returns:
        Raw stdout from ``mount``, or an empty string on a subprocess timeout
        (``subprocess.TimeoutExpired``) or an OS-level failure to spawn the
        binary (``OSError`` — e.g. ``FileNotFoundError``/``PermissionError``).
        Any other, unexpected exception is **not** swallowed: it propagates so a
        genuine bug surfaces instead of masquerading as "no mounts detected".

    Note:
        Result is cached via :func:`functools.lru_cache`.  Mounts do not
        change mid-run; a single shell-out per process is acceptable.
        The 10-second timeout consolidates the former 5s (db.py) and 10s
        (spotlight, scanner) budgets.
    """
    if platform.system() != "Darwin":
        return ""
    try:
        proc = subprocess.run(
            ["mount"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.stdout
    except subprocess.TimeoutExpired as exc:
        # The ``mount`` binary hung past the 10 s budget — surface as a warning
        # (the prior code logged at DEBUG, masking a stuck mount table).
        log.warning("indexer.fs_probe.mount_timeout", timeout_s=10, error=str(exc))
        return ""
    except OSError as exc:
        # Binary missing / not executable / permission denied. Degrade to "no
        # mounts" but warn so the operator sees the probe could not run.
        log.warning("indexer.fs_probe.mount_failed", error=str(exc))
        return ""


def _build_mount_table(mount_output: str) -> dict[str, MountInfo]:
    """Parse full ``mount`` output into a mount-point → :class:`MountInfo` map.

    Args:
        mount_output: Raw stdout from the ``mount`` command.

    Returns:
        Dict keyed on normalised mount-point string (trailing slash stripped).
    """
    table: dict[str, MountInfo] = {}
    for line in mount_output.splitlines():
        info = _parse_mount_line(line)
        if info is not None:
            table[info.mount_point] = info
    return table


def probe_mount(path: str) -> Optional[MountInfo]:
    """Return the :class:`MountInfo` for the volume containing *path*, or None.

    Uses the module-level cached ``mount`` output so the shell-out happens at
    most once per process.  Returns ``None`` on non-Darwin platforms, on
    subprocess failure/timeout, or when no mount point matches *path*.

    The most specific (longest) matching mount point is returned when multiple
    mount points are prefixes of *path* (e.g. ``/`` vs ``/Volumes/Disk1``).

    Args:
        path: Absolute filesystem path.

    Returns:
        :class:`MountInfo` for the containing volume, or ``None``.
    """
    mount_output = _run_mount()
    if not mount_output:
        return None

    table = _build_mount_table(mount_output)
    normalised = path.rstrip("/")

    best: Optional[MountInfo] = None
    for mp, info in table.items():
        if normalised == mp or normalised.startswith(mp.rstrip("/") + "/"):
            if best is None or len(mp) > len(best.mount_point):
                best = info

    return best
