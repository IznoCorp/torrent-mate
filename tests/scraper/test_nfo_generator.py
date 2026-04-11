"""Tests for the NFO XML generator.

Tests movie NFO generation against the MediaElch format, including
ratings, uniqueids, inline images, streamdetails, actors, and the
generator tag. Uses sample data matching real TMDB API responses.
"""

import xml.etree.ElementTree as ET

import pytest

from personalscraper.scraper.nfo_generator import NFOGenerator

# ---------------------------------------------------------------------------
# Sample data matching TMDB API format
# ---------------------------------------------------------------------------

SAMPLE_MOVIE_DATA = {
    "id": 804406,
    "title": "The Piano Lesson",
    "original_title": "The Piano Lesson",
    "overview": "1936, Pittsburgh...",
    "tagline": "Blood is a chord.",
    "runtime": 127,
    "release_date": "2024-11-07",
    "vote_average": 5.878,
    "vote_count": 94,
    "genres": [{"id": 18, "name": "Drame"}, {"id": 10402, "name": "Musique"}],
    "production_countries": [{"name": "United States of America"}],
    "production_companies": [{"name": "Mundy Lane Entertainment"}, {"name": "Escape Artists"}],
    "credits": {
        "cast": [
            {"name": "John David Washington", "character": "Boy Willie", "order": 0, "profile_path": "/abc.jpg"},
            {"name": "Danielle Deadwyler", "character": "Berniece Charles", "order": 1, "profile_path": "/def.jpg"},
        ],
        "crew": [
            {"name": "Malcolm Washington", "job": "Director"},
            {"name": "August Wilson", "job": "Writer"},
            {"name": "Virgil Williams", "job": "Screenplay"},
        ],
    },
    "images": {
        "posters": [
            {"file_path": "/poster1.jpg", "iso_639_1": "fr", "vote_average": 5.3},
        ],
        "backdrops": [
            {"file_path": "/backdrop1.jpg", "iso_639_1": None, "vote_average": 5.5},
        ],
    },
    "external_ids": {
        "imdb_id": "tt15507512",
        "tvdb_id": None,
    },
    "release_dates": {
        "results": [
            {
                "iso_3166_1": "FR",
                "release_dates": [
                    {"type": 3, "certification": "Tous publics", "release_date": "2024-11-27"},
                ],
            },
        ],
    },
}

SAMPLE_STREAM_INFO = {
    "duration_seconds": 7627,
    "video": {
        "codec": "hevc",
        "width": 3840,
        "height": 2160,
        "aspect": 1.778,
        "scantype": "progressive",
    },
    "audio": [
        {"language": "fra", "codec": "eac3", "channels": 6},
        {"language": "eng", "codec": "atmos", "channels": 6},
    ],
    "subtitle": [
        {"language": "fra"},
        {"language": "eng"},
    ],
}


@pytest.fixture
def generator() -> NFOGenerator:
    """Create an NFOGenerator instance."""
    return NFOGenerator()


# ---------------------------------------------------------------------------
# Movie NFO — base structure
# ---------------------------------------------------------------------------

class TestMovieNFOBase:
    """Tests for basic movie NFO structure."""

    def test_xml_declaration(self, generator: NFOGenerator) -> None:
        """NFO should start with XML declaration."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')

    def test_root_element(self, generator: NFOGenerator) -> None:
        """Root element should be <movie>."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag == "movie"

    def test_title(self, generator: NFOGenerator) -> None:
        """Title should match movie_data title."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("title") == "The Piano Lesson"

    def test_plot_and_outline(self, generator: NFOGenerator) -> None:
        """Plot and outline should both contain the overview."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("plot") == "1936, Pittsburgh..."
        assert root.findtext("outline") == "1936, Pittsburgh..."

    def test_runtime(self, generator: NFOGenerator) -> None:
        """Runtime should be in minutes."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("runtime") == "127"

    def test_year_and_premiered(self, generator: NFOGenerator) -> None:
        """Year and premiered should be extracted from release_date."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("year") == "2024"
        assert root.findtext("premiered") == "2024-11-07"


# ---------------------------------------------------------------------------
# Movie NFO — IDs and ratings
# ---------------------------------------------------------------------------

class TestMovieNFOIds:
    """Tests for uniqueids and ratings in movie NFO."""

    def test_uniqueid_imdb(self, generator: NFOGenerator) -> None:
        """IMDB uniqueid should be present with default=true."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        imdb_id = root.find("uniqueid[@type='imdb']")
        assert imdb_id is not None
        assert imdb_id.text == "tt15507512"
        assert imdb_id.get("default") == "true"

    def test_uniqueid_tmdb(self, generator: NFOGenerator) -> None:
        """TMDB uniqueid should be present."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        tmdb_id = root.find("uniqueid[@type='tmdb']")
        assert tmdb_id is not None
        assert tmdb_id.text == "804406"

    def test_ratings_tmdb(self, generator: NFOGenerator) -> None:
        """TMDB rating should be present with correct structure."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        rating = root.find(".//rating[@name='themoviedb']")
        assert rating is not None
        assert rating.get("default") == "true"
        assert rating.get("max") == "10"
        assert rating.findtext("value") == "5.878"
        assert rating.findtext("votes") == "94"

    def test_mpaa_certification(self, generator: NFOGenerator) -> None:
        """MPAA should contain FR theatrical certification."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("mpaa") == "Tous publics"


# ---------------------------------------------------------------------------
# Movie NFO — credits and actors
# ---------------------------------------------------------------------------

class TestMovieNFOCredits:
    """Tests for credits, actors, and genres."""

    def test_genres(self, generator: NFOGenerator) -> None:
        """Genres should be listed as separate elements."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        genres = [g.text for g in root.findall("genre")]
        assert "Drame" in genres
        assert "Musique" in genres

    def test_director(self, generator: NFOGenerator) -> None:
        """Director should be present."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        directors = [d.text for d in root.findall("director")]
        assert "Malcolm Washington" in directors

    def test_credits_writers(self, generator: NFOGenerator) -> None:
        """Writers should be listed as credits."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        writers = [c.text for c in root.findall("credits")]
        assert "August Wilson" in writers

    def test_actors(self, generator: NFOGenerator) -> None:
        """Actors should have name, role, order, and thumb."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        actors = root.findall("actor")
        assert len(actors) >= 2
        assert actors[0].findtext("name") == "John David Washington"
        assert actors[0].findtext("role") == "Boy Willie"
        assert actors[0].findtext("order") == "0"
        assert "/abc.jpg" in (actors[0].findtext("thumb") or "")


# ---------------------------------------------------------------------------
# Movie NFO — inline images
# ---------------------------------------------------------------------------

class TestMovieNFOImages:
    """Tests for inline poster and fanart images."""

    def test_poster_thumbs(self, generator: NFOGenerator) -> None:
        """Poster images should be <thumb aspect='poster'>."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        posters = root.findall("thumb[@aspect='poster']")
        assert len(posters) >= 1
        assert "original" in posters[0].text
        assert "w342" in posters[0].get("preview", "")

    def test_fanart_backdrops(self, generator: NFOGenerator) -> None:
        """Backdrop images should be in <fanart><thumb>."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        fanart = root.find("fanart")
        assert fanart is not None
        thumbs = fanart.findall("thumb")
        assert len(thumbs) >= 1
        assert "original" in thumbs[0].text
        assert "w780" in thumbs[0].get("preview", "")


# ---------------------------------------------------------------------------
# Movie NFO — streamdetails
# ---------------------------------------------------------------------------

class TestMovieNFOStreamdetails:
    """Tests for streamdetails integration."""

    def test_streamdetails_present(self, generator: NFOGenerator) -> None:
        """Streamdetails should be present when stream_info is provided."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        sd = root.find(".//streamdetails")
        assert sd is not None

    def test_video_details(self, generator: NFOGenerator) -> None:
        """Video codec, resolution, and duration should match."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        video = root.find(".//streamdetails/video")
        assert video is not None
        assert video.findtext("codec") == "hevc"
        assert video.findtext("width") == "3840"
        assert video.findtext("height") == "2160"
        assert video.findtext("aspect") == "1.778"
        assert video.findtext("durationinseconds") == "7627"
        assert video.findtext("scantype") == "progressive"

    def test_audio_tracks(self, generator: NFOGenerator) -> None:
        """Audio tracks should all be present."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        audio = root.findall(".//streamdetails/audio")
        assert len(audio) == 2
        assert audio[0].findtext("language") == "fra"
        assert audio[0].findtext("codec") == "eac3"
        assert audio[1].findtext("codec") == "atmos"

    def test_subtitle_tracks(self, generator: NFOGenerator) -> None:
        """Subtitle tracks should all be present."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        subs = root.findall(".//streamdetails/subtitle")
        assert len(subs) == 2
        assert subs[0].findtext("language") == "fra"
        assert subs[1].findtext("language") == "eng"

    def test_no_streamdetails_without_info(self, generator: NFOGenerator) -> None:
        """Streamdetails should be absent when stream_info is None."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.find(".//streamdetails") is None


# ---------------------------------------------------------------------------
# Movie NFO — generator tag
# ---------------------------------------------------------------------------

class TestMovieNFOGenerator:
    """Tests for the generator tag."""

    def test_generator_appname(self, generator: NFOGenerator) -> None:
        """Generator tag should identify personalscraper."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        appname = root.findtext(".//generator/appname")
        assert appname == "personalscraper"

    def test_xml_is_parseable(self, generator: NFOGenerator) -> None:
        """Generated XML should be valid and parseable."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA, SAMPLE_STREAM_INFO)
        # Should not raise
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag == "movie"


# ---------------------------------------------------------------------------
# write_nfo
# ---------------------------------------------------------------------------

class TestWriteNFO:
    """Tests for write_nfo file output."""

    def test_write_nfo_creates_file(self, generator: NFOGenerator, tmp_path: ...) -> None:
        """write_nfo should create a UTF-8 file."""
        xml = generator.generate_movie_nfo(SAMPLE_MOVIE_DATA)
        nfo_path = tmp_path / "test.nfo"
        generator.write_nfo(xml, nfo_path)

        assert nfo_path.exists()
        content = nfo_path.read_text(encoding="utf-8")
        assert content.startswith('<?xml version="1.0"')
        assert "<movie>" in content
