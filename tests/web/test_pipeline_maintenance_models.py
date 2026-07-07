"""Unit tests for maintenance-dashboard additions to pipeline API models."""

from __future__ import annotations

from personalscraper.web.models.pipeline import RunDetail, RunSummary


class TestRunSummaryMaintenanceFields:
    """``RunSummary`` additive fields for the maintenance dashboard."""

    def test_defaults(self) -> None:
        """RunSummary defaults: kind='pipeline', command=None."""
        summary = RunSummary(
            run_uid="test-uid",
            trigger="web",
            dry_run=False,
            started_at="2025-01-01T00:00:00+00:00",
        )
        assert summary.kind == "pipeline"
        assert summary.command is None

    def test_maintenance_kind_round_trip(self) -> None:
        """RunSummary with kind='maintenance' and command set round-trips."""
        summary = RunSummary(
            run_uid="test-uid",
            trigger="web",
            dry_run=False,
            started_at="2025-01-01T00:00:00+00:00",
            kind="maintenance",
            command="library-clean",
        )
        assert summary.kind == "maintenance"
        assert summary.command == "library-clean"
        dumped = summary.model_dump()
        reloaded = RunSummary.model_validate(dumped)
        assert reloaded.kind == "maintenance"
        assert reloaded.command == "library-clean"


class TestRunDetailMaintenanceFields:
    """``RunDetail`` additive fields for the maintenance dashboard."""

    def test_defaults(self) -> None:
        """RunDetail defaults: kind='pipeline', command/options_json/output_tail=None."""
        detail = RunDetail(
            run_uid="test-uid",
            trigger="web",
            dry_run=False,
            started_at="2025-01-01T00:00:00+00:00",
        )
        assert detail.kind == "pipeline"
        assert detail.command is None
        assert detail.options_json is None
        assert detail.output_tail is None

    def test_maintenance_full_round_trip(self) -> None:
        """RunDetail with kind='maintenance' and all new fields round-trips."""
        detail = RunDetail(
            run_uid="test-uid",
            trigger="web",
            dry_run=False,
            started_at="2025-01-01T00:00:00+00:00",
            kind="maintenance",
            command="library-clean",
            options_json='{"a":1}',
            output_tail="log output tail here",
        )
        assert detail.kind == "maintenance"
        assert detail.command == "library-clean"
        assert detail.options_json == '{"a":1}'
        assert detail.output_tail == "log output tail here"

        dumped = detail.model_dump()
        reloaded = RunDetail.model_validate(dumped)
        assert reloaded.kind == "maintenance"
        assert reloaded.command == "library-clean"
        assert reloaded.options_json == '{"a":1}'
        assert reloaded.output_tail == "log output tail here"
