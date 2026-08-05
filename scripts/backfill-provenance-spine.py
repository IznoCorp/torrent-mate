#!/usr/bin/env python3
"""§13 repair — rebuild the provenance journeys the spine lost (feature ``spine-truth``).

A correction that stops the bug but leaves the data it falsified is unfinished work
(product-intent §13: « (1) le code corrigé, (2) l'état existant réparé, (3) le contrôle
exécutable à zéro anomalie. Les trois, ou rien. »). Two defects erased 57 acquisitions
from ``staging_provenance``:

- season grabs were refused by a ``CHECK`` that predated ``kind='season'`` (migration 015);
- episode journeys were nested under a show folder whose ancestor the scrape renamed, so
  the dispatch never correlated them and ``prune_stale`` swept them away.

This script rebuilds those rows **from the databases that still hold the facts** — never
from the logs, which rotate and were already incomplete when the bug was found:

===================  ==================================================  =============
Field                Source                                              Exactness
===================  ==================================================  =============
``info_hash``        ``wanted.grabbed_hash``                             exact
``kind``             ``wanted.kind``                                     exact
``media_ref_json``   ``wanted.media_ref_json``                           exact
``followed_id``      ``wanted.followed_id``                              exact
``grabbed_at``       ``seed_obligation.added_at`` (written at grab time  exact
                     since 2026-07-15)
``dispatch_path``    ``library.db`` → ``item_attribute['dispatch_path']``  exact — it is
                     of the item matched by provider ID, else the        the value the
                     obligation's own ``dispatched_path``                dispatcher wrote
``dispatched_at``    ``media_file.last_verified_at`` of the work's file  to the minute
``status``           ``dispatched`` when a landing is PROVEN and the     derived
                     queue row is closed, else ``grabbed``
===================  ==================================================  =============

``ingest_path``, ``current_path``, ``scraped_at``, ``scraped_ref_json``, the resolution
projection and every ``*_run_uid`` are **left NULL**. The staging folders were deleted;
that information no longer exists anywhere and inventing a plausible path would be exactly
the lie §méthode forbids. A reconstructed row therefore says « grabbé ici, atterri là,
milieu inconnu » — and, as a welcome side effect, a NULL ``current_path`` keeps
``prune_stale`` (which only looks at rows that have one) from ever treating these audit
records as orphans.

Dry-run by default. Nothing is written without ``--apply``.

Usage:
    python scripts/backfill-provenance-spine.py            # preview
    python scripts/backfill-provenance-spine.py --apply    # write
    python scripts/backfill-provenance-spine.py --json     # machine-readable preview
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass

#: Queue statuses that mean the acquisition is closed — the only ones for which a proven
#: library landing may be recorded as a completed ``dispatched`` journey.
_CLOSED_WANTED_STATUSES = ("done",)

#: Preference order when several ``wanted`` rows share one hash (a season pack absorbing
#: its episodes): the pack IS the grab, so it describes the journey.
_KIND_PRIORITY = {"season": 0, "movie": 1, "episode": 2}


@dataclass(frozen=True)
class RebuiltRow:
    """One provenance journey rebuilt from the surviving databases.

    Attributes:
        info_hash: The grabbed torrent hash (lowercase) — the spine's primary key.
        kind: ``movie`` / ``episode`` / ``season``, from the wanted row.
        followed_id: The follow the acquisition belongs to, or None.
        media_ref_json: The identity known at grab time, verbatim from the wanted row.
        grabbed_at: Epoch of the grab, or None when no seed obligation recorded it.
        dispatch_path: The folder the media landed in, or None when unprovable.
        dispatched_at: Epoch the library last verified the landed file, or None.
        status: ``dispatched`` or ``grabbed`` — the furthest stage that can be PROVEN.
        title: Follow title, for the human report only.
    """

    info_hash: str
    kind: str | None
    followed_id: int | None
    media_ref_json: str | None
    grabbed_at: int | None
    dispatch_path: str | None
    dispatched_at: int | None
    status: str
    title: str

    def line(self) -> str:
        """Render the row as one human report line."""
        landed = self.dispatch_path or "— (atterrissage non prouvé)"
        return f"{self.info_hash[:12]}… {self.kind or '?':8} {self.title:32.32} → {self.status:10} {landed}"


def _parse_ref(raw: str | None) -> tuple[int | None, int | None, str | None]:
    """Parse a ``media_ref_json`` payload into ``(tvdb_id, tmdb_id, imdb_id)``.

    Args:
        raw: The JSON text stored in ``media_ref_json``, possibly None or malformed.

    Returns:
        The provider-id triple; a missing or malformed payload yields all-None.
    """
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    def _as_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None  # type: ignore[call-overload]
        except (TypeError, ValueError):
            return None

    imdb = data.get("imdb_id")
    return _as_int(data.get("tvdb_id")), _as_int(data.get("tmdb_id")), str(imdb) if imdb else None


#: Provider-id predicates over ``media_item.external_ids_json`` (indexer migration 005).
_PROVIDER_CLAUSES = {
    "tvdb": "json_extract(external_ids_json, '$.tvdb.series_id') = CAST(? AS TEXT)",
    "tmdb": "json_extract(external_ids_json, '$.tmdb.series_id') = CAST(? AS TEXT)",
    "imdb": "json_extract(external_ids_json, '$.imdb.series_id') = CAST(? AS TEXT)",
}


def _find_item_id(
    indexer_conn: sqlite3.Connection, *, kind: str, ref: tuple[int | None, int | None, str | None]
) -> int | None:
    """Resolve a work's ``media_item.id`` from its provider IDs (tvdb → tmdb → imdb).

    Args:
        indexer_conn: Open connection to ``library.db``.
        kind: The wanted row's kind (``movie`` maps to a movie item, everything else to a show).
        ref: The ``(tvdb_id, tmdb_id, imdb_id)`` triple from the wanted row.

    Returns:
        The matching item id, or None when the library does not know this work.
    """
    item_kind = "movie" if kind == "movie" else "show"
    for provider, value in zip(("tvdb", "tmdb", "imdb"), ref, strict=True):
        if value is None:
            continue
        sql = f"SELECT id FROM media_item WHERE kind = ? AND {_PROVIDER_CLAUSES[provider]}"  # noqa: S608 — fixed clauses
        row = indexer_conn.execute(sql, (item_kind, value)).fetchone()
        if row is not None:
            return int(row[0])
    return None


def _landing(indexer_conn: sqlite3.Connection, item_id: int, *, kind: str, season: int | None) -> tuple[str | None, int | None]:
    """Return ``(dispatch_path, dispatched_at)`` for a landed work, or ``(None, None)``.

    ``dispatch_path`` is read from ``item_attribute`` — the value the DISPATCHER itself
    recorded when it moved the folder, so it is the destination, not a reconstruction.
    ``dispatched_at`` is the most recent ``last_verified_at`` among the work's live files
    (restricted to the relevant season for a season/episode grab), which dates the landing
    to the minute.

    Args:
        indexer_conn: Open connection to ``library.db``.
        item_id: The resolved ``media_item`` id.
        kind: The wanted row's kind.
        season: The season number for an episode/season grab, else None.

    Returns:
        The landing pair; ``(None, None)`` when the library holds no live file for it.
    """
    attr = indexer_conn.execute(
        "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'dispatch_path'", (item_id,)
    ).fetchone()
    dispatch_path = attr[0] if attr is not None and attr[0] else None

    if kind == "movie":
        row = indexer_conn.execute(
            "SELECT MAX(f.last_verified_at) FROM media_file f "
            "JOIN media_release r ON r.id = f.release_id "
            "WHERE r.item_id = ? AND f.deleted_at IS NULL",
            (item_id,),
        ).fetchone()
    elif season is not None:
        row = indexer_conn.execute(
            "SELECT MAX(f.last_verified_at) FROM media_file f "
            "JOIN media_release r ON r.id = f.release_id "
            "JOIN episode e ON e.id = r.episode_id "
            "JOIN season s ON s.id = e.season_id "
            "WHERE s.item_id = ? AND s.number = ? AND f.deleted_at IS NULL",
            (item_id, season),
        ).fetchone()
    else:
        row = indexer_conn.execute(
            "SELECT MAX(f.last_verified_at) FROM media_file f "
            "JOIN media_release r ON r.id = f.release_id "
            "JOIN episode e ON e.id = r.episode_id "
            "JOIN season s ON s.id = e.season_id "
            "WHERE s.item_id = ? AND f.deleted_at IS NULL",
            (item_id,),
        ).fetchone()

    dispatched_at = int(row[0]) if row is not None and row[0] is not None else None
    # No live file → nothing landed that we can prove, whatever an attribute may still say.
    return (dispatch_path, dispatched_at) if dispatched_at is not None else (None, None)


def backfill_spine(
    acquire_conn: sqlite3.Connection,
    indexer_conn: sqlite3.Connection,
    *,
    apply: bool,
    now: int | None = None,
) -> list[RebuiltRow]:
    """Rebuild every missing provenance journey; write them only when *apply*.

    Pure core — no config loading, no I/O beyond the two open connections — so tests drive
    it directly against temp databases.

    Args:
        acquire_conn: Open connection to ``acquire.db`` (read-write when *apply*).
        indexer_conn: Open connection to ``library.db`` (read access only is used).
        apply: When True, INSERT the rebuilt rows. When False, compute and return them
            without touching the database.
        now: Epoch stamped into ``reconstructed_at`` on every rebuilt row (§14.3 — a
            rebuilt journey says so, which is what lets the interface render an unknown
            stage as « inconnue » rather than « pas faite »). Defaults to the wall clock.

    Returns:
        The rebuilt rows, ordered by grab instant then hash. Empty when the spine has no
        hole to fill.
    """
    stamped_at = int(time.time()) if now is None else now
    acquire_conn.row_factory = sqlite3.Row
    existing = {
        (r["info_hash"] or "").lower() for r in acquire_conn.execute("SELECT info_hash FROM staging_provenance")
    }
    titles = {r["id"]: r["title"] for r in acquire_conn.execute("SELECT id, title FROM followed_series")}
    grabbed_at_by_hash: dict[str, int] = {}
    obligation_path_by_hash: dict[str, str] = {}
    for r in acquire_conn.execute("SELECT info_hash, added_at, dispatched_path FROM seed_obligation"):
        info_hash = (r["info_hash"] or "").lower()
        # Several obligations can share a hash (a re-grab); the FIRST is the grab instant.
        grabbed_at_by_hash[info_hash] = min(grabbed_at_by_hash.get(info_hash, r["added_at"]), r["added_at"])
        if r["dispatched_path"]:
            obligation_path_by_hash[info_hash] = r["dispatched_path"]

    # Group the orphaned wanted rows by hash: a season pack spans several rows but is ONE
    # grab, hence one journey.
    by_hash: dict[str, sqlite3.Row] = {}
    for w in acquire_conn.execute(
        "SELECT id, followed_id, media_ref_json, kind, season, episode, status, grabbed_hash "
        "FROM wanted WHERE grabbed_hash IS NOT NULL AND grabbed_hash != '' ORDER BY id"
    ):
        info_hash = w["grabbed_hash"].lower()
        if info_hash in existing:
            continue
        incumbent = by_hash.get(info_hash)
        if incumbent is None or _KIND_PRIORITY.get(w["kind"], 9) < _KIND_PRIORITY.get(incumbent["kind"], 9):
            by_hash[info_hash] = w

    rebuilt: list[RebuiltRow] = []
    for info_hash, w in by_hash.items():
        ref = _parse_ref(w["media_ref_json"])
        dispatch_path: str | None = None
        dispatched_at: int | None = None
        item_id = _find_item_id(indexer_conn, kind=w["kind"], ref=ref)
        if item_id is not None:
            dispatch_path, dispatched_at = _landing(indexer_conn, item_id, kind=w["kind"], season=w["season"])
        # The obligation's own dispatched_path is the dispatcher's record too — use it when
        # the library has no attribute (an older item indexed before the attribute existed).
        dispatch_path = dispatch_path or (obligation_path_by_hash.get(info_hash) if dispatched_at else None)

        # « Dispatché » is claimed only when BOTH halves are provable: the queue closed the
        # row AND the library holds a live file for it. Anything less stops at 'grabbed' —
        # the stage the grab itself proves.
        landed = dispatched_at is not None and w["status"] in _CLOSED_WANTED_STATUSES
        rebuilt.append(
            RebuiltRow(
                info_hash=info_hash,
                kind=w["kind"],
                followed_id=w["followed_id"],
                media_ref_json=w["media_ref_json"],
                grabbed_at=grabbed_at_by_hash.get(info_hash),
                dispatch_path=dispatch_path if landed else None,
                dispatched_at=dispatched_at if landed else None,
                status="dispatched" if landed else "grabbed",
                title=titles.get(w["followed_id"], "(no follow)") if w["followed_id"] is not None else "(no follow)",
            )
        )

    rebuilt.sort(key=lambda r: (r.grabbed_at or 0, r.info_hash))

    if apply and rebuilt:
        acquire_conn.executemany(
            "INSERT INTO staging_provenance "
            "(info_hash, followed_id, media_ref_json, kind, grabbed_at, dispatch_path, dispatched_at, "
            "status, reconstructed_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    r.info_hash,
                    r.followed_id,
                    r.media_ref_json,
                    r.kind,
                    r.grabbed_at,
                    r.dispatch_path,
                    r.dispatched_at,
                    r.status,
                    stamped_at,
                )
                for r in rebuilt
            ],
        )
        acquire_conn.commit()

    return rebuilt


def _open_ro(path: str) -> sqlite3.Connection:
    """Open a SQLite database strictly read-only (URI ``mode=ro``).

    Args:
        path: Filesystem path to the database.

    Returns:
        A read-only connection.
    """
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def main() -> int:
    """Run the backfill against the configured databases.

    Returns:
        0 on success, 2 when a database is missing.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Write the rebuilt rows (default: preview only).")
    parser.add_argument("--json", action="store_true", help="Dump the rebuilt rows as JSON instead of human lines.")
    args = parser.parse_args()

    from personalscraper.conf.loader import load_config  # noqa: PLC0415 — keep the script CLI-runnable

    config = load_config()
    acquire_path, indexer_path = config.acquire.db_path, config.indexer.db_path
    if acquire_path is None or not acquire_path.exists():
        print(f"acquire.db not found ({acquire_path})", file=sys.stderr)
        return 2
    if indexer_path is None or not indexer_path.exists():
        print(f"library.db not found ({indexer_path})", file=sys.stderr)
        return 2

    acquire_conn = sqlite3.connect(str(acquire_path)) if args.apply else _open_ro(str(acquire_path))
    indexer_conn = _open_ro(str(indexer_path))
    try:
        rebuilt = backfill_spine(acquire_conn, indexer_conn, apply=args.apply)
    finally:
        acquire_conn.close()
        indexer_conn.close()

    if args.json:
        print(json.dumps([asdict(r) for r in rebuilt], indent=2, ensure_ascii=False))
    else:
        for r in rebuilt:
            print(r.line())
        landed = sum(1 for r in rebuilt if r.status == "dispatched")
        verb = "rebuilt" if args.apply else "would rebuild"
        print(f"\n{verb} {len(rebuilt)} journey(s) — {landed} dispatched, {len(rebuilt) - landed} stopped at grabbed.")
        if not args.apply:
            print("Dry run: nothing written. Re-run with --apply to persist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
