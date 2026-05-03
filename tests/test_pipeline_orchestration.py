"""Orchestration unit tests for the Pipeline class.

Verifies step ordering, early-abort behaviour, and StepReport aggregation
using the ``step_overrides`` seam instead of module-level ``@patch``.

Tests that exercise the full pipeline with real filesystem operations or
external-API fakes belong in ``tests/integration/test_full_pipeline.py``.
"""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def orch_settings(tmp_path):
    """Minimal Settings mock for orchestration tests.

    ``ingest_dir`` is a callable (mirrors V15 signature); ``staging_dir``
    is set to ``tmp_path`` so staging-tree helpers resolve correctly.

    Args:
        tmp_path: Pytest-provided unique temporary directory.

    Returns:
        MagicMock configured as a minimal Settings substitute.
    """
    s = MagicMock()
    s.staging_dir = tmp_path
    (tmp_path / "097-TEMP").mkdir()
    s.ingest_dir.side_effect = lambda staging_dir: staging_dir / "097-TEMP"
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    (tmp_path / "001-MOVIES").mkdir()
    (tmp_path / "002-TVSHOWS").mkdir()
    return s


@pytest.fixture
def orch_config(tmp_path):
    """Minimal Config mock for orchestration tests.

    ``staging_dirs`` is populated with real ``StagingDirConfig`` entries so
    that ``find_by_file_type()`` and ``folder_name()`` resolve correctly
    without a ``config.json5`` on disk.

    ``trailers.enabled`` is set to ``False`` as a defence against
    MagicMock-string filesystem leaks (finding 10.5/C1): without this guard
    ``run_trailers`` would instantiate a real ``TrailersOrchestrator``,
    which calls ``state_file.with_suffix(".lock")`` on the MagicMock repr
    string and creates a literal ``<MagicMock …>.lock`` file in cwd.
    Tests that explicitly exercise trailers behaviour use ``step_overrides``
    or a module-level ``@patch("personalscraper.trailers.step.run_trailers")``.

    Args:
        tmp_path: Pytest-provided unique temporary directory.

    Returns:
        MagicMock configured as a minimal Config substitute.
    """
    from personalscraper.conf.models.staging import StagingDirConfig

    config = MagicMock()
    config.paths.staging_dir = tmp_path
    config.paths.data_dir = tmp_path / ".data"
    config.disks = []
    config.staging_dirs = [
        StagingDirConfig(id=1, name="movies", file_type="movie"),
        StagingDirConfig(id=2, name="tvshows", file_type="tvshow"),
        StagingDirConfig(id=97, name="temp", role="ingest"),
    ]
    # Defence against MagicMock-string filesystem leaks (finding 10.5/C1).
    config.trailers.enabled = False
    return config


@pytest.fixture
def quiet_console():
    """Console that suppresses all output.

    Returns:
        Rich Console in quiet mode.
    """
    return Console(quiet=True)


def _noop_step(name: str, *_args, **_kwargs) -> StepReport:
    """Return a no-op StepReport for the given step name.

    Args:
        name: Step name used as the StepReport identifier.
        **_kwargs: Ignored kwargs (absorbs whatever the pipeline passes).

    Returns:
        StepReport with zero counts.
    """
    return StepReport(name=name)


def _verify_noop(*_args, **_kwargs):
    """Verify stub returning an empty dispatchable list.

    Args:
        **_kwargs: Ignored kwargs.

    Returns:
        Tuple of (StepReport, empty list).
    """
    return StepReport(name="verify"), []


def _verify_with_items(*_args, **_kwargs):
    """Verify stub returning one dispatchable item.

    Args:
        **_kwargs: Ignored kwargs.

    Returns:
        Tuple of (StepReport, list with one MagicMock item).
    """
    return StepReport(name="verify", success_count=1), [MagicMock()]


# ---------------------------------------------------------------------------
# Orchestration invariants
# ---------------------------------------------------------------------------


class TestPipelineOrchestration:
    """Unit tests for Pipeline orchestration using step_overrides injection."""

    def test_step_order(self, orch_config, orch_settings, quiet_console):
        """Steps execute in canonical order: ingest→sort→clean→scrape→cleanup→enforce→verify→trailers→dispatch.

        Uses step_overrides to record call order without patching module globals.
        """
        order: list[str] = []

        def recorder(name):
            """Build a step-override that appends ``name`` to ``order``.

            Args:
                name: Step label to append on invocation.

            Returns:
                Callable returning a no-op StepReport.
            """

            def fn(*_a, **_kw):
                order.append(name)
                return StepReport(name=name)

            return fn

        def verify_recorder(*_a, **_kw):
            order.append("verify")
            return StepReport(name="verify", success_count=1), [MagicMock()]

        def dispatch_recorder(*_a, **_kw):
            order.append("dispatch")
            return StepReport(name="dispatch")

        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            step_overrides={
                "ingest": recorder("ingest"),
                "sort": recorder("sort"),
                "clean": recorder("clean"),
                "scrape": recorder("scrape"),
                "cleanup": recorder("cleanup"),
                "enforce": recorder("enforce"),
                "verify": verify_recorder,
                "trailers": recorder("trailers"),
                "dispatch": dispatch_recorder,
            },
        )
        pipeline.run()

        assert order == ["ingest", "sort", "clean", "scrape", "cleanup", "enforce", "verify", "trailers", "dispatch"]

    def test_ingest_crash_aborts_pipeline(self, orch_config, orch_settings, quiet_console):
        """A fatal ingest crash causes the pipeline to return early.

        Sort and downstream steps must not execute.
        """
        executed: list[str] = []

        def crashing_ingest(*_a, **_kw) -> StepReport:
            raise RuntimeError("disk full")

        def sort_sentinel(*_a, **_kw) -> StepReport:
            executed.append("sort")
            return StepReport(name="sort")

        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            step_overrides={
                "ingest": crashing_ingest,
                "sort": sort_sentinel,
            },
        )
        report = pipeline.run()

        # Pipeline returned early — only ingest step present, with error
        assert "ingest" in report.steps
        assert report.steps["ingest"].error_count == 1
        assert "sort" not in report.steps
        assert executed == []

    def test_sort_crash_aborts_pipeline(self, orch_config, orch_settings, quiet_console):
        """A fatal sort crash causes the pipeline to return after sort.

        Clean and downstream steps must not execute.
        """
        executed: list[str] = []

        def crashing_sort(*_a, **_kw) -> StepReport:
            raise RuntimeError("sort exploded")

        def clean_sentinel(*_a, **_kw) -> StepReport:
            executed.append("clean")
            return StepReport(name="clean")

        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            step_overrides={
                "ingest": lambda *_a, **_kw: StepReport(name="ingest"),
                "sort": crashing_sort,
                "clean": clean_sentinel,
            },
        )
        report = pipeline.run()

        assert "sort" in report.steps
        assert report.steps["sort"].error_count == 1
        assert "clean" not in report.steps
        assert executed == []

    def test_reporter_aggregation(self, orch_config, orch_settings, quiet_console):
        """All 9 StepReports from overrides roll up into the PipelineReport."""
        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            step_overrides={
                "ingest": lambda *_a, **_kw: StepReport(name="ingest", success_count=3),
                "sort": lambda *_a, **_kw: StepReport(name="sort", success_count=3),
                "clean": lambda *_a, **_kw: StepReport(name="clean", success_count=2),
                "scrape": lambda *_a, **_kw: StepReport(name="scrape", success_count=2),
                "cleanup": lambda *_a, **_kw: StepReport(name="cleanup", success_count=1),
                "enforce": lambda *_a, **_kw: StepReport(name="enforce", success_count=1),
                "verify": _verify_with_items,
                "trailers": lambda *_a, **_kw: StepReport(name="trailers", status="skipped"),
                "dispatch": lambda *_a, **_kw: StepReport(name="dispatch", success_count=3),
            },
        )
        report = pipeline.run()

        assert list(report.steps.keys()) == [
            "ingest",
            "sort",
            "clean",
            "scrape",
            "cleanup",
            "enforce",
            "verify",
            "trailers",
            "dispatch",
        ]
        assert report.steps["ingest"].success_count == 3
        assert report.steps["scrape"].success_count == 2

    def test_dispatch_skipped_no_verified(self, orch_config, orch_settings, quiet_console):
        """Dispatch step is skipped (skip_count=1) when verify returns no items."""
        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            step_overrides={
                "ingest": lambda *_a, **_kw: StepReport(name="ingest"),
                "sort": lambda *_a, **_kw: StepReport(name="sort"),
                "clean": lambda *_a, **_kw: StepReport(name="clean"),
                "scrape": lambda *_a, **_kw: StepReport(name="scrape"),
                "cleanup": lambda *_a, **_kw: StepReport(name="cleanup"),
                "enforce": lambda *_a, **_kw: StepReport(name="enforce"),
                "verify": _verify_noop,
            },
        )
        report = pipeline.run()

        assert "dispatch" in report.steps
        assert report.steps["dispatch"].skip_count == 1

    def test_clean_crash_does_not_block_scrape(self, orch_config, orch_settings, quiet_console):
        """A clean crash is isolated: scrape and cleanup still execute."""

        def crashing_clean(*_a, **_kw) -> StepReport:
            raise RuntimeError("reclean boom")

        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            step_overrides={
                "ingest": lambda *_a, **_kw: StepReport(name="ingest"),
                "sort": lambda *_a, **_kw: StepReport(name="sort"),
                "clean": crashing_clean,
                "scrape": lambda *_a, **_kw: StepReport(name="scrape", success_count=3),
                "cleanup": lambda *_a, **_kw: StepReport(name="cleanup"),
                "enforce": lambda *_a, **_kw: StepReport(name="enforce"),
                "verify": _verify_noop,
            },
        )
        report = pipeline.run()

        # Clean recorded the fatal error
        assert report.steps["clean"].error_count == 1
        assert "reclean boom" in report.steps["clean"].details[0]
        # Scrape ran after the clean crash
        assert report.steps["scrape"].success_count == 3
        assert "cleanup" in report.steps

    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_interactive_propagates_to_scrape(
        self,
        mock_gate,
        mock_ingest,
        mock_sort,
        mock_scrape,
        orch_config,
        orch_settings,
        quiet_console,
    ):
        """``--interactive`` flag is forwarded to run_scrape as a kwarg.

        Uses narrow @patch only to assert on the exact kwarg value passed
        to the production scrape function — injection cannot verify call
        signatures.
        """
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")

        with patch("personalscraper.verify.run.run_verify") as mock_verify:
            mock_verify.return_value = (StepReport(name="verify"), [MagicMock()])
            with patch("personalscraper.dispatch.run.run_dispatch") as mock_dispatch:
                mock_dispatch.return_value = StepReport(name="dispatch")
                pipeline = Pipeline(
                    orch_config,
                    orch_settings,
                    interactive=True,
                    console=quiet_console,
                )
                pipeline.run()

        assert mock_scrape.call_args.kwargs["interactive"] is True

    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_reclean_runs_on_polluted_folder(
        self,
        mock_gate,
        mock_ingest,
        mock_sort,
        mock_scrape,
        orch_config,
        orch_settings,
        quiet_console,
    ):
        """A polluted folder in 001-MOVIES is re-cleaned during the process phase.

        Uses narrow @patch for the steps that are not under test (ingest, sort,
        scrape). The ``clean`` step runs the real ``run_clean`` so that the
        filesystem rename actually happens.
        """
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")

        # Create a polluted folder in movies dir — run_clean should rename it.
        movies = orch_settings.staging_dir / "001-MOVIES"
        polluted = movies / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "movie.mkv").write_text("video")

        with (
            patch("personalscraper.verify.run.run_verify") as mock_verify,
            patch("personalscraper.trailers.step.run_trailers") as mock_trailers,
        ):
            mock_verify.return_value = (StepReport(name="verify"), [])
            # Stub out the real trailers step — this test exercises the clean step
            # only; the real trailers step requires a full config (TMDB key, state
            # file path, etc.) that is not available in this integration fixture.
            mock_trailers.return_value = StepReport(name="trailers", status="skipped")
            pipeline = Pipeline(orch_config, orch_settings, console=quiet_console)
            report = pipeline.run()

        # The clean step should have re-cleaned the polluted folder
        assert report.steps["clean"].success_count >= 1
        assert not polluted.exists()
        # Folder should be renamed to clean format
        assert (movies / "Movie Title (2024)").exists()


# ---------------------------------------------------------------------------
# Trailer error flag wiring (C2)
# ---------------------------------------------------------------------------


class TestTrailerErrorFlagWiring:
    """Tests for --continue-on-trailer-error flag behavior (C2)."""

    def test_pipeline_aborts_when_trailers_error_and_continue_on_error_false(
        self, orch_config, orch_settings, quiet_console
    ):
        """Pipeline raises TrailerStepFailed when trailers step fails and flag is False.

        When the trailers step returns status='error' and
        ``continue_on_trailer_error=False`` (the default), the pipeline must
        raise ``TrailerStepFailed`` before executing dispatch.  This gives the
        CLI a hook to exit with code 2.

        Args:
            orch_config: Minimal Config mock.
            orch_settings: Minimal Settings mock.
            quiet_console: Rich Console in quiet mode.
        """
        from personalscraper.trailers.state import TrailerStepFailed

        dispatch_executed: list[bool] = []

        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            continue_on_trailer_error=False,
            step_overrides={
                "ingest": lambda *_a, **_kw: StepReport(name="ingest"),
                "sort": lambda *_a, **_kw: StepReport(name="sort"),
                "clean": lambda *_a, **_kw: StepReport(name="clean"),
                "scrape": lambda *_a, **_kw: StepReport(name="scrape"),
                "cleanup": lambda *_a, **_kw: StepReport(name="cleanup"),
                "enforce": lambda *_a, **_kw: StepReport(name="enforce"),
                "verify": _verify_with_items,
                # Trailers step returns error status
                "trailers": lambda *_a, **_kw: StepReport(name="trailers", status="error", error_count=1),
                "dispatch": lambda *_a, **_kw: (dispatch_executed.append(True), StepReport(name="dispatch"))[1],
            },
        )

        with pytest.raises(TrailerStepFailed):
            pipeline.run()

        # Dispatch must NOT have been called
        assert dispatch_executed == []

    def test_pipeline_continues_when_continue_on_trailer_error_true(self, orch_config, orch_settings, quiet_console):
        """Pipeline proceeds to dispatch when continue_on_trailer_error=True.

        With the flag set, a trailers step error is logged but the pipeline
        continues and dispatch executes normally.

        Args:
            orch_config: Minimal Config mock.
            orch_settings: Minimal Settings mock.
            quiet_console: Rich Console in quiet mode.
        """
        dispatch_executed: list[bool] = []

        pipeline = Pipeline(
            orch_config,
            orch_settings,
            console=quiet_console,
            continue_on_trailer_error=True,
            step_overrides={
                "ingest": lambda *_a, **_kw: StepReport(name="ingest"),
                "sort": lambda *_a, **_kw: StepReport(name="sort"),
                "clean": lambda *_a, **_kw: StepReport(name="clean"),
                "scrape": lambda *_a, **_kw: StepReport(name="scrape"),
                "cleanup": lambda *_a, **_kw: StepReport(name="cleanup"),
                "enforce": lambda *_a, **_kw: StepReport(name="enforce"),
                "verify": _verify_with_items,
                "trailers": lambda *_a, **_kw: StepReport(name="trailers", status="error", error_count=1),
                "dispatch": lambda *_a, **_kw: (dispatch_executed.append(True), StepReport(name="dispatch"))[1],
            },
        )

        report = pipeline.run()

        # Dispatch must have executed
        assert dispatch_executed == [True]
        # Report still records the trailer error
        assert report.steps["trailers"].status == "error"


# ---------------------------------------------------------------------------
# E2E: real run_trailers + real TrailersOrchestrator → TrailerStepFailed
# ---------------------------------------------------------------------------


class TestTrailerStepFailedE2E:
    """I3 (pr-test-analyzer) — bridge test: real run_trailers → TrailerStepFailed.

    Verifies the full chain without stubbing ``run_trailers``:
    real orchestrator raises ``TrailerStateLocked`` → ``run_trailers``
    returns ``StepReport(status='error')`` → pipeline raises
    ``TrailerStepFailed`` → dispatch does NOT execute.
    """

    def test_real_run_trailers_failure_propagates_TrailerStepFailed_to_pipeline(
        self, orch_config, orch_settings, quiet_console, tmp_path
    ):
        """TrailerStateLocked from state_store.set propagates to TrailerStepFailed.

        Uses a real ``run_trailers`` call (no step_override for "trailers").
        The ``TrailersOrchestrator._state_store.set`` is patched to raise
        ``TrailerStateLocked`` so the real ``run_trailers`` catches it,
        returns ``StepReport(status='error')``, and the pipeline raises
        ``TrailerStepFailed`` before dispatch executes.

        Args:
            orch_config: Minimal Config mock (``trailers.enabled`` overridden
                to ``True`` for this test).
            orch_settings: Minimal Settings mock.
            quiet_console: Rich Console in quiet mode.
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch

        from personalscraper.trailers.state import TrailerStateLocked, TrailerStepFailed

        # Enable trailers so run_trailers does not short-circuit.
        orch_config.trailers.enabled = True
        orch_config.trailers.state_file = str(tmp_path / ".data" / "trailers_state.json")
        orch_config.trailers.filters.min_file_size_bytes = 102400
        orch_config.trailers.seasons.enabled = False

        dispatch_executed: list[bool] = []

        # Build a fake lock_path for the exception.
        lock_path = tmp_path / ".data" / "trailers_state.lock"
        locked_exc = TrailerStateLocked(lock_path, holder_pid=None)

        with patch(
            "personalscraper.trailers.orchestrator.TrailersOrchestrator.run",
            side_effect=locked_exc,
        ):
            pipeline = Pipeline(
                orch_config,
                orch_settings,
                console=quiet_console,
                continue_on_trailer_error=False,
                step_overrides={
                    "ingest": lambda *_a, **_kw: StepReport(name="ingest"),
                    "sort": lambda *_a, **_kw: StepReport(name="sort"),
                    "clean": lambda *_a, **_kw: StepReport(name="clean"),
                    "scrape": lambda *_a, **_kw: StepReport(name="scrape"),
                    "cleanup": lambda *_a, **_kw: StepReport(name="cleanup"),
                    "enforce": lambda *_a, **_kw: StepReport(name="enforce"),
                    "verify": _verify_with_items,
                    # "trailers" NOT overridden — real run_trailers runs.
                    "dispatch": lambda *_a, **_kw: (
                        dispatch_executed.append(True),
                        StepReport(name="dispatch"),
                    )[1],
                },
            )

            with pytest.raises(TrailerStepFailed):
                pipeline.run()

        # Dispatch must NOT have been called — the pipeline aborted before it.
        assert dispatch_executed == [], "dispatch must not execute when TrailerStepFailed is raised"
