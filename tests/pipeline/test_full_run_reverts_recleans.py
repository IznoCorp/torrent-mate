"""F3 regression: a FULL ``Pipeline.run`` reverts unmatched reclean renames.

The CLI ``run_process`` path reverts a reclean rename whenever the scraper
subsequently fails to match the cleaned folder name (``process/run.py``). The
full-run path (``Pipeline.run`` iterating ``STEP_SPECS``) must have the SAME
behaviour: a folder that reclean renamed but scrape could not match is reverted
to its original torrent name so it stays rescrape-eligible.

This test drives the real ``Pipeline.run`` with fake ``clean``/``scrape`` steps
that reproduce the reclean-then-miss sequence on a real staging tree, and
asserts the folder is reverted. It fails before the shared-revert wiring lands
(the full run never reverts) and passes after.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline
from personalscraper.pipeline_protocol import StepContext
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# The polluted torrent name reclean would rename, and the clean name it produces.
_ORIGINAL_NAME = "Les.secrets.du.Prince.Andrew.2023.1080p.WEB.x264-GROUP"
_CLEAN_NAME = "Les secrets du Prince Andrew (2023)"

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


class _RecleanCleanStep:
    """Fake ``clean`` step: renames the polluted folder like reclean does.

    Performs the on-disk ``original → clean`` rename and reports the resulting
    ``new_name → old_name`` map in ``StepReport.renames`` — exactly what
    ``run_clean`` produces after ``reclean_folders``.
    """

    name = "clean"

    def __init__(self, movies_dir: Path) -> None:
        self._movies_dir = movies_dir

    def __call__(self, ctx: StepContext) -> StepReport:
        original = self._movies_dir / _ORIGINAL_NAME
        clean = self._movies_dir / _CLEAN_NAME
        if original.exists():
            original.rename(clean)
        return StepReport(name="clean", success_count=1, renames={_CLEAN_NAME: _ORIGINAL_NAME})


class _MissingScrapeStep:
    """Fake ``scrape`` step: the scraper could not match the clean folder."""

    name = "scrape"

    def __call__(self, ctx: StepContext) -> StepReport:
        return StepReport(name="scrape", unmatched_paths=[_CLEAN_NAME])


def _reclean_registry(movies_dir: Path) -> dict[str, object]:
    """Build a 9-step registry with the reclean-then-miss clean/scrape pair."""
    registry: dict[str, object] = {name: _NoOpStep(name) for name in _NINE_STEP_NAMES}
    registry["clean"] = _RecleanCleanStep(movies_dir)
    registry["scrape"] = _MissingScrapeStep()
    return registry


def _reclean_app(tmp_path: Path) -> tuple[AppContext, Path]:
    """Build an AppContext over a real staging tree with a polluted movie folder.

    Returns the app plus the movies staging dir (``001-MOVIES``).
    """
    config = MagicMock()
    config.disks = []
    config.staging_dirs = CANONICAL_STAGING_DIRS
    config.paths.staging_dir = tmp_path
    # A REAL empty dir for PauseController's ``pipeline.pause`` sentinel probe.
    config.paths.data_dir = Path(tempfile.mkdtemp())

    movies_dir = tmp_path / "001-MOVIES"
    movies_dir.mkdir(parents=True)
    (movies_dir / _ORIGINAL_NAME).mkdir()

    app = AppContext(
        config=config,
        settings=MagicMock(),
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )
    return app, movies_dir


class TestFullRunRevertsUnmatchedRecleans:
    """The full ``Pipeline.run`` reverts a reclean rename scrape could not match."""

    def test_full_run_reverts_unmatched_reclean_rename(self, tmp_path: Path) -> None:
        """A folder reclean renamed but scrape missed is reverted to its torrent name."""
        app, movies_dir = _reclean_app(tmp_path)
        pipeline = Pipeline(app)
        registry = _reclean_registry(movies_dir)

        with (
            patch("personalscraper.pipeline.ensure_staging_tree"),
            patch.object(Pipeline, "_check_temp_empty_gate"),
            patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
            patch("personalscraper.pipeline.apply_step_overrides", return_value=registry),
        ):
            pipeline.run(dry_run=False)

        # The reclean rename must be reverted: original torrent name back, clean
        # name gone — parity with the CLI ``run_process`` path.
        assert (movies_dir / _ORIGINAL_NAME).exists(), "unmatched reclean rename was NOT reverted by the full run"
        assert not (movies_dir / _CLEAN_NAME).exists(), "clean name still present — revert did not run"
