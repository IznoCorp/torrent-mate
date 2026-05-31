# Phase 1 — Consolidate 3 mount-parsers into one cached FsProbe

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the three independent `mount`-parsing implementations in
`db.py`, `_spotlight.py`, and `scanner/__init__.py` with a single cached
`FsProbe` module. Fix the `ufsd_NTFS` dead-branch root cause (exact-token vs
substring asymmetry) with a regression test that reproduces it.

**NTFS invariant:** This phase is purely structural consolidation. The public
behaviour of each call site stays identical; only the implementation is
centralised. The 5s timeout in `db.py` widens to 10s (single probe) — this is
the **only** intentional behaviour change and must be documented in the commit
body.

**Architecture:** New module `personalscraper/indexer/_fs_probe.py` owns the
single `subprocess.run(["mount"])` call (module-level cache, 10s timeout,
returns `MountInfo`). Three callers delegate to it; their public names and
return values stay stable.

**Tech Stack:** Python `subprocess`, `dataclasses`, `functools.lru_cache` (or
module-level dict), `platform`, `structlog`.

---

## Gate (prerequisites from previous phase)

_This is Phase 1 — no previous phase. Prerequisites:_

- Branch `feat/multi-filesystem` is checked out.
- `make lint && make test && make check` passes on HEAD (clean baseline).

Verify:

```bash
git branch --show-current
# expected: feat/multi-filesystem

make check
# expected: exit 0, all green
```

---

## Files

| Action | Path                                                                                                     |
| ------ | -------------------------------------------------------------------------------------------------------- |
| Create | `personalscraper/indexer/_fs_probe.py`                                                                   |
| Create | `tests/indexer/test_fs_probe.py`                                                                         |
| Modify | `personalscraper/indexer/db.py` (lines 176–228, `_find_ntfs_mount`)                                      |
| Modify | `personalscraper/indexer/scanner/_spotlight.py` (lines 37–112, `_parse_mount_output` / `detect_fs_type`) |
| Modify | `personalscraper/indexer/scanner/__init__.py` (lines 225–306, `_check_mount_flags`)                      |

---

## Task 1 — Write `_fs_probe.py` (the new single source of truth)

**Files:**

- Create: `personalscraper/indexer/_fs_probe.py`

- [ ] **Step 1.1: Create `personalscraper/indexer/_fs_probe.py`**

```python
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

_NTFS_TOKENS: frozenset[str] = frozenset(
    {"ufsd_ntfs", "fuse_osxfuse", "osxfuse", "macfuse", "ntfs", "fuse-t"}
)


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

    # NTFS-via-macFUSE: substring match across all known driver spellings.
    if any(token in lowered for token in _NTFS_TOKENS):
        return "ntfs_macfuse"

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

    mount_point = rest[:paren_open].strip().rstrip("/")
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
        Raw stdout from ``mount``, or empty string on any error.

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
    except Exception as exc:
        log.debug("indexer.fs_probe.mount_failed", error=str(exc))
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
```

- [ ] **Step 1.2: Verify the file is importable**

```bash
cd /Users/izno/dev/PersonnalScaper
python -c "from personalscraper.indexer._fs_probe import MountInfo, probe_mount, canonical_fs_type; print('ok')"
# expected: ok
```

---

## Task 2 — Write the regression test for the `ufsd_NTFS` dead-branch bug

**Files:**

- Create: `tests/indexer/test_fs_probe.py`

- [ ] **Step 2.1: Create `tests/indexer/test_fs_probe.py`**

```python
"""Tests for personalscraper.indexer._fs_probe.

Regression test for the ufsd_NTFS dead-branch bug: _spotlight.py used exact-token
matching, so the real production token "ufsd_NTFS" returned "ufsd_ntfs" (not
"macfuse"), causing try_attach() to fall through to the wrong branch.
FsProbe uses substring matching, fixing this at the root.
"""

import pytest

from personalscraper.indexer._fs_probe import (
    MountInfo,
    _build_mount_table,
    _parse_mount_line,
    canonical_fs_type,
    probe_mount,
)


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
        assert canonical_fs_type("ufsd_ntfs") == "ntfs_macfuse"

    def test_macfuse_token(self) -> None:
        assert canonical_fs_type("macfuse") == "ntfs_macfuse"

    def test_fuse_osxfuse_token(self) -> None:
        assert canonical_fs_type("fuse_osxfuse") == "ntfs_macfuse"

    def test_osxfuse_token(self) -> None:
        assert canonical_fs_type("osxfuse") == "ntfs_macfuse"

    def test_ntfs_bare_token(self) -> None:
        assert canonical_fs_type("ntfs") == "ntfs_macfuse"

    def test_fuse_t_token(self) -> None:
        assert canonical_fs_type("fuse-t") == "ntfs_macfuse"

    def test_apfs(self) -> None:
        assert canonical_fs_type("apfs") == "apfs"

    def test_apfs_uppercase(self) -> None:
        assert canonical_fs_type("APFS") == "apfs"

    def test_hfs(self) -> None:
        assert canonical_fs_type("hfs") == "hfsplus"

    def test_hfsplus(self) -> None:
        assert canonical_fs_type("hfsplus") == "hfsplus"

    def test_exfat(self) -> None:
        assert canonical_fs_type("exfat") == "exfat"

    def test_ext4(self) -> None:
        assert canonical_fs_type("ext4") == "ext4"

    def test_unknown_token(self) -> None:
        assert canonical_fs_type("tmpfs") == "unknown"

    def test_empty_string(self) -> None:
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
        line = "/dev/disk1s1 on / (apfs, local, journaled)"
        info = _parse_mount_line(line)
        assert info is not None
        assert info.mount_point == "/"
        assert info.fs_type == "apfs"

    def test_auto_home_line(self) -> None:
        line = "map auto_home on /home (autofs, automounted, nobrowse)"
        info = _parse_mount_line(line)
        assert info is not None
        assert info.mount_point == "/home"
        assert info.fs_type == "unknown"

    def test_malformed_line_returns_none(self) -> None:
        assert _parse_mount_line("not a mount line") is None

    def test_trailing_slash_stripped(self) -> None:
        line = "/dev/disk3s1 on /Volumes/HFS/ (hfs, local)"
        info = _parse_mount_line(line)
        assert info is not None
        assert not info.mount_point.endswith("/")


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
        table = _build_mount_table(self.SAMPLE_MOUNT)
        assert "/" in table
        assert "/Volumes/Disk1" in table
        assert "/home" in table

    def test_ntfs_entry_canonical(self) -> None:
        table = _build_mount_table(self.SAMPLE_MOUNT)
        assert table["/Volumes/Disk1"].fs_type == "ntfs_macfuse"

    def test_apfs_entry(self) -> None:
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
        import personalscraper.indexer._fs_probe as mod

        monkeypatch.setattr(mod, "_run_mount", lambda: self.SAMPLE_MOUNT)
        info = probe_mount("/Volumes/Disk1/Movies/Foo")
        assert info is not None
        assert info.fs_type == "ntfs_macfuse"
        assert info.mount_point == "/Volumes/Disk1"

    def test_probe_returns_most_specific_mount(self, monkeypatch: pytest.MonkeyPatch) -> None:
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
        import personalscraper.indexer._fs_probe as mod

        monkeypatch.setattr(mod, "_run_mount", lambda: self.SAMPLE_MOUNT)
        info = probe_mount("/nonexistent/path")
        assert info is None

    def test_probe_returns_none_on_empty_mount_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import personalscraper.indexer._fs_probe as mod

        monkeypatch.setattr(mod, "_run_mount", lambda: "")
        info = probe_mount("/Volumes/Disk1/foo")
        assert info is None
```

- [ ] **Step 2.2: Run the new tests (must pass — we're testing the new module, not the old callers yet)**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/test_fs_probe.py -v
# expected: all tests PASS
```

- [ ] **Step 2.3: Commit the new module + its tests (no callers changed yet)**

```bash
git add personalscraper/indexer/_fs_probe.py tests/indexer/test_fs_probe.py
git commit -m "feat(multi-filesystem): add FsProbe — canonical_fs_type + probe_mount (fixes ufsd_NTFS dead-branch root cause)"
```

---

## Task 3 — Rewire `db.py::_find_ntfs_mount` to delegate to `_fs_probe`

**Files:**

- Modify: `personalscraper/indexer/db.py`

- [ ] **Step 3.1: Read the current `_find_ntfs_mount` implementation**

Read `personalscraper/indexer/db.py` lines 172–228. The function uses a 5s timeout and substring matching against `_MACFUSE_FSTYPES`.

- [ ] **Step 3.2: Replace `_find_ntfs_mount` with a thin delegator**

Replace the body of `_find_ntfs_mount` (lines 179–228) with a delegation to
`probe_mount`. Keep the public function name and return type unchanged.

```python
from personalscraper.indexer._fs_probe import probe_mount as _probe_mount

_MACFUSE_FSTYPES = frozenset({"fuse_osxfuse", "osxfuse", "macfuse", "ntfs", "fuse-t"})  # kept for reference


def _find_ntfs_mount(path: Path) -> str | None:
    """Return the macFUSE-NTFS mount point that contains *path*, or ``None``.

    Delegates to :func:`personalscraper.indexer._fs_probe.probe_mount` which
    uses a single cached ``mount`` shell-out (10s timeout — up from the former
    5s budget; intentional, documented change).

    Args:
        path: Filesystem path to check.

    Returns:
        The matching mount-point string, or ``None`` if the path is not on a
        macFUSE-NTFS volume.
    """
    info = _probe_mount(str(path.resolve()))
    if info is None:
        return None
    return info.mount_point if info.fs_type == "ntfs_macfuse" else None
```

Note: remove the old `subprocess` import from `db.py` only if it is no longer
used elsewhere in that file (grep first: `rg "subprocess" -g '*.py' personalscraper/indexer/db.py`).

- [ ] **Step 3.3: Run the indexer tests to confirm no regression**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/test_db.py -v
# expected: all tests PASS
```

- [ ] **Step 3.4: Commit**

```bash
git add personalscraper/indexer/db.py
git commit -m "refactor(multi-filesystem): db._find_ntfs_mount delegates to FsProbe (5s→10s timeout, intentional)"
```

---

## Task 4 — Rewire `_spotlight.py::detect_fs_type` to delegate to `_fs_probe`

**Files:**

- Modify: `personalscraper/indexer/scanner/_spotlight.py`

- [ ] **Step 4.1: Read the current `_parse_mount_output` / `detect_fs_type` implementation**

Read `personalscraper/indexer/scanner/_spotlight.py` lines 37–112.

- [ ] **Step 4.2: Replace `detect_fs_type` (and `_parse_mount_output` / `_get_mount_output`) with a delegator**

The public function `detect_fs_type(path: str) -> str | None` must keep its signature. Its new body:

```python
from personalscraper.indexer._fs_probe import probe_mount as _probe_mount


def detect_fs_type(path: str) -> str | None:
    """Return the filesystem type for *path*'s mount point, or ``None`` if unknown.

    Delegates to :func:`personalscraper.indexer._fs_probe.probe_mount`.
    Only meaningful on macOS (Darwin); returns ``None`` on other platforms.

    Args:
        path: Absolute path whose mount-point filesystem type is needed.

    Returns:
        Canonical fs-type string (e.g. ``"apfs"``, ``"ntfs_macfuse"``,
        ``"hfsplus"``), or ``None`` when the mount point cannot be determined.
    """
    import platform as _platform
    if _platform.system() != "Darwin":
        return None
    info = _probe_mount(path)
    return info.fs_type if info is not None else None
```

Keep `_parse_mount_output` and `_get_mount_output` as private functions only if
other code in `_spotlight.py` uses them; otherwise remove them.
Check first: `rg "_parse_mount_output\|_get_mount_output" -g '*.py' personalscraper/indexer/scanner/_spotlight.py`

- [ ] **Step 4.3: Update `try_attach` to recognise `"ntfs_macfuse"` instead of `"macfuse"`**

The dead-branch bug is that `try_attach` checks `fs_type == "macfuse"` but
`detect_fs_type` now returns `"ntfs_macfuse"`. Update the condition:

```python
# Before (dead branch — never matched real ufsd_NTFS mounts):
if fs_type == "macfuse":

# After (matches the canonical key from FsProbe):
if fs_type == "ntfs_macfuse":
```

- [ ] **Step 4.4: Run the spotlight tests**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/ -k "spotlight" -v
# expected: all tests PASS
```

- [ ] **Step 4.5: Commit**

```bash
git add personalscraper/indexer/scanner/_spotlight.py
git commit -m "refactor(multi-filesystem): _spotlight.detect_fs_type delegates to FsProbe; fix ufsd_NTFS dead branch in try_attach"
```

---

## Task 5 — Rewire `scanner/__init__.py::_check_mount_flags` to delegate to `_fs_probe`

**Files:**

- Modify: `personalscraper/indexer/scanner/__init__.py`

- [ ] **Step 5.1: Read the current `_check_mount_flags` implementation**

Read `personalscraper/indexer/scanner/__init__.py` lines 225–306.

- [ ] **Step 5.2: Replace `_check_mount_flags` with a delegator**

Keep `_RECOMMENDED_MOUNT_FLAGS` (it's the config for which flags to warn about;
that logic stays in the scanner). Only replace the inline `subprocess.run` +
mount-line parse with a call to `_build_mount_table` from `_fs_probe`:

```python
from personalscraper.indexer._fs_probe import _build_mount_table, _run_mount


def _check_mount_flags(disks: list[DiskRow]) -> None:
    """Parse ``mount`` output and warn about missing recommended flags.

    Delegates mount parsing to :mod:`personalscraper.indexer._fs_probe`
    (cached shell-out).  The recommendation logic (which flags to check) stays
    here.

    Args:
        disks: List of DiskRow objects whose ``mount_path`` fields are inspected.
    """
    if platform.system() != "Darwin":
        return

    mount_output = _run_mount()
    if not mount_output:
        return

    mount_table = _build_mount_table(mount_output)
    # Convert to mount_point → flag-set for the flag check
    mount_flags: dict[str, frozenset[str]] = {
        mp: info.flags for mp, info in mount_table.items()
    }

    for disk in disks:
        if disk.mount_path is None:
            continue
        mount_point = disk.mount_path.rstrip("/")
        disk_flags = mount_flags.get(mount_point)
        if disk_flags is None:
            log.debug(
                "indexer.disk.mount_flags_unknown",
                disk_label=disk.label,
                mount_path=disk.mount_path,
            )
            continue
        missing = _RECOMMENDED_MOUNT_FLAGS - disk_flags
        if missing:
            log.warning(
                "indexer.disk.mount_flags_missing",
                disk_label=disk.label,
                mount_path=disk.mount_path,
                missing_flags=sorted(missing),
                present_flags=sorted(disk_flags),
            )
```

Note: `MountInfo.flags` stores the option tokens after the first comma (not
including the fs-type token). Check the `_parse_mount_line` implementation —
if the flag check needs `noatime` etc., verify those tokens are in `info.flags`
(they are: `flags = frozenset(tokens[1:])` in `_fs_probe.py`).

- [ ] **Step 5.3: Remove the old inline `subprocess` import from `scanner/__init__.py` if unused**

```bash
rg "subprocess" -g '*.py' personalscraper/indexer/scanner/__init__.py
# if no other uses remain, remove the import
```

- [ ] **Step 5.4: Run the full scanner test suite**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/indexer/ -v
# expected: all tests PASS
```

---

## Task 6 — Phase gate + residual grep + milestone commit

- [ ] **Step 6.1: Residual grep — no more direct `mount` subprocess calls outside `_fs_probe.py`**

```bash
cd /Users/izno/dev/PersonnalScaper
rg "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/
# expected: only personalscraper/indexer/_fs_probe.py matches (count: 1)
```

- [ ] **Step 6.2: Full quality gate**

```bash
make lint && make test && make check
# expected: exit 0, all green
```

- [ ] **Step 6.3: AC-01 smoke test**

```bash
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"
# expected stdout: ntfs_macfuse
```

- [ ] **Step 6.4: AC-11 / AC-12 smoke tests**

```bash
# AC-11: exactly one mount shell-out location
rg -c "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/_fs_probe.py
# expected stdout: 1

# AC-12: old call sites gone
rg -l "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py
# expected: empty stdout (rg exits 1 — nothing found)
```

- [ ] **Step 6.5: Milestone commit**

```bash
git add -u
git commit -m "chore(multi-filesystem): phase 1 gate — FsProbe consolidates 3 mount-parsers, fixes ufsd_NTFS dead branch"
```

---

## Acceptance criteria for this phase

```bash
# AC-01 — FsProbe canonicalises ufsd_NTFS correctly
python -c "from personalscraper.indexer._fs_probe import canonical_fs_type; print(canonical_fs_type('ufsd_NTFS'))"
# expected: ntfs_macfuse

# AC-11 — exactly one mount shell-out
rg -c "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/_fs_probe.py
# expected: 1

# AC-12 — old call sites no longer shell out to mount
rg -l "subprocess.run\(\[.mount.\]" -g '*.py' personalscraper/indexer/db.py personalscraper/indexer/scanner/_spotlight.py personalscraper/indexer/scanner/__init__.py
# expected: empty stdout (exit 1)

# AC-17 — package smoke
python -c "import personalscraper; print('ok')"
# expected: ok
```
