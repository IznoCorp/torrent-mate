# Phase 3 — Make `_transfer.rsync`/`rsync_merge` consume the capability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the two hardcoded rsync flag literals in `_transfer.py` with
a single `_build_rsync_cmd` builder that reads flags from a
`FilesystemCapability`. Thread the capability through `Dispatcher` so it is
resolved once per dest disk (not per file). NTFS output must remain
byte-identical to today's argv — proven by a golden test authored **first**
against the current code before any refactor.

**NTFS invariant:** The golden argv test is the equivalence anchor. After
refactoring, the `ntfs_macfuse` argv must equal the pre-refactor argv
byte-for-byte. After this phase, `rg -n '"--no-perms"' -g '*.py'
personalscraper/dispatch/_transfer.py` must return 0 (flags come only from
the capability table).

**Architecture:** `_transfer.py` gains `_build_rsync_cmd(source, dest,
capability, *, delete, backup_dir)`. `rsync()` and `rsync_merge()` gain a
`capability: FilesystemCapability` parameter. `Dispatcher.__init__` builds
`{disk.id: FilesystemCapability}` once. `_movie.py` and `_tv.py` pre-scans
use `capability.illegal_name_regex`.

**Tech Stack:** `personalscraper.indexer._fs_capability`, `personalscraper.indexer._fs_probe`.

---

## Gate (prerequisites from Phase 2)

Phase 2 produced:

- `personalscraper/indexer/_fs_capability.py` with `FilesystemCapability` and `capability_for`.
- `capability_for("unknown") == capability_for("ntfs_macfuse")` (verified).
- `ntfs_macfuse.rsync_flags` pinned byte-identical to legacy list.

Verify:

```bash
python -c "from personalscraper.indexer._fs_capability import capability_for; print(capability_for('unknown') == capability_for('ntfs_macfuse'))"
# expected: True

python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"
# expected: ['-a', '--no-perms', '--no-owner', '--no-group', '--no-times', '--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store', '--exclude=._*']
```

---

## Files

| Action | Path                                                                                 |
| ------ | ------------------------------------------------------------------------------------ |
| Create | `tests/dispatch/test_transfer_argv.py` (baseline first, then updated for capability) |
| Modify | `personalscraper/dispatch/_transfer.py`                                              |
| Modify | `personalscraper/dispatch/dispatcher.py`                                             |
| Modify | `personalscraper/dispatch/_movie.py`                                                 |
| Modify | `personalscraper/dispatch/_tv.py`                                                    |

---

## Task 1 — Author the golden argv baseline test (BEFORE any refactor)

This task must be completed on the **current code** before touching `_transfer.py`.
It is the equivalence anchor that proves the refactor did not change NTFS behaviour.

**Files:**

- Create: `tests/dispatch/test_transfer_argv.py`

- [ ] **Step 1.1: Read the current `rsync()` implementation in `_transfer.py` lines 85–136**

Confirm the exact flag list: `['-a', '--no-perms', '--no-owner', '--no-group',
'--no-times', '--omit-dir-times', '--inplace', '--partial',
'--exclude=.DS_Store', '--exclude=._*']` (plus optional `--delete`).

- [ ] **Step 1.2: Create `tests/dispatch/test_transfer_argv.py` pinning the current argv**

```python
"""Golden argv tests for _transfer.rsync and _transfer.rsync_merge.

Phase 3 baseline — authored against the PRE-refactor code to serve as the
equivalence anchor.  After the capability refactor, these tests must still
pass with ntfs_macfuse capability injected, proving NTFS behaviour is
byte-identical.
"""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import personalscraper.dispatch._transfer as _transfer
from personalscraper.indexer._fs_capability import NTFS_MACFUSE, APFS, capability_for


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
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync(source, dest)

        called_cmd = mock_run.call_args[0][0]
        # Flags prefix must be byte-identical to legacy hardcoded list.
        assert called_cmd[: len(NTFS_FLAGS_PREFIX)] == NTFS_FLAGS_PREFIX
        assert f"{source}/" in called_cmd
        assert str(dest) in called_cmd
        assert "--delete" not in called_cmd

    def test_rsync_ntfs_argv_with_delete(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync(source, dest, delete=True)

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[: len(NTFS_FLAGS_PREFIX)] == NTFS_FLAGS_PREFIX
        assert "--delete" in called_cmd


class TestRsyncMergeArgvNtfs:
    """Golden pin: rsync_merge() argv for NTFS dest (byte-identical to legacy)."""

    def test_rsync_merge_ntfs_argv(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        dest = tmp_path / "dest"
        backup = tmp_path / "backup"

        with patch("personalscraper.dispatch._transfer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            _transfer.rsync_merge(source, dest, backup)

        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[: len(NTFS_FLAGS_PREFIX)] == NTFS_FLAGS_PREFIX
        assert "--backup" in called_cmd
        assert f"--backup-dir={backup}" in called_cmd
```

- [ ] **Step 1.3: Run the baseline test to verify it passes on current code**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/dispatch/test_transfer_argv.py -v
# expected: all tests PASS (confirming current behaviour is captured)
```

- [ ] **Step 1.4: Commit the baseline test**

```bash
git add tests/dispatch/test_transfer_argv.py
git commit -m "test(multi-filesystem): pin golden rsync argv baseline before capability refactor"
```

---

## Task 2 — Refactor `_transfer.py` to use `FilesystemCapability`

**Files:**

- Modify: `personalscraper/dispatch/_transfer.py`

- [ ] **Step 2.1: Add `_build_rsync_cmd` and update `rsync()` / `rsync_merge()` signatures**

Add the import at the top of `_transfer.py`:

```python
from personalscraper.indexer._fs_capability import FilesystemCapability, NTFS_MACFUSE
```

Add the `_build_rsync_cmd` private builder (replaces both hardcoded lists):

```python
def _build_rsync_cmd(
    source: Path,
    dest: Path,
    capability: FilesystemCapability,
    *,
    delete: bool = False,
    backup_dir: Path | None = None,
) -> list[str]:
    """Build the rsync argv from a FilesystemCapability.

    Single source of truth for both rsync() and rsync_merge() — replaces
    the two hardcoded literal lists.  The capability provides the full
    rsync flag prefix; source/dest paths are appended here.

    Args:
        source: Source directory.
        dest: Destination directory.
        capability: Filesystem capability for the destination volume.
        delete: When True, append ``--delete`` (rsync() only).
        backup_dir: When set, append ``--backup --backup-dir=<path>`` (rsync_merge() only).

    Returns:
        Complete rsync argv list (excluding the ``"rsync"`` binary name).
    """
    cmd = ["rsync", *capability.rsync_flags]
    if delete:
        cmd.append("--delete")
    if backup_dir is not None:
        cmd.append("--backup")
        cmd.append(f"--backup-dir={backup_dir}")
    cmd.extend([f"{source}/", str(dest)])
    return cmd
```

Update `rsync()` signature and body:

```python
def rsync(
    source: Path,
    dest: Path,
    *,
    delete: bool = False,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> bool:
    """Execute rsync from source to dest directory.

    Args:
        source: Source directory.
        dest: Destination directory (created by rsync if absent).
        delete: When True, passes ``--delete`` to remove files in dest
            not present in source.
        capability: Filesystem capability for the destination volume.
            Defaults to ``NTFS_MACFUSE`` (byte-identical to the legacy
            hardcoded flags) so all existing callers without an explicit
            capability are unaffected.

    Returns:
        True if rsync succeeded (returncode 0).
    """
    cmd = _build_rsync_cmd(source, dest, capability, delete=delete)
    log.info("rsync_start", source=source.name, dest=str(dest))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            log.error("rsync_failed", returncode=proc.returncode, stderr=proc.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("rsync_timeout", source=source.name)
        return False
```

Update `rsync_merge()` signature and body:

```python
def rsync_merge(
    source: Path,
    dest: Path,
    backup_dir: Path,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> bool:
    """Execute rsync with backup for merge operations.

    Args:
        source: Source directory.
        dest: Destination directory.
        backup_dir: Directory to store backups of overwritten files.
        capability: Filesystem capability for the destination volume.
            Defaults to ``NTFS_MACFUSE`` (byte-identical to legacy flags).

    Returns:
        True if rsync succeeded.
    """
    cmd = _build_rsync_cmd(source, dest, capability, backup_dir=backup_dir)
    log.info("rsync_merge_start", source=source.name, dest=str(dest), backup=str(backup_dir))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            log.error("rsync_merge_failed", returncode=proc.returncode, stderr=proc.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("rsync_merge_timeout", source=source.name)
        return False
```

Update `has_ntfs_illegal_names()` to accept an optional pattern:

```python
def has_ntfs_illegal_names(
    directory: Path,
    pattern: re.Pattern[str] | None = _NTFS_ILLEGAL,
) -> bool:
    r"""Check if any file in directory has filesystem-illegal characters.

    Scans recursively for filenames matching *pattern*.  Used as a pre-check
    before rsync to filesystems with naming restrictions.

    Args:
        directory: Directory to scan.
        pattern: Compiled regex for illegal characters.  Defaults to the
            NTFS illegal-character set (``<>:"/\|?*``).  Pass ``None`` to
            skip the check entirely (POSIX filesystems with no restrictions).

    Returns:
        True if any file has illegal characters (and pattern is not None).
    """
    if pattern is None:
        return False
    illegal = [f for f in directory.rglob("*") if f.is_file() and pattern.search(f.name)]
    for f in illegal:
        log.warning("ntfs_illegal_filename", path=str(f))
    return len(illegal) > 0
```

- [ ] **Step 2.2: Verify no literal `--no-perms` remains in `_transfer.py`**

```bash
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py
# expected: 0 matches
```

- [ ] **Step 2.3: Run transfer tests**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/dispatch/ -v
# expected: all tests PASS (including the golden argv baseline)
```

- [ ] **Step 2.4: Commit**

```bash
git add personalscraper/dispatch/_transfer.py
git commit -m "refactor(multi-filesystem): _transfer uses FilesystemCapability; remove hardcoded NTFS flag literals"
```

---

## Task 3 — Thread capability through `Dispatcher`, `_movie.py`, `_tv.py`

**Files:**

- Modify: `personalscraper/dispatch/dispatcher.py`
- Modify: `personalscraper/dispatch/_movie.py`
- Modify: `personalscraper/dispatch/_tv.py`

- [ ] **Step 3.1: Add capability resolution to `Dispatcher.__init__`**

In `dispatcher.py`, add imports:

```python
from personalscraper.indexer._fs_capability import FilesystemCapability, capability_for
from personalscraper.indexer._fs_probe import canonical_fs_type, probe_mount
```

In `Dispatcher.__init__`, after `self._disk_configs = get_disk_configs(config)`, add:

```python
# Resolve capability per dest disk once (not per file).
# Override from DiskConfig.fs_type (Phase 4) takes precedence when present;
# for now every disk auto-detects via FsProbe.
self._disk_capabilities: dict[str, FilesystemCapability] = {
    disk.id: capability_for(
        canonical_fs_type(
            (probe_mount(str(disk.path)) or type("_", (), {"raw_fs_type": "unknown"})()).raw_fs_type
            if probe_mount(str(disk.path)) is not None
            else "unknown"
        )
    )
    for disk in self._disk_configs
}
```

Note: `probe_mount` returns `MountInfo | None`. Use a helper for clarity:

```python
def _resolve_capability(disk_path: str) -> FilesystemCapability:
    info = probe_mount(disk_path)
    return capability_for(info.fs_type if info is not None else "unknown")

self._disk_capabilities: dict[str, FilesystemCapability] = {
    disk.id: _resolve_capability(str(disk.path))
    for disk in self._disk_configs
}
```

- [ ] **Step 3.2: Pass capability through `_rsync` and `_rsync_merge` static methods**

Update the static delegator methods to accept and forward `capability`:

```python
@staticmethod
def _rsync(source: Path, dest: Path, delete: bool = False, capability: FilesystemCapability = NTFS_MACFUSE) -> bool:
    """Delegate to ``_transfer.rsync``."""
    return _transfer.rsync(source, dest, delete=delete, capability=capability)

@staticmethod
def _rsync_merge(source: Path, dest: Path, backup_dir: Path, capability: FilesystemCapability = NTFS_MACFUSE) -> bool:
    """Delegate to ``_transfer.rsync_merge``."""
    return _transfer.rsync_merge(source, dest, backup_dir, capability)
```

- [ ] **Step 3.3: Pass capability through `_move_new`**

`_move_new` currently calls `self._rsync(source, tmp_dir)`. Add capability:

```python
def _move_new(self, source: Path, dest: Path, capability: FilesystemCapability = NTFS_MACFUSE) -> bool:
    ...
    if not self._rsync(source, tmp_dir, capability=capability):
    ...
```

- [ ] **Step 3.4: Update `_movie.py` to use `capability.illegal_name_regex` for the pre-scan**

In `_movie.py`, after resolving the target disk, obtain the capability and pass
it to `has_ntfs_illegal_names`:

```python
# Get the capability for the target disk (resolved on Dispatcher init).
# Before a disk is chosen, use the NTFS-safe default for the pre-scan.
cap = dispatcher._disk_capabilities.get(
    existing.disk if existing else "", NTFS_MACFUSE
)

if _transfer.has_ntfs_illegal_names(movie_dir, pattern=cap.illegal_name_regex):
    ...
```

Pass `capability=cap` to `dispatcher._move_new(movie_dir, dest, capability=cap)`.

For the replace path (`replace(movie_dir, dest)`), pass capability similarly
(update `replace()` in `_movie.py` to accept and forward `capability`).

- [ ] **Step 3.5: Mirror the same changes in `_tv.py`**

Same pattern as `_movie.py`: use `dispatcher._disk_capabilities`, pass
`capability.illegal_name_regex` to `has_ntfs_illegal_names`, pass `capability`
to `_move_new` and `merge` (update `merge()` in `_tv.py` to accept and forward
`capability` to `_transfer.rsync_merge`).

- [ ] **Step 3.6: Run the full dispatch test suite**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/dispatch/ -v
# expected: all tests PASS
```

---

## Task 4 — Add APFS and POSIX-name tests

**Files:**

- Modify: `tests/dispatch/test_transfer_argv.py`

- [ ] **Step 4.1: Extend `test_transfer_argv.py` with APFS and POSIX-name tests**

Append to `tests/dispatch/test_transfer_argv.py`:

```python
class TestRsyncArgvApfs:
    """APFS capability drops NTFS-only flags."""

    def test_rsync_apfs_no_no_perms(self, tmp_path: Path) -> None:
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
        # Core flags still present
        assert "-a" in called_cmd
        assert "--inplace" in called_cmd
        assert "--partial" in called_cmd


class TestHasNtfsIllegalNamesPosix:
    """On a POSIX-capable FS (illegal_name_regex=None), colon names are allowed."""

    def test_colon_name_not_flagged_on_apfs(self, tmp_path: Path) -> None:
        colon_dir = tmp_path / "show"
        colon_dir.mkdir()
        (colon_dir / "Episode S01E01: Pilot.mkv").touch()

        # APFS has no illegal-name regex — must return False
        result = _transfer.has_ntfs_illegal_names(colon_dir, pattern=APFS.illegal_name_regex)
        assert result is False

    def test_colon_name_flagged_on_ntfs(self, tmp_path: Path) -> None:
        colon_dir = tmp_path / "show"
        colon_dir.mkdir()
        (colon_dir / "Episode S01E01: Pilot.mkv").touch()

        result = _transfer.has_ntfs_illegal_names(colon_dir, pattern=NTFS_MACFUSE.illegal_name_regex)
        assert result is True
```

- [ ] **Step 4.2: Run the full argv test suite**

```bash
cd /Users/izno/dev/PersonnalScaper
pytest tests/dispatch/test_transfer_argv.py -v
# expected: all tests PASS
```

- [ ] **Step 4.3: Commit the extended tests**

```bash
git add tests/dispatch/test_transfer_argv.py
git commit -m "test(multi-filesystem): extend golden argv tests — APFS drops NTFS flags, POSIX name check"
```

---

## Task 5 — Phase gate + milestone commit

- [ ] **Step 5.1: Residual grep — no literal `--no-perms` in `_transfer.py`**

```bash
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py
# expected: 0 matches (exit 1)
```

- [ ] **Step 5.2: Full quality gate**

```bash
make lint && make test && make check
# expected: exit 0, all green
```

- [ ] **Step 5.3: Milestone commit**

```bash
git add -u
git commit -m "chore(multi-filesystem): phase 3 gate — transfer layer consumes FilesystemCapability, NTFS argv golden-pinned"
```

---

## Acceptance criteria for this phase

```bash
# AC-03: NTFS flags byte-identical (capability_for confirms)
python -c "from personalscraper.indexer._fs_capability import capability_for; print(list(capability_for('ntfs_macfuse').rsync_flags))"
# expected: ['-a', '--no-perms', '--no-owner', '--no-group', '--no-times', '--omit-dir-times', '--inplace', '--partial', '--exclude=.DS_Store', '--exclude=._*']

# AC-10: no literal --no-perms in _transfer.py
rg -n '"--no-perms"' -g '*.py' personalscraper/dispatch/_transfer.py | wc -l | tr -d ' '
# expected: 0

# AC-14: full gate
make check
# expected: exit 0

# AC-17: smoke
python -c "import personalscraper; print('ok')"
# expected: ok
```
