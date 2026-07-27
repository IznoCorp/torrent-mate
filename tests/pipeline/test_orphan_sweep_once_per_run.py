"""P2.4 regression: the crash-recovery orphan sweep runs ONCE per pipeline run.

Before consolidation the sweep ran twice in a full run (boot's
``_recover_from_previous_run`` AND the dispatch/ingest steps' own cleanups). The
single-owner sweep must run at exactly one defined point per run — pipeline boot
— with the ingest and dispatch steps passing ``recover_orphans=False``.

Safe: ``tmp_path`` only, no network. ``crash_recovery.sweep_orphans`` is patched
with a call counter, so boot never touches the real filesystem.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline
from personalscraper.pipeline_protocol import StepContext
from personalscraper.pipeline_steps import DispatchStep, IngestStep
from tests.fixtures.config import CANONICAL_STAGING_DIRS

_NINE_STEP_NAMES = (
    "ingest",
    "sort",
    "clean",
    "scrape",
    "cleanup",
    "enforce",
    "verify",
    "trailers",
    "dispatch",
)


class _NoOpStep:
    """PipelineStep stub returning a clean :class:`StepReport`."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self, ctx: StepContext) -> StepReport | tuple[StepReport, list[Path]]:
        if self.name == "verify":
            # No verified items → dispatch is skipped by its ``skip_when``.
            return StepReport(name=self.name, success_count=0), []
        return StepReport(name=self.name, success_count=0)


def _noop_app(tmp_path: Path) -> AppContext:
    """Build an AppContext over a MagicMock config with a real staging root."""
    config = MagicMock()
    config.disks = []
    config.staging_dirs = CANONICAL_STAGING_DIRS
    config.paths.staging_dir = tmp_path
    config.paths.data_dir = Path(tempfile.mkdtemp())
    return AppContext(
        config=config,
        settings=MagicMock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )


def _step_ctx() -> StepContext:
    """Build a minimal StepContext for driving a single step adapter."""
    return StepContext(
        app=MagicMock(),
        run_id=uuid4(),
        dry_run=False,
        interactive=False,
        verbose=False,
        upstream={},
        extras={},
    )


class TestSweepOncePerRun:
    """The single-owner sweep fires exactly once in a full pipeline run."""

    def test_full_run_sweeps_orphans_exactly_once(self, tmp_path: Path, monkeypatch) -> None:
        """A full ``Pipeline.run`` invokes ``sweep_orphans`` once — at boot."""
        calls: list[object] = []

        def _counting_sweep(roots, *, dry_run, **_kw):
            calls.append(roots)
            return 0

        # Boot imports sweep_orphans lazily from crash_recovery at call time.
        monkeypatch.setattr(
            "personalscraper.dispatch.crash_recovery.sweep_orphans",
            _counting_sweep,
        )

        pipeline = Pipeline(_noop_app(tmp_path))
        registry = {name: _NoOpStep(name) for name in _NINE_STEP_NAMES}

        with (
            patch("personalscraper.pipeline.ensure_staging_tree"),
            patch.object(Pipeline, "_check_temp_empty_gate"),
            patch("personalscraper.pipeline.apply_step_overrides", return_value=registry),
        ):
            pipeline.run(dry_run=False)

        # Exactly one sweep per run — no double-execution.
        assert len(calls) == 1


class TestStepsDeferToBoot:
    """The ingest and dispatch steps pass ``recover_orphans=False`` in a run."""

    def test_dispatch_step_defers_orphan_recovery(self) -> None:
        """DispatchStep calls run_dispatch with recover_orphans=False."""
        captured: dict[str, object] = {}

        def _spy_run_dispatch(*_a, **kw):
            captured.update(kw)
            return StepReport(name="dispatch"), []

        with (
            patch("personalscraper.dispatch.run.run_dispatch", _spy_run_dispatch),
            patch("personalscraper.pipeline_steps.resolve_dispatch_authority", return_value={}),
            patch("personalscraper.dispatch.post_maintenance.maybe_run_post_dispatch_maintenance"),
        ):
            DispatchStep()(_step_ctx())

        assert captured.get("recover_orphans") is False

    def test_ingest_step_defers_orphan_recovery(self) -> None:
        """IngestStep calls run_ingest with recover_orphans=False."""
        captured: dict[str, object] = {}

        def _spy_run_ingest(*_a, **kw):
            captured.update(kw)
            return StepReport(name="ingest")

        with patch("personalscraper.ingest.ingest.run_ingest", _spy_run_ingest):
            IngestStep()(_step_ctx())

        assert captured.get("recover_orphans") is False


class TestRecoverFlagGatesSweep:
    """``recover_orphans=False`` short-circuits before any sweep is issued."""

    def test_dispatch_adapter_no_sweep_when_flag_false(self, tmp_path: Path, monkeypatch) -> None:
        """_sweep_dispatch_orphans(recover_orphans=False) never calls sweep_orphans."""
        from personalscraper.dispatch import run as run_mod

        calls: list[object] = []
        monkeypatch.setattr(run_mod, "sweep_orphans", lambda *a, **k: calls.append(a) or 0)

        result = run_mod._sweep_dispatch_orphans(MagicMock(disks=[]), tmp_path, dry_run=False, recover_orphans=False)

        assert result == 0
        assert calls == []

    def test_ingest_adapter_no_sweep_when_flag_false(self, tmp_path: Path) -> None:
        """_sweep_ingest_orphans(recover_orphans=False) is a pure no-op."""
        from personalscraper.ingest.ingest import _sweep_ingest_orphans

        orphan = tmp_path / ".ingest_tmp_X"
        orphan.mkdir()

        result = _sweep_ingest_orphans(tmp_path, dry_run=False, recover_orphans=False)

        assert result == 0
        assert orphan.exists()
