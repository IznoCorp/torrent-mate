"""Unit tests for trailers/placement.py — Plex naming conventions per media type.

Movies: flat ``{movie}/{movie}-trailer.{ext}`` (Plex Local Media Assets).
TV shows: subfolder ``{show}/Trailers/{show}.{ext}`` and
``{show}/Saison NN/Trailers/{show} - Saison NN.{ext}`` (Plex TV Series agent).

All tests use tmpdir fixtures. No network, no yt-dlp.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from personalscraper.trailers.placement import (
    find_existing_trailer,
    trailer_exists,
    trailer_path_for,
    trailer_path_for_season,
    write_trailer_url_to_nfo,
)

# ── path computation (flat convention, shared for movies and TV) ─────────────


class TestTrailerPathFor:
    """Tests for trailer_path_for() — Plex placement per media_type."""

    def test_movie_follows_flat_name_dash_trailer_ext(self, tmp_path: Path) -> None:
        """Movies use {folder}/{name}-trailer.{ext} (Plex Local Media Assets)."""
        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()
        path = trailer_path_for(movie_dir, "Fight Club (1999)", media_type="movie", ext="mp4")
        assert path == movie_dir / "Fight Club (1999)-trailer.mp4"

    def test_movie_default_media_type_is_movie(self, tmp_path: Path) -> None:
        """Default media_type is 'movie' to keep the flat convention as the safe default."""
        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()
        assert (
            trailer_path_for(movie_dir, "Fight Club (1999)", ext="mp4") == movie_dir / "Fight Club (1999)-trailer.mp4"
        )

    def test_tvshow_uses_plex_trailers_subfolder(self, tmp_path: Path) -> None:
        """TV shows must place show-level trailers under Trailers/ per Plex docs.

        Reference: https://support.plex.tv/articles/local-files-for-tv-show-trailers-and-extras/
        Plex restricts the flat ``-trailer`` suffix to inline-episode extras; using
        it at show level produces an unrecognised orphan video. The 2026-04-25
        pipeline run caught the original buggy flat placement in production.
        """
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        path = trailer_path_for(show_dir, "Breaking Bad (2008)", media_type="tvshow", ext="mp4")
        assert path == show_dir / "Trailers" / "Breaking Bad (2008).mp4"
        # Guard against a regression back to the old flat placement.
        assert path.name != "Breaking Bad (2008)-trailer.mp4"

    def test_default_extension_is_mp4(self, tmp_path: Path) -> None:
        """Default `ext` parameter is 'mp4' since most yt-dlp outputs are mp4."""
        d = tmp_path / "X"
        d.mkdir()
        assert trailer_path_for(d, "X").suffix == ".mp4"

    def test_extension_can_be_webm_or_mkv(self, tmp_path: Path) -> None:
        """Extension is dynamic — yt-dlp may return webm/mkv in edge cases."""
        d = tmp_path / "Interstellar (2014)"
        d.mkdir()
        assert trailer_path_for(d, "Interstellar (2014)", ext="webm").suffix == ".webm"
        assert trailer_path_for(d, "Interstellar (2014)", ext="mkv").suffix == ".mkv"

    def test_leading_dot_in_ext_is_tolerated(self, tmp_path: Path) -> None:
        """Caller may pass 'mp4' or '.mp4' — either works."""
        d = tmp_path / "X"
        d.mkdir()
        a = trailer_path_for(d, "X", ext="mp4")
        b = trailer_path_for(d, "X", ext=".mp4")
        assert a == b


# ── season-level path computation (opt-in via config.trailers.seasons.enabled) ──


class TestTrailerPathForSeason:
    """Tests for trailer_path_for_season() — season-level path convention (opt-in)."""

    def test_trailer_path_for_season_builds_plex_subfolder_path(self, tmp_path: Path) -> None:
        """Season trailer lands at {show}/Saison NN/Trailers/{show} - Saison NN.{ext}.

        This is the Plex TV Series agent's required layout for per-season extras
        (https://support.plex.tv/articles/local-files-for-tv-show-trailers-and-extras/).
        The French ``Saison XX/`` folder name is the project convention and Plex
        matches it correctly; the inner ``Trailers/`` folder is what Plex requires
        for season-scoped extras to be recognised.
        """
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        path = trailer_path_for_season(show_dir, season_number=1, extension="mp4")
        assert path == show_dir / "Saison 01" / "Trailers" / "Breaking Bad (2008) - Saison 01.mp4"

    def test_trailer_path_for_season_respects_custom_extension(self, tmp_path: Path) -> None:
        """Caller decides the extension — yt-dlp may yield mkv/webm in edge cases."""
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        webm_path = trailer_path_for_season(show_dir, season_number=2, extension="webm")
        assert webm_path.suffix == ".webm"
        assert webm_path.name == "Breaking Bad (2008) - Saison 02.webm"
        assert webm_path.parent.name == "Trailers"

    def test_trailer_path_for_season_handles_unicode_show_names(self, tmp_path: Path) -> None:
        """Show names with non-ASCII characters round-trip through the path build."""
        show_dir = tmp_path / "Téléphérique (2019)"
        show_dir.mkdir()
        path = trailer_path_for_season(show_dir, season_number=3, extension="mp4")
        assert path.parent.name == "Trailers"
        assert path.parent.parent.name == "Saison 03"
        assert path.name == "Téléphérique (2019) - Saison 03.mp4"

    def test_trailer_path_for_season_uses_trailers_subfolder(self, tmp_path: Path) -> None:
        """Plex requires a ``Trailers/`` subfolder beneath the season directory."""
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        path = trailer_path_for_season(show_dir, season_number=1, extension="mp4")
        assert "Trailers" in [p.name for p in path.parents]


# ── tolerant lookup across known extensions ──────────────────────────────────


class TestFindExistingTrailer:
    """Tests for find_existing_trailer() — tolerant lookup across known extensions."""

    def test_finds_mp4(self, tmp_path: Path) -> None:
        """find_existing_trailer prefers mp4 when multiple candidates exist."""
        d = tmp_path / "X"
        d.mkdir()
        (d / "X-trailer.mp4").write_bytes(b"x" * 200000)
        assert find_existing_trailer(d, "X") == d / "X-trailer.mp4"

    def test_finds_mkv_when_only_mkv_present(self, tmp_path: Path) -> None:
        """Falls back to .mkv if no .mp4."""
        d = tmp_path / "X"
        d.mkdir()
        (d / "X-trailer.mkv").write_bytes(b"x" * 200000)
        assert find_existing_trailer(d, "X") == d / "X-trailer.mkv"

    def test_prefers_mp4_over_webm(self, tmp_path: Path) -> None:
        """When both mp4 and webm exist, mp4 wins (Plex-friendliness)."""
        d = tmp_path / "X"
        d.mkdir()
        (d / "X-trailer.webm").write_bytes(b"x" * 200000)
        (d / "X-trailer.mp4").write_bytes(b"x" * 200000)
        assert find_existing_trailer(d, "X") == d / "X-trailer.mp4"

    def test_returns_none_when_nothing_present(self, tmp_path: Path) -> None:
        """Returns None when no trailer file exists with any known extension."""
        d = tmp_path / "X"
        d.mkdir()
        assert find_existing_trailer(d, "X") is None


# ── trailer_exists ────────────────────────────────────────────────────────────


class TestTrailerExists:
    """Tests for trailer_exists() — size-gated existence check."""

    def test_returns_false_when_file_absent(self, tmp_path: Path) -> None:
        """trailer_exists returns False when the file does not exist."""
        path = tmp_path / "nonexistent-trailer.mp4"
        assert trailer_exists(path, min_size_bytes=102400) is False

    def test_returns_false_when_file_too_small(self, tmp_path: Path) -> None:
        """trailer_exists returns False when file exists but is below size threshold."""
        trailer = tmp_path / "tiny-trailer.mp4"
        trailer.write_bytes(b"x" * 1000)  # 1 KB
        assert trailer_exists(trailer, min_size_bytes=102400) is False

    def test_returns_true_when_file_large_enough(self, tmp_path: Path) -> None:
        """trailer_exists returns True when file exists and meets size threshold."""
        trailer = tmp_path / "real-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)  # 200 KB
        assert trailer_exists(trailer, min_size_bytes=102400) is True

    def test_zero_min_size_returns_true_for_any_existing_file(self, tmp_path: Path) -> None:
        """trailer_exists with min_size_bytes=0 returns True for any file present."""
        trailer = tmp_path / "empty-trailer.mp4"
        trailer.write_bytes(b"")
        assert trailer_exists(trailer, min_size_bytes=0) is True

    def test_returns_false_for_directory(self, tmp_path: Path) -> None:
        """trailer_exists returns False when the path is a directory."""
        d = tmp_path / "trailers"
        d.mkdir()
        assert trailer_exists(d, min_size_bytes=0) is False

    def test_returns_false_when_stat_fails(self, tmp_path: Path, monkeypatch) -> None:
        """trailer_exists returns False when stat() raises OSError on st_size."""
        trailer = tmp_path / "broken.mkv"
        trailer.write_bytes(b"\x00" * 200000)

        real_stat = Path.stat
        call_count = [0]

        def failing_stat(self_path, *, follow_symlinks=True):
            call_count[0] += 1
            # First call: is_file() needs True → let it succeed
            # Second call: st_size check → raise OSError
            if call_count[0] == 1:
                return real_stat(self_path, follow_symlinks=follow_symlinks)
            raise OSError("broken")

        monkeypatch.setattr(Path, "stat", failing_stat)
        assert trailer_exists(trailer, min_size_bytes=102400) is False


# ── NFO trailer tag population ───────────────────────────────────────────────


class TestWriteTrailerUrlToNfo:
    """Tests for write_trailer_url_to_nfo() — NFO <trailer> tag population."""

    def _make_nfo(self, tmp_path: Path, trailer_text: str = "") -> Path:
        """Build a minimal movie NFO that matches what nfo_generator.py emits."""
        nfo = tmp_path / "Fight Club (1999).nfo"
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Fight Club"
        ET.SubElement(root, "year").text = "1999"
        ET.SubElement(root, "trailer").text = trailer_text
        ET.ElementTree(root).write(nfo, encoding="utf-8", xml_declaration=True)
        return nfo

    def test_populates_empty_trailer_tag(self, tmp_path: Path) -> None:
        """write_trailer_url_to_nfo fills the pre-existing empty <trailer> tag."""
        nfo = self._make_nfo(tmp_path)
        write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=ABC")
        tree = ET.parse(nfo)
        assert tree.find("trailer") is not None
        assert tree.find("trailer").text == "https://www.youtube.com/watch?v=ABC"  # type: ignore[union-attr]

    def test_overwrites_existing_url(self, tmp_path: Path) -> None:
        """An existing URL is replaced (re-scrape case)."""
        nfo = self._make_nfo(tmp_path, trailer_text="https://old.example/x")
        write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=NEW")
        tree = ET.parse(nfo)
        assert tree.find("trailer") is not None
        assert tree.find("trailer").text == "https://www.youtube.com/watch?v=NEW"  # type: ignore[union-attr]

    def test_creates_trailer_tag_if_absent(self, tmp_path: Path) -> None:
        """If the NFO was written by an older generator without <trailer>, add it."""
        nfo = tmp_path / "X.nfo"
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "X"
        ET.ElementTree(root).write(nfo, encoding="utf-8", xml_declaration=True)
        write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=Z")
        tree = ET.parse(nfo)
        elem = tree.find("trailer")
        assert elem is not None
        assert elem.text == "https://www.youtube.com/watch?v=Z"

    def test_missing_nfo_is_noop(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """A missing NFO logs a structured warning and returns — never raises."""
        missing = tmp_path / "does_not_exist.nfo"
        write_trailer_url_to_nfo(missing, "https://example")  # must not raise
        assert any("trailer_nfo_missing" in rec.message for rec in caplog.records)

    def test_write_trailer_url_to_nfo_is_atomic_under_simulated_crash(self, tmp_path: Path) -> None:
        """write_trailer_url_to_nfo leaves the original NFO unchanged when tree.write() raises.

        The atomic write pattern (write to .tmp-PID then os.replace) means that a
        crash mid-write must not truncate or corrupt the original file.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch
        from xml.etree import ElementTree as _ET

        nfo = self._make_nfo(tmp_path)
        original_content = nfo.read_bytes()

        # Monkeypatch ElementTree.write to raise mid-write.
        with patch.object(_ET.ElementTree, "write", side_effect=OSError("disk full")):
            write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=CRASH")

        # Original file must be byte-for-byte unchanged.
        assert nfo.read_bytes() == original_content

        # No temp file must be left behind.
        pid_tmps = list(tmp_path.glob("*.nfo.tmp-*"))
        assert pid_tmps == [], f"Leftover temp files: {pid_tmps}"

    def test_write_trailer_url_to_nfo_cleans_up_tmp_on_unicode_error(self, tmp_path: Path) -> None:
        """write_trailer_url_to_nfo removes the .tmp-PID file when tree.write() raises UnicodeEncodeError.

        Non-OSError exceptions (UnicodeEncodeError, TypeError, ParseError) must
        be covered by the ``finally`` cleanup block, not just the OSError branch.
        The function must also return False to signal the failure to the caller.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch
        from xml.etree import ElementTree as _ET

        nfo = self._make_nfo(tmp_path)

        # Simulate a UnicodeEncodeError mid-write (e.g. exotic filename on
        # a filesystem that cannot represent the encoded bytes).
        unicode_exc = UnicodeEncodeError("utf-8", "x", 0, 1, "surrogates not allowed")
        with patch.object(_ET.ElementTree, "write", side_effect=unicode_exc):
            result = write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=UNI")

        # Function must signal failure.
        assert result is False

        # No .tmp-* orphan must remain.
        pid_tmps = list(tmp_path.glob("*.nfo.tmp-*"))
        assert pid_tmps == [], f"Leftover temp files after UnicodeEncodeError: {pid_tmps}"

    def test_write_trailer_url_to_nfo_returns_false_on_failure(self, tmp_path: Path) -> None:
        """write_trailer_url_to_nfo returns False on any write failure.

        The return value must be False whenever the NFO was NOT updated
        (missing file, parse error, or write error), so that the caller can
        log a structured warning without checking the log itself.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import patch
        from xml.etree import ElementTree as _ET

        nfo = self._make_nfo(tmp_path)

        with patch.object(_ET.ElementTree, "write", side_effect=RuntimeError("unexpected")):
            result = write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=FAIL")

        assert result is False

    def test_write_trailer_url_to_nfo_returns_true_on_success(self, tmp_path: Path) -> None:
        """write_trailer_url_to_nfo returns True when the NFO is updated successfully.

        Args:
            tmp_path: Pytest tmp_path fixture.
        """
        nfo = self._make_nfo(tmp_path)
        result = write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=OK")
        assert result is True

    def test_parse_error_nfo_returns_false(self, tmp_path: Path) -> None:
        """Corrupted NFO (unparseable XML) returns False — no exception raised."""
        nfo = tmp_path / "broken.nfo"
        nfo.write_text("<<<not xml>>>", encoding="utf-8")
        result = write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=X")
        assert result is False

    def test_tmp_unlink_oserror_is_suppressed(self, tmp_path: Path, monkeypatch) -> None:
        """OSError during tmp_path.unlink in the finally block is suppressed."""
        nfo = self._make_nfo(tmp_path)

        def failing_unlink(self_path, missing_ok=False):
            raise OSError("read-only fs")

        monkeypatch.setattr(Path, "unlink", failing_unlink)
        result = write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=OK")
        # The write succeeded BEFORE the unlink; the function returns True.
        assert result is True


# ── TV-show trailer lookup ──────────────────────────────────────────────────


class TestFindExistingTrailerTvShows:
    """Tests for find_existing_trailer() TV-show subfolder lookup."""

    def test_find_existing_trailer_returns_subfolder_path(self, tmp_path: Path) -> None:
        """find_existing_trailer() returns the canonical Trailers/ path."""
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        trailers_dir = show_dir / "Trailers"
        trailers_dir.mkdir()
        canonical = trailers_dir / "Breaking Bad (2008).mp4"
        canonical.write_bytes(b"x" * 1000)

        result = find_existing_trailer(show_dir, "Breaking Bad (2008)", media_type="tvshow")

        assert result == canonical

    def test_find_existing_trailer_ignores_flat_tvshow_path(self, tmp_path: Path) -> None:
        """TV-show lookup does not scan the movie-style flat path."""
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        flat = show_dir / "Breaking Bad (2008)-trailer.mp4"
        flat.write_bytes(b"x" * 1000)

        result = find_existing_trailer(show_dir, "Breaking Bad (2008)", media_type="tvshow")

        assert result is None

    def test_movie_lookup_still_uses_flat_path(self, tmp_path: Path) -> None:
        """Movies use flat trailer naming."""
        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()
        flat = movie_dir / "Fight Club (1999)-trailer.mp4"
        flat.write_bytes(b"x" * 1000)

        result = find_existing_trailer(movie_dir, "Fight Club (1999)", media_type="movie")

        assert result == flat
