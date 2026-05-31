# Phase 2 — Define the FilesystemCapability strategy table

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create `personalscraper/indexer/_fs_capability.py` — a pure-data
strategy table keyed on canonical fs-type strings. Six entries cover all
supported filesystems. No runtime behaviour changes in this phase; callers are
wired in Phases 3–5.

**NTFS invariant:** The `ntfs_macfuse` `rsync_flags` tuple MUST equal the
literal flag list from `_transfer.py` lines 103–115 byte-for-byte:
`('-a', '--no-perms', '--no-owner', '--no-group', '--no-times',
'--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store',
'--exclude=._*')`. The `unknown` entry MUST equal `ntfs_macfuse` — the
restrictive fallback guarantees that an unrecognised filesystem never silently
gains permissive behaviour.

**Architecture:** New module `personalscraper/indexer/_fs_capability.py`
exports `FilesystemCapability` (frozen dataclass) and `capability_for(fs_type)`
(lookup function). Pure data + lookup — fully unit-testable with no I/O.

**Tech Stack:** Python `dataclasses`, `re`, `typing`.

---

## Gate (prerequisites from Phase 1)

Phase 1 produced:

- `personalscraper/indexer/_fs_probe.py` with `canonical_fs_type` returning one
  of: `"ntfs_macfuse"`, `"apfs"`, `"hfsplus"`, `"exfat"`, `"ext4"`, `"unknown"`.
- Three caller modules delegating to `_fs_probe` (no direct `mount` subprocess
  calls in `db.py`, `_spotlight.py`, `scanner/__init__.py`).

Verify:

```bash
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"
# expected: ntfs_macfuse

rg -l "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py
# expected: empty stdout (exit 1)
```

---

## Files

| Action | Path                                        |
| ------ | ------------------------------------------- |
| Create | `personalscraper/indexer/_fs_capability.py` |
| Create | `tests/indexer/test_fs_capability.py`       |

---

## Task 1 — Write `_fs_capability.py`

**Files:**

- Create: `personalscraper/indexer/_fs_capability.py`

- [ ] **Step 1.1: Create `personalscraper/indexer/_fs_capability.py`**

```python
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
from dataclasses import dataclass
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

    fs_type: str
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
```

- [ ] **Step 1.2: Verify the module imports cleanly**

```bash
cd /Users/izno/dev/PersonnalScaper
python -c "from personalscraper.indexer._fs_capability import capability_for, FilesystemCapability; print('ok')"
# expected: ok
```

---

## Task 2 — Write the capability tests

**Files:**

- Create: `tests/indexer/test_fs_capability.py`

- [ ] **Step 2.1: Create `tests/indexer/test_fs_capability.py`**

```python
"""Tests for personalscraper.indexer._fs_capability.

Verifies the FilesystemCapability table: field values per fs_type, the
unknown==ntfs_macfuse invariant, and the byte-identical NTFS rsync-flags pin.
"""

import pytest

from personalscraper.indexer._fs_capability import (
    APFS,
    EXT4,
    EXFAT,
    HFSPLUS,
    NTFS_MACFUSE,
    UNKNOWN,
    FilesystemCapability,
    capability_for,
)


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
        """unknown falls back to NTFS-safe superset."""
        assert UNKNOWN.rsync_flags == self.EXPECTED_FLAGS


# ---------------------------------------------------------------------------
# AC-02: unknown == ntfs_macfuse (every field)
# ---------------------------------------------------------------------------


class TestUnknownFallback:
    """AC-02: capability_for('unknown') must equal capability_for('ntfs_macfuse')."""

    def test_unknown_equals_ntfs_macfuse_full(self) -> None:
        assert capability_for("unknown") == capability_for("ntfs_macfuse")

    def test_unknown_forbids_unix_perms(self) -> None:
        assert UNKNOWN.forbids_unix_perms is True

    def test_unknown_forbids_apple_metadata(self) -> None:
        assert UNKNOWN.forbids_apple_metadata is True

    def test_unknown_has_ntfs_illegal_regex(self) -> None:
        assert UNKNOWN.illegal_name_regex is not None

    def test_unrecognised_key_returns_unknown(self) -> None:
        cap = capability_for("nfs")
        assert cap == UNKNOWN


# ---------------------------------------------------------------------------
# AC-03: NTFS rsync flags (via capability_for)
# ---------------------------------------------------------------------------


class TestNtfsMacfuse:
    def test_fs_type_key(self) -> None:
        assert NTFS_MACFUSE.fs_type == "ntfs_macfuse"

    def test_forbids_unix_perms(self) -> None:
        assert NTFS_MACFUSE.forbids_unix_perms is True

    def test_forbids_apple_metadata(self) -> None:
        assert NTFS_MACFUSE.forbids_apple_metadata is True

    def test_illegal_name_regex_matches_colon(self) -> None:
        assert NTFS_MACFUSE.illegal_name_regex is not None
        assert NTFS_MACFUSE.illegal_name_regex.search("file:name") is not None

    def test_tier1_uses_ctime(self) -> None:
        assert NTFS_MACFUSE.tier1_uses_ctime is True

    def test_mtime_granularity_exact(self) -> None:
        assert NTFS_MACFUSE.mtime_granularity_ns == 1

    def test_capability_for_lookup(self) -> None:
        assert capability_for("ntfs_macfuse") is NTFS_MACFUSE


# ---------------------------------------------------------------------------
# AC-04: APFS drops NTFS-only flags
# ---------------------------------------------------------------------------


class TestApfs:
    def test_no_no_perms_flag(self) -> None:
        assert "--no-perms" not in APFS.rsync_flags

    def test_no_no_times_flag(self) -> None:
        assert "--no-times" not in APFS.rsync_flags

    def test_no_omit_dir_times(self) -> None:
        assert "--omit-dir-times" not in APFS.rsync_flags

    def test_no_appledouble_excludes(self) -> None:
        assert "--exclude=.DS_Store" not in APFS.rsync_flags
        assert "--exclude=._*" not in APFS.rsync_flags

    def test_does_not_forbid_unix_perms(self) -> None:
        assert APFS.forbids_unix_perms is False

    def test_does_not_forbid_apple_metadata(self) -> None:
        assert APFS.forbids_apple_metadata is False

    def test_dir_mtime_reliable_true(self) -> None:
        assert APFS.dir_mtime_reliable_default is True


# ---------------------------------------------------------------------------
# AC-05: APFS has no NTFS illegal-name restriction
# ---------------------------------------------------------------------------


class TestApfsNamePolicy:
    def test_illegal_name_regex_is_none(self) -> None:
        assert APFS.illegal_name_regex is None

    def test_colon_not_illegal_on_apfs(self) -> None:
        """A name with ':' must NOT be flagged as illegal on APFS (AC-05)."""
        r = APFS.illegal_name_regex
        assert r is None or r.search("a:b") is None


# ---------------------------------------------------------------------------
# AC-06: exFAT — no ctime, 2s mtime granularity
# ---------------------------------------------------------------------------


class TestExfat:
    def test_tier1_uses_ctime_false(self) -> None:
        assert EXFAT.tier1_uses_ctime is False

    def test_mtime_granularity_2s(self) -> None:
        assert EXFAT.mtime_granularity_ns == 2_000_000_000

    def test_appledouble_excluded(self) -> None:
        assert "--exclude=.DS_Store" in EXFAT.rsync_flags

    def test_does_not_forbid_unix_perms(self) -> None:
        assert EXFAT.forbids_unix_perms is False


# ---------------------------------------------------------------------------
# AC-07: HFS+ (AppleRAID target) — full POSIX, no NTFS restrictions
# ---------------------------------------------------------------------------


class TestHfsplus:
    def test_does_not_forbid_unix_perms(self) -> None:
        assert HFSPLUS.forbids_unix_perms is False

    def test_illegal_name_regex_is_none(self) -> None:
        assert HFSPLUS.illegal_name_regex is None

    def test_mtime_granularity_1s(self) -> None:
        assert HFSPLUS.mtime_granularity_ns == 1_000_000_000

    def test_dir_mtime_reliable_true(self) -> None:
        assert HFSPLUS.dir_mtime_reliable_default is True

    def test_no_appledouble_excludes(self) -> None:
        assert "--exclude=.DS_Store" not in HFSPLUS.rsync_flags


# ---------------------------------------------------------------------------
# ext4 (data-only entry)
# ---------------------------------------------------------------------------


class TestExt4:
    def test_tier1_uses_ctime(self) -> None:
        assert EXT4.tier1_uses_ctime is True

    def test_mtime_granularity_exact(self) -> None:
        assert EXT4.mtime_granularity_ns == 1

    def test_does_not_forbid_unix_perms(self) -> None:
        assert EXT4.forbids_unix_perms is False


# ---------------------------------------------------------------------------
# capability_for: all 6 keys return a FilesystemCapability
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fs_type",
    ["ntfs_macfuse", "unknown", "apfs", "hfsplus", "exfat", "ext4"],
)
def test_capability_for_all_keys(fs_type: str) -> None:
    cap = capability_for(fs_type)
    assert isinstance(cap, FilesystemCapability)
    assert cap.fs_type == fs_type
```

- [ ] **Step 2.2: Run the capability tests**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/test_fs_capability.py -v
# expected: all tests PASS
```

- [ ] **Step 2.3: Commit tests + module**

```bash
git add personalscraper/indexer/_fs_capability.py tests/indexer/test_fs_capability.py
git commit -m "feat(multi-filesystem): add FilesystemCapability strategy table (6 entries, NTFS flags pinned)"
```

---

## Task 3 — Phase gate + milestone commit

- [ ] **Step 3.1: Full quality gate**

```bash
make lint && make test && make check
# expected: exit 0, all green
```

- [ ] **Step 3.2: AC spot checks**

```bash
# AC-02
python -c "from personalscraper.indexer._fs_capability import capability_for; print(capability_for('unknown') == capability_for('ntfs_macfuse'))"
# expected: True

# AC-03
python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"
# expected: ['-a', '--no-perms', '--no-owner', '--no-group', '--no-times', '--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store', '--exclude=._*']

# AC-04
python -c "from personalscraper.indexer._fs_capability import capability_for; f=capability_for('apfs').rsync_flags; print('--no-perms' not in f and '--no-times' not in f)"
# expected: True

# AC-05
python -c "from personalscraper.indexer._fs_capability import capability_for; r=capability_for('apfs').illegal_name_regex; print(r is None or r.search('a:b') is None)"
# expected: True

# AC-06
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('exfat'); print(c.tier1_uses_ctime, c.mtime_granularity_ns)"
# expected: False 2000000000

# AC-07
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('hfsplus'); print(c.forbids_unix_perms, c.illegal_name_regex is None)"
# expected: False True
```

- [ ] **Step 3.3: Milestone commit**

```bash
git add -u
git commit -m "chore(multi-filesystem): phase 2 gate — FilesystemCapability table complete, all 6 fs-types, NTFS flags pinned"
```

---

## Acceptance criteria for this phase

```bash
# AC-02
python -c "from personalscraper.indexer._fs_capability import capability_for; print(capability_for('unknown') == capability_for('ntfs_macfuse'))"
# expected: True

# AC-03
python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"
# expected: ['-a', '--no-perms', '--no-owner', '--no-group', '--no-times', '--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store', '--exclude=._*']

# AC-04
python -c "from personalscraper.indexer._fs_capability import capability_for; f=capability_for('apfs').rsync_flags; print('--no-perms' not in f and '--no-times' not in f)"
# expected: True

# AC-05
python -c "from personalscraper.indexer._fs_capability import capability_for; r=capability_for('apfs').illegal_name_regex; print(r is None or r.search('a:b') is None)"
# expected: True

# AC-06
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('exfat'); print(c.tier1_uses_ctime, c.mtime_granularity_ns)"
# expected: False 2000000000

# AC-07
python -c "from personalscraper.indexer._fs_capability import capability_for; c=capability_for('hfsplus'); print(c.forbids_unix_perms, c.illegal_name_regex is None)"
# expected: False True

# AC-17
python -c "import personalscraper; print('ok')"
# expected: ok
```
