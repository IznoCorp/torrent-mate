"""Link freshly-walked ``media_file`` rows to ``media_release`` rows.

Stage A (full scan) inserts ``media_file`` rows with ``release_id IS NULL``
because no release row exists yet (DESIGN §11.3, §6.2). Stage B (enrich)
needs a release on each file before the NFO / artwork inventory steps can
attach to a ``media_item``.

This module performs the linkage by walking the file's directory chain and
matching it against ``item_attribute.dispatch_path``: dispatch indexing
already maps every top-level media folder to a ``media_item`` via that
attribute, so the release linker just needs to follow the chain back up,
detect intermediate ``Saison NN`` segments for TV hierarchy, parse the
episode number from the filename, and create / fetch the appropriate
``season``, ``episode``, and ``media_release`` rows.

Default releases (NULL ``quality`` / ``edition`` / ``primary_lang``) are used
for the V1 implementation; quality-specific releases can be introduced
later by parsing release tags from filenames.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from personalscraper.indexer.repos.item_repo import _ATTR_DISPATCH_PATH, _canonical_title
from personalscraper.logger import get_logger

log = get_logger("indexer.release_linker")


from personalscraper.naming_patterns import season_number_from_dir as parse_season_dir  # noqa: E402

# Match ``S01E02`` / ``s1e2`` / ``1x02`` style markers anywhere in the filename.
# The SxxEyy form optionally carries a span suffix (``S09E23-24`` / ``S01E01-E22``,
# hyphen or en-dash) that must follow the start number IMMEDIATELY — a spaced
# `` - `` separates the episode marker from the title, never a span
# (``S09E23 - 24 heures chrono`` is episode 23, not 23–24).
_EPISODE_RE = re.compile(r"[sS](\d{1,2})[eE](\d{1,3})(?:[-–][eE]?(\d{1,3}))?|(\d{1,2})x(\d{1,3})")

# Widest believable span (a whole-season Intégrale file): anything larger is a
# parsing artefact (e.g. a year glued to the marker) and degrades to single.
_MAX_SPAN_LENGTH = 60


def parse_episode_span(filename: str) -> tuple[int, int] | None:
    """Extract the full ``(start, end)`` episode coverage from a filename.

    Recognises ``SxxEyy`` (with an optional ``-zz`` / ``-Ezz`` span suffix) and
    ``xxXyy`` markers. A single-episode file returns ``(n, n)``. A reversed or
    absurdly long span degrades to ``(start, start)`` — the start episode is
    always real, the suffix is then treated as title noise.

    Args:
        filename: Bare filename (no directory component).

    Returns:
        ``(start, end)`` episode numbers, or ``None`` when no marker is found.
    """
    match = _EPISODE_RE.search(filename)
    if match is None:
        return None
    # Either group 2 (S01E02) or group 5 (1x02) carries the start number.
    start_str = match.group(2) or match.group(5)
    if start_str is None:
        return None
    start = int(start_str)
    end_str = match.group(3)
    if end_str is None:
        return (start, start)
    end = int(end_str)
    if end <= start or (end - start) > _MAX_SPAN_LENGTH:
        return (start, start)
    return (start, end)


def parse_episode_number(filename: str) -> int | None:
    """Extract the FIRST episode number from a filename.

    Thin wrapper over :func:`parse_episode_span` kept for callers that only
    need the primary number (e.g. NFO title attachment).

    Args:
        filename: Bare filename (no directory component).

    Returns:
        Episode number as int, or ``None`` when no marker is found.
    """
    span = parse_episode_span(filename)
    return span[0] if span is not None else None


_TITLE_YEAR_RE = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*$")


def _parse_title_year(folder_name: str) -> tuple[str, int | None]:
    """Split a ``Title (Year)`` folder name into its components.

    Falls back to ``(folder_name, None)`` when no year suffix is present.

    Args:
        folder_name: Bare directory name (no parent path).

    Returns:
        ``(title, year)`` — year is ``None`` when the folder name does not
        end with a 4-digit year in parentheses.
    """
    match = _TITLE_YEAR_RE.match(folder_name)
    if match is None:
        return folder_name, None
    return match.group("title").strip(), int(match.group("year"))


def find_item_for_path(conn: sqlite3.Connection, abs_dir: str) -> tuple[int, str, int | None] | None:
    """Locate the owning ``media_item`` for a file given its parent directory.

    Walks parents of ``abs_dir`` upward, peeling off any ``Saison NN``
    segment along the way. Three matching strategies are attempted at
    each parent level, in order:

    1. ``item_attribute.dispatch_path`` exact match — fastest and
       primary; works for items registered via dispatch.
    2. ``media_item.title`` exact match against the folder name —
       catches items where dispatch indexed the folder as the title.
       Post-migration 007 the lookup uses ``_canonical_title()`` so
       on-disk ``"Inception (2010)"`` matches stored ``"Inception"``
       (year suffix stripped).
    3. ``media_item.(title, year)`` match after parsing ``Title (Year)``
       from the folder name — catches items registered via the
       library scanner (``parse_title_year`` strips the year suffix).

    Args:
        conn: Open SQLite connection.
        abs_dir: Absolute path of the directory containing the file.

    Returns:
        ``(item_id, kind, season_num)`` triple — ``season_num`` is the
        season number captured from a ``Saison NN`` parent (``None`` for
        files not inside a season directory). Returns ``None`` when no
        matching item is found within 6 parent levels.
    """
    season_num: int | None = None
    current = Path(abs_dir)
    for _ in range(6):  # safety bound — deeper than any real layout
        season_capture = parse_season_dir(current.name)
        if season_capture is not None and season_num is None:
            season_num = season_capture
            parent = current.parent
            if parent == current:
                break
            current = parent
            continue

        # Strategy 1: dispatch_path exact match (fast, indexed).
        # ``COLLATE NOCASE`` because macFUSE-NTFS may surface a folder
        # with different casing than what was stored at dispatch time
        # (the FS preserves the original case but lookups by SQL `=`
        # are case-sensitive in SQLite by default).
        row = conn.execute(
            "SELECT mi.id, mi.kind FROM media_item mi "
            "JOIN item_attribute ia ON ia.item_id = mi.id "
            "WHERE ia.key = ? AND ia.value = ? COLLATE NOCASE",
            (_ATTR_DISPATCH_PATH, str(current)),
        ).fetchone()
        if row is not None:
            return int(row[0]), str(row[1]), season_num

        # Strategy 2: title equals the folder name (dispatch-style title).
        # Case-insensitive: a re-scrape may have rewritten the canonical
        # title with different casing (``Les Griffes de la Nuit`` vs
        # ``Les Griffes de la nuit``) without us renaming the on-disk
        # folder. Without NOCASE the linker leaves every file orphan.
        #
        # After migration 007 stored titles are canonicalised (no year
        # suffix), so "Inception (2010)" on disk won't match stored
        # "Inception".  Canonicalise before lookup.
        canonical = _canonical_title(current.name)
        row = conn.execute(
            "SELECT id, kind FROM media_item WHERE title = ? COLLATE NOCASE LIMIT 1",
            (canonical,),
        ).fetchone()
        if row is not None:
            return int(row[0]), str(row[1]), season_num

        # Strategy 3: parsed (title, year) match.
        parsed_title, parsed_year = _parse_title_year(current.name)
        if parsed_year is not None:
            row = conn.execute(
                "SELECT id, kind FROM media_item WHERE title = ? COLLATE NOCASE AND year = ? LIMIT 1",
                (parsed_title, parsed_year),
            ).fetchone()
            if row is not None:
                return int(row[0]), str(row[1]), season_num

        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def get_or_create_season(conn: sqlite3.Connection, item_id: int, season_num: int) -> int:
    """Find or insert a ``season`` row for ``(item_id, season_num)``.

    Args:
        conn: Open SQLite connection.
        item_id: PK of the owning show ``media_item``.
        season_num: Season number (>= 0).

    Returns:
        PK of the matching or newly inserted ``season`` row.
    """
    row = conn.execute(
        "SELECT id FROM season WHERE item_id = ? AND number = ?",
        (item_id, season_num),
    ).fetchone()
    if row is not None:
        return int(row[0])
    cursor = conn.execute(
        "INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo) VALUES (?, ?, 0, 0, 0)",
        (item_id, season_num),
    )
    return int(cursor.lastrowid)  # type: ignore[arg-type]


def get_or_create_episode(conn: sqlite3.Connection, season_id: int, episode_num: int) -> int:
    """Find or insert an ``episode`` row for ``(season_id, episode_num)``.

    Args:
        conn: Open SQLite connection.
        season_id: PK of the owning ``season`` row.
        episode_num: Episode number (>= 0).

    Returns:
        PK of the matching or newly inserted ``episode`` row.
    """
    row = conn.execute(
        "SELECT id FROM episode WHERE season_id = ? AND number = ?",
        (season_id, episode_num),
    ).fetchone()
    if row is not None:
        return int(row[0])
    cursor = conn.execute(
        "INSERT INTO episode (season_id, number, title) VALUES (?, ?, NULL)",
        (season_id, episode_num),
    )
    return int(cursor.lastrowid)  # type: ignore[arg-type]


def get_or_create_default_release(
    conn: sqlite3.Connection,
    item_id: int | None = None,
    episode_id: int | None = None,
    episode_end_id: int | None = None,
) -> int:
    """Find or insert the default ``media_release`` for an item or episode.

    The default release uses NULL ``quality`` / ``edition`` / ``primary_lang``
    — matches the partial UNIQUE index on ``media_release`` for that triple.
    Exactly one of ``item_id`` or ``episode_id`` must be set.

    Args:
        conn: Open SQLite connection.
        item_id: PK of the ``media_item`` for movie / show-level releases.
        episode_id: PK of the ``episode`` for episode-level releases (the FIRST
            episode when the file covers a span).
        episode_end_id: PK of the LAST episode covered by a multi-episode file
            (migration 014), or ``None`` for single-episode releases. When an
            existing release is found without a span end, a non-``None`` value
            upgrades it in place (idempotent span repair).

    Returns:
        PK of the matching or newly inserted ``media_release`` row.

    Raises:
        ValueError: If both or neither of ``item_id`` / ``episode_id`` is set,
            or if ``episode_end_id`` is given for an item-level release.
    """
    if (item_id is None) == (episode_id is None):
        raise ValueError("exactly one of item_id or episode_id must be set")
    if item_id is not None and episode_end_id is not None:
        raise ValueError("episode_end_id only applies to episode-level releases")

    if item_id is not None:
        row = conn.execute(
            "SELECT id FROM media_release WHERE item_id = ? AND episode_id IS NULL "
            "AND quality IS NULL AND edition IS NULL AND primary_lang IS NULL",
            (item_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, episode_end_id FROM media_release WHERE episode_id = ? AND item_id IS NULL "
            "AND quality IS NULL AND edition IS NULL AND primary_lang IS NULL",
            (episode_id,),
        ).fetchone()
    if row is not None:
        release_id = int(row[0])
        # Span upgrade: a release linked before span support (or by a
        # single-episode variant of the same episode) gains the span end.
        if episode_id is not None and episode_end_id is not None and row[1] != episode_end_id:
            conn.execute(
                "UPDATE media_release SET episode_end_id = ? WHERE id = ?",
                (episode_end_id, release_id),
            )
        return release_id
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, episode_id, episode_end_id, quality, edition, primary_lang) "
        "VALUES (?, ?, ?, NULL, NULL, NULL)",
        (item_id, episode_id, episode_end_id),
    )
    return int(cursor.lastrowid)  # type: ignore[arg-type]


def recompute_season_episode_counts(conn: sqlite3.Connection) -> int:
    """Refresh ``season.episode_count`` to match the actual episode rows.

    The linker creates ``season`` rows with ``episode_count=0`` and inserts
    ``episode`` rows lazily as files are enriched, so the stored counter
    drifts during a pass. Call at the end of an enrich run to bring the
    cached value back in sync.

    Args:
        conn: Open SQLite connection.

    Returns:
        Number of season rows whose ``episode_count`` was updated.
    """
    cursor = conn.execute(
        """
        UPDATE season
           SET episode_count = (
               SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id
           )
         WHERE episode_count != (
               SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id
           )
        """
    )
    updated = cursor.rowcount
    if updated > 0:
        log.info("indexer.release_linker.episode_count_recomputed", updated=updated)
    return updated


def link_file_to_release(conn: sqlite3.Connection, file_id: int, abs_path: str) -> int | None:
    """Link a ``media_file`` row to its ``media_release``.

    Resolves the owning item via :func:`find_item_for_path`, creates the
    season + episode chain when the file lives in a ``Saison NN``
    directory, then upserts a default release and updates
    ``media_file.release_id``. Idempotent: re-linking an already-linked
    file is a no-op.

    Args:
        conn: Open SQLite connection.
        file_id: PK of the ``media_file`` row to link.
        abs_path: Absolute path of the file on disk.

    Returns:
        PK of the linked ``media_release`` row, or ``None`` when no
        owning ``media_item`` could be located (file remains unlinked,
        caller can decide to surface this via item_issue / log).
    """
    parent_dir = str(Path(abs_path).parent)
    resolved = find_item_for_path(conn, parent_dir)
    if resolved is None:
        return None

    item_id, kind, season_num = resolved

    # Episode-level release path: TV show file inside Saison NN with parseable number.
    if kind == "show" and season_num is not None:
        span = parse_episode_span(Path(abs_path).name)
        if span is not None:
            start, end = span
            season_id = get_or_create_season(conn, item_id, season_num)
            # Create a row for EVERY episode the file covers so ownership can
            # expand the span (Friends S09E23-24 owns both 23 and 24).
            episode_id = get_or_create_episode(conn, season_id, start)
            episode_end_id: int | None = None
            for num in range(start + 1, end + 1):
                episode_end_id = get_or_create_episode(conn, season_id, num)
            release_id = get_or_create_default_release(conn, episode_id=episode_id, episode_end_id=episode_end_id)
        else:
            # Episode marker missing — fall back to item-level release.
            release_id = get_or_create_default_release(conn, item_id=item_id)
    else:
        # Movie file, or sidecar at the show root (poster.jpg, tvshow.nfo, etc.).
        release_id = get_or_create_default_release(conn, item_id=item_id)

    conn.execute(
        "UPDATE media_file SET release_id = ? WHERE id = ?",
        (release_id, file_id),
    )
    return release_id
