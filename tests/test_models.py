"""Tests for personalscraper.models — PipelineReport.to_html() formatting."""

from datetime import datetime

from personalscraper.models import PipelineReport, StepReport


class TestPipelineReportToHtml:
    """Tests for PipelineReport.to_html() Telegram HTML formatting."""

    def test_empty_report(self):
        """Empty report (no steps) still produces valid HTML."""
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.finished_at = datetime(2026, 4, 11, 3, 0, 5)
        html = report.to_html()
        assert "<b>PersonalScraper" in html
        assert "5s" in html

    def test_all_steps_success(self):
        """Report with all successful steps shows OK counts."""
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("ingest", StepReport(name="ingest", success_count=3))
        report.add_step("sort", StepReport(name="sort", success_count=5))
        report.finished_at = datetime(2026, 4, 11, 3, 2, 30)
        html = report.to_html()
        assert "3 OK" in html
        assert "5 OK" in html
        assert "2min 30s" in html
        # No errors → header should have ✅
        assert "\u2705" in html

    def test_steps_with_errors(self):
        """Report with errors shows error counts and ❌ header."""
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("scrape", StepReport(name="scrape", success_count=2, error_count=1))
        report.finished_at = datetime(2026, 4, 11, 3, 1, 0)
        html = report.to_html()
        assert "1 err" in html
        assert "\u274c" in html

    def test_details_included(self):
        """Step details appear in the output (up to 5)."""
        step = StepReport(name="dispatch", success_count=2)
        step.details = ["Film A → Disk3", "Film B → Disk1"]
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("dispatch", step)
        report.finished_at = datetime(2026, 4, 11, 3, 0, 10)
        html = report.to_html()
        assert "Film A" in html
        assert "Film B" in html

    def test_details_truncated_at_five(self):
        """More than 5 details shows truncation indicator."""
        step = StepReport(name="sort", success_count=8)
        step.details = [f"Item {i}" for i in range(8)]
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("sort", step)
        report.finished_at = datetime(2026, 4, 11, 3, 0, 10)
        html = report.to_html()
        assert "Item 0" in html
        assert "Item 4" in html
        assert "+3 autres" in html
        assert "Item 5" not in html

    def test_warnings_included(self):
        """Step warnings appear in the output."""
        step = StepReport(name="verify", success_count=1)
        step.warnings = ["Missing poster for Film X"]
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("verify", step)
        report.finished_at = datetime(2026, 4, 11, 3, 0, 5)
        html = report.to_html()
        assert "Missing poster" in html

    def test_skip_count_shown(self):
        """Skip count appears in the output."""
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("ingest", StepReport(name="ingest", success_count=2, skip_count=3))
        report.finished_at = datetime(2026, 4, 11, 3, 0, 5)
        html = report.to_html()
        assert "3 skip" in html

    def test_zero_counts_omitted(self):
        """Zero counts (0 OK, 0 skip, 0 err) are not shown."""
        step = StepReport(name="sort")
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("sort", step)
        report.finished_at = datetime(2026, 4, 11, 3, 0, 5)
        html = report.to_html()
        assert "aucun item" in html

    def test_timestamp_footer(self):
        """Finished timestamp appears in the footer."""
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.finished_at = datetime(2026, 4, 11, 3, 4, 32)
        html = report.to_html()
        assert "2026-04-11 03:04:32" in html

    def test_step_names_capitalized(self):
        """Step names are capitalized in the output."""
        report = PipelineReport(started_at=datetime(2026, 4, 11, 3, 0, 0))
        report.add_step("ingest", StepReport(name="ingest", success_count=1))
        report.finished_at = datetime(2026, 4, 11, 3, 0, 5)
        html = report.to_html()
        assert "<b>Ingest</b>" in html
