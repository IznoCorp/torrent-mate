"""Tests for personalscraper.library.reporter — library statistics."""

from personalscraper.library.reporter import generate_report


class TestGenerateReport:
    """Tests for report generation from JSON data."""

    def test_empty_report(self) -> None:
        """Report with no data should have zero counts."""
        report = generate_report(scan_data=None, analysis_data=None,
                                  validation_data=None, recommendation_data=None)
        assert report.total_items == 0
        assert report.total_size_gb == 0.0

    def test_report_from_scan(self) -> None:
        """Report should aggregate scan data."""
        scan_data = {
            "scanned_at": "2026-04-15T12:00:00",
            "item_count": 3,
            "items": [
                {"disk": "Disk1", "category": "films", "media_type": "movie",
                 "folder_size_gb": 2.0, "actors_dir": True, "issues": ["actors_dir_present"],
                 "nfo": {"present": True, "valid": True}, "artwork": {"poster": True}},
                {"disk": "Disk1", "category": "films", "media_type": "movie",
                 "folder_size_gb": 3.5, "actors_dir": False, "issues": [],
                 "nfo": {"present": True, "valid": True}, "artwork": {"poster": True}},
                {"disk": "Disk2", "category": "series", "media_type": "tvshow",
                 "folder_size_gb": 15.0, "actors_dir": True, "issues": ["actors_dir_present"],
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

    def test_report_from_recommendations(self) -> None:
        """Report should include recommendation summary."""
        rec_data = {
            "total_recommendations": 5,
            "estimated_total_savings_gb": 12.5,
            "items": [
                {"priority": "high"}, {"priority": "high"},
                {"priority": "medium"}, {"priority": "medium"}, {"priority": "low"},
            ],
        }
        report = generate_report(recommendation_data=rec_data)
        assert report.recommendation_count == 5
        assert report.estimated_savings_gb == 12.5
        assert report.recommendations_by_priority["high"] == 2
        assert report.recommendations_by_priority["medium"] == 2
        assert report.recommendations_by_priority["low"] == 1
