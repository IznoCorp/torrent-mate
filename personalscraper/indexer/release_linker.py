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

from personalscraper.indexer.repos.item_repo import _ATTR_DISPATCH_PATH
from personalscraper.logger import get_logger

log = get_logger("indexer.release_linker")


# Match French ``Saison 01`` / ``Saison 1`` and English ``Season 01`` / ``Season 1``.
_SEASON_DIR_RE = re.compile(r"^Sa[ie]son\s+(\d+)$|^Season\s+(\d+)$", re.IGNORECASE)

# Match ``S01E02`` / ``s1e2`` / ``1x02`` style markers anywhere in the filename.
_EPISODE_RE = re.compile(r"[sS](\d{1,2})[eE](\d{1,3})|(\d{1,2})x(\d{1,3})")


def parse_season_dir(name: str) -> int | None:
    """Return the season number when ``name`` matches a season directory.

    Args:
        name: Bare directory name (no parent path).

    Returns:
        Season number as int, or ``None`` when ``name`` is not a season dir.
    """
    match = _SEASON_DIR_RE.match(name)
    if match is None:
        return None
    captured = next((g for g in match.groups() if g is not None), None)
    return int(captured) if captured is not None else None


def parse_episode_number(filename: str) -> int | None:
    """Extract the episode number from a filename.

    Recognises ``SxxEyy`` and ``xxXyy`` markers. Returns the first episode
    number when a multi-episode marker is present (e.g. ``S01E25-26`` →
    ``25``); the second episode is folded into the same release in V1.

    Args:
        filename: Bare filename (no directory component).

    Returns:
        Episode number as int, or ``None`` when no marker is found.
    """
    match = _EPISODE_RE.search(filename)
    if match is None:
        return None
    # Either group 2 (S01E02) or group 4 (1x02) carries the episode number.
    episode = match.group(2) or match.group(4)
    return int(episode) if episode is not None else None


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
       catches items where dispatch indexed the folder as the title
       (e.g. ``"Inception (2010)"``).
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
        row = conn.execute(
            "SELECT mi.id, mi.kind FROM media_item mi "
            "JOIN item_attribute ia ON ia.item_id = mi.id "
            "WHERE ia.key = ? AND ia.value = ?",
            (_ATTR_DISPATCH_PATH, str(current)),
        ).fetchone()
        if row is not None:
            return int(row[0]), str(row[1]), season_num

        # Strategy 2: title equals the folder name (dispatch-style title).
        row = conn.execute(
            "SELECT id, kind FROM media_item WHERE title = ? LIMIT 1",
            (current.name,),
        ).fetchone()
        if row is not None:
            return int(row[0]), str(row[1]), season_num

        # Strategy 3: parsed (title, year) match (library-scanner style).
        parsed_title, parsed_year = _parse_title_year(current.name)
        if parsed_year is not None:
            row = conn.execute(
                "SELECT id, kind FROM media_item WHERE title = ? AND year = ? LIMIT 1",
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
) -> int:
    """Find or insert the default ``media_release`` for an item or episode.

    The default release uses NULL ``quality`` / ``edition`` / ``primary_lang``
    — matches the partial UNIQUE index on ``media_release`` for that triple.
    Exactly one of ``item_id`` or ``episode_id`` must be set.

    Args:
        conn: Open SQLite connection.
        item_id: PK of the ``media_item`` for movie / show-level releases.
        episode_id: PK of the ``episode`` for episode-level releases.

    Returns:
        PK of the matching or newly inserted ``media_release`` row.

    Raises:
        ValueError: If both or neither of ``item_id`` / ``episode_id`` is set.
    """
    if (item_id is None) == (episode_id is None):
        raise ValueError("exactly one of item_id or episode_id must be set")

    if item_id is not None:
        row = conn.execute(
            "SELECT id FROM media_release WHERE item_id = ? AND episode_id IS NULL "
            "AND quality IS NULL AND edition IS NULL AND primary_lang IS NULL",
            (item_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM media_release WHERE episode_id = ? AND item_id IS NULL "
            "AND quality IS NULL AND edition IS NULL AND primary_lang IS NULL",
            (episode_id,),
        ).fetchone()
    if row is not None:
        return int(row[0])
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (?, ?, NULL, NULL, NULL)",
        (item_id, episode_id),
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
        episode_num = parse_episode_number(Path(abs_path).name)
        if episode_num is not None:
            season_id = get_or_create_season(conn, item_id, season_num)
            episode_id = get_or_create_episode(conn, season_id, episode_num)
            release_id = get_or_create_default_release(conn, episode_id=episode_id)
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
