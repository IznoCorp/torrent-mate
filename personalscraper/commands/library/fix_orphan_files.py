"""Repair ``media_file`` orphan rows with ``release_id IS NULL`` (DEVIATION #8, invariant AO).

Some ``media_file`` rows have ``release_id IS NULL`` after incomplete
ingest/dispatch or DB recovery. This command locates each orphan, resolves
the owning ``media_item`` via ``item_attribute.dispatch_path``, and links
the file to its ``media_release``.

Matching is attempted in two tiers:

1. **Item-level** — find ``media_release`` rows where ``item_id`` matches
   the resolved item.  This covers movies and show-level releases.
2. **Episode-level** — when no item-level release is found AND the filename
   matches an ``SxxEyy`` / ``xxXyy`` pattern, the command looks up the
   season and episode rows, then searches for ``media_release`` rows keyed
   on ``episode_id``.

Dry-run by default — use ``--apply`` to execute the UPDATE.

Examples:
    personalscraper library-fix-orphan-files
    personalscraper library-fix-orphan-files --apply
    personalscraper library-fix-orphan-files --db /custom/path/library.db --apply
"""

from __future__ import annotations

import re as _re
import sqlite3 as _sqlite3
from dataclasses import dataclass, fields, replace
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.indexer.release_linker import parse_episode_number
from personalscraper.logger import get_logger

log = get_logger("cli")

_ORPHANS_QUERY = """
SELECT mf.id, mf.path_id, mf.filename, p.rel_path, p.disk_id
FROM media_file mf
JOIN path p ON p.id = mf.path_id
WHERE mf.release_id IS NULL
"""

_FIND_ITEM_BY_ABS_PATH = """
SELECT mi.id, mi.kind
FROM media_item mi
JOIN item_attribute ia ON ia.item_id = mi.id
WHERE ia.key = 'dispatch_path' AND ia.value = ? COLLATE NOCASE
LIMIT 1
"""

_CANDIDATE_RELEASES_QUERY = """
SELECT id, quality FROM media_release WHERE item_id = ?
"""

_FIND_SEASON_SQL = """
SELECT id FROM season WHERE item_id = ? AND number = ?
"""

_FIND_EPISODE_SQL = """
SELECT id FROM episode WHERE season_id = ? AND number = ?
"""

_CANDIDATE_EPISODE_RELEASES_SQL = """
SELECT id, quality FROM media_release WHERE episode_id = ?
"""

_UPDATE_RELEASE_SQL = """
UPDATE media_file SET release_id = ? WHERE id = ?
"""

# Regex mirroring _EPISODE_RE in release_linker.py — extracts season number
# from SxxEyy (group 1) or xxXyy (group 3) markers.
_SEASON_EPISODE_RE = _re.compile(r"[sS](\d{1,2})[eE](\d{1,3})|(\d{1,2})x(\d{1,3})")


@dataclass
class FixOrphanFilesStats:
    """Counters for ``library_fix_orphan_files``.

    ``items_scanned`` is the total number of orphan ``media_file`` rows
    examined.  ``fixed`` tracks files successfully linked to a single
    candidate ``media_release``.  ``episode_level_fixed`` is the subset
    of ``fixed`` matched via episode-level lookups.  ``item_level_fixed``
    is the complementary subset matched via item-level lookups.
    ``no_release`` counts files where no owning item or no release was
    found.  ``ambiguous`` counts files with multiple candidate releases
    that require manual review.
    """

    items_scanned: int = 0
    fixed: int = 0
    episode_level_fixed: int = 0
    item_level_fixed: int = 0
    no_release: int = 0
    ambiguous: int = 0

    def frozen(self) -> "FixOrphanFilesStats":
        """Return an independent copy (defensive for downstream emitters)."""
        return replace(self)

    def to_cli_json(self, *, apply: bool) -> dict[str, int | bool]:
        """Project to the CLI JSON output shape.

        Args:
            apply: Whether ``--apply`` was passed. Controls the key name for
                fixed rows (``"fixed"`` vs ``"would_fix"``).

        Returns:
            Dict with ``apply`` flag and the relevant count keys.
        """
        base: dict[str, int | bool] = {
            "apply": apply,
            "items_scanned": self.items_scanned,
            "episode_level_fixed": self.episode_level_fixed,
            "item_level_fixed": self.item_level_fixed,
            "no_release": self.no_release,
            "ambiguous": self.ambiguous,
        }
        base["fixed" if apply else "would_fix"] = self.fixed
        return base

    def to_log_dict(self) -> dict[str, int]:
        """Project to a ``dict[str, int]`` suitable for structlog ``stats=``."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


def _find_item_for_orphan(conn: _sqlite3.Connection, rel_path: str, disk_id: int) -> tuple[int, str] | None:
    """Resolve the owning ``media_item`` for a file given its path metadata.

    Reconstructs the absolute directory path from ``disk.mount_path`` and
    ``path.rel_path``, then matches against ``item_attribute.dispatch_path``
    (exact match, case-insensitive).  Walks up parent directories when no
    match is found (handles files inside ``Saison NN`` subdirectories).

    Args:
        conn: Open SQLite connection.
        rel_path: Relative directory path from the ``path`` table.
        disk_id: FK to the ``disk`` table for mount-path resolution.

    Returns:
        ``(item_id, kind)`` tuple, or ``None`` when no matching item is
        found within 6 parent levels or the disk has no ``mount_path``.
    """
    disk_row = conn.execute("SELECT mount_path FROM disk WHERE id = ?", (disk_id,)).fetchone()
    if disk_row is None or disk_row["mount_path"] is None:
        return None

    abs_dir = str(Path(disk_row["mount_path"]) / rel_path)
    current = Path(abs_dir)

    for _ in range(6):
        row = conn.execute(_FIND_ITEM_BY_ABS_PATH, (str(current),)).fetchone()
        if row is not None:
            return (int(row[0]), str(row[1]))

        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _find_candidate_releases(conn: _sqlite3.Connection, item_id: int) -> list[tuple[int, str | None]]:
    """Return ``(id, quality)`` for every ``media_release`` on *item_id*."""
    rows = conn.execute(_CANDIDATE_RELEASES_QUERY, (item_id,)).fetchall()
    return [(int(r[0]), r[1]) for r in rows]


def _parse_season_number(filename: str) -> int | None:
    """Extract the season number from a filename using ``SxxEyy`` / ``xxXyy``.

    Mirrors ``_EPISODE_RE`` in ``release_linker.py`` — group 1 or 3 carries
    the season number.

    Args:
        filename: Bare filename (no directory component).

    Returns:
        Season number as int, or ``None`` when no marker is found.
    """
    match = _SEASON_EPISODE_RE.search(filename)
    if match is None:
        return None
    season = match.group(1) or match.group(3)
    return int(season) if season is not None else None


def _try_episode_level_link(
    conn: _sqlite3.Connection,
    item_id: int,
    filename: str,
) -> list[tuple[int, str | None]]:
    """Find episode-level ``media_release`` candidates for an orphan file.

    Parses season + episode numbers from *filename*, looks up the matching
    ``season`` and ``episode`` rows under *item_id*, then returns every
    ``media_release`` keyed on ``episode_id``.

    Args:
        conn: Open SQLite connection.
        item_id: The resolved ``media_item.id`` for the orphan.
        filename: Bare filename (to extract ``SxxEyy`` / ``xxXyy``).

    Returns:
        ``(release_id, quality)`` tuples, or an empty list when the filename
        doesn't match an episode pattern, no season row exists, no episode
        row exists, or no episode-level releases exist.
    """
    episode_num = parse_episode_number(filename)
    if episode_num is None:
        return []

    season_num = _parse_season_number(filename)
    if season_num is None:
        return []

    season_row = conn.execute(_FIND_SEASON_SQL, (item_id, season_num)).fetchone()
    if season_row is None:
        log.info("episode_no_season", item_id=item_id, filename=filename, season_num=season_num)
        return []

    season_id = int(season_row["id"])

    episode_row = conn.execute(_FIND_EPISODE_SQL, (season_id, episode_num)).fetchone()
    if episode_row is None:
        log.info(
            "episode_not_in_db",
            item_id=item_id,
            filename=filename,
            season_num=season_num,
            episode_num=episode_num,
        )
        return []

    episode_id = int(episode_row["id"])
    rows = conn.execute(_CANDIDATE_EPISODE_RELEASES_SQL, (episode_id,)).fetchall()
    return [(int(r[0]), r[1]) for r in rows]


@app.command("library-fix-orphan-files")
@handle_cli_errors
def library_fix_orphan_files(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (default: dry-run preview)."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Repair ``media_file`` rows with ``release_id IS NULL``.

    For each orphan file, resolves the owning ``media_item`` via the
    ``item_attribute.dispatch_path`` registry, then attempts to link to a
    ``media_release`` in two tiers:

    1. **Item-level** — match ``media_release.item_id``.
    2. **Episode-level** — when no item-level match is found and the
       filename contains an ``SxxEyy`` / ``xxXyy`` marker, look up the
       season + episode rows and match ``media_release.episode_id``.

    Dry-run by default — use ``--apply`` to execute the UPDATE statements.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415

    cfg = ctx.obj.config if ctx.obj is not None else load_config(config)

    if db is not None:
        db_path = db
    elif cfg.indexer.db_path is not None:
        db_path = Path(cfg.indexer.db_path)
    else:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)

    from personalscraper.indexer.db import _apply_pragmas as _db_apply_pragmas  # noqa: PLC0415

    conn = _sqlite3.connect(str(db_path))
    _db_apply_pragmas(conn)
    conn.row_factory = _sqlite3.Row

    stats = FixOrphanFilesStats()

    log.info("orphan_files_scan_started")

    orphans = conn.execute(_ORPHANS_QUERY).fetchall()
    stats.items_scanned = len(orphans)

    updates: list[tuple[int, int]] = []

    for orphan in orphans:
        file_id = int(orphan["id"])
        rel_path = str(orphan["rel_path"])
        disk_id = int(orphan["disk_id"])

        resolved = _find_item_for_orphan(conn, rel_path, disk_id)
        if resolved is None:
            stats.no_release += 1
            continue

        item_id, _kind = resolved
        filename = str(orphan["filename"])
        releases = _find_candidate_releases(conn, item_id)

        if len(releases) == 0:
            episode_releases = _try_episode_level_link(conn, item_id, filename)
            if len(episode_releases) == 1:
                if apply:
                    updates.append((episode_releases[0][0], file_id))
                stats.fixed += 1
                stats.episode_level_fixed += 1
            elif len(episode_releases) == 0:
                stats.no_release += 1
            else:
                stats.ambiguous += 1
        elif len(releases) == 1:
            if apply:
                updates.append((releases[0][0], file_id))
            stats.fixed += 1
            stats.item_level_fixed += 1
        else:
            stats.ambiguous += 1

    if apply and updates:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for release_id, file_id in updates:
                conn.execute(_UPDATE_RELEASE_SQL, (release_id, file_id))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn.close()

    log.info("orphan_files_done", stats=stats.to_log_dict())

    emit(stats.frozen().to_cli_json(apply=apply))
