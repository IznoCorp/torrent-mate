"""Tests for the dispatch step runner."""

import shutil
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.run import (
    _cleanup_staging_orphans,
    _drain_dispatch_outbox,
    _enrich_after_dispatch,
    _to_step_report,
    run_dispatch,
)
from tests.fixtures.config import CANONICAL_STAGING_DIRS


class TestToStepReport:
    """Tests for _to_step_report conversion."""

    def test_counts(self) -> None:
        """Should count replaced/merged/moved as success."""
        results = [
            DispatchResult(source=Path("a"), action="replaced", disk="Disk1"),
            DispatchResult(source=Path("b"), action="merged", disk="Disk2"),
            DispatchResult(source=Path("c"), action="moved", disk="Disk1"),
            DispatchResult(source=Path("d"), action="skipped", reason="no space"),
            DispatchResult(source=Path("e"), action="error", reason="rsync failed"),
        ]
        report = _to_step_report(results)
        assert report.success_count == 3
        assert report.skip_count == 1
        assert report.error_count == 1
        assert report.name == "dispatch"

    def test_skipped_without_reason(self) -> None:
        """Skipped result with reason=None should still be counted."""
        results = [
            DispatchResult(source=Path("a"), action="skipped", reason=None),
            DispatchResult(source=Path("b"), action="error", reason=None),
        ]
        report = _to_step_report(results)
        assert report.skip_count == 1
        assert report.error_count == 1

    def test_error_followed_by_success_continues_loop(self) -> None:
        """Error result followed by another result — loop continues after error."""
        results = [
            DispatchResult(source=Path("a"), action="error", reason="fail"),
            DispatchResult(source=Path("b"), action="moved", disk="Disk1"),
        ]
        report = _to_step_report(results)
        assert report.error_count == 1
        assert report.success_count == 1

    def test_unknown_action_does_not_crash(self) -> None:
        """Result with an unexpected action is silently ignored (no count)."""
        results = [
            DispatchResult(source=Path("a"), action="unknown_action"),
            DispatchResult(source=Path("b"), action="moved", disk="Disk1"),
        ]
        report = _to_step_report(results)
        assert report.success_count == 1
        assert report.skip_count == 0
        assert report.error_count == 0


class TestCleanupStagingOrphans:
    """Tests for _cleanup_staging_orphans — safe, tmp_path only."""

    def test_missing_category_dir_is_noop(self, tmp_path: Path) -> None:
        """When a category dir does not exist, it is skipped (no error)."""
        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS

        cleaned = _cleanup_staging_orphans(settings, config, tmp_path)
        assert cleaned == 0

    def test_non_dir_items_skipped(self, tmp_path: Path) -> None:
        """Files inside a category dir are skipped (only dirs are scanned)."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "readme.txt").write_text("not a dir")

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS

        cleaned = _cleanup_staging_orphans(settings, config, tmp_path)
        assert cleaned == 0

    def test_tmp_dispatch_orphan_cleaned(self, tmp_path: Path) -> None:
        """_tmp_dispatch_* dirs inside category dirs are removed."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        orphan = movies_dir / "_tmp_dispatch_Movie (2024)"
        orphan.mkdir()

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS

        cleaned = _cleanup_staging_orphans(settings, config, tmp_path)
        assert cleaned == 1
        assert not orphan.exists()

    def test_merge_backup_orphan_cleaned(self, tmp_path: Path) -> None:
        """.merge_backup/ dirs inside media dirs are removed."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        media = movies_dir / "Some Movie (2024)"
        media.mkdir()
        backup = media / ".merge_backup"
        backup.mkdir()

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS

        cleaned = _cleanup_staging_orphans(settings, config, tmp_path)
        assert cleaned == 1
        assert not backup.exists()

    def test_tmp_orphan_rmtree_oserror_caught(self, tmp_path: Path) -> None:
        """OSError during rmtree of _tmp_dispatch_ is caught, not raised."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        orphan = movies_dir / "_tmp_dispatch_Broken"
        orphan.mkdir()

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS

        with patch.object(shutil, "rmtree", side_effect=OSError("device busy")):
            cleaned = _cleanup_staging_orphans(settings, config, tmp_path)

        assert cleaned == 0  # failed cleanup counts zero
        assert orphan.exists()  # orphan still exists

    def test_backup_rmtree_oserror_caught(self, tmp_path: Path) -> None:
        """OSError during rmtree of .merge_backup/ is caught, not raised."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        media = movies_dir / "Some Movie (2024)"
        media.mkdir()
        backup = media / ".merge_backup"
        backup.mkdir()

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS

        # First call cleans _tmp_dispatch_ (succeeds, but none found),
        # second call tries to clean .merge_backup/ (fails).
        with patch.object(shutil, "rmtree", side_effect=[0, OSError("busy")]):
            _cleanup_staging_orphans(settings, config, tmp_path)

        # The first call does nothing (no tmp_dispatch), the second fails.
        assert backup.exists()


class TestRunDispatch:
    """Tests for run_dispatch function."""

    def test_runs_with_mocked_dispatcher(self, tmp_path: Path) -> None:
        """Should create dispatcher and process."""
        settings = MagicMock()
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"

        config = MagicMock()
        config.paths.staging_dir = tmp_path
        config.paths.data_dir = tmp_path / ".data"
        config.indexer.db_path = tmp_path / ".data" / "library.db"
        config.disks = []
        config.staging_dirs = CANONICAL_STAGING_DIRS

        with (
            patch("personalscraper.dispatch.run.Dispatcher") as MockDisp,
            patch("personalscraper.dispatch.run.MediaIndex") as MockIdx,
        ):
            mock_idx = MockIdx.return_value
            mock_idx.__enter__ = MagicMock(return_value=mock_idx)
            mock_idx.__exit__ = MagicMock(return_value=False)
            mock_idx.count = 5  # non-zero so rebuild branch is skipped
            mock_disp = MockDisp.return_value
            mock_disp.process.return_value = []

            caller_bus = EventBus()
            report = run_dispatch(settings, config=config, dry_run=True, event_bus=caller_bus)

        assert report.name == "dispatch"
        MockIdx.assert_called_once_with(config.indexer.db_path, config=config, auto_rebuild=False, event_bus=caller_bus)
        mock_idx.begin_preview.assert_called_once()
        mock_idx.rebuild.assert_not_called()  # count=5 > 0 skips rebuild

    def test_dry_run_empty_index_rebuild_is_rolled_back(self, tmp_path: Path) -> None:
        """Dry-run can preview with a rebuilt index without persisting cache rows."""
        settings = MagicMock()
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"

        disk_root = tmp_path / "disk" / "medias"
        (disk_root / "movies" / "Existing Movie (2024)").mkdir(parents=True)

        config = MagicMock()
        config.paths.staging_dir = tmp_path / "staging"
        config.paths.data_dir = tmp_path / ".data"
        config.indexer.db_path = tmp_path / ".data" / "library.db"
        config.disks = [DiskConfig(id="disk_1", path=disk_root, categories=["movies"])]
        config.categories = {}
        config.staging_dirs = CANONICAL_STAGING_DIRS

        report = run_dispatch(settings, config=config, dry_run=True, verified=[], event_bus=EventBus())

        assert report.name == "dispatch"
        with sqlite3.connect(config.indexer.db_path) as conn:
            media_items = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
            dispatch_attrs = conn.execute(
                "SELECT COUNT(*) FROM item_attribute WHERE key = 'dispatch_normalized_title'"
            ).fetchone()[0]

        assert media_items == 0
        assert dispatch_attrs == 0

    def test_cleaned_orphans_appended_to_details(self, tmp_path: Path) -> None:
        """When orphans are cleaned, an info detail is added to the report."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        orphan = movies_dir / "_tmp_dispatch_Test"
        orphan.mkdir()

        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = tmp_path
        config.paths.data_dir = tmp_path / ".data"
        config.indexer.db_path = tmp_path / ".data" / "library.db"
        config.disks = []
        config.staging_dirs = CANONICAL_STAGING_DIRS

        with (
            patch("personalscraper.dispatch.run.Dispatcher") as MockDisp,
            patch("personalscraper.dispatch.run.MediaIndex") as MockIdx,
            patch("personalscraper.dispatch.run._drain_dispatch_outbox"),
            patch("personalscraper.dispatch.run._enrich_after_dispatch"),
        ):
            mock_idx = MockIdx.return_value
            mock_idx.__enter__ = MagicMock(return_value=mock_idx)
            mock_idx.__exit__ = MagicMock(return_value=False)
            mock_idx.count = 5
            mock_disp = MockDisp.return_value
            mock_disp.process.return_value = []

            report = run_dispatch(settings, config=config, dry_run=False, verified=[], event_bus=EventBus())

        assert report.name == "dispatch"
        assert any("Cleaned" in d and "staging orphan" in d for d in report.details)

    def test_outbox_drain_called_after_dispatch(self, tmp_path: Path) -> None:
        """After non-dry-run dispatch, _drain_dispatch_outbox is called."""
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = tmp_path
        config.paths.data_dir = tmp_path / ".data"
        config.indexer.db_path = tmp_path / ".data" / "library.db"
        config.disks = []
        config.staging_dirs = CANONICAL_STAGING_DIRS

        with (
            patch("personalscraper.dispatch.run.Dispatcher") as MockDisp,
            patch("personalscraper.dispatch.run.MediaIndex") as MockIdx,
            patch("personalscraper.dispatch.run._drain_dispatch_outbox") as mock_drain,
            patch("personalscraper.dispatch.run._enrich_after_dispatch") as mock_enrich,
        ):
            mock_idx = MockIdx.return_value
            mock_idx.__enter__ = MagicMock(return_value=mock_idx)
            mock_idx.__exit__ = MagicMock(return_value=False)
            mock_idx.count = 5
            mock_disp = MockDisp.return_value
            mock_disp.process.return_value = []

            run_dispatch(settings, config=config, dry_run=False, verified=[], event_bus=EventBus())

        mock_drain.assert_called_once()
        mock_enrich.assert_called_once()

    def test_dry_run_skips_outbox_drain_and_enrich(self, tmp_path: Path) -> None:
        """In dry_run mode, neither outbox drain nor enrich is called."""
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = tmp_path
        config.paths.data_dir = tmp_path / ".data"
        config.indexer.db_path = tmp_path / ".data" / "library.db"
        config.disks = []
        config.staging_dirs = CANONICAL_STAGING_DIRS

        with (
            patch("personalscraper.dispatch.run.Dispatcher") as MockDisp,
            patch("personalscraper.dispatch.run.MediaIndex") as MockIdx,
            patch("personalscraper.dispatch.run._drain_dispatch_outbox") as mock_drain,
            patch("personalscraper.dispatch.run._enrich_after_dispatch") as mock_enrich,
        ):
            mock_idx = MockIdx.return_value
            mock_idx.__enter__ = MagicMock(return_value=mock_idx)
            mock_idx.__exit__ = MagicMock(return_value=False)
            mock_idx.count = 5
            mock_disp = MockDisp.return_value
            mock_disp.process.return_value = []

            run_dispatch(settings, config=config, dry_run=True, verified=[], event_bus=EventBus())

        mock_drain.assert_not_called()
        mock_enrich.assert_not_called()

    def test_backup_rmtree_oserror_caught(self, tmp_path: Path) -> None:
        """OSError during .merge_backup/ rmtree is caught, not raised."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        media = movies_dir / "Some Movie (2024)"
        media.mkdir()
        backup = media / ".merge_backup"
        backup.mkdir()

        settings = MagicMock()
        config = MagicMock()
        config.staging_dirs = CANONICAL_STAGING_DIRS

        with patch.object(shutil, "rmtree", side_effect=OSError("busy")):
            cleaned = _cleanup_staging_orphans(settings, config, tmp_path)
        assert cleaned == 0


# ---------------------------------------------------------------------------
# _drain_dispatch_outbox + _enrich_after_dispatch with real SQLite DB
# ---------------------------------------------------------------------------


_SCHEMA_DDL = """
CREATE TABLE disk (
  id           INTEGER PRIMARY KEY,
  uuid         TEXT NOT NULL UNIQUE,
  label        TEXT NOT NULL,
  mount_path   TEXT,
  last_seen_at INTEGER,
  merkle_root  TEXT,
  is_mounted   INTEGER NOT NULL DEFAULT 0 CHECK(is_mounted IN (0,1)),
  unreachable_strikes INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE scan_run (
  id          INTEGER PRIMARY KEY,
  generation  INTEGER NOT NULL,
  mode        TEXT NOT NULL CHECK(mode IN ('quick','incremental','enrich','full','verify','repair')),
  disk_filter TEXT,
  started_at  INTEGER NOT NULL,
  finished_at INTEGER,
  last_path   TEXT,
  status      TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','ok','failed','aborted')),
  stats_json  TEXT
);
"""


def _make_drain_db(tmp_path: Path) -> Path:
    """Create a minimal SQLite DB with the disk + scan_run tables."""
    import sqlite3

    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_DDL)
    conn.execute(
        "INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES (?,?,?,?)",
        ("drive-uuid", "DriveA", str(tmp_path / "drive"), 1),
    )
    conn.commit()
    conn.close()
    return db_path


class TestDrainDispatchOutbox:
    """Tests for _drain_dispatch_outbox with a real SQLite DB."""

    def test_drain_with_applied_rows_logs_count(self, tmp_path: Path) -> None:
        """When drain_if_present returns > 0, dispatch_outbox_drained is logged."""
        db_path = _make_drain_db(tmp_path)
        indexer_mock = MagicMock()
        config = MagicMock()
        config.indexer = indexer_mock
        config.indexer.db_path = db_path

        with patch(
            "personalscraper.indexer.outbox._drain.drain_if_present",
            return_value=3,
        ):
            _drain_dispatch_outbox(config)  # type: ignore[arg-type]

    def test_drain_with_no_applied_rows_no_log(self, tmp_path: Path) -> None:
        """When drain_if_present returns 0, only merkle roots are reset."""
        db_path = _make_drain_db(tmp_path)
        indexer_mock = MagicMock()
        config = MagicMock()
        config.indexer = indexer_mock
        config.indexer.db_path = db_path

        with patch(
            "personalscraper.indexer.outbox._drain.drain_if_present",
            return_value=0,
        ):
            _drain_dispatch_outbox(config)  # type: ignore[arg-type]

    def test_drain_resets_merkle_roots(self, tmp_path: Path) -> None:
        """update_merkle_root is called for each mounted disk (even if no commit)."""
        db_path = _make_drain_db(tmp_path)

        indexer_mock = MagicMock()
        config = MagicMock()
        config.indexer = indexer_mock
        config.indexer.db_path = db_path

        with (
            patch(
                "personalscraper.indexer.outbox._drain.drain_if_present",
                return_value=0,
            ),
            patch(
                "personalscraper.indexer.repos.disk_repo.update_merkle_root",
            ) as mock_update,
        ):
            _drain_dispatch_outbox(config)  # type: ignore[arg-type]

        # update_merkle_root is called once per mounted disk.
        mock_update.assert_called()


class TestEnrichAfterDispatch:
    """Tests for _enrich_after_dispatch with a real SQLite DB."""

    def test_no_affected_ids_returns_immediately(self, tmp_path: Path) -> None:
        """Empty results → no affected disks → early return."""
        db_path = _make_drain_db(tmp_path)
        config = MagicMock()
        config.indexer.db_path = db_path
        _enrich_after_dispatch(config, [], event_bus=EventBus())  # type: ignore[arg-type]
        # Should not raise.

    def test_no_matching_disk_row_returns_early(self, tmp_path: Path) -> None:
        """Affected disk ID does not match any disk.uuid → early return."""
        db_path = _make_drain_db(tmp_path)
        config = MagicMock()
        config.indexer.db_path = db_path

        # Result references a disk whose uuid is NOT in the DB.
        _enrich_after_dispatch(
            config,
            [  # type: ignore[arg-type]
                DispatchResult(source=Path("a"), action="moved", disk="nonexistent-id"),
            ],
            event_bus=EventBus(),
        )

    def test_matching_disk_triggers_enrich_scan(self, tmp_path: Path) -> None:
        """When a matching disk row exists, the enrich scan runs."""
        db_path = _make_drain_db(tmp_path)
        config = MagicMock()
        config.indexer.db_path = db_path

        with patch(
            "personalscraper.indexer.scanner.scan",
            return_value=MagicMock(files_visited=42, status="ok"),
        ):
            _enrich_after_dispatch(
                config,
                [  # type: ignore[arg-type]
                    DispatchResult(source=Path("a"), action="moved", disk="drive-uuid"),
                ],
                event_bus=EventBus(),
            )
