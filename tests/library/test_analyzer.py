"""Tests for personalscraper.library.analyzer — ffprobe deep scan."""

from pathlib import Path

from personalscraper.conf.models import CategoryConfig, Config, DiskConfig, PathConfig
from personalscraper.library.analyzer import deduce_audio_profile
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_v15_config(
    disk_path: Path,
    disk_id: str,
    folder_name: str,
    category_id: str,
    tmp_path: Path,
) -> Config:
    """Create a minimal V15 Config for a single disk/category."""
    disk_cfg = DiskConfig(id=disk_id, path=disk_path, categories=[category_id])
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[disk_cfg],
        categories={category_id: CategoryConfig(folder_name=folder_name)},
        staging_dirs=CANONICAL_STAGING_DIRS,
    )


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

    def test_vf_fra_with_subs(self) -> None:
        """French audio with French subtitle should still be VF (not VOSTFR)."""
        audio = [{"language": "fra", "is_default": True}]
        subs = [{"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vf"

    def test_vo_und_language(self) -> None:
        """'und' (undefined) language without French subtitles = vo."""
        audio = [{"language": "und", "is_default": True}]
        assert deduce_audio_profile(audio, []) == "vo"

    def test_vo_empty_subs(self) -> None:
        """English audio without subtitles = vo."""
        audio = [{"language": "eng", "is_default": True}]
        assert deduce_audio_profile(audio, []) == "vo"

    def test_vostfr_via_second_sub(self) -> None:
        """Should detect VOSTFR even with multiple subtitle tracks."""
        audio = [{"language": "eng", "is_default": True}]
        subs = [{"language": "eng"}, {"language": "fra"}]
        assert deduce_audio_profile(audio, subs) == "vostfr"


class TestAnalyzeLibrary:
    """Tests for analyze_library — disk iteration, filtering, incremental."""

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

    def test_disk_filter(self, tmp_path: Path) -> None:
        """--disk filter should only analyze the specified disk."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk1 = tmp_path / "d1" / "medias"
        disk2 = tmp_path / "d2" / "medias"
        (disk1 / "films" / "A (2024)").mkdir(parents=True)
        (disk1 / "films" / "A (2024)" / "a.mkv").write_bytes(b"\x00" * 1000)
        (disk2 / "films" / "B (2024)").mkdir(parents=True)
        (disk2 / "films" / "B (2024)" / "b.mkv").write_bytes(b"\x00" * 1000)

        config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "torrents",
                staging_dir=tmp_path / "staging",
                data_dir=tmp_path / ".data",
            ),
            disks=[
                DiskConfig(id="disk1", path=disk1, categories=["movies"]),
                DiskConfig(id="disk2", path=disk2, categories=["movies"]),
            ],
            categories={"movies": CategoryConfig(folder_name="films")},
            staging_dirs=CANONICAL_STAGING_DIRS,
        )

        with patch("personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()):
            result = analyze_library(config, disk_filter="disk1")

        assert result.item_count == 1

    def test_max_items(self, tmp_path: Path) -> None:
        """--max-items should limit items analyzed."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        for name in ("A (2024)", "B (2024)", "C (2024)"):
            d = disk / "films" / name
            d.mkdir(parents=True)
            (d / "movie.mkv").write_bytes(b"\x00" * 1000)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)

        with patch("personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()):
            result = analyze_library(config, max_items=2)

        assert result.item_count == 2

    def test_incremental_skips_unchanged(self, tmp_path: Path) -> None:
        """Incremental mode should skip files with matching size_gb."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        video = movie / "Movie.mkv"
        video.write_bytes(b"\x00" * 1000)
        size_gb = round(video.stat().st_size / (1024**3), 3)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)
        existing = {str(video): size_gb}

        with patch(
            "personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()
        ) as mock_extract:
            result = analyze_library(config, incremental=True, existing_sizes=existing)

        mock_extract.assert_not_called()
        assert result.file_count == 0

    def test_macos_resource_forks_skipped(self, tmp_path: Path) -> None:
        """MacOS resource fork files (._*) should be skipped."""
        from unittest.mock import patch

        from personalscraper.library.analyzer import analyze_library

        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "._Movie.mkv").write_bytes(b"\x00" * 100)

        config = _make_v15_config(disk, "disk1", "films", "movies", tmp_path)

        with patch(
            "personalscraper.library.analyzer.extract_stream_info", return_value=self._make_stream_info()
        ) as mock_extract:
            analyze_library(config)

        assert mock_extract.call_count == 1
