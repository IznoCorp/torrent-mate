"""Tests for personalscraper.library.reporter — library statistics."""

from personalscraper.library.reporter import LibraryReport, format_report_text, generate_report


class TestGenerateReport:
    """Tests for report generation from JSON data."""

    def test_empty_report(self) -> None:
        """Report with no data should have zero counts."""
        report = generate_report(scan_data=None, analysis_data=None,
                                  validation_data=None, recommendation_data=None)
        assert report.total_items == 0
        assert report.total_size_gb == 0.0

    def test_report_from_scan(self) -> None:
        """Report should aggregate scan data with issue breakdown."""
        scan_data = {
            "scanned_at": "2026-04-15T12:00:00",
            "item_count": 3,
            "items": [
                {"disk": "Disk1", "category": "films", "media_type": "movie",
                 "folder_size_gb": 2.0, "actors_dir": True,
                 "issues": ["actors_dir_present", "junk_files"],
                 "nfo": {"present": True, "valid": True}, "artwork": {"poster": True}},
                {"disk": "Disk1", "category": "films", "media_type": "movie",
                 "folder_size_gb": 3.5, "actors_dir": False, "issues": [],
                 "nfo": {"present": True, "valid": True}, "artwork": {"poster": True}},
                {"disk": "Disk2", "category": "series", "media_type": "tvshow",
                 "folder_size_gb": 15.0, "actors_dir": True,
                 "issues": ["actors_dir_present"],
                 "nfo": {"present": True, "valid": False}, "artwork": {"poster": False}},
            ],
        }
        report = generate_report(scan_data=scan_data)
        assert report.total_items == 3
        assert report.total_size_gb == 20.5
        assert report.items_per_disk["Disk1"] == 2
        assert report.items_per_disk["Disk2"] == 1
        assert report.items_per_category["films"] == 2
        assert report.actors_dir_count == 2
        assert report.nfo_valid_count == 2
        assert report.nfo_invalid_count == 1
        # Issue breakdown
        assert report.scan_issues["actors_dir_present"] == 2
        assert report.scan_issues["junk_files"] == 1

    def test_report_from_analysis(self) -> None:
        """Report should aggregate codec distribution from analysis."""
        analysis_data = {
            "item_count": 2, "file_count": 3,
            "items": [
                {"files": [
                    {"video": {"codec": "hevc"}, "audio_profile": "multi", "size_gb": 2.0},
                ]},
                {"files": [
                    {"video": {"codec": "h264"}, "audio_profile": "vf", "size_gb": 5.0},
                    {"video": {"codec": "h264"}, "audio_profile": "vo", "size_gb": 4.0},
                ]},
            ],
        }
        report = generate_report(analysis_data=analysis_data)
        assert report.codec_distribution["hevc"] == 1
        assert report.codec_distribution["h264"] == 2
        assert report.audio_distribution["multi"] == 1
        assert report.audio_distribution["vf"] == 1
        assert report.audio_distribution["vo"] == 1
        assert report.analysis_item_count == 2
        assert report.analysis_file_count == 3

    def test_report_from_validation(self) -> None:
        """Report should include validation error breakdown."""
        validation_data = {
            "valid_count": 10, "fixed_count": 0, "issues_count": 5,
            "items": [
                {"status": "issues", "errors": ["nfo_present", "poster_present"], "warnings": ["artwork_landscape"]},
                {"status": "issues", "errors": ["nfo_valid"], "warnings": ["artwork_landscape"]},
                {"status": "issues", "errors": ["nfo_present"], "warnings": []},
                {"status": "issues", "errors": ["nfo_valid", "category"], "warnings": []},
                {"status": "issues", "errors": ["dir_naming"], "warnings": []},
            ],
        }
        report = generate_report(validation_data=validation_data)
        assert report.validation_valid == 10
        assert report.validation_issues == 5
        assert report.validation_errors["nfo_present"] == 2
        assert report.validation_errors["nfo_valid"] == 2
        assert report.validation_warnings["artwork_landscape"] == 2

    def test_report_from_recommendations(self) -> None:
        """Report should include recommendation details."""
        rec_data = {
            "total_recommendations": 3,
            "estimated_total_savings_gb": 12.5,
            "items": [
                {"priority": "high", "title": "Movie A",
                 "current": {"codec": "mpeg2", "resolution": "1080p", "size_gb": 8.0, "audio_profile": "vf"},
                 "reasons": ["rejected codec mpeg2"]},
                {"priority": "medium", "title": "Movie B",
                 "current": {"codec": "h264", "resolution": "720p", "size_gb": 5.0, "audio_profile": "vo"},
                 "reasons": ["non-preferred codec"]},
                {"priority": "low", "title": "Movie C",
                 "current": {"codec": "hevc", "resolution": "1080p", "size_gb": 2.0, "audio_profile": "multi"},
                 "reasons": ["missing subtitles"]},
            ],
        }
        report = generate_report(recommendation_data=rec_data)
        assert report.recommendation_count == 3
        assert report.estimated_savings_gb == 12.5
        assert report.recommendations_by_priority["high"] == 1
        assert len(report.recommendation_details) == 3
        assert report.recommendation_details[0]["title"] == "Movie A"


class TestFormatReportText:
    """Tests for report text formatting."""

    def test_format_includes_sections(self) -> None:
        """Formatted report should include key sections."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            total_items=100,
            total_size_gb=500.0,
            scan_issues={"actors_dir_present": 50, "junk_files": 20},
            validation_valid=80,
            validation_issues=20,
            validation_errors={"nfo_present": 10, "nfo_valid": 10},
        )
        text = format_report_text(report)
        assert "RAPPORT DE SANTÉ" in text
        assert "SCAN" in text
        assert "VALIDATION" in text
        assert "ACTIONS SUGGÉRÉES" in text
        assert "library-clean" in text
        assert "re-scrape" in text.lower()

    def test_format_empty_report(self) -> None:
        """Empty report should still produce valid text."""
        report = LibraryReport(generated_at="2026-04-17T12:00:00")
        text = format_report_text(report)
        assert "RAPPORT DE SANTÉ" in text
        assert "Aucune action nécessaire" in text


class TestRescrapeSection:
    """Tests for rescrape section in report."""

    def test_report_with_rescrape_data(self) -> None:
        """Report should include rescrape summary when data is present."""
        rescrape_data = {
            "rescraped_at": "2026-04-17T14:00:00",
            "fixed_count": 10, "skipped_count": 5, "error_count": 2,
            "items": [
                {"actions_taken": ["nfo_regenerated"]},
                {"actions_taken": ["artwork_downloaded"]},
                {"actions_taken": ["nfo_regenerated", "artwork_downloaded"]},
            ],
        }
        report = generate_report(rescrape_data=rescrape_data)
        assert report.rescrape_fixed == 10
        assert report.rescrape_skipped == 5
        assert report.rescrape_errors == 2
        assert report.rescrape_nfo_count == 2
        assert report.rescrape_artwork_count == 2

    def test_rescrape_section_in_text(self) -> None:
        """Formatted report should include RESCRAPE section."""
        report = LibraryReport(
            generated_at="2026-04-17T12:00:00",
            rescrape_fixed=10, rescrape_skipped=5, rescrape_errors=2,
            rescrape_nfo_count=6, rescrape_artwork_count=4,
        )
        text = format_report_text(report)
        assert "RESCRAPE" in text
        assert "NFO régénérés: 6" in text
        assert "Artwork téléchargé: 4" in text

    def test_no_rescrape_data_no_section(self) -> None:
        """Report without rescrape data should not show RESCRAPE section."""
        report = LibraryReport(generated_at="2026-04-17T12:00:00")
        text = format_report_text(report)
        assert "RESCRAPE" not in text
