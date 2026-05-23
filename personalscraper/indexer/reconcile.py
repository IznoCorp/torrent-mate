"""Index ↔ filesystem coherence detection without a full rescan.

The indexer DB and the on-disk reality drift over time:

- Files get modified externally (size / mtime change) and the indexer's
  ``enriched_at`` becomes stale relative to the new ``mtime_ns``.
- Media directories are renamed, moved between disks, or deleted by the
  user — the ``item_attribute(dispatch_path)`` chain points to a
  no-longer-existing path.
- ``media_release`` rows are left orphaned when their files were
  soft-deleted faster than the release row was cleaned up.
- ``media_file`` rows linger with ``release_id IS NULL`` because Stage B
  (enrich + release_linker) never ran for them.
- ``season.episode_count`` becomes stale because new episodes were
  ingested without the season row being recomputed.

Each scenario above can be detected with a small targeted SQL query
that runs in milliseconds, even for a 100k-row library — no walk of
the actual disks is needed.  When the user wants the index to converge
back to reality, the divergent rows are escalated into ``repair_queue``
with the appropriate ``scope`` so that ``library-repair`` (which already
drains the queue with a wall-clock budget) can fix them one by one
without a full rescan.

Public entry point: :func:`reconcile`, which runs the requested
detectors and returns a :class:`ReconcileReport`.  Each detector is also
exposed individually so the CLI can present granular findings and the
test suite can exercise one branch at a time.

This is the "fast convergence" complement to ``ScanMode.verify``:
``verify`` does the I/O-bound re-stat pass; ``reconcile`` does the
DB-only structural checks.  The two are orthogonal — typical
maintenance flow is ``reconcile`` (cheap) → ``library-verify`` (only
on disks the reconcile flagged) → ``library-repair`` (drain).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from personalscraper.indexer.repos import outbox_repo
from personalscraper.indexer.schema import RepairQueueRow
from personalscraper.logger import get_logger

log = get_logger("indexer.reconcile")


ReconcileScope = Literal[
    "merkle",
    "dispatch_path",
    "enrich",
    "release",
    "season",
    "item",
    "path_missing",
]
"""Logical detection scopes exposed to callers.

- ``merkle`` — disk-level drift (stored vs computed merkle root).
- ``dispatch_path`` — items whose ``dispatch_path`` attribute points to a
  filesystem path that no longer exists.
- ``enrich`` — files where ``enriched_at`` is stale relative to ``mtime_ns``.
- ``release`` — orphan ``media_release`` rows (no surviving file) and
  ``media_file`` rows with ``release_id IS NULL`` despite mtime > 0.
- ``season`` — ``season.episode_count`` mismatching the actual episode
  count (counted on the same row).
- ``item`` — ``media_item`` rows that have no file evidence at all.
- ``path_missing`` — ``path`` rows whose resolved absolute path
  (``disk.mount_path + rel_path``) no longer exists on the filesystem.
  Only evaluated for mounted disks (``disk.is_mounted = 1``).
"""


_ALL_SCOPES: tuple[ReconcileScope, ...] = (
    "merkle",
    "dispatch_path",
    "enrich",
    "release",
    "season",
    "item",
    "path_missing",
)


@dataclass
class DivergenceItem:
    """A single divergence finding ready for ``repair_queue`` enqueue.

    Attributes:
        scope: One of the values accepted by ``repair_queue.scope`` —
            ``'file'``, ``'item'``, ``'release'``, ``'subtree'``, ``'path'``,
            ``'disk'``.  This maps the detection scope into the repair
            scope expected by the worker.
        scope_id: Application-managed soft-FK whose meaning depends on
            ``scope``.  ``None`` is permitted for ``'disk'`` scope when the
            divergence affects the whole disk uniformly.
        reason: Human-readable reason, e.g.
            ``"reconcile.dispatch_path.missing"``.
        payload: Optional dict serialised as JSON in the repair row's
            ``payload_json``.  Carries diagnostic context (expected vs
            actual values) so the worker / operator does not have to
            re-derive it.
    """

    scope: str
    scope_id: int | None
    reason: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass
class ReconcileReport:
    """Aggregate result of a :func:`reconcile` run.

    Attributes:
        merkle_drift: Disk IDs whose stored merkle_root differs from the
            value computed live from the indexer's own fingerprints.
        dispatch_path_missing: Item IDs whose ``dispatch_path`` attribute
            no longer exists on disk.
        enrich_stale: Number of ``media_file`` rows whose ``enriched_at``
            predates their ``mtime_ns`` (need re-enrich).
        release_orphans: ``media_release`` IDs with no surviving file.
        files_without_release: Number of ``media_file`` rows with
            ``release_id IS NULL`` whose owning item is not Stage A any more
            (i.e. enrich budget should have reached them but didn't).
        season_count_drift: Season IDs whose ``episode_count`` does not
            match the count of ``episode`` rows joined to it.
        items_without_files: Item IDs that have no ``media_file`` link
            at all (release-linked or otherwise).
        path_missing: ``path.id`` values whose resolved absolute path
            (``disk.mount_path / rel_path``) no longer exists on the
            filesystem.  Only populated for mounted disks.
        enqueued_repairs: Number of repair_queue rows actually inserted
            (deduped via the partial UNIQUE index from migration 003).
    """

    merkle_drift: list[int] = field(default_factory=list)
    dispatch_path_missing: list[int] = field(default_factory=list)
    enrich_stale: int = 0
    release_orphans: list[int] = field(default_factory=list)
    files_without_release: int = 0
    season_count_drift: list[int] = field(default_factory=list)
    items_without_files: list[int] = field(default_factory=list)
    path_missing: list[int] = field(default_factory=list)
    enqueued_repairs: int = 0

    @property
    def total_findings(self) -> int:
        """Sum of every detector's count — the operator's headline number."""
        return (
            len(self.merkle_drift)
            + len(self.dispatch_path_missing)
            + self.enrich_stale
            + len(self.release_orphans)
            + self.files_without_release
            + len(self.season_count_drift)
            + len(self.items_without_files)
            + len(self.path_missing)
        )


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def detect_merkle_drift(conn: sqlite3.Connection) -> list[int]:
    """Return disk IDs whose stored merkle differs from the live computation.

    The stored merkle (``disk.merkle_root``) is the value persisted at
    the end of the last walk that reached the disk.  The live merkle is
    re-computed here from the indexer's own ``media_file`` fingerprints —
    no on-disk read.  If the two values differ, either a recent scan
    finished partially (``enriched_at`` not yet propagated to merkle) or
    the file fingerprints have moved without the disk row being refreshed.

    Args:
        conn: Open SQLite connection on the indexer DB.

    Returns:
        Sorted list of ``disk.id`` values whose merkle has drifted.
        Disks with ``merkle_root IS NULL`` are excluded — they have never
        been fingerprinted, which is "missing" rather than "drifted".
    """
    from personalscraper.indexer.merkle import FileFingerprint, compute_merkle_root  # noqa: PLC0415

    conn.row_factory = sqlite3.Row
    disks = conn.execute("SELECT id, merkle_root FROM disk WHERE merkle_root IS NOT NULL ORDER BY id").fetchall()
    drifted: list[int] = []

    for d in disks:
        rows = conn.execute(
            """
            SELECT mf.path_id AS path_id, mf.size_bytes AS size,
                   mf.mtime_ns AS mtime_ns, mf.oshash AS oshash
              FROM media_file mf
              JOIN path p ON p.id = mf.path_id
             WHERE p.disk_id = ?
               AND mf.deleted_at IS NULL
               AND mf.oshash IS NOT NULL
            """,
            (d["id"],),
        ).fetchall()
        if not rows:
            # Disk has a stored merkle but no fingerprinted files anymore —
            # the stored value is by definition stale.
            drifted.append(int(d["id"]))
            continue
        fingerprints = [
            FileFingerprint(
                path_id=int(r["path_id"]),
                size=int(r["size"]),
                mtime_ns=int(r["mtime_ns"]),
                oshash=str(r["oshash"]),
            )
            for r in rows
        ]
        live_root = compute_merkle_root(fingerprints)
        if live_root != d["merkle_root"]:
            drifted.append(int(d["id"]))
    return drifted


def detect_dispatch_path_missing(conn: sqlite3.Connection) -> list[int]:
    """Return item IDs whose ``dispatch_path`` attribute points off-disk.

    Iterates ``item_attribute(key='dispatch_path')`` rows and checks
    ``Path.exists()`` for each value.  Cheap on APFS (~10 µs / stat) and
    bounded to the number of indexed items, not files.

    Args:
        conn: Open SQLite connection.

    Returns:
        Sorted list of ``media_item.id`` values whose dispatch_path is gone.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT item_id, value FROM item_attribute WHERE key = 'dispatch_path' ORDER BY item_id"
    ).fetchall()
    missing: list[int] = []
    for r in rows:
        path_value = r["value"]
        if not path_value:
            continue
        if not Path(path_value).exists():
            missing.append(int(r["item_id"]))
    return missing


def detect_enrich_stale(conn: sqlite3.Connection) -> int:
    """Count files whose ``enriched_at`` predates their on-disk ``mtime_ns``.

    A file is enrich-stale when the indexer's last enrichment timestamp
    is older than the file's last modification, meaning the cached
    ``media_stream`` rows reflect a previous content version.  The query
    is fully DB-side; no filesystem access.

    Args:
        conn: Open SQLite connection.

    Returns:
        Number of ``media_file`` rows that need re-enrichment.
    """
    row = conn.execute(
        """
        SELECT COUNT(*)
          FROM media_file
         WHERE deleted_at IS NULL
           AND enriched_at IS NOT NULL
           AND enriched_at < (mtime_ns / 1000000000)
        """
    ).fetchone()
    return int(row[0]) if row is not None else 0


def detect_release_orphans(conn: sqlite3.Connection) -> tuple[list[int], int]:
    """Return orphan ``media_release`` IDs and the count of NULL-release files.

    Two related findings reported together:

    - ``media_release`` rows with no surviving (non-deleted) ``media_file``
      pointing to them.  Could be left over after bulk soft-delete or a
      crashed dispatch.
    - ``media_file`` rows still ``release_id IS NULL`` despite having a
      non-zero ``enriched_at`` — this means enrich processed the file
      but ``release_linker`` never linked it (missing ``dispatch_path``
      attribute on the owning item, malformed path chain, etc.).

    Args:
        conn: Open SQLite connection.

    Returns:
        ``(release_orphan_ids, file_without_release_count)``.
    """
    conn.row_factory = sqlite3.Row
    orphan_rows = conn.execute(
        """
        SELECT mr.id
          FROM media_release mr
         WHERE NOT EXISTS (
             SELECT 1 FROM media_file mf
              WHERE mf.release_id = mr.id
                AND mf.deleted_at IS NULL
         )
         ORDER BY mr.id
        """
    ).fetchall()
    orphan_ids = [int(r["id"]) for r in orphan_rows]

    null_release = conn.execute(
        """
        SELECT COUNT(*)
          FROM media_file
         WHERE deleted_at IS NULL
           AND release_id IS NULL
           AND enriched_at IS NOT NULL
        """
    ).fetchone()
    null_count = int(null_release[0]) if null_release is not None else 0
    return orphan_ids, null_count


def detect_season_count_drift(conn: sqlite3.Connection) -> list[int]:
    """Return season IDs whose ``episode_count`` mismatches actual rows.

    The ``season.episode_count`` column is a denormalised cache populated
    by the library scanner from the directory walk.  Drift happens when
    new episodes are ingested without the season row being recomputed.

    Args:
        conn: Open SQLite connection.

    Returns:
        Sorted list of ``season.id`` values whose count is wrong.
    """
    rows = conn.execute(
        """
        SELECT s.id
          FROM season s
          LEFT JOIN (
              SELECT season_id, COUNT(*) AS cnt FROM episode GROUP BY season_id
          ) e ON e.season_id = s.id
         WHERE s.episode_count != COALESCE(e.cnt, 0)
         ORDER BY s.id
        """
    ).fetchall()
    return [int(r[0]) for r in rows]


def detect_items_without_files(conn: sqlite3.Connection) -> list[int]:
    """Return item IDs that have no surviving ``media_file`` evidence.

    Items in this state are either freshly inserted on a walk that did not
    also populate ``media_file`` rows (e.g. the delegated ``indexer.scan``
    failed mid-disk) or are stale ghosts left behind after every file under
    them was soft-deleted.

    Args:
        conn: Open SQLite connection.

    Returns:
        Sorted list of ``media_item.id`` values with zero file linkage.
    """
    rows = conn.execute(
        """
        SELECT mi.id
          FROM media_item mi
         WHERE NOT EXISTS (
             SELECT 1
               FROM media_release mr
               JOIN media_file mf ON mf.release_id = mr.id
              WHERE mr.item_id = mi.id
                AND mf.deleted_at IS NULL
         )
         ORDER BY mi.id
        """
    ).fetchall()
    return [int(r[0]) for r in rows]


def detect_path_missing(conn: sqlite3.Connection) -> list[int]:
    """Return path.id values whose resolved absolute path no longer exists on FS.

    Resolves the absolute path for each ``path`` row belonging to a mounted
    disk (``disk.is_mounted = 1``) by joining ``disk.mount_path`` with
    ``path.rel_path``.  Any row whose resolved path does not exist on the
    filesystem is returned.

    Unmounted disks are excluded — a path on an offline disk is not
    "missing", just inaccessible; the correct reconcile action for missing
    disks is the ``merkle`` or unreachable-strikes detectors, not this one.

    Args:
        conn: Open SQLite connection on the indexer DB.

    Returns:
        Sorted list of ``path.id`` values whose absolute path is gone from
        the filesystem.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT p.id, p.disk_id, p.rel_path, d.mount_path
          FROM path p JOIN disk d ON d.id = p.disk_id
         WHERE d.is_mounted = 1
         ORDER BY p.id
        """
    ).fetchall()
    missing: list[int] = []
    for r in rows:
        abs_path = Path(r["mount_path"]) / r["rel_path"]
        if not abs_path.exists():
            missing.append(int(r["id"]))
    return missing


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def reconcile(
    conn: sqlite3.Connection,
    *,
    scopes: list[ReconcileScope] | None = None,
    enqueue_repairs: bool = False,
) -> ReconcileReport:
    """Run every detector in ``scopes`` and optionally enqueue repairs.

    By default all detectors run.  Passing a subset (e.g.
    ``scopes=['enrich']``) is useful when the operator already knows
    which divergence they want to converge.

    When ``enqueue_repairs=True``, every finding is translated into a
    ``repair_queue`` row via :func:`outbox_repo.insert_repair_queue` so
    the existing ``library-repair`` worker can drain them.  The partial
    UNIQUE INDEX added in migration 003 deduplicates findings that the
    last reconcile already enqueued; the report's ``enqueued_repairs``
    counter reflects net new rows, not the raw call count.

    Args:
        conn: Open SQLite connection on the indexer DB.
        scopes: Subset of detectors to run.  ``None`` runs all.
        enqueue_repairs: When True, push every finding into ``repair_queue``.

    Returns:
        Populated :class:`ReconcileReport`.
    """
    if scopes is None:
        scopes = list(_ALL_SCOPES)

    report = ReconcileReport()
    divergences: list[DivergenceItem] = []

    if "merkle" in scopes:
        report.merkle_drift = detect_merkle_drift(conn)
        for disk_id in report.merkle_drift:
            divergences.append(
                DivergenceItem(
                    scope="disk",
                    scope_id=disk_id,
                    reason="reconcile.merkle.drift",
                    payload={"detector": "merkle"},
                )
            )

    if "dispatch_path" in scopes:
        report.dispatch_path_missing = detect_dispatch_path_missing(conn)
        for item_id in report.dispatch_path_missing:
            divergences.append(
                DivergenceItem(
                    scope="item",
                    scope_id=item_id,
                    reason="reconcile.dispatch_path.missing",
                    payload={"detector": "dispatch_path"},
                )
            )

    if "enrich" in scopes:
        report.enrich_stale = detect_enrich_stale(conn)
        # enrich_stale is a count-only finding because the corrective
        # action is the same for every row (run library-index --mode enrich).
        # No per-row scope_id repair is enqueued — the operator runs the
        # bulk action once instead.

    if "release" in scopes:
        report.release_orphans, report.files_without_release = detect_release_orphans(conn)
        for release_id in report.release_orphans:
            divergences.append(
                DivergenceItem(
                    scope="release",
                    scope_id=release_id,
                    reason="reconcile.release.orphan",
                    payload={"detector": "release"},
                )
            )

    if "season" in scopes:
        report.season_count_drift = detect_season_count_drift(conn)
        for season_id in report.season_count_drift:
            divergences.append(
                DivergenceItem(
                    scope="release",  # season has no scope value; release covers it
                    scope_id=season_id,
                    reason="reconcile.season.count_drift",
                    payload={"detector": "season"},
                )
            )

    if "item" in scopes:
        report.items_without_files = detect_items_without_files(conn)
        for item_id in report.items_without_files:
            divergences.append(
                DivergenceItem(
                    scope="item",
                    scope_id=item_id,
                    reason="reconcile.item.no_files",
                    payload={"detector": "item"},
                )
            )

    if "path_missing" in scopes:
        report.path_missing = detect_path_missing(conn)
        for path_id in report.path_missing:
            divergences.append(
                DivergenceItem(
                    scope="path",
                    scope_id=path_id,
                    reason="reconcile.path.missing",
                    payload={"detector": "path_missing"},
                )
            )

    log.info(
        "indexer.reconcile.report",
        merkle_drift=len(report.merkle_drift),
        dispatch_path_missing=len(report.dispatch_path_missing),
        enrich_stale=report.enrich_stale,
        release_orphans=len(report.release_orphans),
        files_without_release=report.files_without_release,
        season_count_drift=len(report.season_count_drift),
        items_without_files=len(report.items_without_files),
        path_missing=len(report.path_missing),
    )

    if enqueue_repairs and divergences:
        import json  # noqa: PLC0415

        now = int(time.time())
        before = conn.execute("SELECT COUNT(*) FROM repair_queue WHERE status='pending'").fetchone()[0]
        for div in divergences:
            outbox_repo.insert_repair_queue(
                conn,
                RepairQueueRow(
                    id=0,
                    scope=div.scope,  # type: ignore[arg-type]
                    scope_id=div.scope_id,
                    reason=div.reason,
                    payload_json=json.dumps(div.payload),
                    enqueued_at=now,
                    status="pending",
                    attempted_at=None,
                    attempts=0,
                ),
            )
        after = conn.execute("SELECT COUNT(*) FROM repair_queue WHERE status='pending'").fetchone()[0]
        report.enqueued_repairs = max(0, after - before)
        log.info("indexer.reconcile.enqueued", count=report.enqueued_repairs)

    return report
