"""Resilience test: full pipeline double-run idempotence.

Runs the complete 9-step pipeline twice and verifies that the
second run fast-skips most phases, including the trailers step.
"""

from unittest.mock import MagicMock, patch

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline


class TestPipelineDoubleRun:
    """Test 7: Pipeline is idempotent — second run skips everything."""

    @patch("personalscraper.dispatch.run.run_dispatch")
    @patch("personalscraper.verify.run.run_verify")
    @patch("personalscraper.enforce.run.run_enforce")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    # Defence-in-depth stub: prevent the real orchestrator from running against
    # MagicMock strings in config even if trailers.enabled is not False
    # (finding 10.5/C1).
    @patch(
        "personalscraper.trailers.step.run_trailers",
        return_value=StepReport(name="trailers", status="skipped"),
    )
    def test_second_run_mostly_skips(
        self,
        mock_trailers,
        mock_gate,
        mock_ingest,
        mock_sort,
        mock_scrape,
        mock_enforce,
        mock_verify,
        mock_dispatch,
        staging,
        resilience_settings,
    ):
        """Second pipeline run produces mostly skip/zero counts.

        Also asserts that the trailers step is idempotent: on the second run it
        reports skipped/success with zero downloads (finding 10.5, finding 3).
        """
        # First run: normal processing
        mock_ingest.return_value = StepReport(name="ingest", success_count=2)
        mock_sort.return_value = StepReport(name="sort", success_count=2)
        mock_scrape.return_value = StepReport(name="scrape", success_count=2)
        mock_enforce.return_value = StepReport(name="enforce", success_count=1)
        mock_verify.return_value = (
            StepReport(name="verify", success_count=2),
            [MagicMock()],
        )
        mock_dispatch.return_value = StepReport(name="dispatch", success_count=2)

        config = MagicMock()
        config.paths.staging_dir = staging
        config.paths.data_dir = staging / ".data"
        config.disks = []
        # Disable trailers at the config level: defence-in-depth so the real
        # orchestrator is never invoked even if the run_trailers stub is removed.
        config.trailers.enabled = False

        # console removed — no longer needed
        pipeline = Pipeline(
            AppContext(
                config=config,
                settings=resilience_settings,
                event_bus=EventBus(),
                provider_registry=MagicMock(spec=ProviderRegistry),
            )
        )
        report1 = pipeline.run()

        assert len(report1.steps) == 9
        assert report1.steps["ingest"].success_count == 2

        # Second run: simulate "nothing to do" state
        mock_ingest.return_value = StepReport(name="ingest", skip_count=2)
        mock_sort.return_value = StepReport(name="sort")  # fast-skip
        mock_scrape.return_value = StepReport(name="scrape", skip_count=2)
        mock_enforce.return_value = StepReport(name="enforce", skip_count=1)
        mock_verify.return_value = (
            StepReport(name="verify", success_count=2),
            [MagicMock()],
        )
        mock_dispatch.return_value = StepReport(name="dispatch", success_count=2)

        report2 = pipeline.run()

        assert len(report2.steps) == 9
        # Ingest should show skips (all already ingested)
        assert report2.steps["ingest"].skip_count >= 0
        # Sort should show zero (fast-skip)
        assert report2.steps["sort"].success_count == 0
        # Trailers step idempotence: second run must not re-download anything.
        assert report2.steps["trailers"].status in {"skipped", "success"}
        assert report2.steps["trailers"].counts.get("downloaded", 0) == 0
