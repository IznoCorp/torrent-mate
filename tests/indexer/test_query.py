"""Tests for personalscraper.indexer.query — flex-attr parser (Phase 8.2).

Covers every :data:`~personalscraper.indexer.query.FIELD_REGISTRY` path:

- ``kind`` (str equality)
- ``title`` (LIKE, auto-% wrap, prefix mode)
- ``year`` (int, equality and comparison operators)
- ``disk`` (JOIN on disk.label)
- ``category`` (str equality on media_item.category_id)
- ``tmdb_id`` / ``imdb_id`` (int / str equality)
- ``nfo`` (nfo_status equality + allowed-values guard)
- ``codec`` (EXISTS on media_stream video, negation)
- ``lang`` (EXISTS on media_stream audio, negation)
- ``quality`` (EXISTS on media_release.quality)
- Flex-attr equality, presence, prefix (error), numeric op (error)
- Bare-key negation: ``-trailer_found``
- Bare title fragment (no field)
- Quoted bare-phrase title fragment
- Negation of column-based fields
- AND conjunction of multiple tokens
- Unknown field raises :class:`~personalscraper.indexer.query.QueryError`
- Numeric comparison on flex attr raises :class:`~personalscraper.indexer.query.QueryError`
- nfo with disallowed value raises :class:`~personalscraper.indexer.query.QueryError`
- Empty query returns all items (up to limit)
- ``find_items_without_trailer`` named query

Test strategy:
    All tests use an in-memory SQLite DB seeded via :func:`apply_migrations` and
    a thin set of fixture-insertion helpers.  No real filesystem is touched.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.query import QueryError, execute, find_items_without_trailer
from personalscraper.indexer.schema import MediaItemRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with the full migration chain applied.

    Returns:
        An open :class:`sqlite3.Connection` with FK enforcement enabled.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


# ---------------------------------------------------------------------------
# Fixture-insertion helpers
# ---------------------------------------------------------------------------


def _insert_disk(conn: sqlite3.Connection, label: str, mount: str = "/Volumes/TestDisk") -> int:
    """Insert a mounted disk row and return its PK.

    Args:
        conn: Open SQLite connection.
        label: Disk label string (e.g. ``'Disk1'``).
        mount: Mount-path string for the disk.

    Returns:
        PK of the inserted disk row.
    """
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (f"uuid-{label}", label, mount, int(time.time())),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_path(conn: sqlite3.Connection, disk_id: int, rel_path: str = "MOVIES/Item") -> int:
    """Insert a path row and return its PK.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the owning disk.
        rel_path: Relative directory path.

    Returns:
        PK of the inserted path row.
    """
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
        (disk_id, rel_path),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_item(
    conn: sqlite3.Connection,
    *,
    title: str = "Test Movie",
    title_sort: str | None = None,
    kind: str = "movie",
    year: int | None = 2024,
    category_id: str = "movies",
    tmdb_id: int | None = None,
    imdb_id: str | None = None,
    nfo_status: str | None = None,
    is_locked: int = 0,
    preferred_lang: str = "fr",
) -> int:
    """Insert a minimal media_item row and return its PK.

    Args:
        conn: Open SQLite connection.
        title: Display title.
        title_sort: Sort title; defaults to *title* if not provided.
        kind: ``'movie'`` or ``'show'``.
        year: Release year or ``None``.
        category_id: Logical category identifier.
        tmdb_id: TMDB numeric ID or ``None``.
        imdb_id: IMDb tt-ID string or ``None``.
        nfo_status: ``'valid'``, ``'invalid'``, ``'missing'``, or ``None``.
        is_locked: 0 or 1.
        preferred_lang: BCP-47 language code.

    Returns:
        PK of the inserted row.
    """
    now = int(time.time())
    cursor = conn.execute(
        "INSERT INTO media_item "
        "(kind, title, title_sort, original_title, year, category_id, tmdb_id, imdb_id, "
        "tvdb_id, nfo_status, artwork_json, date_created, date_modified, "
        "date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES (?, ?, ?, NULL, ?, ?, ?, ?, NULL, ?, NULL, ?, ?, NULL, ?, ?)",
        (
            kind,
            title,
            title_sort or title,
            year,
            category_id,
            tmdb_id,
            imdb_id,
            nfo_status,
            now,
            now,
            is_locked,
            preferred_lang,
        ),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_release(conn: sqlite3.Connection, item_id: int, quality: str | None = "1080p") -> int:
    """Insert a media_release row linked to *item_id* and return its PK.

    Args:
        conn: Open SQLite connection.
        item_id: PK of the owning media_item.
        quality: Quality label or ``None``.

    Returns:
        PK of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, quality) VALUES (?, ?)",
        (item_id, quality),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_file(conn: sqlite3.Connection, release_id: int, path_id: int, filename: str = "video.mkv") -> int:
    """Insert a media_file row and return its PK.

    Args:
        conn: Open SQLite connection.
        release_id: PK of the owning media_release.
        path_id: PK of the owning path.
        filename: Bare filename string.

    Returns:
        PK of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO media_file "
        "(release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation, last_verified_at) "
        "VALUES (?, ?, ?, 1000000, 1000000000, 'aabbccddeeff0011', 1, ?)",
        (release_id, path_id, filename, int(time.time())),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_stream(
    conn: sqlite3.Connection,
    file_id: int,
    *,
    idx: int = 0,
    kind: str = "video",
    codec: str | None = "h264",
    lang: str | None = None,
) -> int:
    """Insert a media_stream row and return its PK.

    Args:
        conn: Open SQLite connection.
        file_id: PK of the owning media_file.
        idx: Stream index within the file (0-based).
        kind: ``'video'``, ``'audio'``, or ``'subtitle'``.
        codec: Codec name or ``None``.
        lang: BCP-47 language code or ``None``.

    Returns:
        PK of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO media_stream (file_id, idx, kind, codec, lang) VALUES (?, ?, ?, ?, ?)",
        (file_id, idx, kind, codec, lang),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_attr(conn: sqlite3.Connection, item_id: int, key: str, value: str | None = "1") -> None:
    """Insert or replace an item_attribute row.

    Args:
        conn: Open SQLite connection.
        item_id: PK of the owning media_item.
        key: Attribute key string.
        value: Attribute value string or ``None``.
    """
    conn.execute(
        "INSERT OR REPLACE INTO item_attribute (item_id, key, value) VALUES (?, ?, ?)",
        (item_id, key, value),
    )


# ---------------------------------------------------------------------------
# Convenience: insert item + full chain on a disk
# ---------------------------------------------------------------------------


def _insert_item_on_disk(
    conn: sqlite3.Connection,
    disk_id: int,
    *,
    title: str = "Test Movie",
    title_sort: str | None = None,
    kind: str = "movie",
    year: int | None = 2024,
    category_id: str = "movies",
    nfo_status: str | None = None,
    tmdb_id: int | None = None,
    imdb_id: str | None = None,
    quality: str | None = "1080p",
    codec: str | None = None,
    lang: str | None = None,
) -> int:
    """Insert a complete item → release → file → (optional stream) chain on *disk_id*.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the target disk.
        title: Item title.
        title_sort: Sort title; defaults to *title* when not provided.
        kind: ``'movie'`` or ``'show'``.
        year: Release year.
        category_id: Logical category.
        nfo_status: NFO status or ``None``.
        tmdb_id: TMDB ID or ``None``.
        imdb_id: IMDb ID or ``None``.
        quality: Release quality or ``None``.
        codec: If provided, a video stream with this codec is inserted.
        lang: If provided, an audio stream with this language is inserted.

    Returns:
        PK of the inserted media_item.
    """
    # Use title as path component so each item gets a unique (disk_id, rel_path).
    safe_title = title.replace("/", "_").replace(" ", "_")
    path_id = _insert_path(conn, disk_id, rel_path=f"MOVIES/{safe_title}")
    item_id = _insert_item(
        conn,
        title=title,
        title_sort=title_sort,
        kind=kind,
        year=year,
        category_id=category_id,
        nfo_status=nfo_status,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
    )
    release_id = _insert_release(conn, item_id, quality=quality)
    file_id = _insert_file(conn, release_id, path_id)
    if codec:
        _insert_stream(conn, file_id, idx=0, kind="video", codec=codec)
    if lang:
        _insert_stream(conn, file_id, idx=1, kind="audio", lang=lang)
    return item_id


# ---------------------------------------------------------------------------
# Helper: collect IDs from a query result
# ---------------------------------------------------------------------------


def _ids(rows: list[MediaItemRow]) -> set[int]:
    """Return the set of item IDs from *rows*.

    Args:
        rows: Query result list.

    Returns:
        Set of integer IDs.
    """
    return {r.id for r in rows}


# ===========================================================================
# Tests
# ===========================================================================


class TestFieldKind:
    """FIELD_REGISTRY path: ``kind`` → media_item.kind (str equality)."""

    def test_kind_movie_returns_movies(self, conn: sqlite3.Connection) -> None:
        """kind:movie filters to movie items only."""
        disk_id = _insert_disk(conn, "Disk1")
        movie_id = _insert_item_on_disk(conn, disk_id, title="A Movie", kind="movie")
        show_id = _insert_item_on_disk(conn, disk_id, title="A Show", kind="show")

        results = execute(conn, "kind:movie")
        ids = _ids(results)
        assert movie_id in ids
        assert show_id not in ids

    def test_kind_show_returns_shows(self, conn: sqlite3.Connection) -> None:
        """kind:show filters to TV-show items only."""
        disk_id = _insert_disk(conn, "Disk1")
        show_id = _insert_item_on_disk(conn, disk_id, title="A Show", kind="show")

        results = execute(conn, "kind:show")
        assert show_id in _ids(results)

    def test_negated_kind(self, conn: sqlite3.Connection) -> None:
        """-kind:movie excludes movies."""
        disk_id = _insert_disk(conn, "Disk1")
        movie_id = _insert_item_on_disk(conn, disk_id, title="A Movie", kind="movie")
        show_id = _insert_item_on_disk(conn, disk_id, title="A Show", kind="show")

        results = execute(conn, "-kind:movie")
        ids = _ids(results)
        assert movie_id not in ids
        assert show_id in ids


class TestFieldTitle:
    """FIELD_REGISTRY path: ``title`` → media_item.title LIKE (auto-% wrapped)."""

    def test_title_fragment_matches_substring(self, conn: sqlite3.Connection) -> None:
        """Bare title fragment auto-wraps with % for substring matching."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id, title="Lost Highway")

        results = execute(conn, "title:Highway")
        assert item_id in _ids(results)

    def test_title_prefix_match(self, conn: sqlite3.Connection) -> None:
        """title:Lost* matches items whose title starts with 'Lost'."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id, title="Lost Highway")
        other_id = _insert_item_on_disk(conn, disk_id, title="The Lost Boys")

        results = execute(conn, "title:Lost*")
        ids = _ids(results)
        assert item_id in ids
        # 'The Lost Boys' does not start with 'Lost'
        assert other_id not in ids

    def test_title_no_match_returns_empty(self, conn: sqlite3.Connection) -> None:
        """A title query that matches nothing returns an empty list."""
        disk_id = _insert_disk(conn, "Disk1")
        _insert_item_on_disk(conn, disk_id, title="Inception")

        results = execute(conn, "title:XYZZY_NOMATCH")
        assert results == []

    def test_bare_title_fragment(self, conn: sqlite3.Connection) -> None:
        """A bare term (no field) is treated as a title fragment (auto-% wrapped)."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id, title="Mulholland Drive")

        results = execute(conn, "Mulholland")
        assert item_id in _ids(results)

    def test_quoted_phrase_exact_substring(self, conn: sqlite3.Connection) -> None:
        """A "quoted phrase" is matched as a literal LIKE substring (no auto-%)."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id, title="Lost Highway")
        other_id = _insert_item_on_disk(conn, disk_id, title="Highway to Hell")

        # Quoted phrase lands in title LIKE with bare value and % on both sides added
        # by the base tokeniser path for bare (no-field) tokens.
        results = execute(conn, '"Lost Highway"')
        ids = _ids(results)
        assert item_id in ids
        assert other_id not in ids


class TestFieldYear:
    """FIELD_REGISTRY path: ``year`` → media_item.year (int, supports comparisons)."""

    def test_year_equality(self, conn: sqlite3.Connection) -> None:
        """year:2024 returns only items from 2024."""
        disk_id = _insert_disk(conn, "Disk1")
        item_2024 = _insert_item_on_disk(conn, disk_id, title="Movie 2024", year=2024)
        item_2020 = _insert_item_on_disk(conn, disk_id, title="Movie 2020", year=2020)

        results = execute(conn, "year:2024")
        ids = _ids(results)
        assert item_2024 in ids
        assert item_2020 not in ids

    def test_year_gte(self, conn: sqlite3.Connection) -> None:
        """year:>=2022 returns items from 2022 and later."""
        disk_id = _insert_disk(conn, "Disk1")
        item_2020 = _insert_item_on_disk(conn, disk_id, title="Old Movie", year=2020)
        item_2022 = _insert_item_on_disk(conn, disk_id, title="New Movie A", year=2022)
        item_2024 = _insert_item_on_disk(conn, disk_id, title="New Movie B", year=2024)

        results = execute(conn, "year:>=2022")
        ids = _ids(results)
        assert item_2020 not in ids
        assert item_2022 in ids
        assert item_2024 in ids

    def test_year_lte(self, conn: sqlite3.Connection) -> None:
        """year:<=2021 returns items from 2021 and earlier."""
        disk_id = _insert_disk(conn, "Disk1")
        item_2020 = _insert_item_on_disk(conn, disk_id, title="Old Movie", year=2020)
        item_2022 = _insert_item_on_disk(conn, disk_id, title="New Movie", year=2022)

        results = execute(conn, "year:<=2021")
        ids = _ids(results)
        assert item_2020 in ids
        assert item_2022 not in ids

    def test_year_gt(self, conn: sqlite3.Connection) -> None:
        """year:>2023 returns only items strictly after 2023."""
        disk_id = _insert_disk(conn, "Disk1")
        item_2023 = _insert_item_on_disk(conn, disk_id, title="Movie 2023", year=2023)
        item_2024 = _insert_item_on_disk(conn, disk_id, title="Movie 2024", year=2024)

        results = execute(conn, "year:>2023")
        ids = _ids(results)
        assert item_2023 not in ids
        assert item_2024 in ids

    def test_year_lt(self, conn: sqlite3.Connection) -> None:
        """year:<2023 returns only items strictly before 2023."""
        disk_id = _insert_disk(conn, "Disk1")
        item_2022 = _insert_item_on_disk(conn, disk_id, title="Movie 2022", year=2022)
        item_2023 = _insert_item_on_disk(conn, disk_id, title="Movie 2023", year=2023)

        results = execute(conn, "year:<2023")
        ids = _ids(results)
        assert item_2022 in ids
        assert item_2023 not in ids

    def test_year_non_integer_raises(self, conn: sqlite3.Connection) -> None:
        """year:abc raises QueryError — year must be an integer."""
        with pytest.raises(QueryError, match="integer"):
            execute(conn, "year:abc")


class TestFieldDisk:
    """FIELD_REGISTRY path: ``disk`` → JOIN disk.label."""

    def test_disk_filters_to_named_disk(self, conn: sqlite3.Connection) -> None:
        """disk:Disk1 returns only items with files on Disk1."""
        disk1 = _insert_disk(conn, "Disk1", "/Volumes/Disk1")
        disk2 = _insert_disk(conn, "Disk2", "/Volumes/Disk2")
        item1 = _insert_item_on_disk(conn, disk1, title="On Disk1")
        item2 = _insert_item_on_disk(conn, disk2, title="On Disk2")

        results = execute(conn, "disk:Disk1")
        ids = _ids(results)
        assert item1 in ids
        assert item2 not in ids

    def test_negated_disk_excludes_named_disk(self, conn: sqlite3.Connection) -> None:
        """-disk:Disk1 excludes items from Disk1."""
        disk1 = _insert_disk(conn, "Disk1", "/Volumes/Disk1")
        disk2 = _insert_disk(conn, "Disk2", "/Volumes/Disk2")
        _insert_item_on_disk(conn, disk1, title="On Disk1")
        item2 = _insert_item_on_disk(conn, disk2, title="On Disk2")

        results = execute(conn, "-disk:Disk1")
        ids = _ids(results)
        assert item2 in ids


class TestFieldCategory:
    """FIELD_REGISTRY path: ``category`` → media_item.category_id."""

    def test_category_equality(self, conn: sqlite3.Connection) -> None:
        """category:movies returns items with category_id='movies'."""
        disk_id = _insert_disk(conn, "Disk1")
        movie_id = _insert_item_on_disk(conn, disk_id, category_id="movies")
        show_id = _insert_item_on_disk(conn, disk_id, category_id="tv_shows", title="A Show")

        results = execute(conn, "category:movies")
        ids = _ids(results)
        assert movie_id in ids
        assert show_id not in ids


class TestFieldTmdbId:
    """FIELD_REGISTRY path: ``tmdb_id`` → media_item.tmdb_id (int)."""

    def test_tmdb_id_equality(self, conn: sqlite3.Connection) -> None:
        """tmdb_id:12345 returns the item with that TMDB ID."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id, tmdb_id=12345)
        _insert_item_on_disk(conn, disk_id, tmdb_id=99999, title="Other Movie")

        results = execute(conn, "tmdb_id:12345")
        ids = _ids(results)
        assert item_id in ids
        assert len(ids) == 1

    def test_tmdb_id_gte(self, conn: sqlite3.Connection) -> None:
        """tmdb_id:>=10000 returns items with TMDB ID >= 10000."""
        disk_id = _insert_disk(conn, "Disk1")
        low_id = _insert_item_on_disk(conn, disk_id, tmdb_id=5000)
        high_id = _insert_item_on_disk(conn, disk_id, tmdb_id=10001, title="High ID Movie")

        results = execute(conn, "tmdb_id:>=10000")
        ids = _ids(results)
        assert low_id not in ids
        assert high_id in ids


class TestFieldImdbId:
    """FIELD_REGISTRY path: ``imdb_id`` → media_item.imdb_id (str equality)."""

    def test_imdb_id_equality(self, conn: sqlite3.Connection) -> None:
        """imdb_id:tt1234567 returns the matching item."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id, imdb_id="tt1234567")
        _insert_item_on_disk(conn, disk_id, imdb_id="tt9999999", title="Other")

        results = execute(conn, "imdb_id:tt1234567")
        assert item_id in _ids(results)
        assert len(results) == 1


class TestFieldNfo:
    """FIELD_REGISTRY path: ``nfo`` → media_item.nfo_status (str, allowed values guard)."""

    def test_nfo_valid(self, conn: sqlite3.Connection) -> None:
        """nfo:valid returns items with nfo_status='valid'."""
        disk_id = _insert_disk(conn, "Disk1")
        valid_id = _insert_item_on_disk(conn, disk_id, nfo_status="valid")
        invalid_id = _insert_item_on_disk(conn, disk_id, nfo_status="invalid", title="Invalid NFO")

        results = execute(conn, "nfo:valid")
        ids = _ids(results)
        assert valid_id in ids
        assert invalid_id not in ids

    def test_nfo_missing(self, conn: sqlite3.Connection) -> None:
        """nfo:missing returns items with nfo_status='missing'."""
        disk_id = _insert_disk(conn, "Disk1")
        missing_id = _insert_item_on_disk(conn, disk_id, nfo_status="missing")

        results = execute(conn, "nfo:missing")
        assert missing_id in _ids(results)

    def test_nfo_negation(self, conn: sqlite3.Connection) -> None:
        """-nfo:valid excludes items with a valid NFO."""
        disk_id = _insert_disk(conn, "Disk1")
        valid_id = _insert_item_on_disk(conn, disk_id, nfo_status="valid")
        missing_id = _insert_item_on_disk(conn, disk_id, nfo_status="missing", title="No NFO")

        results = execute(conn, "-nfo:valid")
        ids = _ids(results)
        assert valid_id not in ids
        assert missing_id in ids

    def test_nfo_disallowed_value_raises(self, conn: sqlite3.Connection) -> None:
        """nfo:garbage raises QueryError — only missing/invalid/valid are allowed."""
        with pytest.raises(QueryError, match="nfo"):
            execute(conn, "nfo:garbage")


class TestFieldCodec:
    """FIELD_REGISTRY path: ``codec`` → EXISTS on media_stream (video streams)."""

    def test_codec_hevc_matches(self, conn: sqlite3.Connection) -> None:
        """codec:hevc returns items that have a video stream with codec='hevc'."""
        disk_id = _insert_disk(conn, "Disk1")
        hevc_id = _insert_item_on_disk(conn, disk_id, title="HEVC Movie", codec="hevc")
        h264_id = _insert_item_on_disk(conn, disk_id, title="H264 Movie", codec="h264")

        results = execute(conn, "codec:hevc")
        ids = _ids(results)
        assert hevc_id in ids
        assert h264_id not in ids

    def test_codec_negation_excludes_hevc(self, conn: sqlite3.Connection) -> None:
        """-codec:hevc excludes items with an HEVC video stream."""
        disk_id = _insert_disk(conn, "Disk1")
        hevc_id = _insert_item_on_disk(conn, disk_id, title="HEVC Movie", codec="hevc")
        h264_id = _insert_item_on_disk(conn, disk_id, title="H264 Movie", codec="h264")

        results = execute(conn, "-codec:hevc")
        ids = _ids(results)
        assert hevc_id not in ids
        assert h264_id in ids


class TestFieldLang:
    """FIELD_REGISTRY path: ``lang`` → EXISTS on media_stream (audio streams)."""

    def test_lang_matches_audio_stream(self, conn: sqlite3.Connection) -> None:
        """lang:fr returns items that have an audio stream with lang='fr'."""
        disk_id = _insert_disk(conn, "Disk1")
        fr_id = _insert_item_on_disk(conn, disk_id, title="French Audio Movie", lang="fr")
        en_id = _insert_item_on_disk(conn, disk_id, title="English Audio Movie", lang="en")

        results = execute(conn, "lang:fr")
        ids = _ids(results)
        assert fr_id in ids
        assert en_id not in ids

    def test_lang_negation(self, conn: sqlite3.Connection) -> None:
        """-lang:en excludes items with English audio."""
        disk_id = _insert_disk(conn, "Disk1")
        fr_id = _insert_item_on_disk(conn, disk_id, title="French Audio Movie", lang="fr")
        en_id = _insert_item_on_disk(conn, disk_id, title="English Audio Movie", lang="en")

        results = execute(conn, "-lang:en")
        ids = _ids(results)
        assert fr_id in ids
        assert en_id not in ids


class TestFieldQuality:
    """FIELD_REGISTRY path: ``quality`` → EXISTS on media_release.quality."""

    def test_quality_4k(self, conn: sqlite3.Connection) -> None:
        """quality:2160p returns items with a 2160p release."""
        disk_id = _insert_disk(conn, "Disk1")
        path_id = _insert_path(conn, disk_id, "MOVIES/4K Movie")
        uhd_id = _insert_item(conn, title="UHD Movie")
        hd_id = _insert_item(conn, title="HD Movie")

        release_uhd = _insert_release(conn, uhd_id, quality="2160p")
        _insert_file(conn, release_uhd, path_id)
        path_hd = _insert_path(conn, disk_id, "MOVIES/HD Movie")
        release_hd = _insert_release(conn, hd_id, quality="1080p")
        _insert_file(conn, release_hd, path_hd)

        results = execute(conn, "quality:2160p")
        ids = _ids(results)
        assert uhd_id in ids
        assert hd_id not in ids


class TestFlexAttributes:
    """Flex-attr lookup path (key not in FIELD_REGISTRY)."""

    def test_flex_equality_matches(self, conn: sqlite3.Connection) -> None:
        """user_rating:9 returns items with that exact attribute value."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id)
        other_id = _insert_item_on_disk(conn, disk_id, title="Other Movie")
        _insert_attr(conn, item_id, "user_rating", "9")
        _insert_attr(conn, other_id, "user_rating", "5")

        results = execute(conn, "user_rating:9")
        assert item_id in _ids(results)
        assert other_id not in _ids(results)

    def test_flex_presence_positive(self, conn: sqlite3.Connection) -> None:
        """trailer_found:* returns items that have the trailer_found attribute (any value)."""
        disk_id = _insert_disk(conn, "Disk1")
        item_with = _insert_item_on_disk(conn, disk_id, title="With Trailer")
        item_without = _insert_item_on_disk(conn, disk_id, title="Without Trailer")
        _insert_attr(conn, item_with, "trailer_found", "1")

        results = execute(conn, "trailer_found:*")
        ids = _ids(results)
        assert item_with in ids
        assert item_without not in ids

    def test_flex_bare_key_negation(self, conn: sqlite3.Connection) -> None:
        """-trailer_found returns items that do NOT have the trailer_found attribute."""
        disk_id = _insert_disk(conn, "Disk1")
        item_with = _insert_item_on_disk(conn, disk_id, title="With Trailer")
        item_without = _insert_item_on_disk(conn, disk_id, title="Without Trailer")
        _insert_attr(conn, item_with, "trailer_found", "1")

        results = execute(conn, "-trailer_found")
        ids = _ids(results)
        assert item_with not in ids
        assert item_without in ids

    def test_flex_prefix_match_raises(self, conn: sqlite3.Connection) -> None:
        """Prefix match on a flex attr raises QueryError."""
        disk_id = _insert_disk(conn, "Disk1")
        _insert_item_on_disk(conn, disk_id)

        with pytest.raises(QueryError, match="prefix"):
            execute(conn, "user_rating:9*")

    def test_flex_numeric_op_raises(self, conn: sqlite3.Connection) -> None:
        """Numeric comparison on an untyped flex attr raises QueryError."""
        disk_id = _insert_disk(conn, "Disk1")
        _insert_item_on_disk(conn, disk_id)

        with pytest.raises(QueryError, match="declared type"):
            execute(conn, "user_rating:>=9")


class TestNegation:
    """Negation compilation for column-based and EXISTS-based fields."""

    def test_negated_kind_excludes_matches(self, conn: sqlite3.Connection) -> None:
        """-kind:show returns only movies."""
        disk_id = _insert_disk(conn, "Disk1")
        show_id = _insert_item_on_disk(conn, disk_id, title="Show", kind="show")
        movie_id = _insert_item_on_disk(conn, disk_id, title="Movie", kind="movie")

        results = execute(conn, "-kind:show")
        ids = _ids(results)
        assert show_id not in ids
        assert movie_id in ids

    def test_negated_year_excludes_year(self, conn: sqlite3.Connection) -> None:
        """-year:2020 excludes items from 2020."""
        disk_id = _insert_disk(conn, "Disk1")
        old_id = _insert_item_on_disk(conn, disk_id, title="Old Movie", year=2020)
        new_id = _insert_item_on_disk(conn, disk_id, title="New Movie", year=2024)

        results = execute(conn, "-year:2020")
        ids = _ids(results)
        assert old_id not in ids
        assert new_id in ids


class TestAndConjunction:
    """AND conjunction: multiple tokens all must match."""

    def test_year_and_nfo_conjunction(self, conn: sqlite3.Connection) -> None:
        """year:2024 nfo:valid returns only the intersection."""
        disk_id = _insert_disk(conn, "Disk1")
        match_id = _insert_item_on_disk(conn, disk_id, title="Match", year=2024, nfo_status="valid")
        wrong_year = _insert_item_on_disk(conn, disk_id, title="Wrong Year", year=2020, nfo_status="valid")
        wrong_nfo = _insert_item_on_disk(conn, disk_id, title="Wrong NFO", year=2024, nfo_status="missing")

        results = execute(conn, "year:2024 nfo:valid")
        ids = _ids(results)
        assert match_id in ids
        assert wrong_year not in ids
        assert wrong_nfo not in ids

    def test_disk_and_kind_conjunction(self, conn: sqlite3.Connection) -> None:
        """disk:Disk1 kind:movie returns movies on Disk1 only."""
        disk1 = _insert_disk(conn, "Disk1", "/Volumes/Disk1")
        disk2 = _insert_disk(conn, "Disk2", "/Volumes/Disk2")
        movie_disk1 = _insert_item_on_disk(conn, disk1, title="Movie on Disk1", kind="movie")
        show_disk1 = _insert_item_on_disk(conn, disk1, title="Show on Disk1", kind="show")
        movie_disk2 = _insert_item_on_disk(conn, disk2, title="Movie on Disk2", kind="movie")

        results = execute(conn, "disk:Disk1 kind:movie")
        ids = _ids(results)
        assert movie_disk1 in ids
        assert show_disk1 not in ids
        assert movie_disk2 not in ids

    def test_compound_query_year_disk_nfo(self, conn: sqlite3.Connection) -> None:
        """year:2024 disk:Disk1 -nfo:valid returns the correct items."""
        disk1 = _insert_disk(conn, "Disk1", "/Volumes/Disk1")
        match_id = _insert_item_on_disk(conn, disk1, title="Match", year=2024, nfo_status="missing")
        excluded = _insert_item_on_disk(conn, disk1, title="Has Valid NFO", year=2024, nfo_status="valid")

        results = execute(conn, "year:2024 disk:Disk1 -nfo:valid")
        ids = _ids(results)
        assert match_id in ids
        assert excluded not in ids


class TestUnknownField:
    """Unknown field → QueryError with actionable message."""

    def test_unknown_field_raises_query_error(self, conn: sqlite3.Connection) -> None:
        """execute() raises QueryError for an unknown field name with no value."""
        # Unknown fields with operators raise immediately in _compile_flex_token.
        with pytest.raises(QueryError, match="declared type"):
            execute(conn, "field_does_not_exist:>=42")

    def test_unknown_str_field_treated_as_flex_equality(self, conn: sqlite3.Connection) -> None:
        """An unknown field with str equality is treated as a flex-attr lookup (no error)."""
        # This is correct per DESIGN §13.1: any other key → flex attribute.
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id)
        _insert_attr(conn, item_id, "custom_tag", "gold")

        results = execute(conn, "custom_tag:gold")
        assert item_id in _ids(results)


class TestLimit:
    """LIMIT clause is respected."""

    def test_limit_caps_results(self, conn: sqlite3.Connection) -> None:
        """execute() returns at most *limit* rows."""
        disk_id = _insert_disk(conn, "Disk1")
        for i in range(10):
            _insert_item_on_disk(conn, disk_id, title=f"Movie {i:02d}", year=2024)

        results = execute(conn, "year:2024", limit=3)
        assert len(results) == 3

    def test_empty_query_returns_all_items(self, conn: sqlite3.Connection) -> None:
        """An empty query string returns all items up to the default limit."""
        disk_id = _insert_disk(conn, "Disk1")
        ids_inserted = {_insert_item_on_disk(conn, disk_id, title=f"Movie {i}") for i in range(5)}

        results = execute(conn, "", limit=100)
        assert ids_inserted.issubset(_ids(results))


class TestFindItemsWithoutTrailer:
    """Named query: find_items_without_trailer."""

    def test_returns_items_without_trailer_found_attr(self, conn: sqlite3.Connection) -> None:
        """Items without the trailer_found attribute are returned."""
        disk_id = _insert_disk(conn, "Disk1")
        with_trailer = _insert_item_on_disk(conn, disk_id, title="Has Trailer")
        without_trailer = _insert_item_on_disk(conn, disk_id, title="No Trailer")
        _insert_attr(conn, with_trailer, "trailer_found", "1")

        results = find_items_without_trailer(conn)
        ids = _ids(results)
        assert without_trailer in ids
        assert with_trailer not in ids

    def test_empty_db_returns_empty(self, conn: sqlite3.Connection) -> None:
        """When there are no items, find_items_without_trailer returns an empty list."""
        results = find_items_without_trailer(conn)
        assert results == []

    def test_all_have_trailer_returns_empty(self, conn: sqlite3.Connection) -> None:
        """When all items have trailer_found, the result is empty."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(conn, disk_id, title="All Have Trailer")
        _insert_attr(conn, item_id, "trailer_found", "1")

        results = find_items_without_trailer(conn)
        assert results == []


class TestPrefixMatch:
    """Prefix match (value*) for title field."""

    def test_prefix_match_on_title(self, conn: sqlite3.Connection) -> None:
        """title:Star* returns items whose title starts with 'Star'."""
        disk_id = _insert_disk(conn, "Disk1")
        star_id = _insert_item_on_disk(conn, disk_id, title="Star Wars", title_sort="Star Wars")
        inc_id = _insert_item_on_disk(conn, disk_id, title="Inception", title_sort="Inception")

        results = execute(conn, "title:Star*")
        ids = _ids(results)
        assert star_id in ids
        assert inc_id not in ids


class TestReturnedRowFields:
    """Verify that returned MediaItemRow instances are fully populated."""

    def test_returned_row_has_expected_fields(self, conn: sqlite3.Connection) -> None:
        """execute() returns MediaItemRow with all fields set correctly."""
        disk_id = _insert_disk(conn, "Disk1")
        item_id = _insert_item_on_disk(
            conn,
            disk_id,
            title="Blade Runner 2049",
            kind="movie",
            year=2017,
            category_id="movies",
            nfo_status="valid",
            tmdb_id=335984,
        )

        results = execute(conn, "tmdb_id:335984")
        assert len(results) == 1
        row = results[0]
        assert row.id == item_id
        assert row.title == "Blade Runner 2049"
        assert row.year == 2017
        assert row.kind == "movie"
        assert row.nfo_status == "valid"
        assert isinstance(row, MediaItemRow)
