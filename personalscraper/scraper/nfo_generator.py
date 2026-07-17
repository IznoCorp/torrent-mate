"""Kodi-compatible NFO XML generator (MediaElch format).

Generates movie, tvshow, and episodedetails NFO files that match
the structure produced by MediaElch. Uses xml.etree.ElementTree
for XML construction with manual pretty-printing for readability.

The XML structure has been validated against real MediaElch NFO files
from the {movies_dir}/ directory.
"""

import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from personalscraper.api.metadata._base import Notations
from personalscraper.indexer.outbox._disk import disk_id_for_path
from personalscraper.indexer.outbox._publish import publish_event
from personalscraper.io_utils import atomic_write_text
from personalscraper.logger import get_logger

log = get_logger("scraper.nfo_generator")

# Preview image sizes for inline thumbs
POSTER_PREVIEW_SIZE = "w342"
BACKDROP_PREVIEW_SIZE = "w780"
ACTOR_THUMB_SIZE = "original"
IMAGE_BASE = "https://image.tmdb.org/t/p"

# Translate the internal ``Notations.source`` literal into the NFO /
# Plex source identifier expected by readers (Plex, Kodi, MediaElch).
_NFO_RATING_SOURCE_NAMES: dict[str, str] = {
    "imdb": "imdb",
    "tmdb": "themoviedb",
    "rotten_tomatoes": "rottentomatoes",
    "metacritic": "metacritic",
    "trakt": "trakt",
}

# Value range per source. Plex/Kodi readers compute the visible
# percentage from ``value / max`` ; mismatching the range produces a
# rating that looks off by an order of magnitude.
_NFO_RATING_MAX: dict[str, int] = {
    "imdb": 10,
    "themoviedb": 10,
    "trakt": 10,
    "metacritic": 100,
    "rottentomatoes": 100,
}


def _image_url(path: str, size: str = "original") -> str:
    """Build an image URL, leaving absolute URLs untouched.

    TMDB returns relative paths (``/abcd.jpg``) that must be prefixed
    with ``https://image.tmdb.org/t/p/<size>``. TVDB (used as fallback
    when a show is absent from TMDB) returns absolute URLs already, so
    prefixing them again produces broken double URLs like
    ``https://image.tmdb.org/t/p/originalhttps://artworks.thetvdb.com/...``.

    Args:
        path: Either a TMDB relative path or an absolute URL.
        size: TMDB size bucket (e.g. ``original``, ``w342``).

    Returns:
        A usable image URL.
    """
    if path.startswith(("http://", "https://")):
        return path
    return f"{IMAGE_BASE}/{size}{path}"


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


def _strip_title_year(title: str, date: str) -> str:
    """Strip a trailing ``(YYYY)`` from a title when it matches the release year.

    Providers (TMDB movies, TVDB shows) occasionally bake the disambiguating
    year into the title itself (``INVINCIBLE (2021)``). Kodi/Plex NFO
    conventions expect ``<title>`` bare and ``<year>`` separate, so the
    trailing ``(YYYY)`` is removed only when it matches the four-digit year
    derived from ``date`` — never a parenthetical that is part of the real
    title. Shared by the movie and tvshow generators (SCRAPER-05).

    Args:
        title: Raw title as returned by the provider.
        date: Release / first-air date (``YYYY-MM-DD`` or empty); only its
            first four characters are consulted.

    Returns:
        The title with a matching trailing ``(YYYY)`` removed, else unchanged.
    """
    year_str = date[:4] if date else ""
    if year_str and title.endswith(f" ({year_str})"):
        return title[: -len(f" ({year_str})")]
    return title


def _clean_id(raw: Any) -> str:
    """Coerce a provider id to a clean string, mapping placeholders to ``""``.

    A missing provider id historically surfaced as ``None``, ``0``, ``"0"`` or
    the literal string ``"None"`` (from ``str(None)``). Written verbatim into a
    ``<uniqueid>`` those poison Kodi's scraper cache, so they collapse to the
    empty string, which :func:`_write_uniqueids` then omits. This is the single
    id guard shared by all three generators (SCRAPER-05); before it, the movie
    path applied no guard and could emit ``<uniqueid>None</uniqueid>``.

    Args:
        raw: Raw id value from a provider payload (any type).

    Returns:
        ``str(raw)`` for real ids, or ``""`` for the placeholder set.
    """
    return str(raw) if raw not in (None, 0, "0", "", "None") else ""


def _write_uniqueids(root: ET.Element, ids: Sequence[tuple[str, str]], canonical_family: str) -> None:
    """Write ordered ``<uniqueid>`` rows, skipping blanks and flagging one default.

    The single ``<uniqueid>`` writer shared by the movie, tvshow and episode
    generators (SCRAPER-05) — the episode's ordered/default logic generalised.
    ``ids`` is an ordered sequence of ``(family, value)`` pairs; empty values
    are skipped (a blank ``<uniqueid>`` is junk Kodi would still try to
    resolve). The first written row whose family equals ``canonical_family``
    receives ``default="true"`` — at most one row is ever flagged default.

    Args:
        root: Parent element to append the ``<uniqueid>`` rows to.
        ids: Ordered ``(family, value)`` pairs (e.g. ``[("tvdb", "42"), ...]``);
            already cleaned via :func:`_clean_id` so blanks mean "absent".
        canonical_family: Family whose row carries ``default="true"``; when its
            value is blank (or the family is not in ``ids``) no default is set.
    """
    default_applied = False
    for family, value in ids:
        if not value:
            continue
        element = _sub(root, "uniqueid", value)
        element.set("type", family)
        if not default_applied and family == canonical_family:
            element.set("default", "true")
            default_applied = True


class NFOGenerator:
    """Generate Kodi-compatible .nfo XML files (MediaElch format).

    Produces XML that matches the structure of MediaElch-generated NFO files,
    including ratings, uniqueids, inline thumbs, streamdetails, and actors.

    Attributes:
        _db_path: Path to the indexer SQLite database used for best-effort
            outbox publish on :meth:`write_nfo`.  ``None`` disables publishing.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialise the NFO generator.

        Args:
            db_path: Resolved ``Config.indexer.db_path`` passed through from
                the caller.  When ``None``, the write-through outbox publish
                in :meth:`write_nfo` is silently skipped (best-effort contract).
        """
        self._db_path = db_path

    def generate_movie_nfo(
        self,
        movie_data: dict[str, Any],
        stream_info: dict[str, Any] | None = None,
        category_id: str | None = None,
    ) -> str:
        """Generate a <movie> NFO XML string.

        Produces XML matching MediaElch output structure. Fields are mapped
        from TMDB API response format to Kodi NFO format.

        When ``category_id`` is provided, inserts
        ``<category source="personalscraper">{category_id}</category>``
        immediately after all ``<genre>`` elements. This element is used by
        ``classifier._read_nfo_category`` for priority-1 NFO override on
        subsequent pipeline runs.

        Args:
            movie_data: TMDB movie details dict (from get_movie()).
            stream_info: Stream details dict from extract_stream_info(), or None.
            category_id: Category ID to embed in NFO, or None to omit.

        Returns:
            UTF-8 XML string with <?xml?> declaration.
        """
        root = ET.Element("movie")

        # --- Basic metadata ---
        # TMDB occasionally returns titles with the year baked in for
        # disambiguation. Kodi/Plex expect ``<title>`` bare with ``<year>``
        # separate, so strip a trailing ``(YYYY)`` when it matches the
        # release year. Mirrors the same defensive logic applied to TV shows.
        raw_movie_title = movie_data.get("title", "")
        release_date = movie_data.get("release_date") or ""
        year_str = release_date[:4] if release_date else ""
        movie_title = raw_movie_title
        if year_str and movie_title.endswith(f" ({year_str})"):
            movie_title = movie_title[: -len(f" ({year_str})")]
        _sub(root, "title", movie_title)
        # Multi-source ratings (phase 6) : forward optional ``notations``
        # + ``canonical_source`` keys so callers that resolved
        # IMDb / Rotten Tomatoes ratings via _resolve_external_ids get a
        # one-row-per-source ``<ratings>`` block. Absent keys fall back
        # to the legacy single-row TMDb path.
        self._add_ratings(
            root,
            movie_data,
            notations=movie_data.get("notations"),
            canonical_source=movie_data.get("canonical_source"),
        )
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

        # --- Category (classifier output, written after genres for readability) ---
        if category_id is not None:
            cat_elem = _sub(root, "category", category_id)
            cat_elem.set("source", "personalscraper")

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
            root,
            encoding="unicode",
        )

    def generate_tvshow_nfo(
        self,
        show_data: dict[str, Any],
        category_id: str | None = None,
    ) -> str:
        """Generate a <tvshow> NFO XML string matching MediaElch format.

        Produces XML with the same tag structure and ordering as MediaElch.
        For TV shows, TMDB is the default uniqueid (unlike movies which use IMDB).

        When ``category_id`` is provided, inserts
        ``<category source="personalscraper">{category_id}</category>``
        immediately after all ``<genre>`` elements.

        Args:
            show_data: TMDB TV show details dict (from get_tv()).
            category_id: Category ID to embed in NFO, or None to omit.

        Returns:
            UTF-8 XML string with <?xml?> declaration.
        """
        root = ET.Element("tvshow")

        # --- Basic metadata ---
        # TVDB sometimes returns the disambiguating year inside the title
        # itself (e.g. ``INVINCIBLE (2021)``). Kodi/Plex NFO conventions
        # expect ``<title>`` to be the bare title and ``<year>`` to carry the
        # year separately, so strip a trailing ``(YYYY)`` when it matches the
        # year we're about to write below.
        raw_title = show_data.get("name", show_data.get("title", ""))
        first_aired = show_data.get("first_air_date") or show_data.get("firstAired") or ""
        year_str = first_aired[:4] if first_aired else ""
        title = raw_title
        if year_str and title.endswith(f" ({year_str})"):
            title = title[: -len(f" ({year_str})")]
        raw_original_title = show_data.get(
            "original_name",
            show_data.get("originalName", ""),
        )
        original_title = raw_original_title
        if year_str and original_title.endswith(f" ({year_str})"):
            original_title = original_title[: -len(f" ({year_str})")]
        _sub(root, "title", title)
        _sub(root, "showtitle", "")
        _sub(root, "originaltitle", original_title)

        # --- IDs (TVDB is canonical for TV shows; TMDB is the secondary
        # source). Kodi, Jellyfin, and most TV-aware libraries treat TVDB
        # as the authoritative TV database — TMDB's TV branch is a
        # secondary mirror with weaker localisation, less complete season
        # / episode data, and frequent year mismatches. The previous code
        # promoted TMDB as ``default`` because the show data was fetched
        # via TMDB; that was an artefact of the fetch path, not a metadata
        # decision. TVDB is now default whenever a TVDB id is available;
        # TMDB stays as a non-default fallback for downstream tools that
        # only know how to read TMDB.
        external_ids = show_data.get("external_ids") or {}
        imdb_id = external_ids.get("imdb_id") or ""
        raw_tmdb_id = show_data.get("id")
        raw_tvdb_id = external_ids.get("tvdb_id")
        tmdb_id = str(raw_tmdb_id) if raw_tmdb_id not in (None, 0, "0", "", "None") else ""
        tvdb_id = str(raw_tvdb_id) if raw_tvdb_id not in (None, 0, "0", "", "None") else ""

        tvdb_is_default = bool(tvdb_id)
        if tvdb_id:
            uniqueid_tvdb = _sub(root, "uniqueid", tvdb_id)
            uniqueid_tvdb.set("default", "true")
            uniqueid_tvdb.set("type", "tvdb")
        if tmdb_id:
            uniqueid_tmdb = _sub(root, "uniqueid", tmdb_id)
            if not tvdb_is_default:
                uniqueid_tmdb.set("default", "true")
            uniqueid_tmdb.set("type", "tmdb")
        uniqueid_imdb = _sub(root, "uniqueid", imdb_id)
        uniqueid_imdb.set("type", "imdb")
        # ``<id>`` mirrors the default uniqueid: TVDB when present, TMDB
        # otherwise. Consumers that only read ``<id>`` (e.g. legacy Kodi
        # add-ons) get the same id Kodi itself would resolve via uniqueid.
        _sub(root, "id", tvdb_id or tmdb_id)

        # --- Ratings (multi-source via optional ``notations``) ---
        self._add_ratings(
            root,
            show_data,
            notations=show_data.get("notations"),
            canonical_source=show_data.get("canonical_source"),
        )
        _sub(root, "userrating", "0")
        _sub(root, "top250", "0")

        # --- Episode and season counts ---
        _sub(root, "episode", str(show_data.get("number_of_episodes", 0)))
        _sub(root, "season", str(show_data.get("number_of_seasons", 0)))

        # --- Plot ---
        _sub(root, "plot", show_data.get("overview", ""))

        # --- Classification ---
        _sub(root, "mpaa", self._extract_content_rating_fr(show_data))

        # --- Dates ---
        premiered = show_data.get("first_air_date", "")
        _sub(root, "premiered", premiered)
        year = premiered[:4] if premiered and len(premiered) >= 4 else ""
        _sub(root, "year", year)
        _sub(root, "dateadded", "")

        # --- Status ---
        _sub(root, "status", show_data.get("status", ""))

        # --- Studios (networks for TV shows) ---
        for network in show_data.get("networks", show_data.get("production_companies", [])):
            _sub(root, "studio", network.get("name", ""))

        _sub(root, "trailer", "")

        # --- Episode guide ---
        # Mirrors the default uniqueid: TVDB when available (canonical for
        # TV shows), TMDB otherwise. Kodi's TV scraper picks up the same
        # source as <id>, so consistency between the two avoids the
        # "scraper resolves an unknown id" failure mode.
        _sub(root, "episodeguide", tvdb_id or tmdb_id)

        # --- Genres ---
        for genre in show_data.get("genres", []):
            _sub(root, "genre", genre.get("name", ""))

        # --- Category (classifier output, written after genres for readability) ---
        if category_id is not None:
            cat_elem = _sub(root, "category", category_id)
            cat_elem.set("source", "personalscraper")

        # --- Tags (from TMDB keywords) ---
        keywords = show_data.get("keywords", {})
        # TMDB TV uses "results" key, TMDB movies use "keywords" key
        keyword_list = keywords.get("results", keywords.get("keywords", []))
        for keyword in keyword_list:
            _sub(root, "tag", keyword.get("name", ""))

        # --- Inline images ---
        self._add_inline_images_tv(root, show_data)

        # --- Actors (aggregate_credits for TMDB TV) ---
        credits_data = show_data.get("aggregate_credits", show_data.get("credits", {}))
        for actor in credits_data.get("cast", []):
            self._add_actor_tv(root, actor)

        # --- Generator ---
        generator = ET.SubElement(root, "generator")
        _sub(generator, "appname", "personalscraper")

        _indent(root)
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(
            root,
            encoding="unicode",
        )

    def generate_episode_nfo(self, episode_data: dict[str, Any], stream_info: dict[str, Any] | None = None) -> str:
        """Generate an <episodedetails> NFO XML string matching MediaElch format.

        Produces XML with the same tag structure and ordering as MediaElch.
        For episodes, TVDB is the default uniqueid type.

        Args:
            episode_data: Episode dict enriched with show-level fields
                (showtitle, mpaa, studio) and crew data from TMDB season API.
            stream_info: Stream details dict from extract_stream_info(), or None.

        Returns:
            UTF-8 XML string with <?xml?> declaration.
        """
        root = ET.Element("episodedetails")

        # --- Basic metadata ---
        _sub(root, "title", episode_data.get("name", ""))
        _sub(root, "showtitle", episode_data.get("showtitle", ""))

        # --- IDs ---
        # When an id resolves to None/0/"" the tag is omitted rather than
        # written as the literal string "None" (Kodi reads "None" as a real
        # id and tries to look it up, poisoning the scraper cache).
        #
        # Provider-ids feature (phase 6.3, Q6=A) : the ``default="true"``
        # attribute follows ``episode_data["canonical_provider"]`` when set
        # — "tvdb" → tvdb wins ; "tmdb" → tmdb wins. The pre-feature
        # default (TVDB-when-present) is preserved when the caller has
        # not declared a canonical provider, keeping legacy NFO outputs
        # unchanged.
        raw_tvdb_id = episode_data.get("tvdb_id")
        raw_tmdb_id = episode_data.get("id", episode_data.get("tmdb_id"))
        raw_imdb_id = episode_data.get("imdb_id")
        tvdb_id = str(raw_tvdb_id) if raw_tvdb_id not in (None, 0, "0", "", "None") else ""
        tmdb_id = str(raw_tmdb_id) if raw_tmdb_id not in (None, 0, "0", "", "None") else ""
        imdb_id = str(raw_imdb_id) if raw_imdb_id not in (None, 0, "0", "", "None") else ""

        canonical_family = (episode_data.get("canonical_provider") or "").strip().lower()
        if canonical_family not in ("tvdb", "tmdb"):
            canonical_family = "tvdb" if tvdb_id else ("tmdb" if tmdb_id else "")

        ordered = (
            ("tvdb", tvdb_id),
            ("tmdb", tmdb_id),
            ("imdb", imdb_id),
        )
        default_applied = False
        for family, value in ordered:
            if not value:
                continue
            element = _sub(root, "uniqueid", value)
            element.set("type", family)
            if not default_applied and family == canonical_family:
                element.set("default", "true")
                default_applied = True

        # --- Ratings (episodes use "tmdb" not "themoviedb") ---
        self._add_ratings(
            root,
            episode_data,
            rating_name="tmdb",
            notations=episode_data.get("notations"),
            canonical_source=episode_data.get("canonical_source"),
        )
        _sub(root, "userrating", "0")
        _sub(root, "top250", "0")

        # --- Season and episode ---
        _sub(
            root,
            "season",
            str(
                episode_data.get(
                    "season_number",
                    episode_data.get("seasonNumber", 0),
                )
            ),
        )
        _sub(
            root,
            "episode",
            str(
                episode_data.get(
                    "episode_number",
                    episode_data.get("number", 0),
                )
            ),
        )

        # --- Plot ---
        _sub(root, "plot", episode_data.get("overview", ""))

        # --- Classification ---
        _sub(root, "mpaa", episode_data.get("mpaa", ""))
        _sub(root, "playcount", "0")
        _sub(root, "lastplayed", "")

        # --- Aired date ---
        _sub(root, "aired", episode_data.get("air_date", episode_data.get("aired", "")))

        # --- Studio (inherited from show) ---
        _sub(root, "studio", episode_data.get("studio", ""))

        # --- Credits and director (from TMDB crew data) ---
        crew = episode_data.get("crew", [])
        for member in crew:
            if member.get("job") in ("Writer", "Screenplay", "Story"):
                _sub(root, "credits", member.get("name", ""))

        for member in crew:
            if member.get("job") == "Director":
                _sub(root, "director", member.get("name", ""))

        # --- Episode thumb (screenshot) ---
        still_path = episode_data.get("still_path", "")
        if still_path:
            _sub(root, "thumb", _image_url(still_path))

        # --- Streamdetails ---
        if stream_info:
            self._add_streamdetails(root, stream_info)

        # --- Generator ---
        generator = ET.SubElement(root, "generator")
        _sub(generator, "appname", "personalscraper")

        _indent(root)
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + ET.tostring(
            root,
            encoding="unicode",
        )

    def write_nfo(self, xml_content: str, path: Path) -> None:
        """Write NFO XML content to a file with fsync durability.

        Delegates to :func:`atomic_write_text` which fsyncs the file *and*
        the parent directory so the NFO survives a machine crash (ext4 /
        macFUSE-mounted NTFS safety).

        Args:
            xml_content: UTF-8 XML string to write.
            path: Destination file path.
        """
        atomic_write_text(path, xml_content)

        # Best-effort outbox publish for the indexer (DESIGN §9.1).
        # Skipped when _db_path is None (no config available at construction time).
        if self._db_path is not None:
            resolved = disk_id_for_path(path, self._db_path)
            if resolved is not None:
                disk_id, rel_path = resolved
                item_kind = (
                    "tvshow"
                    if path.parent.name.lower() in {"saison", "season"} or "episodes" in path.name.lower()
                    else "movie"
                )
                publish_event(
                    disk_id,
                    op="nfo_write",
                    payload={
                        "rel_path": rel_path,
                        "item_kind": item_kind,
                        "tmdb_id": None,
                        "imdb_id": None,
                    },
                    db_path=self._db_path,
                    source="scraper",
                )

    # --- Private helpers ---

    def _add_ratings(
        self,
        root: ET.Element,
        data: dict[str, Any],
        rating_name: str = "themoviedb",
        notations: list[Notations] | None = None,
        canonical_source: str | None = None,
    ) -> None:
        """Add a ``<ratings>`` element to ``root`` carrying one or more rating rows.

        Backwards-compatible with the legacy single-source signature : when
        ``notations`` is ``None`` (or empty), the method writes one
        ``<rating>`` row from ``data["vote_average"]`` / ``data["vote_count"]``
        using ``rating_name`` as the source — exactly the previous behaviour.

        When ``notations`` is non-empty the method switches to the
        multi-source mode introduced by the ``provider-ids`` feature
        (phase 6) : one ``<rating>`` child per :class:`Notations` row,
        with the source identifier translated to its NFO / Plex
        equivalent (``imdb``, ``themoviedb``, ``rottentomatoes``, …) and
        the ``max`` attribute set to the value range matching each
        source (10 for IMDb / TMDb / Trakt / Metacritic-10, 100 for
        Rotten Tomatoes and Metacritic-100). The
        ``canonical_source`` argument (e.g. ``"themoviedb"``,
        ``"imdb"``) selects which row receives the ``default="true"``
        attribute — applied to at most one row, exactly as DESIGN §7
        requires.

        Args:
            root: Parent XML element.
            data: Legacy API payload (consumed only when ``notations``
                is empty).
            rating_name: Source identifier for the legacy single-row
                path. Defaults to ``"themoviedb"``.
            notations: Optional list of :class:`Notations` to render
                in multi-source mode.
            canonical_source: NFO-name of the canonical source to flag
                with ``default="true"``. ``None`` falls back to the
                first row in ``notations``.
        """
        ratings = ET.SubElement(root, "ratings")
        if notations:
            self._write_multi_source_ratings(ratings, notations, canonical_source)
            return
        rating = ET.SubElement(ratings, "rating")
        rating.set("name", rating_name)
        rating.set("default", "true")
        rating.set("max", "10")
        _sub(rating, "value", str(data.get("vote_average", 0)))
        _sub(rating, "votes", str(data.get("vote_count", 0)))

    def _write_multi_source_ratings(
        self,
        ratings: ET.Element,
        notations: list[Notations],
        canonical_source: str | None,
    ) -> None:
        """Emit one ``<rating>`` child per :class:`Notations` row.

        Helper for :meth:`_add_ratings` multi-source branch. Translates
        each ``Notations.source`` into its NFO name (e.g. ``imdb`` →
        ``imdb``, ``rotten_tomatoes`` → ``rottentomatoes``) and selects
        a single row to flag ``default="true"`` — the one whose NFO
        name matches ``canonical_source``, defaulting to the first
        rendered row when no match exists.
        """
        rows: list[tuple[str, Notations]] = []
        seen: dict[str, float] = {}
        for entry in notations:
            nfo_name = _NFO_RATING_SOURCE_NAMES.get(entry.source, entry.source)
            if nfo_name in seen:
                # Two Notations from the same NFO source — keep the first
                # (insertion-order) and drop the rest, but log so an
                # operator can audit the divergence. Plex/Kodi only read
                # one <rating> per name, so the silent drop is the right
                # behaviour ; the log makes it traceable.
                log.debug(
                    "nfo_rating_duplicate_dropped",
                    source=nfo_name,
                    kept_score=seen[nfo_name],
                    dropped_score=float(entry.score),
                )
                continue
            seen[nfo_name] = float(entry.score)
            rows.append((nfo_name, entry))

        canonical_name = canonical_source or (rows[0][0] if rows else None)
        default_applied = False
        for nfo_name, entry in rows:
            rating = ET.SubElement(ratings, "rating")
            rating.set("name", nfo_name)
            if not default_applied and nfo_name == canonical_name:
                rating.set("default", "true")
                default_applied = True
            rating.set("max", str(_NFO_RATING_MAX.get(nfo_name, 10)))
            _sub(rating, "value", str(entry.score))
            _sub(rating, "votes", str(entry.votes_count))

    def _add_inline_images(self, root: ET.Element, data: dict[str, Any]) -> None:
        """Add inline <thumb> and <fanart> elements.

        Args:
            root: Parent XML element.
            data: API data with images.posters and images.backdrops.
        """
        images = data.get("images", {})

        # Posters as <thumb aspect="poster">
        for img in images.get("posters", []):
            path = img.get("file_path", "")
            thumb = _sub(root, "thumb", _image_url(path))
            thumb.set("aspect", "poster")
            thumb.set("preview", _image_url(path, POSTER_PREVIEW_SIZE))

        # Backdrops as <fanart><thumb>
        backdrops = images.get("backdrops", [])
        if backdrops:
            fanart = ET.SubElement(root, "fanart")
            for img in backdrops:
                path = img.get("file_path", "")
                thumb = _sub(fanart, "thumb", _image_url(path))
                thumb.set("preview", _image_url(path, BACKDROP_PREVIEW_SIZE))

    def _add_inline_images_tv(self, root: ET.Element, data: dict[str, Any]) -> None:
        """Add inline <thumb> and <fanart> elements for TV shows.

        MediaElch uses original-size URLs for TV show image previews
        (unlike movies which use w342/w780 preview sizes).

        Args:
            root: Parent XML element.
            data: API data with images.posters and images.backdrops.
        """
        images = data.get("images", {})

        # Posters: first one gets aspect="poster", rest get aspect="0" with language
        posters = images.get("posters", [])
        for i, img in enumerate(posters):
            path = img.get("file_path", "")
            url = _image_url(path)
            thumb = _sub(root, "thumb", url)
            if i == 0:
                thumb.set("aspect", "poster")
                thumb.set("preview", url)
            else:
                lang = img.get("iso_639_1", "")
                if lang:
                    thumb.set("language", lang)
                thumb.set("aspect", "0")
                thumb.set("preview", url)

        # Backdrops as <fanart><thumb> with original-size previews
        backdrops = images.get("backdrops", [])
        if backdrops:
            fanart = ET.SubElement(root, "fanart")
            for img in backdrops:
                path = img.get("file_path", "")
                url = _image_url(path)
                thumb = _sub(fanart, "thumb", url)
                thumb.set("preview", url)

    def _add_streamdetails(self, root: ET.Element, stream_info: dict[str, Any]) -> None:
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

    def _add_actor(self, root: ET.Element, actor: dict[str, Any]) -> None:
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

    def _add_actor_tv(self, root: ET.Element, actor: dict[str, Any]) -> None:
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
    def _extract_certification_fr(movie_data: dict[str, Any]) -> str:
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
                        return cast(str, rd.get("certification", ""))
        return ""

    @staticmethod
    def _extract_content_rating_fr(show_data: dict[str, Any]) -> str:
        """Extract French content rating for TV shows.

        Args:
            show_data: TMDB TV show details dict.

        Returns:
            Rating string, or empty string if not found.
        """
        for rating in show_data.get("content_ratings", {}).get("results", []):
            if rating.get("iso_3166_1") == "FR":
                return cast(str, rating.get("rating", ""))
        return ""
