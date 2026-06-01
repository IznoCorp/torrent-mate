"""Golden corpus builders for the check-plugins characterization test.

Provides deterministic, hermetic builders for four corpus layouts:

- ``build_item_corpus`` — flat media-item dirs (for check_movie / check_tvshow / verify_*)
- ``build_staging_corpus`` — staging layout (for check_coherence)
- ``build_disk_corpus`` — disk layout (for validate_library)
- ``seed_index_db`` — SQLite seed rows (for validate_from_index)

Every NFO is written with fixed bytes — no datetime, no randomness — so that
the golden JSON files produced by the 0.2 capture step are byte-stable across
runs.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.core.media_types import FileType

# ---------------------------------------------------------------------------
# NFO writers — deterministic, fixed bytes, no datetime / randomness
# ---------------------------------------------------------------------------


def _write_movie_nfo(
    movie_dir: Path,
    *,
    title: str,
    year: str | int,
    tmdb_id: str | None = None,
    imdb_id: str | None = None,
    genres: list[str] | None = None,
    streamdetails: bool = True,
) -> None:
    """Write a minimal ``{Title}.nfo`` for a movie directory.

    Args:
        movie_dir: Path to the movie directory.
        title: Movie title (also used for the NFO filename stem).
        year: Release year.
        tmdb_id: Optional TMDB uniqueid value.
        imdb_id: Optional IMDB uniqueid value.
        genres: Optional list of ``<genre>`` tag strings.
        streamdetails: If True, include a ``<streamdetails>`` block.
    """
    nfo_name = f"{title}.nfo"
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<movie>",
        f"  <title>{title}</title>",
        f"  <year>{year}</year>",
    ]
    if tmdb_id:
        lines.append(f'  <uniqueid type="tmdb">{tmdb_id}</uniqueid>')
    if imdb_id:
        lines.append(f'  <uniqueid type="imdb">{imdb_id}</uniqueid>')
    if genres:
        for g in genres:
            lines.append(f"  <genre>{g}</genre>")
    if streamdetails:
        lines.append("  <streamdetails>")
        lines.append("    <video><codec>h264</codec><width>1920</width><height>1080</height></video>")
        lines.append("    <audio><codec>aac</codec><language>eng</language></audio>")
        lines.append("  </streamdetails>")
    lines.append("</movie>")
    (movie_dir / nfo_name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_tvshow_nfo(
    show_dir: Path,
    *,
    title: str,
    year: str | int,
    tvdb_id: str | None = None,
    tmdb_id: str | None = None,
    genres: list[str] | None = None,
) -> None:
    """Write a minimal ``tvshow.nfo`` for a TV show directory.

    Args:
        show_dir: Path to the TV show directory.
        title: Show title.
        year: Release year.
        tvdb_id: Optional TVDB uniqueid value (set as ``default="true"``).
        tmdb_id: Optional TMDB uniqueid value.
        genres: Optional list of ``<genre>`` tag strings.
    """
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<tvshow>",
        f"  <title>{title}</title>",
        f"  <year>{year}</year>",
    ]
    if tvdb_id:
        lines.append(f'  <uniqueid default="true" type="tvdb">{tvdb_id}</uniqueid>')
    if tmdb_id:
        lines.append(f'  <uniqueid type="tmdb">{tmdb_id}</uniqueid>')
    if genres:
        for g in genres:
            lines.append(f"  <genre>{g}</genre>")
    lines.append("</tvshow>")
    (show_dir / "tvshow.nfo").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_ep_nfo(
    episode_dir: Path,
    *,
    season: int,
    episode: int,
    title: str,
    tvdb_id: str | None = None,
    tmdb_id: str | None = None,
    imdb_id: str | None = None,
) -> str:
    """Write an episode NFO file and return its filename.

    Args:
        episode_dir: Path to the season directory.
        season: Season number.
        episode: Episode number.
        title: Episode title.
        tvdb_id: Optional TVDB uniqueid value.
        tmdb_id: Optional TMDB uniqueid value.
        imdb_id: Optional IMDB uniqueid value.

    Returns:
        The episode NFO filename (e.g. ``"S01E01 - Pilot.nfo"``).
    """
    nfo_name = f"S{season:02d}E{episode:02d} - {title}.nfo"
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<episodedetails>",
        f"  <title>{title}</title>",
        f"  <season>{season}</season>",
        f"  <episode>{episode}</episode>",
    ]
    if tvdb_id:
        lines.append(f'  <uniqueid type="tvdb" default="true">{tvdb_id}</uniqueid>')
    if tmdb_id:
        lines.append(f'  <uniqueid type="tmdb">{tmdb_id}</uniqueid>')
    if imdb_id:
        lines.append(f'  <uniqueid type="imdb">{imdb_id}</uniqueid>')
    lines.append("</episodedetails>")
    (episode_dir / nfo_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return nfo_name


# ---------------------------------------------------------------------------
# Flat item corpus — movie and TV show directories under ``root``
# ---------------------------------------------------------------------------


def build_item_corpus(root: Path) -> dict[str, Path]:
    """Build a flat corpus of media-item directories under ``root``.

    Every item lives directly under ``root`` (no staging/disk nesting).
    Keys are prefixed ``movie_`` for movies, ``tvshow_`` for TV shows so
    that the 0.2 characterization test can filter by prefix.

    Covers every branch of ``MediaChecker.check_movie`` and
    ``MediaChecker.check_tvshow``.

    Args:
        root: Parent directory that will receive all corpus items.

    Returns:
        Dict mapping item key → path to the media directory.
    """
    root.mkdir(parents=True, exist_ok=True)
    items: dict[str, Path] = {}

    # ── Movie items ───────────────────────────────────────────────────────

    # movie_valid — fully valid: NFO with TMDB+IMDB, poster, landscape, streamdetails
    d = root / "Movie Valid (2024)"
    d.mkdir()
    _write_movie_nfo(d, title="Movie Valid", year=2024, tmdb_id="12345", imdb_id="tt0123456", genres=["Action"])
    (d / "Movie Valid-poster.jpg").write_text("")
    (d / "Movie Valid-landscape.jpg").write_text("")
    (d / "Movie Valid.mkv").write_text("fake_video_data" * 10)  # > 100MB trigger size for not_sample
    items["movie_valid"] = d

    # movie_missing_nfo — no NFO file at all (nfo_present ERROR)
    d = root / "Movie NoNFO (2020)"
    d.mkdir()
    (d / "Movie NoNFO-poster.jpg").write_text("")
    (d / "Movie NoNFO-landscape.jpg").write_text("")
    (d / "Movie NoNFO.mkv").write_text("fake_video_data" * 10)
    items["movie_missing_nfo"] = d

    # movie_nfo_no_ids — NFO exists but has neither TMDB nor IMDB (nfo_ids ERROR)
    d = root / "Movie NoIDs (2021)"
    d.mkdir()
    _write_movie_nfo(d, title="Movie NoIDs", year=2021, genres=["Drama"], streamdetails=True)
    (d / "Movie NoIDs-poster.jpg").write_text("")
    (d / "Movie NoIDs-landscape.jpg").write_text("")
    (d / "Movie NoIDs.mkv").write_text("fake_video_data" * 10)
    items["movie_nfo_no_ids"] = d

    # movie_missing_landscape — has poster + NFO + ids, but no landscape file
    d = root / "Movie NoLandscape (2022)"
    d.mkdir()
    _write_movie_nfo(d, title="Movie NoLandscape", year=2022, tmdb_id="22222", imdb_id="tt0222222", genres=["Comedy"])
    (d / "Movie NoLandscape-poster.jpg").write_text("")
    (d / "Movie NoLandscape.mkv").write_text("fake_video_data" * 10)
    items["movie_missing_landscape"] = d

    # movie_no_streamdetails — NFO with ids but no <streamdetails> block
    d = root / "Movie NoStream (2023)"
    d.mkdir()
    _write_movie_nfo(d, title="Movie NoStream", year=2023, tmdb_id="33333", imdb_id="tt0333333", streamdetails=False)
    (d / "Movie NoStream-poster.jpg").write_text("")
    (d / "Movie NoStream-landscape.jpg").write_text("")
    (d / "Movie NoStream.mkv").write_text("fake_video_data" * 10)
    items["movie_no_streamdetails"] = d

    # ── TV show items ─────────────────────────────────────────────────────

    # tvshow_valid — fully valid: tvshow.nfo, poster, landscape, season dirs
    #   with properly-named episodes and episode NFOs
    d = root / "TVShow Valid (2024)"
    d.mkdir()
    _write_tvshow_nfo(d, title="TVShow Valid", year=2024, tvdb_id="111111", tmdb_id="22222", genres=["Drama"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - Pilot.mkv").write_text("fake_video_data" * 10)
    _write_ep_nfo(s1, season=1, episode=1, title="Pilot", tvdb_id="1111111", tmdb_id="2222222")
    (s1 / "S01E02 - Episode Two.mkv").write_text("fake_video_data" * 10)
    _write_ep_nfo(s1, season=1, episode=2, title="Episode Two", tvdb_id="1111112", tmdb_id="2222223")
    items["tvshow_valid"] = d

    # tvshow_missing_ep_nfo — has season dirs with episodes but NO episode NFO files
    d = root / "TVShow NoEpNFO (2020)"
    d.mkdir()
    _write_tvshow_nfo(d, title="TVShow NoEpNFO", year=2020, tvdb_id="333333", tmdb_id="44444", genres=["Comedy"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - First.mkv").write_text("fake_video_data" * 10)
    (s1 / "S01E02 - Second.mkv").write_text("fake_video_data" * 10)
    # No episode NFO files — episode_nfo check will WARN
    items["tvshow_missing_ep_nfo"] = d

    # tvshow_unrenamed_episode — video files in season dir that don't match SxxExx pattern
    d = root / "TVShow Unrenamed (2021)"
    d.mkdir()
    _write_tvshow_nfo(d, title="TVShow Unrenamed", year=2021, tvdb_id="555555", tmdb_id="66666", genres=["Drama"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - Proper.mkv").write_text("fake_video_data" * 10)
    _write_ep_nfo(s1, season=1, episode=1, title="Proper", tvdb_id="5555551")
    # Unrenamed: raw filename, not SxxExx pattern
    (s1 / "episode02.mkv").write_text("fake_video_data" * 10)
    items["tvshow_unrenamed_episode"] = d

    # tvshow_empty_subdir — has an empty subdirectory (no_empty_dirs ERROR)
    d = root / "TVShow EmptyDir (2022)"
    d.mkdir()
    _write_tvshow_nfo(d, title="TVShow EmptyDir", year=2022, tvdb_id="777777", tmdb_id="88888", genres=["Drama"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - Only.mkv").write_text("fake_video_data" * 10)
    _write_ep_nfo(s1, season=1, episode=1, title="Only", tvdb_id="7777771")
    # Empty subdirectory
    empty = d / "Extras"
    empty.mkdir()  # empty — no files, no subdirs
    items["tvshow_empty_subdir"] = d

    # tvshow_ntfs_illegal — contains a file with NTFS-illegal characters
    d = root / "TVShow NTFS (2023)"
    d.mkdir()
    _write_tvshow_nfo(d, title="TVShow NTFS", year=2023, tvdb_id="999999", tmdb_id="101010", genres=["Drama"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - Legal.mkv").write_text("fake_video_data" * 10)
    _write_ep_nfo(s1, season=1, episode=1, title="Legal", tvdb_id="9999991")
    # NTFS-illegal filename: colon is forbidden on NTFS
    (s1 / "bad:file.mkv").write_text("fake_video_data" * 10)
    items["tvshow_ntfs_illegal"] = d

    return items


# ---------------------------------------------------------------------------
# Staging corpus — 001-MOVIES/ + 002-TVSHOWS/ layout under ``root``
# ---------------------------------------------------------------------------


def build_staging_corpus(root: Path, base_config: Config) -> Config:
    """Build a staging-layout corpus under ``root``.

    Creates ``001-MOVIES/`` and ``002-TVSHOWS/`` (using the folder-name
    derivation from the base Config's ``staging_dirs``) and populates them
    with items that exercise ``check_coherence``:

    * A valid movie in MOVIES.
    * A TV-show NFO misplaced in MOVIES (wrong-category warning).
    * A valid TV show in TVSHOWS.
    * A movie-NFO misplaced in TVSHOWS (wrong-category warning).
    * A TV show whose genre maps to ``tv_programs`` (genre_coherence warning).

    Returns a new Config whose ``paths.staging_dir`` is repointed at ``root``.

    Args:
        root: Directory that will become the staging root.
        base_config: A Config instance (e.g. from the ``test_config`` fixture).

    Returns:
        A new Config with ``paths.staging_dir`` set to ``root``.
    """
    root.mkdir(parents=True, exist_ok=True)

    # Resolve folder names from base_config's staging_dirs
    movies_entry = find_by_file_type(base_config, FileType.MOVIE)
    tvshows_entry = find_by_file_type(base_config, FileType.TVSHOW)
    movies_folder = folder_name(movies_entry)  # e.g. "001-MOVIES"
    tvshows_folder = folder_name(tvshows_entry)  # e.g. "002-TVSHOWS"

    movies_dir = root / movies_folder
    tvshows_dir = root / tvshows_folder

    # ── 001-MOVIES/ ───────────────────────────────────────────────────────
    movies_dir.mkdir()

    # Valid movie
    d = movies_dir / "Staging Movie (2024)"
    d.mkdir()
    _write_movie_nfo(d, title="Staging Movie", year=2024, tmdb_id="10001", imdb_id="tt0100001", genres=["Action"])
    (d / "Staging Movie-poster.jpg").write_text("")
    (d / "Staging Movie-landscape.jpg").write_text("")
    (d / "Staging Movie.mkv").write_text("fake_video_data" * 10)

    # Wrong category: a directory with tvshow.nfo inside MOVIES
    d = movies_dir / "Wrong Cat TV (2020)"
    d.mkdir()
    _write_tvshow_nfo(d, title="Wrong Cat TV", year=2020, tvdb_id="888888", genres=["Drama"])
    # Also include a dummy video so it looks like real content
    (d / "S01E01 - Pilot.mkv").write_text("fake_video_data" * 10)

    # ── 002-TVSHOWS/ ──────────────────────────────────────────────────────
    tvshows_dir.mkdir()

    # Valid TV show
    d = tvshows_dir / "Staging TVShow (2024)"
    d.mkdir()
    _write_tvshow_nfo(d, title="Staging TVShow", year=2024, tvdb_id="222222", tmdb_id="33333", genres=["Drama"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - Start.mkv").write_text("fake_video_data" * 10)

    # Wrong category: a directory with a movie NFO (not tvshow.nfo) inside TVSHOWS
    d = tvshows_dir / "Wrong Cat Movie (2021)"
    d.mkdir()
    _write_movie_nfo(d, title="Wrong Cat Movie", year=2021, tmdb_id="40004", imdb_id="tt0400004", genres=["Comedy"])
    (d / "Wrong Cat Movie.mkv").write_text("fake_video_data" * 10)

    # Genre → TV_PROGRAMS: a TV show whose genre triggers the tv_programs rule
    d = tvshows_dir / "Reality Show (2022)"
    d.mkdir()
    _write_tvshow_nfo(d, title="Reality Show", year=2022, tvdb_id="555555", tmdb_id="66666", genres=["Reality"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - Intro.mkv").write_text("fake_video_data" * 10)

    # Repoint staging_dir
    new_paths = base_config.paths.model_copy(update={"staging_dir": root})
    return base_config.model_copy(update={"paths": new_paths})


# ---------------------------------------------------------------------------
# Disk corpus — category folders under a single disk root
# ---------------------------------------------------------------------------


def build_disk_corpus(root: Path, base_config: Config) -> Config:
    """Build a disk-layout corpus under ``root``.

    Creates category folders (using ``config.category(id).folder_name``)
    under ``root``, populating them with at least one movie and one TV show
    so that ``validate_library`` exercises both movie and TV paths.

    Returns a new Config with a single disk at ``root`` that accepts all
    the movie and TV category IDs.

    Args:
        root: Directory that will become the disk mount point.
        base_config: A Config instance (e.g. from the ``test_config`` fixture).

    Returns:
        A new Config with a single disk repointed at ``root``.
    """
    root.mkdir(parents=True, exist_ok=True)

    # Resolve folder names from base_config's categories
    movies_folder = base_config.category(CID.MOVIES).folder_name
    tvshows_folder = base_config.category(CID.TV_SHOWS).folder_name

    # ── Movie category ────────────────────────────────────────────────────
    movies_dir = root / movies_folder
    movies_dir.mkdir()
    d = movies_dir / "Disk Movie (2024)"
    d.mkdir()
    _write_movie_nfo(d, title="Disk Movie", year=2024, tmdb_id="70007", imdb_id="tt0700007", genres=["Action"])
    (d / "Disk Movie-poster.jpg").write_text("")
    (d / "Disk Movie-landscape.jpg").write_text("")
    (d / "Disk Movie.mkv").write_text("fake_video_data" * 10)

    # ── TV show category ──────────────────────────────────────────────────
    tvshows_dir = root / tvshows_folder
    tvshows_dir.mkdir()
    d = tvshows_dir / "Disk TVShow (2024)"
    d.mkdir()
    _write_tvshow_nfo(d, title="Disk TVShow", year=2024, tvdb_id="888888", tmdb_id="99999", genres=["Drama"])
    (d / "poster.jpg").write_text("")
    (d / "landscape.jpg").write_text("")
    s1 = d / "Saison 01"
    s1.mkdir()
    (s1 / "S01E01 - DiskEp.mkv").write_text("fake_video_data" * 10)
    _write_ep_nfo(s1, season=1, episode=1, title="DiskEp", tvdb_id="8888881")

    # Build a single disk with categories covering movies and TV shows
    disk = DiskConfig(
        id="corpus_disk",
        path=root,
        categories=[
            CID.MOVIES,
            CID.MOVIES_ANIMATION,
            CID.MOVIES_DOCUMENTARY,
            CID.TV_SHOWS,
            CID.TV_SHOWS_ANIMATION,
            CID.TV_SHOWS_DOCUMENTARY,
            CID.ANIME,
            CID.TV_PROGRAMS,
            CID.STANDUP,
            CID.THEATER,
        ],
    )
    return base_config.model_copy(update={"disks": [disk]})


# ---------------------------------------------------------------------------
# Index DB seed — media_item + item_attribute rows
# ---------------------------------------------------------------------------

# Fixed timestamp for deterministic seed rows.
_SEED_NOW = 1700000000


def seed_index_db(conn: sqlite3.Connection) -> None:
    """Create ``media_item`` and ``item_attribute`` tables and insert rows.

    Covers ``nfo_status`` ∈ {missing, invalid, valid, NULL} and
    ``artwork_json`` with/without poster+landscape, for both movies and shows.

    The schema matches the columns that :func:`validate_from_index` queries
    (library_checks.py L226-238). This is a lightweight in-memory seed —
    it does NOT run the real indexer migrations.

    Args:
        conn: An open SQLite connection (typically ``:memory:``).
    """
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS media_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            year INTEGER,
            category_id TEXT NOT NULL,
            nfo_status TEXT,
            artwork_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS item_attribute (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT
        )
        """
    )

    # ── Movie rows ────────────────────────────────────────────────────────

    # Movie 1: nfo_status='valid', artwork with poster + landscape → valid
    _insert_item(
        conn,
        kind="movie",
        title="DB Movie Valid",
        year=2024,
        category_id=CID.MOVIES,
        nfo_status="valid",
        artwork_json='{"poster":true,"landscape":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/Disk Movie (2024)",
    )

    # Movie 2: nfo_status='missing', artwork with poster → nfo_present ERROR
    _insert_item(
        conn,
        kind="movie",
        title="DB Movie MissingNFO",
        year=2023,
        category_id=CID.MOVIES,
        nfo_status="missing",
        artwork_json='{"poster":true,"landscape":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Movie MissingNFO (2023)",
    )

    # Movie 3: nfo_status='invalid', artwork has poster → nfo_valid ERROR
    _insert_item(
        conn,
        kind="movie",
        title="DB Movie InvalidNFO",
        year=2022,
        category_id=CID.MOVIES,
        nfo_status="invalid",
        artwork_json='{"poster":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Movie InvalidNFO (2022)",
    )

    # Movie 4: nfo_status=NULL (never enriched), artwork_json=NULL → valid (no findings)
    _insert_item(
        conn,
        kind="movie",
        title="DB Movie Fresh",
        year=2025,
        category_id=CID.MOVIES,
        nfo_status=None,
        artwork_json=None,
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Movie Fresh (2025)",
    )

    # Movie 5: nfo_status='valid', artwork without poster → poster_present ERROR
    _insert_item(
        conn,
        kind="movie",
        title="DB Movie NoPoster",
        year=2021,
        category_id=CID.MOVIES,
        nfo_status="valid",
        artwork_json='{"poster":false,"landscape":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Movie NoPoster (2021)",
    )

    # Movie 6: nfo_status='valid', artwork without landscape → artwork_landscape WARNING
    _insert_item(
        conn,
        kind="movie",
        title="DB Movie NoLandscape",
        year=2020,
        category_id=CID.MOVIES_ANIMATION,
        nfo_status="valid",
        artwork_json='{"poster":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Movie NoLandscape (2020)",
    )

    # ── Show rows ─────────────────────────────────────────────────────────

    # Show 1: nfo_status='valid', artwork with poster → valid
    _insert_item(
        conn,
        kind="show",
        title="DB Show Valid",
        year=2024,
        category_id=CID.TV_SHOWS,
        nfo_status="valid",
        artwork_json='{"poster":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Show Valid (2024)",
    )

    # Show 2: nfo_status='missing' → nfo_present ERROR
    _insert_item(
        conn,
        kind="show",
        title="DB Show MissingNFO",
        year=2023,
        category_id=CID.TV_SHOWS,
        nfo_status="missing",
        artwork_json='{"poster":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Show MissingNFO (2023)",
    )

    # Show 3: nfo_status='invalid' → nfo_valid ERROR
    _insert_item(
        conn,
        kind="show",
        title="DB Show InvalidNFO",
        year=2022,
        category_id=CID.TV_SHOWS,
        nfo_status="invalid",
        artwork_json='{"poster":true}',
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Show InvalidNFO (2022)",
    )

    # Show 4: nfo_status=NULL, artwork_json=NULL → valid (no findings)
    _insert_item(
        conn,
        kind="show",
        title="DB Show Fresh",
        year=2025,
        category_id=CID.TV_SHOWS,
        nfo_status=None,
        artwork_json=None,
        disk_label="corpus_disk",
        dispatch_path="/tmp/corpus/DB Show Fresh (2025)",
    )

    conn.commit()


def _insert_item(
    conn: sqlite3.Connection,
    *,
    kind: str,
    title: str,
    year: int,
    category_id: str,
    nfo_status: str | None,
    artwork_json: str | None,
    disk_label: str | None,
    dispatch_path: str | None,
) -> int:
    """Insert a media_item row and its item_attribute rows.

    Args:
        conn: SQLite connection.
        kind: ``"movie"`` or ``"show"``.
        title: Media title.
        year: Release year.
        category_id: Category ID string.
        nfo_status: One of ``"missing"``, ``"invalid"``, ``"valid"``, or ``None``.
        artwork_json: JSON string with poster/landscape keys, or ``None``.
        disk_label: Value for the ``dispatch_disk`` attribute.
        dispatch_path: Value for the ``dispatch_path`` attribute.

    Returns:
        The new item's ``id``.
    """
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, year, category_id, nfo_status, artwork_json) VALUES (?, ?, ?, ?, ?, ?)",
        (kind, title, year, category_id, nfo_status, artwork_json),
    )
    item_id: int = cur.lastrowid  # type: ignore[assignment]

    if disk_label is not None:
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_disk', ?)",
            (item_id, disk_label),
        )
    if dispatch_path is not None:
        conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)",
            (item_id, dispatch_path),
        )
    return item_id
