# Phase 6: Crash recovery pipeline (bug #15)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Clean crash artifacts at pipeline startup — orphan `_tmp_dispatch_*`, expired lockout, stale ingest temps.

**Architecture:** New `_recover_from_previous_run()` method in Pipeline, called at start of `run()`.

**Tech Stack:** Python, pytest

---

## Task 1: Write reproducer tests

**Files:**

- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests**

```python
class TestCrashRecovery:
    """Tests for _recover_from_previous_run cleanup."""

    def test_expired_lockout_cleaned(self, tmp_path: Path) -> None:
        """Expired qBit lockout file (>1h) should be removed at startup."""
        import time
        from personalscraper.pipeline import Pipeline

        lockout = tmp_path / ".cache" / "personalscraper" / "qbit_auth_lockout"
        lockout.parent.mkdir(parents=True)
        lockout.write_text("login_failed")
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        os.utime(lockout, (old_time, old_time))

        settings = MagicMock()
        settings.disk_configs = []
        settings.ingest_dir = tmp_path / "097-TEMP"
        settings.ingest_dir.mkdir()

        pipeline = Pipeline(settings, dry_run=False)
        pipeline._recover_from_previous_run(lockout_path=lockout)

        assert not lockout.exists()

    def test_non_expired_lockout_kept(self, tmp_path: Path) -> None:
        """Recent lockout file (<1h) should NOT be removed."""
        from personalscraper.pipeline import Pipeline

        lockout = tmp_path / ".cache" / "personalscraper" / "qbit_auth_lockout"
        lockout.parent.mkdir(parents=True)
        lockout.write_text("login_failed")
        # mtime is now (just created) — not expired

        settings = MagicMock()
        settings.disk_configs = []
        settings.ingest_dir = tmp_path / "097-TEMP"
        settings.ingest_dir.mkdir()

        pipeline = Pipeline(settings, dry_run=False)
        pipeline._recover_from_previous_run(lockout_path=lockout)

        assert lockout.exists()

    def test_orphan_tmp_dispatch_cleaned(self, tmp_path: Path) -> None:
        """Orphan _tmp_dispatch_* dirs on storage disks should be removed."""
        from personalscraper.pipeline import Pipeline

        # Simulate a storage disk with an orphan
        disk_path = tmp_path / "Disk1" / "medias"
        category = disk_path / "films"
        orphan = category / "_tmp_dispatch_Movie (2025)"
        orphan.mkdir(parents=True)
        (orphan / "file.mkv").write_bytes(b"\x00" * 100)

        disk_config = MagicMock()
        disk_config.path = disk_path

        settings = MagicMock()
        settings.disk_configs = [disk_config]
        settings.ingest_dir = tmp_path / "097-TEMP"
        settings.ingest_dir.mkdir()

        pipeline = Pipeline(settings, dry_run=False)
        pipeline._recover_from_previous_run(
            lockout_path=tmp_path / "nonexistent_lockout"
        )

        assert not orphan.exists()

    def test_orphan_ingest_tmp_cleaned(self, tmp_path: Path) -> None:
        """Orphan .ingest_tmp_* dirs in staging should be removed."""
        from personalscraper.pipeline import Pipeline

        ingest_dir = tmp_path / "097-TEMP"
        ingest_dir.mkdir()
        orphan = ingest_dir / ".ingest_tmp_Movie"
        orphan.mkdir()
        (orphan / "file.mkv").write_bytes(b"\x00" * 100)

        settings = MagicMock()
        settings.disk_configs = []
        settings.ingest_dir = ingest_dir

        pipeline = Pipeline(settings, dry_run=False)
        pipeline._recover_from_previous_run(
            lockout_path=tmp_path / "nonexistent_lockout"
        )

        assert not orphan.exists()
```

Add `import os` at the top of the test file if not already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pipeline.py::TestCrashRecovery -v`
Expected: FAIL — `Pipeline` has no `_recover_from_previous_run` method

- [ ] **Step 3: Commit**

```bash
git add tests/test_pipeline.py
git commit -m "v12.6.1: Add failing tests for pipeline crash recovery"
```

## Task 2: Implement \_recover_from_previous_run

**Files:**

- Modify: `personalscraper/pipeline.py`

- [ ] **Step 1: Add imports**

Add at the top of `pipeline.py`:

```python
import shutil
import time
```

- [ ] **Step 2: Add \_recover_from_previous_run method**

Add to the `Pipeline` class:

```python
    def _recover_from_previous_run(
        self, lockout_path: Path | None = None,
    ) -> int:
        """Clean up artifacts from a previous interrupted pipeline run.

        Runs at pipeline startup before INGEST. Handles:
        1. Orphan _tmp_dispatch_* directories on storage disks
        2. Expired qBit auth lockout file (>1 hour)
        3. Orphan .ingest_tmp_* directories in staging

        Args:
            lockout_path: Override lockout file path (for testing).
                Defaults to ~/.cache/personalscraper/qbit_auth_lockout.

        Returns:
            Number of artifacts cleaned.
        """
        cleaned = 0

        # 1. Clean _tmp_dispatch_* on ALL storage disks
        for disk_config in self.settings.disk_configs:
            if not disk_config.path.exists():
                continue
            try:
                for category_dir in disk_config.path.iterdir():
                    if not category_dir.is_dir():
                        continue
                    for item in category_dir.iterdir():
                        if item.name.startswith("_tmp_dispatch_"):
                            try:
                                shutil.rmtree(item)
                                self._log.info("crash_recovery_dispatch_orphan", path=str(item))
                                cleaned += 1
                            except OSError as exc:
                                self._log.warning("crash_recovery_failed", path=str(item), error=str(exc))
            except OSError:
                continue

        # 2. Clean expired qBit lockout
        if lockout_path is None:
            lockout_path = Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"
        if lockout_path.exists():
            try:
                age = time.time() - lockout_path.stat().st_mtime
                if age > 3600:
                    lockout_path.unlink(missing_ok=True)
                    self._log.info("crash_recovery_lockout_expired", age_seconds=int(age))
                    cleaned += 1
            except OSError:
                pass

        # 3. Clean .ingest_tmp_* in staging
        from personalscraper.ingest.ingest import _cleanup_orphan_temps
        ingest_dir = self.settings.ingest_dir
        if ingest_dir.exists():
            cleaned += _cleanup_orphan_temps(ingest_dir)

        if cleaned:
            self._log.info("crash_recovery_complete", cleaned=cleaned)
        return cleaned
```

- [ ] **Step 3: Call at start of run()**

In `Pipeline.run()`, after `report = PipelineReport(...)` (line 95) and before Phase 1 INGEST, add:

```python
        report = PipelineReport(started_at=datetime.now())

        # Recover from previous interrupted run
        self._recover_from_previous_run()

        # Phase 1: INGEST
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_pipeline.py::TestCrashRecovery -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/pipeline.py
git commit -m "v12.6.2: Add crash recovery at pipeline startup — clean orphans and expired lockout"
```

## Task 3: Update IMPLEMENTATION.md

- [ ] **Step 1: Mark Phase 6 complete**
- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.6.3: Update IMPLEMENTATION.md — Phase 6 complete"
```
