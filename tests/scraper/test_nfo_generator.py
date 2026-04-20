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


# ---------------------------------------------------------------------------
# Sample TV show data (matching TMDB get_tv() response for Fallout)
# ---------------------------------------------------------------------------

SAMPLE_TVSHOW_DATA = {
    "id": 106379,
    "name": "Fallout",
    "original_name": "Fallout",
    "overview": "Une terrible catastrophe nucléaire...",
    "vote_average": 8.142,
    "vote_count": 2493,
    "genres": [
        {"id": 10759, "name": "Action & Adventure"},
        {"id": 10765, "name": "Science-Fiction & Fantastique"},
    ],
    "first_air_date": "2024-04-10",
    "status": "Returning Series",
    "networks": [{"name": "Prime Video"}],
    "production_companies": [{"name": "Bethesda Game Studios"}],
    "origin_country": ["US"],
    "number_of_episodes": 9,
    "number_of_seasons": 2,
    "external_ids": {
        "imdb_id": "tt12637874",
        "tvdb_id": 416744,
    },
    "aggregate_credits": {
        "cast": [
            {
                "name": "Ella Purnell",
                "roles": [{"character": "Lucy MacLean"}],
                "order": 0,
                "profile_path": "/5PscK9HNXGFQMIxkpbR8ObB7vuR.jpg",
            },
            {
                "name": "Aaron Moten",
                "roles": [{"character": "Maximus"}],
                "order": 1,
                "profile_path": "/h2CJjnDEy2nCbCy6dWzXLmZ4p47.jpg",
            },
        ],
    },
    "images": {
        "posters": [
            {"file_path": "/eyG7Rb6r4oIYQR07qUVq0gJ2gDj.jpg", "iso_639_1": "fr", "vote_average": 5.3},
        ],
        "backdrops": [
            {"file_path": "/cIgHBLTMbcIkS0yvIrUUVVKLdOz.jpg", "iso_639_1": None, "vote_average": 5.5},
        ],
    },
    "content_ratings": {
        "results": [
            {"iso_3166_1": "US", "rating": "TV-MA"},
        ],
    },
    "keywords": {
        "results": [
            {"name": "nuclear war"},
            {"name": "vault"},
            {"name": "post-apocalyptic future"},
        ],
    },
}

SAMPLE_EPISODE_DATA = {
    "name": "La Fin",
    "showtitle": "Fallout",
    "id": 2362884,
    "tvdb_id": "",
    "season_number": 1,
    "episode_number": 1,
    "overview": "Fille du superviseur de l'Abri 33...",
    "air_date": "2024-04-10",
    "vote_average": 7.6,
    "vote_count": 135,
    "mpaa": "TV-MA",
    "studio": "Prime Video",
    "still_path": "/sEQLaNLxV6zX22ESkTlbXFDROKK.jpg",
    "crew": [
        {"name": "Geneva Robertson-Dworet", "job": "Writer"},
        {"name": "Graham Wagner", "job": "Writer"},
        {"name": "Jonathan Nolan", "job": "Director"},
    ],
}

# Multi-season show data (Invincible-inspired, 4 seasons)
SAMPLE_MULTISEASON_DATA = {
    "id": 95557,
    "name": "Invincible",
    "original_name": "Invincible",
    "overview": "Mark Grayson is a normal teenager...",
    "vote_average": 8.6,
    "vote_count": 4200,
    "genres": [{"id": 16, "name": "Animation"}, {"id": 10759, "name": "Action & Adventure"}],
    "first_air_date": "2021-03-25",
    "status": "Returning Series",
    "networks": [{"name": "Amazon"}],
    "origin_country": ["US"],
    "number_of_episodes": 30,
    "number_of_seasons": 4,
    "external_ids": {"imdb_id": "tt6741278", "tvdb_id": 349834},
    "aggregate_credits": {"cast": []},
    "images": {"posters": [], "backdrops": []},
    "content_ratings": {"results": []},
    "keywords": {"results": []},
}


# ---------------------------------------------------------------------------
# TV show NFO — base structure
# ---------------------------------------------------------------------------


class TestTvshowNFOBase:
    """Tests for basic tvshow NFO structure."""

    def test_xml_declaration(self, generator: NFOGenerator) -> None:
        """NFO should start with XML declaration."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')

    def test_root_element(self, generator: NFOGenerator) -> None:
        """Root element should be <tvshow>."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag == "tvshow"

    def test_title(self, generator: NFOGenerator) -> None:
        """Title should match show name."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("title") == "Fallout"

    def test_showtitle_empty(self, generator: NFOGenerator) -> None:
        """Showtitle should be empty (MediaElch convention)."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.find("showtitle") is not None
        assert root.findtext("showtitle") == ""

    def test_originaltitle(self, generator: NFOGenerator) -> None:
        """Original title should be present."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("originaltitle") == "Fallout"


# ---------------------------------------------------------------------------
# TV show NFO — IDs
# ---------------------------------------------------------------------------


class TestTvshowNFOIds:
    """Tests for uniqueids in tvshow NFO (TMDB is default)."""

    def test_uniqueid_tmdb_default(self, generator: NFOGenerator) -> None:
        """TMDB uniqueid should be default for TV shows."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        tmdb_id = root.find("uniqueid[@type='tmdb']")
        assert tmdb_id is not None
        assert tmdb_id.text == "106379"
        assert tmdb_id.get("default") == "true"

    def test_uniqueid_tvdb(self, generator: NFOGenerator) -> None:
        """TVDB uniqueid should be present."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        tvdb_id = root.find("uniqueid[@type='tvdb']")
        assert tvdb_id is not None
        assert tvdb_id.text == "416744"

    def test_uniqueid_imdb(self, generator: NFOGenerator) -> None:
        """IMDB uniqueid should be present (not default)."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        imdb_id = root.find("uniqueid[@type='imdb']")
        assert imdb_id is not None
        assert imdb_id.text == "tt12637874"
        assert imdb_id.get("default") is None

    def test_id_is_tmdb(self, generator: NFOGenerator) -> None:
        """<id> should contain TMDB ID for TV shows."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("id") == "106379"

    def test_episodeguide(self, generator: NFOGenerator) -> None:
        """Episodeguide should contain TMDB ID."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("episodeguide") == "106379"


# ---------------------------------------------------------------------------
# TV show NFO — ratings and metadata
# ---------------------------------------------------------------------------


class TestTvshowNFOMetadata:
    """Tests for ratings, counts, and metadata fields."""

    def test_ratings(self, generator: NFOGenerator) -> None:
        """Ratings should use name='themoviedb' for TV shows."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        rating = root.find(".//rating[@name='themoviedb']")
        assert rating is not None
        assert rating.findtext("value") == "8.142"
        assert rating.findtext("votes") == "2493"

    def test_episode_count(self, generator: NFOGenerator) -> None:
        """Episode count should be present."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("episode") == "9"

    def test_season_count(self, generator: NFOGenerator) -> None:
        """Season count should be present."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("season") == "2"

    def test_premiered_and_year(self, generator: NFOGenerator) -> None:
        """Premiered and year should be extracted."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("premiered") == "2024-04-10"
        assert root.findtext("year") == "2024"

    def test_status(self, generator: NFOGenerator) -> None:
        """Status should be present."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("status") == "Returning Series"

    def test_studio_from_networks(self, generator: NFOGenerator) -> None:
        """Studio should come from networks for TV shows."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        studios = [s.text for s in root.findall("studio")]
        assert "Prime Video" in studios

    def test_genres(self, generator: NFOGenerator) -> None:
        """Genres should be listed as separate elements."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        genres = [g.text for g in root.findall("genre")]
        assert "Action & Adventure" in genres
        assert "Science-Fiction & Fantastique" in genres

    def test_tags_from_keywords(self, generator: NFOGenerator) -> None:
        """Tags should come from TMDB keywords."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        tags = [t.text for t in root.findall("tag")]
        assert "nuclear war" in tags
        assert "vault" in tags


# ---------------------------------------------------------------------------
# TV show NFO — actors and images
# ---------------------------------------------------------------------------


class TestTvshowNFOActorsImages:
    """Tests for actors and inline images in tvshow NFO."""

    def test_actors_with_roles(self, generator: NFOGenerator) -> None:
        """Actors should have name, role (from aggregate_credits), order, thumb."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        actors = root.findall("actor")
        assert len(actors) >= 2
        assert actors[0].findtext("name") == "Ella Purnell"
        assert actors[0].findtext("role") == "Lucy MacLean"
        assert actors[0].findtext("order") == "0"

    def test_poster_thumb(self, generator: NFOGenerator) -> None:
        """First poster should have aspect='poster'."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        poster = root.find("thumb[@aspect='poster']")
        assert poster is not None
        assert "original" in poster.text

    def test_fanart(self, generator: NFOGenerator) -> None:
        """Fanart should contain backdrop thumbs."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        fanart = root.find("fanart")
        assert fanart is not None
        thumbs = fanart.findall("thumb")
        assert len(thumbs) >= 1

    def test_generator(self, generator: NFOGenerator) -> None:
        """Generator tag should identify personalscraper."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext(".//generator/appname") == "personalscraper"


# ---------------------------------------------------------------------------
# TV show NFO — multi-season
# ---------------------------------------------------------------------------


class TestTvshowNFOMultiSeason:
    """Tests with multi-season show data."""

    def test_multiseason_counts(self, generator: NFOGenerator) -> None:
        """Multi-season show should have correct episode/season counts."""
        xml = generator.generate_tvshow_nfo(SAMPLE_MULTISEASON_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("episode") == "30"
        assert root.findtext("season") == "4"

    def test_multiseason_xml_valid(self, generator: NFOGenerator) -> None:
        """Multi-season NFO should be valid XML."""
        xml = generator.generate_tvshow_nfo(SAMPLE_MULTISEASON_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag == "tvshow"
        assert root.findtext("title") == "Invincible"


# ---------------------------------------------------------------------------
# TV show NFO — MediaElch conformity
# ---------------------------------------------------------------------------


class TestTvshowMediaElchConformity:
    """Verify our tvshow NFO structure matches MediaElch output.

    Compares the set of first-level child tags against a real MediaElch
    tvshow.nfo from Fallout (2024). Checks structural conformity, not
    exact text values (since our sample data may differ slightly).
    """

    # Tags present in a real MediaElch tvshow.nfo (Fallout 2024)
    MEDIAELCH_TAGS = {
        "title",
        "showtitle",
        "originaltitle",
        "uniqueid",
        "id",
        "ratings",
        "userrating",
        "top250",
        "episode",
        "season",
        "plot",
        "mpaa",
        "premiered",
        "year",
        "dateadded",
        "status",
        "studio",
        "trailer",
        "episodeguide",
        "genre",
        "tag",
        "thumb",
        "fanart",
        "actor",
        "generator",
    }

    def test_all_mediaelch_tags_present(self, generator: NFOGenerator) -> None:
        """Our NFO should contain all tags that MediaElch generates."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        our_tags = {child.tag for child in root}
        missing = self.MEDIAELCH_TAGS - our_tags
        assert not missing, f"Missing MediaElch tags: {missing}"

    def test_uniqueid_types_match(self, generator: NFOGenerator) -> None:
        """Uniqueid types should match MediaElch: tmdb (default), tvdb, imdb."""
        xml = generator.generate_tvshow_nfo(SAMPLE_TVSHOW_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        uids = root.findall("uniqueid")
        types = {u.get("type") for u in uids}
        assert types == {"tmdb", "tvdb", "imdb"}
        # TMDB should be default for TV shows
        default_uid = [u for u in uids if u.get("default") == "true"]
        assert len(default_uid) == 1
        assert default_uid[0].get("type") == "tmdb"


# ---------------------------------------------------------------------------
# Episode NFO — base structure
# ---------------------------------------------------------------------------


class TestEpisodeNFOBase:
    """Tests for basic episodedetails NFO structure."""

    def test_xml_declaration(self, generator: NFOGenerator) -> None:
        """NFO should start with XML declaration."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')

    def test_root_element(self, generator: NFOGenerator) -> None:
        """Root element should be <episodedetails>."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag == "episodedetails"

    def test_title(self, generator: NFOGenerator) -> None:
        """Title should match episode name."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("title") == "La Fin"

    def test_showtitle(self, generator: NFOGenerator) -> None:
        """Showtitle should contain the show name."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("showtitle") == "Fallout"


# ---------------------------------------------------------------------------
# Episode NFO — IDs and ratings
# ---------------------------------------------------------------------------


class TestEpisodeNFOIds:
    """Tests for uniqueids and ratings in episode NFO."""

    def test_uniqueid_tvdb_default(self, generator: NFOGenerator) -> None:
        """TVDB uniqueid should be default for episodes."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        tvdb_uid = root.find("uniqueid[@type='tvdb']")
        assert tvdb_uid is not None
        assert tvdb_uid.get("default") == "true"

    def test_uniqueid_tmdb(self, generator: NFOGenerator) -> None:
        """TMDB uniqueid should be present."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        tmdb_uid = root.find("uniqueid[@type='tmdb']")
        assert tmdb_uid is not None
        assert tmdb_uid.text == "2362884"

    def test_ratings_tmdb_name(self, generator: NFOGenerator) -> None:
        """Episode ratings should use name='tmdb' (not 'themoviedb')."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        rating = root.find(".//rating[@name='tmdb']")
        assert rating is not None
        assert rating.get("default") == "true"
        assert rating.findtext("value") == "7.6"
        assert rating.findtext("votes") == "135"


# ---------------------------------------------------------------------------
# Episode NFO — metadata
# ---------------------------------------------------------------------------


class TestEpisodeNFOMetadata:
    """Tests for episode metadata fields."""

    def test_season_episode(self, generator: NFOGenerator) -> None:
        """Season and episode numbers should be present."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("season") == "1"
        assert root.findtext("episode") == "1"

    def test_mpaa(self, generator: NFOGenerator) -> None:
        """MPAA should contain content rating from show."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("mpaa") == "TV-MA"

    def test_aired(self, generator: NFOGenerator) -> None:
        """Aired date should be present."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("aired") == "2024-04-10"

    def test_studio(self, generator: NFOGenerator) -> None:
        """Studio should be inherited from show."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.findtext("studio") == "Prime Video"


# ---------------------------------------------------------------------------
# Episode NFO — credits and director
# ---------------------------------------------------------------------------


class TestEpisodeNFOCredits:
    """Tests for writers and director in episode NFO."""

    def test_credits_writers(self, generator: NFOGenerator) -> None:
        """Writers should be listed as <credits> elements."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        credits = [c.text for c in root.findall("credits")]
        assert "Geneva Robertson-Dworet" in credits
        assert "Graham Wagner" in credits

    def test_director(self, generator: NFOGenerator) -> None:
        """Director should be present."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        directors = [d.text for d in root.findall("director")]
        assert "Jonathan Nolan" in directors

    def test_thumb(self, generator: NFOGenerator) -> None:
        """Episode thumb should be present with still_path."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        thumb = root.findtext("thumb")
        assert thumb is not None
        assert "original" in thumb
        assert "sEQLaNLxV6zX22ESkTlbXFDROKK" in thumb


# ---------------------------------------------------------------------------
# Episode NFO — streamdetails
# ---------------------------------------------------------------------------


class TestEpisodeNFOStreamdetails:
    """Tests for streamdetails in episode NFO."""

    def test_streamdetails_present(self, generator: NFOGenerator) -> None:
        """Streamdetails should be present when stream_info is provided."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        sd = root.find(".//streamdetails")
        assert sd is not None

    def test_video_details(self, generator: NFOGenerator) -> None:
        """Video codec, resolution should match."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        video = root.find(".//streamdetails/video")
        assert video is not None
        assert video.findtext("codec") == "hevc"
        assert video.findtext("width") == "3840"
        assert video.findtext("height") == "2160"

    def test_no_streamdetails_without_info(self, generator: NFOGenerator) -> None:
        """Streamdetails should be absent when stream_info is None."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.find(".//streamdetails") is None


# ---------------------------------------------------------------------------
# Episode NFO — MediaElch conformity
# ---------------------------------------------------------------------------


class TestEpisodeMediaElchConformity:
    """Verify our episode NFO structure matches MediaElch output.

    Compares the set of first-level child tags against a real MediaElch
    episode NFO from Fallout S01E01.
    """

    # Tags present in a real MediaElch episode NFO (Fallout S01E01)
    MEDIAELCH_TAGS = {
        "title",
        "showtitle",
        "uniqueid",
        "ratings",
        "userrating",
        "top250",
        "season",
        "episode",
        "plot",
        "mpaa",
        "playcount",
        "lastplayed",
        "aired",
        "studio",
        "credits",
        "director",
        "thumb",
        "fileinfo",
        "generator",
    }

    def test_all_mediaelch_tags_present(self, generator: NFOGenerator) -> None:
        """Our NFO should contain all tags that MediaElch generates."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        our_tags = {child.tag for child in root}
        missing = self.MEDIAELCH_TAGS - our_tags
        assert not missing, f"Missing MediaElch tags: {missing}"

    def test_uniqueid_types_match(self, generator: NFOGenerator) -> None:
        """Uniqueid types should match MediaElch: tvdb (default), tmdb."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        uids = root.findall("uniqueid")
        types = {u.get("type") for u in uids}
        assert types == {"tvdb", "tmdb"}
        # TVDB should be default for episodes
        default_uid = [u for u in uids if u.get("default") == "true"]
        assert len(default_uid) == 1
        assert default_uid[0].get("type") == "tvdb"

    def test_rating_name_tmdb(self, generator: NFOGenerator) -> None:
        """Episode ratings should use 'tmdb' (MediaElch convention)."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA)
        root = ET.fromstring(xml.split("\n", 1)[1])
        rating = root.find(".//rating")
        assert rating is not None
        assert rating.get("name") == "tmdb"

    def test_xml_is_parseable(self, generator: NFOGenerator) -> None:
        """Generated XML should be valid and parseable."""
        xml = generator.generate_episode_nfo(SAMPLE_EPISODE_DATA, SAMPLE_STREAM_INFO)
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert root.tag == "episodedetails"
