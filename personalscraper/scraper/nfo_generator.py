"""Kodi-compatible NFO XML generator (MediaElch format).

Generates movie, tvshow, and episodedetails NFO files that match
the structure produced by MediaElch. Uses xml.etree.ElementTree
for XML construction with manual pretty-printing for readability.

The XML structure has been validated against real MediaElch NFO files
from the 001-MOVIES/ directory.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

# Preview image sizes for inline thumbs
POSTER_PREVIEW_SIZE = "w342"
BACKDROP_PREVIEW_SIZE = "w780"
ACTOR_THUMB_SIZE = "original"
IMAGE_BASE = "http://image.tmdb.org/t/p"


def _sub(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    """Add a sub-element with optional text content.

    Args:
        parent: Parent XML element.
        tag: Element tag name.
        text: Text content (empty string if omitted).

    Returns:
        The newly created sub-element.
    """
    elem = ET.SubElement(parent, tag)
    elem.text = str(text)
    return elem


def _indent(elem: ET.Element, level: int = 0) -> None:
    """Add indentation to XML tree for pretty printing.

    Args:
        elem: Root element to indent.
        level: Current indentation depth.
    """
    indent = "\n" + "    " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        last_child = None
        for child in elem:
            _indent(child, level + 1)
            last_child = child
        if last_child is not None and (not last_child.tail or not last_child.tail.strip()):
            last_child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent


class NFOGenerator:
    """Generate Kodi-compatible .nfo XML files (MediaElch format).

    Produces XML that matches the structure of MediaElch-generated NFO files,
    including ratings, uniqueids, inline thumbs, streamdetails, and actors.
    """

    def generate_movie_nfo(self, movie_data: dict, stream_info: dict | None = None) -> str:
        """Generate a <movie> NFO XML string.

        Produces XML matching MediaElch output structure. Fields are mapped
        from TMDB API response format to Kodi NFO format.

        Args:
            movie_data: TMDB movie details dict (from get_movie()).
            stream_info: Stream details dict from extract_stream_info(), or None.

        Returns:
            UTF-8 XML string with <?xml?> declaration.
        """
        root = ET.Element("movie")

        # --- Basic metadata ---
        _sub(root, "title", movie_data.get("title", ""))
        self._add_ratings(root, movie_data)
        _sub(root, "userrating", "0")
        _sub(root, "top250", "0")
        _sub(root, "outline", movie_data.get("overview", ""))
        _sub(root, "plot", movie_data.get("overview", ""))
        _sub(root, "tagline", movie_data.get("tagline", ""))
        _sub(root, "runtime", str(movie_data.get("runtime", 0)))

        # --- Inline images (posters + fanart) ---
        self._add_inline_images(root, movie_data)

        # --- Classification ---
        _sub(root, "mpaa", self._extract_certification_fr(movie_data))
        _sub(root, "playcount", "0")
        _sub(root, "lastplayed", "")

        # --- IDs ---
        external_ids = movie_data.get("external_ids", {})
        imdb_id = external_ids.get("imdb_id", "")
        tmdb_id = str(movie_data.get("id", ""))

        _sub(root, "id", imdb_id)
        uniqueid_imdb = _sub(root, "uniqueid", imdb_id)
        uniqueid_imdb.set("default", "true")
        uniqueid_imdb.set("type", "imdb")
        uniqueid_tmdb = _sub(root, "uniqueid", tmdb_id)
        uniqueid_tmdb.set("type", "tmdb")

        # --- Genres ---
        for genre in movie_data.get("genres", []):
            _sub(root, "genre", genre.get("name", ""))

        # --- Country ---
        for country in movie_data.get("production_countries", []):
            _sub(root, "country", country.get("name", ""))

        # --- Credits (writers) ---
        credits_data = movie_data.get("credits", {})
        for crew in credits_data.get("crew", []):
            if crew.get("job") in ("Writer", "Screenplay", "Story"):
                _sub(root, "credits", crew.get("name", ""))

        # --- Director ---
        for crew in credits_data.get("crew", []):
            if crew.get("job") == "Director":
                _sub(root, "director", crew.get("name", ""))

        # --- Dates ---
        premiered = movie_data.get("release_date", "")
        _sub(root, "premiered", premiered)
        year = premiered[:4] if premiered and len(premiered) >= 4 else ""
        _sub(root, "year", year)

        # --- Studios ---
        for studio in movie_data.get("production_companies", []):
            _sub(root, "studio", studio.get("name", ""))

        _sub(root, "trailer", "")

        # --- Streamdetails ---
        if stream_info:
            self._add_streamdetails(root, stream_info)

        # --- Actors ---
        for actor in credits_data.get("cast", []):
            self._add_actor(root, actor)

        # --- Generator ---
        generator = ET.SubElement(root, "generator")
        _sub(generator, "appname", "personalscraper")

        _indent(root)
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(
            root, encoding="unicode",
        )

    def generate_tvshow_nfo(self, show_data: dict) -> str:
        """Generate a <tvshow> NFO XML string.

        Args:
            show_data: TMDB or TVDB show details dict.

        Returns:
            UTF-8 XML string with <?xml?> declaration.
        """
        root = ET.Element("tvshow")

        _sub(root, "title", show_data.get("name", show_data.get("title", "")))
        self._add_ratings(root, show_data)
        _sub(root, "userrating", "0")
        _sub(root, "plot", show_data.get("overview", ""))
        _sub(root, "mpaa", self._extract_content_rating_fr(show_data))

        # IDs
        external_ids = show_data.get("external_ids", {})
        imdb_id = external_ids.get("imdb_id", "")
        tmdb_id = str(show_data.get("id", ""))
        tvdb_id = str(external_ids.get("tvdb_id", ""))

        _sub(root, "id", imdb_id)
        uniqueid_imdb = _sub(root, "uniqueid", imdb_id)
        uniqueid_imdb.set("default", "true")
        uniqueid_imdb.set("type", "imdb")
        uniqueid_tmdb = _sub(root, "uniqueid", tmdb_id)
        uniqueid_tmdb.set("type", "tmdb")
        if tvdb_id and tvdb_id != "None":
            uniqueid_tvdb = _sub(root, "uniqueid", tvdb_id)
            uniqueid_tvdb.set("type", "tvdb")

        for genre in show_data.get("genres", []):
            _sub(root, "genre", genre.get("name", ""))

        premiered = show_data.get("first_air_date", "")
        _sub(root, "premiered", premiered)
        year = premiered[:4] if premiered and len(premiered) >= 4 else ""
        _sub(root, "year", year)

        _sub(root, "status", show_data.get("status", ""))

        for studio in show_data.get("production_companies", show_data.get("networks", [])):
            _sub(root, "studio", studio.get("name", ""))

        # Actors (aggregate_credits for TMDB TV)
        credits_data = show_data.get("aggregate_credits", show_data.get("credits", {}))
        for actor in credits_data.get("cast", []):
            self._add_actor_tv(root, actor)

        generator = ET.SubElement(root, "generator")
        _sub(generator, "appname", "personalscraper")

        _indent(root)
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(
            root, encoding="unicode",
        )

    def generate_episode_nfo(self, episode_data: dict, stream_info: dict | None = None) -> str:
        """Generate an <episodedetails> NFO XML string.

        Args:
            episode_data: Episode dict from TMDB/TVDB API.
            stream_info: Stream details dict from extract_stream_info(), or None.

        Returns:
            UTF-8 XML string with <?xml?> declaration.
        """
        root = ET.Element("episodedetails")

        _sub(root, "title", episode_data.get("name", ""))
        _sub(root, "season", str(episode_data.get("season_number", episode_data.get("seasonNumber", 0))))
        _sub(root, "episode", str(episode_data.get("episode_number", episode_data.get("number", 0))))
        _sub(root, "plot", episode_data.get("overview", ""))
        _sub(root, "runtime", str(episode_data.get("runtime", 0)))
        _sub(root, "aired", episode_data.get("air_date", episode_data.get("aired", "")))

        if stream_info:
            self._add_streamdetails(root, stream_info)

        generator = ET.SubElement(root, "generator")
        _sub(generator, "appname", "personalscraper")

        _indent(root)
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(
            root, encoding="unicode",
        )

    def write_nfo(self, xml_content: str, path: Path) -> None:
        """Write NFO XML content to a file.

        Args:
            xml_content: UTF-8 XML string to write.
            path: Destination file path.
        """
        path.write_text(xml_content, encoding="utf-8")

    # --- Private helpers ---

    def _add_ratings(self, root: ET.Element, data: dict) -> None:
        """Add <ratings> element with TMDB rating.

        Args:
            root: Parent XML element.
            data: API data with vote_average and vote_count.
        """
        ratings = ET.SubElement(root, "ratings")
        rating = ET.SubElement(ratings, "rating")
        rating.set("name", "themoviedb")
        rating.set("default", "true")
        rating.set("max", "10")
        _sub(rating, "value", str(data.get("vote_average", 0)))
        _sub(rating, "votes", str(data.get("vote_count", 0)))

    def _add_inline_images(self, root: ET.Element, data: dict) -> None:
        """Add inline <thumb> and <fanart> elements.

        Args:
            root: Parent XML element.
            data: API data with images.posters and images.backdrops.
        """
        images = data.get("images", {})

        # Posters as <thumb aspect="poster">
        for img in images.get("posters", []):
            path = img.get("file_path", "")
            thumb = _sub(root, "thumb", f"{IMAGE_BASE}/original{path}")
            thumb.set("aspect", "poster")
            thumb.set("preview", f"{IMAGE_BASE}/{POSTER_PREVIEW_SIZE}{path}")

        # Backdrops as <fanart><thumb>
        backdrops = images.get("backdrops", [])
        if backdrops:
            fanart = ET.SubElement(root, "fanart")
            for img in backdrops:
                path = img.get("file_path", "")
                thumb = _sub(fanart, "thumb", f"{IMAGE_BASE}/original{path}")
                thumb.set("preview", f"{IMAGE_BASE}/{BACKDROP_PREVIEW_SIZE}{path}")

    def _add_streamdetails(self, root: ET.Element, stream_info: dict) -> None:
        """Add <fileinfo><streamdetails> element.

        Args:
            root: Parent XML element.
            stream_info: Dict from extract_stream_info().
        """
        fileinfo = ET.SubElement(root, "fileinfo")
        sd = ET.SubElement(fileinfo, "streamdetails")

        # Video
        video_info = stream_info.get("video", {})
        video = ET.SubElement(sd, "video")
        _sub(video, "durationinseconds", str(stream_info.get("duration_seconds", 0)))
        _sub(video, "codec", video_info.get("codec", ""))
        _sub(video, "aspect", str(video_info.get("aspect", 0)))
        _sub(video, "width", str(video_info.get("width", 0)))
        _sub(video, "height", str(video_info.get("height", 0)))
        _sub(video, "scantype", video_info.get("scantype", "progressive"))

        # Audio tracks
        for track in stream_info.get("audio", []):
            audio = ET.SubElement(sd, "audio")
            _sub(audio, "language", track.get("language", ""))
            _sub(audio, "codec", track.get("codec", ""))
            _sub(audio, "channels", str(track.get("channels", 0)))

        # Subtitle tracks
        for track in stream_info.get("subtitle", []):
            subtitle = ET.SubElement(sd, "subtitle")
            _sub(subtitle, "language", track.get("language", ""))

    def _add_actor(self, root: ET.Element, actor: dict) -> None:
        """Add an <actor> element for movie credits.

        Args:
            root: Parent XML element.
            actor: Actor dict from TMDB credits.cast.
        """
        actor_elem = ET.SubElement(root, "actor")
        _sub(actor_elem, "name", actor.get("name", ""))
        _sub(actor_elem, "role", actor.get("character", ""))
        _sub(actor_elem, "order", str(actor.get("order", 0)))
        profile = actor.get("profile_path", "")
        thumb_url = f"{IMAGE_BASE}/{ACTOR_THUMB_SIZE}{profile}" if profile else ""
        _sub(actor_elem, "thumb", thumb_url)

    def _add_actor_tv(self, root: ET.Element, actor: dict) -> None:
        """Add an <actor> element for TV show aggregate credits.

        Handles aggregate_credits format where roles[] replaces character.

        Args:
            root: Parent XML element.
            actor: Actor dict from TMDB aggregate_credits.cast.
        """
        actor_elem = ET.SubElement(root, "actor")
        _sub(actor_elem, "name", actor.get("name", ""))
        # aggregate_credits uses roles[] instead of character
        roles = actor.get("roles", [])
        character = roles[0].get("character", "") if roles else actor.get("character", "")
        _sub(actor_elem, "role", character)
        _sub(actor_elem, "order", str(actor.get("order", 0)))
        profile = actor.get("profile_path", "")
        thumb_url = f"{IMAGE_BASE}/{ACTOR_THUMB_SIZE}{profile}" if profile else ""
        _sub(actor_elem, "thumb", thumb_url)

    @staticmethod
    def _extract_certification_fr(movie_data: dict) -> str:
        """Extract French theatrical certification from release_dates.

        Looks for iso_3166_1=="FR" with type==3 (theatrical release).

        Args:
            movie_data: TMDB movie details dict.

        Returns:
            Certification string, or empty string if not found.
        """
        for release in movie_data.get("release_dates", {}).get("results", []):
            if release.get("iso_3166_1") == "FR":
                for rd in release.get("release_dates", []):
                    if rd.get("type") == 3:
                        return rd.get("certification", "")
        return ""

    @staticmethod
    def _extract_content_rating_fr(show_data: dict) -> str:
        """Extract French content rating for TV shows.

        Args:
            show_data: TMDB TV show details dict.

        Returns:
            Rating string, or empty string if not found.
        """
        for rating in show_data.get("content_ratings", {}).get("results", []):
            if rating.get("iso_3166_1") == "FR":
                return rating.get("rating", "")
        return ""
