# Phase 01 — Core `info` module + CLI wiring + tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `personalscraper info` command end-to-end: new `info/` module with types and logic, CLI wiring, unit tests, and smoke test.

**Architecture:** New isolated module `personalscraper/info/run.py` with frozen dataclasses (`DiskStatus`, `InfoReport`), `collect_info(config)` gathering version/paths/disk stats via `shutil.disk_usage`, and `format_info(report)` rendering plain text. The CLI command is a thin wrapper added to `personalscraper/cli.py`. No modifications to existing modules.

**Tech Stack:** Python 3.11+, typer, shutil, dataclasses, pytest, typer.testing.CliRunner, ruff, mypy (strict).

---

## File map

| Action | Path                               | Responsibility                                                     |
| ------ | ---------------------------------- | ------------------------------------------------------------------ |
| Create | `personalscraper/info/__init__.py` | Empty package marker                                               |
| Create | `personalscraper/info/run.py`      | `DiskStatus`, `InfoReport`, `collect_info`, `format_info`          |
| Create | `tests/info/__init__.py`           | Empty package marker                                               |
| Create | `tests/info/test_run.py`           | Unit tests: version, disk_usage OK, not-mounted, empty, formatting |
| Modify | `personalscraper/cli.py`           | Add `info` command (lazy import)                                   |
| Modify | `tests/test_cli.py`                | Add `test_info_command` smoke test                                 |

---

## Sub-phase 1.1 — `info/` module + unit tests

### Task 1: Create the `info` package skeleton

**Files:**

- Create: `personalscraper/info/__init__.py`
- Create: `tests/info/__init__.py`

- [ ] **Step 1: Create the two empty `__init__.py` files**

```bash
touch "/Volumes/IznoServer SSD/A TRIER/personalscraper/info/__init__.py"
touch "/Volumes/IznoServer SSD/A TRIER/tests/info/__init__.py"
```

- [ ] **Step 2: Verify both files exist**

```bash
ls personalscraper/info/ tests/info/
```

Expected: each directory shows `__init__.py`.

---

### Task 2: Write failing unit tests for `collect_info` and `format_info`

**Files:**

- Create: `tests/info/test_run.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for personalscraper.info.run — collect_info and format_info."""

from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.info.run import DiskStatus, InfoReport, collect_info, format_info


# ── Helpers ─────────────────────────────────────────────────────────────────

def _disk_usage_result(total: int, used: int, free: int):
    """Return a namedtuple-like object matching shutil.disk_usage output."""
    import collections
    Usage = collections.namedtuple("Usage", ["total", "used", "free"])
    return Usage(total=total, used=used, free=free)


# ── DiskStatus unit tests ────────────────────────────────────────────────────

def test_disk_status_not_mounted():
    """DiskStatus with mounted=False has zero byte counts."""
    ds = DiskStatus(name="DISK01", path=None, mounted=False, total_bytes=0, used_bytes=0)
    assert ds.mounted is False
    assert ds.total_bytes == 0
    assert ds.used_bytes == 0


def test_disk_status_mounted_with_data():
    """DiskStatus with mounted=True carries real byte counts."""
    ds = DiskStatus(
        name="DISK01",
        path=Path("/Volumes/DISK01"),
        mounted=True,
        total_bytes=2_000_000_000_000,
        used_bytes=1_200_000_000_000,
    )
    assert ds.mounted is True
    assert ds.total_bytes == 2_000_000_000_000


# ── collect_info unit tests ──────────────────────────────────────────────────

def test_collect_info_version(test_config):
    """collect_info returns current __version__ string."""
    import personalscraper

    with patch("shutil.disk_usage", return_value=_disk_usage_result(1_000, 500, 500)):
        report = collect_info(test_config)

    assert report.version == personalscraper.__version__


def test_collect_info_staging_path(test_config):
    """collect_info sets staging_path from config.paths.staging_dir."""
    with patch("shutil.disk_usage", return_value=_disk_usage_result(1_000, 500, 500)):
        report = collect_info(test_config)

    assert report.staging_path == test_config.paths.staging_dir


def test_collect_info_disk_not_mounted(test_config):
    """collect_info marks disk as NOT MOUNTED when path does not exist."""
    # Patch disk paths to a non-existent location
    with patch("personalscraper.info.run.Path.exists", return_value=False):
        report = collect_info(test_config)

    for disk_status in report.disks:
        assert disk_status.mounted is False
        assert disk_status.total_bytes == 0
        assert disk_status.used_bytes == 0


def test_collect_info_disk_mounted_with_data(test_config, tmp_path):
    """collect_info reads shutil.disk_usage for mounted disks."""
    # Make the disk path exist
    disk_path = tmp_path / "fake_disk"
    disk_path.mkdir()

    fake_usage = _disk_usage_result(
        total=2_000_000_000_000,
        used=1_200_000_000_000,
        free=800_000_000_000,
    )
    with (
        patch("personalscraper.info.run.Path.exists", return_value=True),
        patch("shutil.disk_usage", return_value=fake_usage),
    ):
        report = collect_info(test_config)

    for disk_status in report.disks:
        assert disk_status.mounted is True
        assert disk_status.total_bytes == 2_000_000_000_000
        assert disk_status.used_bytes == 1_200_000_000_000


def test_collect_info_disk_mounted_but_empty(test_config):
    """collect_info marks disk as empty when used bytes < 1 MB."""
    fake_usage = _disk_usage_result(
        total=10_000_000_000,
        used=512_000,   # 512 KB — filesystem headers only
        free=9_999_488_000,
    )
    with (
        patch("personalscraper.info.run.Path.exists", return_value=True),
        patch("shutil.disk_usage", return_value=fake_usage),
    ):
        report = collect_info(test_config)

    # All disks show mounted=True but used_bytes below 1 MB threshold
    for disk_status in report.disks:
        assert disk_status.mounted is True
        assert disk_status.used_bytes < 1_000_000


# ── format_info unit tests ───────────────────────────────────────────────────

def _make_report(*, mounted: bool = True, used: int = 1_200_000_000_000, total: int = 2_000_000_000_000) -> InfoReport:
    """Build a minimal InfoReport for formatting tests."""
    return InfoReport(
        version="0.2.0",
        staging_path=Path("/Volumes/IznoServer SSD/A TRIER"),
        archive_path=Path("/Volumes/IznoServer SSD/A TRIER/Done"),
        disks=[
            DiskStatus(
                name="drive_a",
                path=Path("/Volumes/DISK01") if mounted else None,
                mounted=mounted,
                total_bytes=total if mounted else 0,
                used_bytes=used if mounted else 0,
            )
        ],
    )


def test_format_info_contains_version():
    """format_info output includes 'personalscraper' and version."""
    output = format_info(_make_report())
    assert "personalscraper" in output
    assert "0.2.0" in output


def test_format_info_contains_staging():
    """format_info output includes staging: label."""
    output = format_info(_make_report())
    assert "staging:" in output


def test_format_info_contains_archive():
    """format_info output includes archive: label."""
    output = format_info(_make_report())
    assert "archive:" in output


def test_format_info_not_mounted_label():
    """format_info shows NOT MOUNTED for unmounted disks."""
    output = format_info(_make_report(mounted=False))
    assert "NOT MOUNTED" in output


def test_format_info_empty_disk_label():
    """format_info shows MOUNTED BUT EMPTY for disks with < 1 MB used."""
    output = format_info(_make_report(used=512_000, total=10_000_000_000))
    assert "MOUNTED BUT EMPTY" in output


def test_format_info_disk_with_data_shows_percent():
    """format_info shows percentage for disks with real data."""
    output = format_info(_make_report(used=1_200_000_000_000, total=2_000_000_000_000))
    assert "%" in output


def test_format_info_disk_count_header(test_config):
    """format_info header shows the number of configured disks."""
    report = InfoReport(
        version="0.2.0",
        staging_path=Path("/fake/staging"),
        archive_path=Path("/fake/done"),
        disks=[
            DiskStatus(name=d.id, path=d.path, mounted=False, total_bytes=0, used_bytes=0)
            for d in test_config.disks
        ],
    )
    output = format_info(report)
    assert f"({len(test_config.disks)} configured)" in output
```

Save to: `tests/info/test_run.py`

- [ ] **Step 2: Run the tests — verify they fail with ImportError (module not created yet)**

```bash
pytest tests/info/test_run.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'personalscraper.info.run'`

---

### Task 3: Implement `personalscraper/info/run.py`

**Files:**

- Create: `personalscraper/info/run.py`

- [ ] **Step 1: Write the implementation**

```python
"""Info command runner: collect and format pipeline status.

Gathers current version, config paths, and disk statistics for the
`personalscraper info` CLI command.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from personalscraper import __version__
from personalscraper.conf.models import Config


@dataclass(frozen=True)
class DiskStatus:
    """Status snapshot for a single configured storage disk.

    Attributes:
        name: Disk identifier from DiskConfig.id (e.g. "drive_a").
        path: Mount point Path, or None if the disk path is not configured.
        mounted: True when the path exists on the filesystem.
        total_bytes: Total capacity in bytes; 0 if not mounted.
        used_bytes: Used space in bytes; 0 if not mounted.
    """

    name: str
    path: Path | None
    mounted: bool
    total_bytes: int
    used_bytes: int


@dataclass(frozen=True)
class InfoReport:
    """Aggregated status report for the `info` command.

    Attributes:
        version: Current personalscraper version string.
        staging_path: Staging directory (A TRIER) from config.
        archive_path: Archive/done directory from config (staging_dir parent).
        disks: Status snapshot for each configured disk.
    """

    version: str
    staging_path: Path
    archive_path: Path
    disks: list[DiskStatus]


_EMPTY_THRESHOLD_BYTES = 1_000_000  # 1 MB — below this, disk is "mounted but empty"


def _human_bytes(n: int) -> str:
    """Format a byte count as a human-readable string with appropriate unit.

    Uses 1000-based units (KB, MB, GB, TB) matching common disk labelling.

    Args:
        n: Number of bytes.

    Returns:
        String like "1.2 TB", "800 GB", "512 MB".
    """
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1000.0
        if abs(n) < 1000:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} PB"


def collect_info(config: Config) -> InfoReport:
    """Gather version, config paths, and disk stats from the current environment.

    For each disk in config.disks: checks if the path exists (mounted), then
    calls shutil.disk_usage to get capacity. Non-existent paths are reported
    as NOT MOUNTED with zero byte counts.

    Args:
        config: Loaded and validated pipeline Config.

    Returns:
        InfoReport with version, paths, and per-disk DiskStatus entries.
    """
    disks: list[DiskStatus] = []
    for disk_cfg in config.disks:
        path = disk_cfg.path
        if not path.exists():
            disks.append(DiskStatus(name=disk_cfg.id, path=None, mounted=False, total_bytes=0, used_bytes=0))
            continue

        usage = shutil.disk_usage(path)
        disks.append(
            DiskStatus(
                name=disk_cfg.id,
                path=path,
                mounted=True,
                total_bytes=usage.total,
                used_bytes=usage.used,
            )
        )

    # Derive archive_path as the "Done" sub-folder of staging_dir (conventional).
    archive_path = config.paths.staging_dir / "Done"

    return InfoReport(
        version=__version__,
        staging_path=config.paths.staging_dir,
        archive_path=archive_path,
        disks=disks,
    )


def format_info(report: InfoReport) -> str:
    """Render an InfoReport as a plain-text human-readable string.

    Format mirrors the DESIGN.md spec: version header, Config section with
    staging/archive paths, then Disks section with per-disk status.

    Args:
        report: InfoReport produced by collect_info().

    Returns:
        Multi-line string ready to print to stdout.
    """
    lines: list[str] = []

    # Header: version
    lines.append(f"personalscraper {report.version}")
    lines.append("")

    # Config section
    lines.append("Config")
    lines.append(f"  staging: {report.staging_path}")
    lines.append(f"  archive: {report.archive_path}")
    lines.append("")

    # Disks section
    lines.append(f"Disks ({len(report.disks)} configured)")
    for disk in report.disks:
        if not disk.mounted:
            lines.append(f"  {disk.name:<10} -                 NOT MOUNTED")
            continue

        if disk.used_bytes < _EMPTY_THRESHOLD_BYTES:
            path_str = str(disk.path) if disk.path else "-"
            lines.append(f"  {disk.name:<10} {path_str:<25} MOUNTED BUT EMPTY")
            continue

        used_str = _human_bytes(disk.used_bytes)
        total_str = _human_bytes(disk.total_bytes)
        percent = int(disk.used_bytes / disk.total_bytes * 100) if disk.total_bytes else 0
        path_str = str(disk.path) if disk.path else "-"
        lines.append(f"  {disk.name:<10} {path_str:<25} {used_str} / {total_str} ({percent}% used)")

    return "\n".join(lines)
```

- [ ] **Step 2: Run the unit tests — all must pass**

```bash
pytest tests/info/test_run.py -v
```

Expected: all tests PASS (no failures, no errors).

- [ ] **Step 3: Commit sub-phase 1.1**

```bash
git add personalscraper/info/__init__.py personalscraper/info/run.py tests/info/__init__.py tests/info/test_run.py
git commit -m "feat(info-cmd): add info module with collect_info, format_info, and unit tests"
```

---

## Sub-phase 1.2 — CLI wiring + smoke test

### Task 4: Add the `info` command to `personalscraper/cli.py`

**Files:**

- Modify: `personalscraper/cli.py`

The existing `cli.py` uses `@app.command()` with lazy imports (see `scrape` command pattern). Add `info` in the same style — no lock required (read-only operation).

- [ ] **Step 1: Locate the insertion point**

Open `personalscraper/cli.py`. Find any existing `@app.command()` block (e.g. the `ingest` command around line 165). Add the new `info` command after all existing commands, before any `if __name__ == "__main__"` block (if it exists).

- [ ] **Step 2: Add the `info` command**

Add at the end of the command definitions in `personalscraper/cli.py`:

```python
@app.command()
def info(ctx: typer.Context) -> None:
    """Display version, config paths, and disk status."""
    from personalscraper.info.run import collect_info, format_info

    config = ctx.obj.config
    assert config is not None  # guaranteed non-None by callback
    report = collect_info(config)
    print(format_info(report))
```

- [ ] **Step 3: Verify the CLI recognises the command**

```bash
python -m personalscraper --help 2>&1 | grep info
```

Expected: `info` appears in the command list.

---

### Task 5: Add CLI smoke test in `tests/test_cli.py`

**Files:**

- Modify: `tests/test_cli.py`

The `conftest.py` autouse fixture patches `load_config` / `resolve_config_path` for `test_cli.py` automatically. The `test_config` fixture provides a synthetic Config. The `runner` variable (CliRunner) and `_PATCH_LOAD_CONFIG` / `_PATCH_RESOLVE_PATH` are already defined at the top of `tests/test_cli.py`.

- [ ] **Step 1: Add the smoke test**

Append the following test at the end of `tests/test_cli.py`:

```python
# ── info command ─────────────────────────────────────────────────────────────


def test_info_command(test_config) -> None:
    """info command exits 0 and output contains 'personalscraper' and version."""
    from unittest.mock import patch as _patch

    import personalscraper

    # Patch shutil.disk_usage so no real filesystem access occurs.
    import collections
    Usage = collections.namedtuple("Usage", ["total", "used", "free"])
    fake_usage = Usage(total=2_000_000_000_000, used=1_200_000_000_000, free=800_000_000_000)

    with _patch("shutil.disk_usage", return_value=fake_usage):
        result = runner.invoke(app, ["info"])

    assert result.exit_code == 0, f"exit_code={result.exit_code}\n{result.output}"
    assert "personalscraper" in result.output
    assert personalscraper.__version__ in result.output
    assert "staging:" in result.output
    assert "archive:" in result.output
```

- [ ] **Step 2: Run the smoke test**

```bash
pytest tests/test_cli.py::test_info_command -v
```

Expected: PASS.

- [ ] **Step 3: Run all CLI tests to catch regressions**

```bash
pytest tests/test_cli.py -v 2>&1 | tail -20
```

Expected: all existing tests still PASS.

- [ ] **Step 4: Commit sub-phase 1.2**

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "feat(info-cmd): wire info CLI command and add smoke test"
```

---

## Sub-phase 1.3 — Quality gate

### Task 6: Lint, type-check, full test suite

**Files:** none (verification only)

- [ ] **Step 1: Run ruff check**

```bash
make lint
```

Or directly:

```bash
ruff check personalscraper/info/ tests/info/ && ruff format --check personalscraper/info/ tests/info/
```

Expected: no errors. If ruff reports issues, fix them, re-stage, and amend or add a fixup commit.

- [ ] **Step 2: Run mypy**

```bash
mypy personalscraper/info/run.py
```

Expected: `Success: no issues found`. Common issues to pre-empt:

- `list[DiskStatus]` in a frozen dataclass field needs `field(default_factory=list)` only if mutable default — here it's passed at construction, fine.
- If mypy complains about `Path | None`, ensure `from __future__ import annotations` is at top of `run.py`.

- [ ] **Step 3: Run full test suite**

```bash
make test
```

Or directly:

```bash
pytest --tb=short -q
```

Expected: all tests pass (≥ 1702 existing + new info tests).

- [ ] **Step 4: Commit quality gate**

```bash
git commit --allow-empty -m "chore(info-cmd): quality gate — ruff + mypy + full test suite green"
```

(Use `--allow-empty` only if there were no lint fixes needed; if fixes were needed, stage and commit the fixes instead.)
