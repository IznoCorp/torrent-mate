"""Unit tests for post-dispatch index maintenance hook."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Pre-load cli so personalscraper.indexer.commands.scan is importable.
# scan.py has a circular import with cli.py; patching its module path
# requires the module to already be in sys.modules as an attribute of
# the commands package.
import personalscraper.indexer.cli  # noqa: F401  # needed for mock patch path
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.post_maintenance import (
    collect_touched_disks,
    run_post_dispatch_maintenance,
)
from personalscraper.models import StepReport

# The migrated ``dispatch`` command runs inside the ``cli_helpers.boundary``
# scaffold, which enters ``per_step_boundary`` + takes the lock from its OWN
# module namespace — patch that module, not ``personalscraper.commands.pipeline``
# / ``personalscraper.cli``.
_BOUNDARY_MOD = importlib.import_module("personalscraper.cli_helpers.boundary")


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config with a resolved indexer.db_path."""
    cfg = MagicMock()
    cfg.indexer.db_path = "/tmp/test_library.db"
    cfg.indexer.post_dispatch_maintenance.enabled = True
    return cfg


# ── collect_touched_disks ──


def test_collect_touched_disks_includes_moved_merged_replaced() -> None:
    """Results with action in (moved, merged, replaced) and non-None disk are included."""
    results = [
        DispatchResult(source=Path("/src/a"), disk="disk_1", action="moved"),
        DispatchResult(source=Path("/src/b"), disk="disk_2", action="merged"),
        DispatchResult(source=Path("/src/c"), disk="disk_1", action="replaced"),
    ]
    assert collect_touched_disks(results) == {"disk_1", "disk_2"}


def test_collect_touched_disks_excludes_skipped_error_none_disk() -> None:
    """Skipped items, errors, and None-disk results are excluded."""
    results = [
        DispatchResult(source=Path("/src/a"), disk=None, action="skipped"),
        DispatchResult(source=Path("/src/b"), disk=None, action="error"),
        DispatchResult(source=Path("/src/c"), disk="disk_1", action="moved"),
    ]
    assert collect_touched_disks(results) == {"disk_1"}


def test_collect_touched_disks_dedups() -> None:
    """Duplicate disk labels are deduplicated."""
    results = [
        DispatchResult(source=Path("/src/a"), disk="disk_1", action="moved"),
        DispatchResult(source=Path("/src/b"), disk="disk_1", action="merged"),
        DispatchResult(source=Path("/src/c"), disk="disk_2", action="moved"),
    ]
    assert collect_touched_disks(results) == {"disk_1", "disk_2"}


def test_collect_touched_disks_empty_results() -> None:
    """Empty results list returns empty set."""
    assert collect_touched_disks([]) == set()


# ── Core behaviour ──


def test_empty_touched_disks_no_op(mock_config: MagicMock) -> None:
    """Empty touched_disks set skips all steps — no scan nor relink nor fix."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental") as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink") as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts") as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, set(), enabled=True)
        mock_scan.assert_not_called()
        mock_relink.assert_not_called()
        mock_fix.assert_not_called()


def test_disabled_no_op(mock_config: MagicMock) -> None:
    """When enabled=False, the function is a no-op even with touched disks."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental") as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink") as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts") as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1", "disk_2"}, enabled=False)
        mock_scan.assert_not_called()
        mock_relink.assert_not_called()
        mock_fix.assert_not_called()


def test_sequential_per_disk_scan(mock_config: MagicMock) -> None:
    """Each touched disk gets an incremental scan call, sequentially."""
    touched = {"disk_1", "disk_2"}
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0) as mock_scan,
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        run_post_dispatch_maintenance(mock_config, touched, enabled=True)
        assert mock_scan.call_count == 2
        # Verify per-disk calls (sorted order)
        mock_scan.assert_any_call(mock_config, "disk_1")
        mock_scan.assert_any_call(mock_config, "disk_2")


def test_relink_and_fix_called_after_scans(mock_config: MagicMock) -> None:
    """Relink and fix-season-counts are each called exactly once after all scans."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0) as mock_scan,
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 3, "unmatched": 0, "errors": 0},
        ) as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=5) as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)
        mock_scan.assert_called_once()
        mock_relink.assert_called_once()
        mock_fix.assert_called_once()


# ── Fail-soft ──


def test_fail_soft_scan_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in a scan step is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", side_effect=RuntimeError("boom")),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        # Must not raise
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)


def test_fail_soft_relink_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in relink is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_relink", side_effect=RuntimeError("boom")),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)


def test_fail_soft_fix_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in fix-season-counts is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", side_effect=RuntimeError("boom")),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)


# ── Fail-soft surfacing (DESIGN Decision #2) ──


def test_relink_exception_surfaces_post_maintenance_incomplete(
    mock_config: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """A total _run_relink exception causes post_maintenance_incomplete warning."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_relink", side_effect=RuntimeError("relink boom")),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when relink throws"
    )


def test_fix_exception_surfaces_post_maintenance_incomplete(
    mock_config: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """A total _run_fix_season_counts exception causes post_maintenance_incomplete warning."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", side_effect=RuntimeError("fix boom")),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when fix_season_counts throws"
    )


def test_scan_failure_surfaces_post_maintenance_incomplete(
    mock_config: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-zero scan exit code causes post_maintenance_incomplete warning."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=1),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when a scan fails"
    )
    # The manual_fallback should include library-index --mode full when scans failed
    assert any("library-index --mode full" in r.message for r in caplog.records), (
        "manual_fallback should include library-index --mode full when scan_failures is non-empty"
    )


def test_no_scan_failure_fallback_omits_full_scan(mock_config: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    """When only relink errors exist (no scan failures), fallback omits library-index."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 1},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when relink has errors"
    )
    # Should NOT include full scan since there are no scan failures
    assert not any("library-index --mode full" in r.message for r in caplog.records), (
        "manual_fallback should NOT include library-index --mode full when scan_failures is empty"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Subtree invalidation (S3 — the merge-into-existing-folder blindness)
# ═══════════════════════════════════════════════════════════════════════════


def _invalidation_db(tmp_path):
    """Build a minimal library.db with a disk row + path rows for one show."""
    import sqlite3 as _sqlite3
    from pathlib import Path as _Path

    from personalscraper.indexer import migrations as _migrations_pkg
    from personalscraper.indexer.db import apply_migrations as _apply

    db_path = tmp_path / "library.db"
    conn = _sqlite3.connect(str(db_path))
    _apply(conn, _Path(_migrations_pkg.__file__).parent)
    conn.execute(
        "INSERT INTO disk (id, uuid, label, mount_path, merkle_root, is_mounted) "
        "VALUES (3, 'uuid-3', 'disk_3', '/Volumes/Disk3', 'abcd1234', 1)"
    )
    rows = [
        ("medias", 111, 999),
        ("medias/series", 222, 999),
        ("medias/series/House of the Dragon (2022)", 333, 999),
        ("medias/series/House of the Dragon (2022)/Saison 03", 444, 999),
        ("medias/series/Autre Show (2020)", 555, 999),
    ]
    conn.executemany(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (3, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db_path


def test_invalidate_dispatched_subtrees_resets_dest_and_ancestors(tmp_path, test_config) -> None:
    """The dispatched dest subtree AND its ancestors lose their walk short-circuits.

    Red-on-old: merging episodes into an existing 'Saison 03' does not bump
    parent mtimes on NTFS/macFUSE, so the post-dispatch incremental scan
    skipped exactly the branch dispatch had just written (prod: AD S22E10/E11
    invisible 11 days, HotD S03E04 missed in-run). After invalidation the
    walker must re-stat the whole branch.
    """
    import sqlite3 as _sqlite3
    from pathlib import Path as _Path

    from personalscraper.dispatch.post_maintenance import _invalidate_dispatched_subtrees

    db_path = _invalidation_db(tmp_path)
    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": db_path})})

    count = _invalidate_dispatched_subtrees(
        cfg,
        {"disk_3": {_Path("/Volumes/Disk3/medias/series/House of the Dragon (2022)")}},
    )
    assert count >= 4  # dest + Saison 03 + series + medias

    conn = _sqlite3.connect(str(db_path))
    reset = dict(conn.execute("SELECT rel_path, dir_mtime_ns IS NULL FROM path WHERE disk_id = 3").fetchall())
    # The dispatched branch + every ancestor is reset…
    assert reset["medias/series/House of the Dragon (2022)"] == 1
    assert reset["medias/series/House of the Dragon (2022)/Saison 03"] == 1
    assert reset["medias/series"] == 1
    assert reset["medias"] == 1
    # …an unrelated sibling keeps its short-circuit (surgical, not a full rewalk).
    assert reset["medias/series/Autre Show (2020)"] == 0
    # The disk-level merkle short-circuit is cleared too.
    assert conn.execute("SELECT merkle_root FROM disk WHERE id = 3").fetchone()[0] is None
    conn.close()


def test_collect_touched_destinations_filters_actions(tmp_path) -> None:
    """Only moved/merged/replaced results with a disk AND a destination count."""
    from pathlib import Path as _Path
    from types import SimpleNamespace

    from personalscraper.dispatch.post_maintenance import collect_touched_destinations

    results = [
        SimpleNamespace(disk="disk_1", destination=_Path("/Volumes/Disk1/medias/A"), action="moved"),
        SimpleNamespace(disk="disk_1", destination=_Path("/Volumes/Disk1/medias/B"), action="merged"),
        SimpleNamespace(disk="disk_2", destination=_Path("/Volumes/Disk2/medias/C"), action="replaced"),
        SimpleNamespace(disk="disk_2", destination=_Path("/Volumes/Disk2/medias/D"), action="skipped"),
        SimpleNamespace(disk=None, destination=_Path("/x"), action="moved"),
        SimpleNamespace(disk="disk_3", destination=None, action="moved"),
    ]
    touched = collect_touched_destinations(results)
    assert touched == {
        "disk_1": {_Path("/Volumes/Disk1/medias/A"), _Path("/Volumes/Disk1/medias/B")},
        "disk_2": {_Path("/Volumes/Disk2/medias/C")},
    }


def test_invalidation_handles_nfd_stored_paths(tmp_path, test_config) -> None:
    """NFD-stored rel_paths (macFUSE) are still invalidated by an NFC destination."""
    import sqlite3 as _sqlite3
    import unicodedata
    from pathlib import Path as _Path

    from personalscraper.dispatch.post_maintenance import _invalidate_dispatched_subtrees
    from personalscraper.indexer import migrations as _migrations_pkg
    from personalscraper.indexer.db import apply_migrations as _apply

    db_path = tmp_path / "library.db"
    conn = _sqlite3.connect(str(db_path))
    _apply(conn, _Path(_migrations_pkg.__file__).parent)
    conn.execute(
        "INSERT INTO disk (id, uuid, label, mount_path, merkle_root, is_mounted) "
        "VALUES (1, 'uuid-1', 'disk_1', '/Volumes/Disk1', 'ff', 1)"
    )
    nfd_rel = unicodedata.normalize("NFD", "medias/series/Éclairé (2020)")
    conn.execute(
        "INSERT INTO path (disk_id, rel_path, dir_mtime_ns, last_walked_at) VALUES (1, ?, 1, 1)",
        (nfd_rel,),
    )
    conn.commit()
    conn.close()

    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": db_path})})
    nfc_dest = _Path(unicodedata.normalize("NFC", "/Volumes/Disk1/medias/series/Éclairé (2020)"))
    count = _invalidate_dispatched_subtrees(cfg, {"disk_1": {nfc_dest}})
    assert count >= 1

    conn = _sqlite3.connect(str(db_path))
    assert conn.execute("SELECT dir_mtime_ns IS NULL FROM path WHERE rel_path = ?", (nfd_rel,)).fetchone()[0] == 1
    conn.close()


def test_run_repair_drain_processes_pending_rows(tmp_path, test_config) -> None:
    """Post-dispatch drains the repair queue (it had NO automatic drainer).

    Red-on-old: repairs enqueued by the scanner (content_drift re-hashes)
    accumulated forever because only the manual ``library-repair`` CLI drained
    them and no cron ran it (prod: 25 rows pending for 6+ days).
    """
    import sqlite3 as _sqlite3
    from pathlib import Path as _Path

    from personalscraper.dispatch.post_maintenance import _run_repair_drain
    from personalscraper.indexer import migrations as _migrations_pkg
    from personalscraper.indexer.db import apply_migrations as _apply

    db_path = tmp_path / "library.db"
    conn = _sqlite3.connect(str(db_path))
    _apply(conn, _Path(_migrations_pkg.__file__).parent)
    # An unknown (scope, reason) row: the default processor no-ops it but the
    # drain must still mark it done (graceful-degradation contract).
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at, status) "
        "VALUES ('item', 1, 'test_reason', 1750000000, 'pending')"
    )
    conn.commit()
    conn.close()

    cfg = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": db_path})})
    processed = _run_repair_drain(cfg, budget_seconds=10.0)
    assert processed == 1

    conn = _sqlite3.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM repair_queue WHERE status = 'pending'").fetchone()[0] == 0
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# Single-owner trigger/guard (maybe_run_post_dispatch_maintenance) — P1.8
# ═══════════════════════════════════════════════════════════════════════════
#
# PIPELINE-CORE-01: the enablement resolution + touched-disk collection +
# dry-run guard around ``run_post_dispatch_maintenance`` used to be duplicated
# (and had drifted) between the full-run ``DispatchStep`` and the standalone
# ``personalscraper dispatch`` CLI command. Both now route through the single
# owner ``maybe_run_post_dispatch_maintenance``; these tests pin its guard
# algebra and prove BOTH paths funnel through it with identical call shapes.


def _moved_result(disk: str = "disk_1") -> DispatchResult:
    """One dispatched result that counts as a touched disk (action=moved)."""
    return DispatchResult(source=Path("/src/a"), disk=disk, action="moved")


def test_maybe_run_triggers_when_touched_and_not_dry_run(mock_config: MagicMock) -> None:
    """Touched disks + not dry_run + enabled ⇒ one call with enabled=True."""
    from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

    with patch("personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance") as mock_run:
        maybe_run_post_dispatch_maintenance(mock_config, [_moved_result()], dry_run=False)

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] is mock_config
    assert args[1] == {"disk_1"}
    assert kwargs["enabled"] is True


def test_maybe_run_dry_run_skips(mock_config: MagicMock) -> None:
    """dry_run ⇒ maintenance is never triggered even with touched disks."""
    from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

    with patch("personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance") as mock_run:
        maybe_run_post_dispatch_maintenance(mock_config, [_moved_result()], dry_run=True)

    mock_run.assert_not_called()


def test_maybe_run_no_touched_disks_skips(mock_config: MagicMock) -> None:
    """No touched disks (only skipped/None results) ⇒ never triggered."""
    from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

    skipped = [DispatchResult(source=Path("/src/a"), disk=None, action="skipped")]
    with patch("personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance") as mock_run:
        maybe_run_post_dispatch_maintenance(mock_config, skipped, dry_run=False)

    mock_run.assert_not_called()


def test_maybe_run_no_post_maintenance_flag_calls_with_enabled_false(mock_config: MagicMock) -> None:
    """The opt-out flag still CALLS maintenance (touched, not dry_run) with enabled=False.

    Preserves the standalone dispatch command's historical call shape asserted by
    ``test_dispatch_e2e.test_no_post_maintenance_flag_disables``: a disabled run is
    a logged no-op inside ``run_post_dispatch_maintenance``, not an omitted call.
    """
    from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

    with patch("personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance") as mock_run:
        maybe_run_post_dispatch_maintenance(mock_config, [_moved_result()], dry_run=False, no_post_maintenance=True)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["enabled"] is False


def test_maybe_run_config_disabled_calls_with_enabled_false(mock_config: MagicMock) -> None:
    """config-level disable ⇒ one call with enabled=False (touched, not dry_run)."""
    from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

    mock_config.indexer.post_dispatch_maintenance.enabled = False
    with patch("personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance") as mock_run:
        maybe_run_post_dispatch_maintenance(mock_config, [_moved_result()], dry_run=False)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["enabled"] is False


def test_maybe_run_forwards_touched_destinations(mock_config: MagicMock) -> None:
    """The per-disk destinations mapping is collected and forwarded through."""
    result = DispatchResult(
        source=Path("/src/a"),
        disk="disk_1",
        destination=Path("/Volumes/Disk1/medias/A"),
        action="moved",
    )
    from personalscraper.dispatch.post_maintenance import maybe_run_post_dispatch_maintenance

    with patch("personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance") as mock_run:
        maybe_run_post_dispatch_maintenance(mock_config, [result], dry_run=False)

    assert mock_run.call_args.kwargs["destinations"] == {"disk_1": {Path("/Volumes/Disk1/medias/A")}}


def test_both_paths_route_through_single_owner_identically(test_config) -> None:  # noqa: ANN001
    """Both entry points funnel through the single owner with an identical call shape.

    DispatchStep and the CLI ``dispatch`` command each invoke
    ``maybe_run_post_dispatch_maintenance`` with ``(config, results)`` positional +
    ``dry_run``/``no_post_maintenance`` keyword. Capture-fake parity: whatever shape
    one path uses, the other uses the same — so the trigger logic can never again
    diverge between the two entry points (PIPELINE-CORE-01).
    """
    from contextlib import contextmanager
    from pathlib import Path as _Path
    from types import SimpleNamespace
    from uuid import uuid4

    from typer.testing import CliRunner

    from personalscraper.cli import app as cli_app
    from personalscraper.core.event_bus import EventBus
    from personalscraper.pipeline_protocol import StepContext
    from personalscraper.pipeline_steps import DispatchStep
    from tests.fixtures.settings_stub import make_typed_settings_stub

    # ── Path A: full-run DispatchStep ──
    step_results = [_moved_result("disk_1")]
    captured_step: dict[str, object] = {}

    def _capture_step(config: object, results: object, *, dry_run: bool, no_post_maintenance: bool) -> None:
        captured_step.update(config=config, results=results, dry_run=dry_run, no_post_maintenance=no_post_maintenance)

    app = SimpleNamespace(
        settings=MagicMock(name="settings"),
        config=MagicMock(name="step_config"),
        event_bus=MagicMock(name="event_bus"),
        acquire=None,
    )
    ctx = StepContext(
        app=app,  # type: ignore[arg-type]
        run_id=uuid4(),
        dry_run=False,
        interactive=False,
        verbose=False,
        upstream={},
        extras={},
    )
    with (
        patch("personalscraper.dispatch.run.run_dispatch", return_value=(StepReport(name="dispatch"), step_results)),
        patch(
            "personalscraper.dispatch.post_maintenance.maybe_run_post_dispatch_maintenance",
            side_effect=_capture_step,
        ),
    ):
        DispatchStep()(ctx)

    assert captured_step["results"] is step_results
    assert captured_step["config"] is app.config
    assert captured_step["dry_run"] is False
    assert captured_step["no_post_maintenance"] is False

    # ── Path B: standalone dispatch CLI command ──
    cli_results = [_moved_result("disk_1")]
    captured_cli: dict[str, object] = {}

    def _capture_cli(config: object, results: object, *, dry_run: bool, no_post_maintenance: bool) -> None:
        captured_cli.update(config=config, results=results, dry_run=dry_run, no_post_maintenance=no_post_maintenance)

    @contextmanager
    def _boundary(*_a: object, **_k: object):  # noqa: ANN202
        yield SimpleNamespace(event_bus=EventBus(), acquire=None)

    with (
        # The Typer callback eagerly loads config; patch the loader so the CLI
        # runs without a real config.json5 on disk (tests/dispatch/ is outside
        # the commands-conftest autouse patch).
        patch("personalscraper.conf.loader.resolve_config_path", return_value=_Path("/fake/config.json5")),
        patch("personalscraper.conf.loader.load_config", return_value=test_config),
        patch.object(_BOUNDARY_MOD, "per_step_boundary", _boundary),
        patch("personalscraper.dispatch.run.run_dispatch", return_value=(StepReport(name="dispatch"), cli_results)),
        patch(
            "personalscraper.dispatch.post_maintenance.maybe_run_post_dispatch_maintenance",
            side_effect=_capture_cli,
        ),
        patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True),
        patch.object(_BOUNDARY_MOD, "release_lock"),
        patch.object(_BOUNDARY_MOD, "get_settings", return_value=make_typed_settings_stub()),
    ):
        result = CliRunner().invoke(cli_app, ["dispatch"])
    assert result.exit_code == 0, result.output

    assert captured_cli["results"] is cli_results
    assert captured_cli["dry_run"] is False
    assert captured_cli["no_post_maintenance"] is False

    # ── Identical call shape between the two paths ──
    assert set(captured_step) == set(captured_cli) == {"config", "results", "dry_run", "no_post_maintenance"}
    assert captured_step["dry_run"] == captured_cli["dry_run"]
    assert captured_step["no_post_maintenance"] == captured_cli["no_post_maintenance"]
