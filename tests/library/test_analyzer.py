"""Tests for personalscraper.library.analyzer — ffprobe deep scan."""

from personalscraper.library.analyzer import deduce_audio_profile


class TestDeduceAudioProfile:
    """Tests for audio profile detection logic."""

    def test_multi_two_languages(self) -> None:
        """Two different audio languages = multi."""
        tracks = [
            {"language": "fra", "is_default": True},
            {"language": "eng", "is_default": False},
        ]
        assert deduce_audio_profile(tracks, []) == "multi"

    def test_vf_single_french(self) -> None:
        """Single French audio = vf."""
        tracks = [{"language": "fra", "is_default": True}]
        assert deduce_audio_profile(tracks, []) == "vf"

    def test_vostfr_eng_audio_french_sub(self) -> None:
        """English audio + French subtitle = vostfr."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"

    def test_vostfr_japanese_audio_french_sub(self) -> None:
        """Japanese audio + French subtitle = vostfr (anime)."""
        audio = [{"language": "jpn", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"

    def test_vo_english_no_french_subs(self) -> None:
        """English audio without French subtitles = vo."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "eng"}]
        assert deduce_audio_profile(audio, subs) == "vo"

    def test_vo_no_tracks(self) -> None:
        """No audio tracks = vo (unknown)."""
        assert deduce_audio_profile([], []) == "vo"

    def test_multi_three_languages(self) -> None:
        """Three different languages = multi."""
        tracks = [
            {"language": "fra", "is_default": True},
            {"language": "eng", "is_default": False},
            {"language": "jpn", "is_default": False},
        ]
        assert deduce_audio_profile(tracks, []) == "multi"

    def test_vf_fre_iso639_2b(self) -> None:
        """ISO 639-2/B 'fre' should be recognized as French (VF)."""
        tracks = [{"language": "fre", "is_default": True}]
        assert deduce_audio_profile(tracks, []) == "vf"

    def test_vostfr_fre_subtitle(self) -> None:
        """ISO 639-2/B 'fre' in subtitles should be recognized as VOSTFR."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "fre"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"


class TestAnalyzeLibrary:
    """Tests for analyze_library — disk iteration, filtering, incremental."""

    def _make_config(self, path, name, categories):
        """Create a mock DiskConfig."""
        from unittest.mock import MagicMock

        config = MagicMock()
        config.path = path
        config.name = name
        config.categories = categories
        return config

    def _make_stream_info(self):
        """Create a minimal stream info dict for mocking extract_stream_info."""
        return {
            "video": {
                "codec": "hevc",
                "width": 1920,
                "height": 1080,
                "bitrate_kbps": 5000,
                "hdr": {"is_hdr": False, "hdr_type": None},
            },
            "audio": [{"codec": "aac", "language": "fra", "channels": 2, "is_atmos": False, "is_default": True}],
            "subtitle": [],
            "duration_seconds": 7200.0,
        }

    def test_disk_filter(self, tmp_path):
        """--disk filter should only analyze the specified disk."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk1 = tmp_path / "d1" / "medias"
        disk2 = tmp_path / "d2" / "medias"
        (disk1 / "films" / "A (2024)").mkdir(parents=True)
        (disk1 / "films" / "A (2024)" / "a.mkv").write_bytes(b"\x00" * 1000)
        (disk2 / "films" / "B (2024)").mkdir(parents=True)
        (disk2 / "films" / "B (2024)" / "b.mkv").write_bytes(b"\x00" * 1000)

        configs = [
            self._make_config(disk1, "Disk1", ["films"]),
            self._make_config(disk2, "Disk2", ["films"]),
        ]

        with patch("personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()):
            result = analyze_library(configs, disk_filter="Disk1")

        assert result.item_count == 1

    def test_max_items(self, tmp_path):
        """--max-items should limit items analyzed."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        for name in ("A (2024)", "B (2024)", "C (2024)"):
            d = disk / "films" / name
            d.mkdir(parents=True)
            (d / "movie.mkv").write_bytes(b"\x00" * 1000)

        config = self._make_config(disk, "Disk1", ["films"])

        with patch("personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()):
            result = analyze_library([config], max_items=2)

        assert result.item_count == 2

    def test_incremental_skips_unchanged(self, tmp_path):
        """Incremental mode should skip files with matching size_gb."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        video = movie / "Movie.mkv"
        video.write_bytes(b"\x00" * 1000)
        size_gb = round(video.stat().st_size / (1024**3), 3)

        config = self._make_config(disk, "Disk1", ["films"])
        existing = {str(video): size_gb}

        with patch(
            "personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()
        ) as mock_extract:
            result = analyze_library([config], incremental=True, existing_sizes=existing)

        mock_extract.assert_not_called()
        assert result.file_count == 0

    def test_macos_resource_forks_skipped(self, tmp_path):
        """MacOS resource fork files (._*) should be skipped."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "._Movie.mkv").write_bytes(b"\x00" * 100)

        config = self._make_config(disk, "Disk1", ["films"])

        with patch(
            "personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()
        ) as mock_extract:
            analyze_library([config])

        assert mock_extract.call_count == 1
