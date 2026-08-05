"""Provenance sub-store — the advisory staging registry (feature ``provenance``, F0).

Records the journey of a **follow-driven** acquisition through the pipeline
(grab → ingest → sort/rename → scrape → dispatch) so the scrape can resolve
identity DETERMINISTICALLY (#30) instead of re-inferring it from the renamed
folder. Keyed on the torrent info-hash (one hash = one staging folder, even for a
season-pack that spans many ``wanted`` rows).

ADVISORY OVERLAY — the filesystem stays the source of truth:

- **Every write is best-effort**: an error is logged and swallowed, NEVER raised
  to a pipeline step (a provenance write must never fail a grab/ingest/dispatch).
- **Only :meth:`_ProvenanceSubStore.upsert_grab` creates a row**, and it is called
  ONLY for a follow-driven grab (a ``wanted`` item with a known identity). Every
  other method is UPDATE-only — a no-op when no row exists. So a **manual/direct
  torrent** (no wanted → no ``upsert_grab``) gets NO row and no method touches it
  (ACC-06), in BOTH senses: a torrent added straight into qBittorrent, and any
  personalscraper grab launched without a follow.
- **Reads are fail-soft**: any error → ``None`` (the caller falls back to the #29
  inference, then free match).
"""

from __future__ import annotations

import sqlite3
import unicodedata
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import PurePosixPath

from personalscraper.acquire._store_rows import _media_ref_from_json, _media_ref_to_json
from personalscraper.core.identity import MediaRef
from personalscraper.logger import get_logger

log = get_logger(__name__)


def _path_key_forms(path: str) -> tuple[str, str]:
    """Return the (NFC, NFD) unicode forms of *path* for normalization-robust matching.

    ``current_path`` is persisted un-normalized — whatever ``str(Path)`` the pipeline
    produced (NFD from ``iterdir`` on macOS for a decomposable name, NFC elsewhere) —
    while a cross-store caller may hold the OTHER form (a decision's ``staging_path`` is
    NFC-normalized by ``DecisionWriter``; a scrape's ``media_path`` is raw NFD). Matching
    a path-keyed write against BOTH forms makes it hit regardless of the stored
    normalization. For an ASCII path the two forms are identical, so this never changes
    the behaviour of the (ASCII) paths that shipped in F0.
    """
    return unicodedata.normalize("NFC", path), unicodedata.normalize("NFD", path)


#: Statuses that close a journey. A terminal row is an AUDIT RECORD: no later staging move,
#: scrape or dispatch of the same folder may rewrite it (a subsequent run legitimately
#: recreates the very same show folder for a NEW episode).
_TERMINAL_STATUSES = ("dispatched", "reconciled")


def _path_parts(path: str) -> tuple[str, ...]:
    """Split *path* into NFC-normalized components for containment tests.

    Comparing whole strings would make ``American Dad 2`` look like a child of
    ``American Dad``; comparing components cannot. Normalising to NFC makes the test
    immune to the macOS NFD/NFC split that already forced ``_path_key_forms`` to exist.
    """
    return PurePosixPath(unicodedata.normalize("NFC", path)).parts


def _is_within(candidate: str, root: str) -> bool:
    """Return True when *candidate* IS *root* or lives underneath it.

    The relation the pipeline actually has between a dispatched folder and the items it
    holds: ``sort`` nests a TV release under its show folder
    (``002-TVSHOWS/{show}/{release}``), and the dispatch works on the SHOW folder. An
    equality test — what the spine used until 0.80.0 — sees no relation at all there,
    which is precisely how 47 episode journeys were lost.
    """
    root_parts = _path_parts(root)
    return _path_parts(candidate)[: len(root_parts)] == root_parts


# An in-flight item (not yet dispatched/reconciled) can get STUCK mid-pipeline (F4): its
# staging folder still exists on disk but no stage has advanced it for a while. These are
# the statuses a targeted re-action (re-scrape / requeue) can act on.
_STUCK_STATUSES = ("grabbed", "ingested", "scraped")

# Default idle horizon before an in-flight item is considered stuck (2h) — long enough that
# a normally-cadenced pipeline would have advanced it.
STUCK_IDLE_SECONDS = 7200


def _latest_stage_at(row: ProvenanceRow) -> int | None:
    """The most-recent stage timestamp reached (scrape → ingest → grab)."""
    return row.scraped_at or row.ingested_at or row.grabbed_at


def provenance_row_is_stuck(
    row: ProvenanceRow, *, now: int, idle_seconds: int, exists_fn: Callable[[str], bool]
) -> bool:
    """Return True when *row* is a stuck in-flight item (F4 substrate).

    Stuck = an in-flight status (grabbed/ingested/scraped, never a terminal
    dispatched/reconciled), whose ``current_path`` still exists on disk (FS = truth — a
    vanished folder is a ``prune_stale`` candidate, not a resume), and whose latest stage
    is older than *idle_seconds*.
    """
    if row.status not in _STUCK_STATUSES or not row.current_path:
        return False
    latest = _latest_stage_at(row)
    if latest is None or latest >= now - idle_seconds:
        return False
    return exists_fn(row.current_path)


@dataclass(frozen=True)
class ProvenanceRow:
    """One acquisition's provenance record (a row of ``staging_provenance``)."""

    info_hash: str
    followed_id: int | None
    media_ref: MediaRef | None
    kind: str | None
    ingest_path: str | None
    current_path: str | None
    scraped_ref: MediaRef | None
    dispatch_path: str | None
    grabbed_at: int | None
    ingested_at: int | None
    scraped_at: int | None
    dispatched_at: int | None
    status: str | None
    # Resolution-state projection (F2, decisions-spine) — an ADVISORY mirror of the
    # scrape-arbiter decision lifecycle. ``resolution_state`` is None when no decision
    # was ever raised (a confident scrape). ``decision_id`` back-links (cross-DB, no FK)
    # to ``scrape_decision.id`` so the UI can deep-link to the resolution deck.
    resolution_state: str | None = None
    decision_id: int | None = None
    resolution_trigger: str | None = None
    resolution_at: int | None = None
    # Pipeline-run linkage (F3, run-linkage) — the run that advanced this acquisition at
    # each stage (hex ``pipeline_run.run_uid``, cross-DB back-link, no FK). Each is None
    # until that stage runs under a resolvable run (a grab via qBittorrent-direct or a
    # stage with no run stays NULL).
    grab_run_uid: str | None = None
    ingest_run_uid: str | None = None
    scrape_run_uid: str | None = None
    dispatch_run_uid: str | None = None
    # Rebuild marker (§14.3). Non-None when this journey was RECONSTRUCTED from the
    # surviving databases rather than written by the pipeline as it happened. On such a
    # row a NULL stage timestamp means « unknown », NOT « stage never reached »: a
    # dispatched media went through ingest/sort/scrape by definition (§14.2), the
    # reconstruction simply cannot date those steps. Every journey the pipeline wrote
    # itself carries None here.
    reconstructed_at: int | None = None
    # Identité AFFICHABLE du parcours (017). ``media_ref`` ne porte que l'œuvre (l'id de
    # série) : sans saison/épisode, quatre acquisitions de la même série sont quatre
    # cartes identiques à l'écran — ce que l'opérateur lit comme des doublons. NULL pour
    # un film, et pour un parcours dont l'épisode n'a jamais été connu.
    season: int | None = None
    episode: int | None = None
    #: Étapes dont l'instant a été CALCULÉ et non observé (« ingested,scraped »), ou None
    #: quand tout ce que la ligne porte a été mesuré. C'est ce qui permet d'afficher une
    #: date approchée en le DISANT, plutôt que de faire passer une interpolation pour une
    #: mesure — la seule chose qui distingue une estimation d'un mensonge.
    estimated_stages: str | None = None


def _row_to_provenance(row: sqlite3.Row) -> ProvenanceRow:
    """Decode a ``staging_provenance`` row into a :class:`ProvenanceRow` VO."""
    media_json = row["media_ref_json"]
    scraped_json = row["scraped_ref_json"]
    keys = row.keys()
    return ProvenanceRow(
        info_hash=row["info_hash"],
        followed_id=row["followed_id"],
        media_ref=_media_ref_from_json(media_json) if media_json else None,
        kind=row["kind"],
        ingest_path=row["ingest_path"],
        current_path=row["current_path"],
        scraped_ref=_media_ref_from_json(scraped_json) if scraped_json else None,
        dispatch_path=row["dispatch_path"],
        grabbed_at=row["grabbed_at"],
        ingested_at=row["ingested_at"],
        scraped_at=row["scraped_at"],
        dispatched_at=row["dispatched_at"],
        status=row["status"],
        # F2 columns — tolerate a pre-011 row shape (defensive: a SELECT * against an
        # un-migrated table would omit these; default to None rather than KeyError).
        resolution_state=row["resolution_state"] if "resolution_state" in keys else None,
        decision_id=row["decision_id"] if "decision_id" in keys else None,
        resolution_trigger=row["resolution_trigger"] if "resolution_trigger" in keys else None,
        resolution_at=row["resolution_at"] if "resolution_at" in keys else None,
        # F3 run linkage — tolerate a pre-012 row shape (defensive against a SELECT *
        # against an un-migrated table).
        grab_run_uid=row["grab_run_uid"] if "grab_run_uid" in keys else None,
        ingest_run_uid=row["ingest_run_uid"] if "ingest_run_uid" in keys else None,
        scrape_run_uid=row["scrape_run_uid"] if "scrape_run_uid" in keys else None,
        dispatch_run_uid=row["dispatch_run_uid"] if "dispatch_run_uid" in keys else None,
        # Rebuild marker (016) — tolerate a pre-016 row shape, like the F2/F3 columns.
        reconstructed_at=row["reconstructed_at"] if "reconstructed_at" in keys else None,
        # Identité affichable (017) — tolère une forme de ligne antérieure.
        season=row["season"] if "season" in keys else None,
        episode=row["episode"] if "episode" in keys else None,
        estimated_stages=row["estimated_stages"] if "estimated_stages" in keys else None,
    )


class _ProvenanceSubStore:
    """Advisory writer + reader for ``staging_provenance`` (all writes best-effort)."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        write_tx: Callable[[sqlite3.Connection], AbstractContextManager[None]],
    ) -> None:
        """Initialise with the shared connection and the write-transaction factory.

        Args:
            conn: The shared ``acquire.db`` connection.
            write_tx: The ``_write_tx`` context-manager factory (BEGIN IMMEDIATE).
        """
        self._conn = conn
        self._write_tx = write_tx

    # -- writes (best-effort: an error NEVER escapes to the pipeline step) -------

    def _safe_write(self, sql: str, params: tuple[object, ...]) -> None:
        """Run one write in its own transaction, swallowing any error (advisory).

        Swallowed, but **not silent**. This is where cause A hid for four days: a
        ``kind='season'`` refused by the table's CHECK was reported at ``warning`` — the
        level the pipeline uses for expected, benign degradations — and drowned among
        them, so every season acquisition vanished from the spine unnoticed. A write the
        database REFUSES is a defect, so it is logged at ``error`` with the failing
        statement's target table and the constraint that refused it. The write itself
        stays advisory: no exception ever reaches the grab/ingest/scrape/dispatch step.
        """
        try:
            with self._write_tx(self._conn):
                self._conn.execute(sql, params)
        except Exception as exc:  # noqa: BLE001 — advisory: a provenance write never fails a step
            log.error(  # noqa: TRY400 — the traceback is carried by exc_info, not by log.exception's level
                "acquire.provenance.write_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                operation=sql.split(maxsplit=1)[0].upper(),
                exc_info=True,
            )

    def upsert_grab(
        self,
        info_hash: str,
        *,
        followed_id: int | None,
        media_ref: MediaRef | None,
        kind: str | None,
        grabbed_at: int,
        run_uid: str | None = None,
        season: int | None = None,
        episode: int | None = None,
    ) -> None:
        """Create/refresh the row for a FOLLOW-DRIVEN grab (the identity seed).

        The ONLY row-creating method — called exclusively when a grab carries a
        wanted-derived identity. A manual/direct grab never reaches here, so it
        never gets a row (ACC-06). ``run_uid`` (F3) is the grab command's own
        ``pipeline_run.run_uid`` (hex) — None when grab runs with no run row.
        """
        self._safe_write(
            """
            INSERT INTO staging_provenance
              (info_hash, followed_id, media_ref_json, kind, grabbed_at, status, grab_run_uid,
               season, episode)
            VALUES (?, ?, ?, ?, ?, 'grabbed', ?, ?, ?)
            ON CONFLICT(info_hash) DO UPDATE SET
              followed_id    = excluded.followed_id,
              media_ref_json = excluded.media_ref_json,
              kind           = excluded.kind,
              grabbed_at     = excluded.grabbed_at,
              status         = 'grabbed',
              grab_run_uid   = excluded.grab_run_uid,
              season         = excluded.season,
              episode        = excluded.episode
            """,
            (
                info_hash.lower(),
                followed_id,
                _media_ref_to_json(media_ref) if media_ref is not None else None,
                kind,
                grabbed_at,
                run_uid,
                season,
                episode,
            ),
        )

    def set_ingest(self, info_hash: str, *, ingest_path: str, ingested_at: int, run_uid: str | None = None) -> None:
        """Record the staging folder at ingest (UPDATE-only — no-op if untracked).

        ``run_uid`` (F3) is the ingesting run's ``pipeline_run.run_uid`` (hex), or None.
        """
        self._safe_write(
            "UPDATE staging_provenance SET ingest_path = ?, current_path = ?, "
            "ingested_at = ?, status = 'ingested', ingest_run_uid = ? WHERE info_hash = ?",
            (ingest_path, ingest_path, ingested_at, run_uid, info_hash.lower()),
        )

    def set_current_path(self, info_hash: str, *, path: str) -> None:
        """Keep ``current_path`` live across a sort/rename (UPDATE-only)."""
        self._safe_write(
            "UPDATE staging_provenance SET current_path = ? WHERE info_hash = ?",
            (path, info_hash.lower()),
        )

    def set_scraped(self, info_hash: str, *, scraped_ref: MediaRef | None, scraped_at: int) -> None:
        """Record the identity actually scraped (audit; UPDATE-only)."""
        self._safe_write(
            "UPDATE staging_provenance SET scraped_ref_json = ?, scraped_at = ?, "
            "status = 'scraped' WHERE info_hash = ?",
            (
                _media_ref_to_json(scraped_ref) if scraped_ref is not None else None,
                scraped_at,
                info_hash.lower(),
            ),
        )

    def set_dispatch(self, info_hash: str, *, dispatch_path: str, dispatched_at: int) -> None:
        """Record the final destination at dispatch (UPDATE-only)."""
        self._safe_write(
            "UPDATE staging_provenance SET dispatch_path = ?, dispatched_at = ?, "
            "status = 'dispatched' WHERE info_hash = ?",
            (dispatch_path, dispatched_at, info_hash.lower()),
        )

    # -- path-keyed writes (pipeline steps work on folders, not hashes) ---------

    def hashes_under(self, folder: str) -> list[str]:
        """Resolve a staging folder → the ``info_hash`` of every OPEN row it holds.

        The one place a path is turned into the spine's stable key. A row qualifies when
        its ``current_path`` **is** *folder* or lives **underneath** it, and its journey is
        not already terminal. Fail-soft: an empty list on any error (the caller then writes
        nothing, exactly as an unmatched UPDATE did before).

        Containment — not equality — is the relation the pipeline actually has: ``sort``
        nests a TV release under its show folder and the later stages act on the SHOW
        folder. It also means a stage that FORGOT to re-point a row still gets that row's
        journey closed, instead of leaving it to be pruned as an orphan.

        Args:
            folder: The staging folder a pipeline stage is acting on.

        Returns:
            The lowercase info-hashes to write, ordered by hash for a stable write order.
        """
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT info_hash, current_path FROM staging_provenance "
                "WHERE current_path IS NOT NULL AND (status IS NULL OR status NOT IN (?, ?))",
                _TERMINAL_STATUSES,
            ).fetchall()
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error resolves to no hashes
            log.warning("acquire.provenance.resolve_failed", error=str(exc))
            return []
        return sorted(r["info_hash"] for r in rows if _is_within(r["current_path"], folder))

    def _write_by_hashes(self, set_clause: str, params: tuple[object, ...], hashes: list[str]) -> None:
        """Run one hash-keyed UPDATE over *hashes* (a no-op on an empty list).

        Args:
            set_clause: The ``SET`` body (without the keyword), with ``?`` placeholders.
            params: Bind values for *set_clause*, in order.
            hashes: The target info-hashes — the STABLE key every spine write uses.
        """
        if not hashes:
            return
        placeholders = ", ".join("?" * len(hashes))
        self._safe_write(
            f"UPDATE staging_provenance SET {set_clause} WHERE info_hash IN ({placeholders})",  # noqa: S608
            (*params, *hashes),
        )

    def move_path(self, old_path: str, new_path: str) -> None:
        """Re-point the tracked SUBTREE at *old_path* onto *new_path* (sort/rename).

        A directory move, not a string swap: every open row whose ``current_path`` is
        *old_path* **or lives under it** now lives at *new_path*. The collapse of a nested
        row onto the new root is not an approximation — by the time the scrape reports the
        rename it has already flattened the release folders into ``Saison NN/`` and deleted
        them, so the renamed media folder IS the item's live location. Writing anything
        else would be inventing a path that no longer exists.

        Resolves by path, writes by ``info_hash``. UPDATE-only — a no-op when the moved
        folder holds no tracked item (a manual/direct item).
        """
        self._write_by_hashes("current_path = ?", (new_path,), self.hashes_under(old_path))

    def record_dispatch_by_path(
        self, staging_path: str, *, dispatch_path: str, dispatched_at: int, run_uid: str | None = None
    ) -> None:
        """Record the dispatch of everything the folder at *staging_path* holds.

        Dispatching ``002-TVSHOWS/American Dad! (2005)`` dispatches every season pack merged
        into it, so every open row that folder contains is closed — each by its own
        ``info_hash``, the key that does not move. ``run_uid`` (F3) is the dispatching run's
        ``pipeline_run.run_uid`` (hex), or None. No-op when the folder holds nothing tracked.
        """
        self._write_by_hashes(
            "dispatch_path = ?, dispatched_at = ?, status = 'dispatched', dispatch_run_uid = ?",
            (dispatch_path, dispatched_at, run_uid),
            self.hashes_under(staging_path),
        )

    def set_scrape_run(self, staging_path: str, *, run_uid: str | None, scraped_at: int) -> None:
        """Record the scrape STAGE for the folder at *staging_path* (F3, UPDATE-only).

        Advances every open row that folder holds to ``status='scraped'`` + ``scraped_at``
        (so the journey stepper lights up the « Scrapé » stage), stamps ``scrape_run_uid``
        (None outside a run), **and re-points ``current_path`` onto the scraped folder**.

        That last part is what keeps the registry truthful when NO rename happened — a
        release sorted under an ALREADY-canonical show folder is flattened into
        ``Saison NN/`` without any ``move_path`` call, so without this the row would keep
        pointing at a directory the scrape just deleted and ``prune_stale`` would erase the
        journey before the dispatch could close it.

        Called once per CONFIDENTLY-scraped item; an ambiguous item awaiting resolution is
        NOT marked scraped. No-op when untracked. Advisory: never raises.
        """
        self._write_by_hashes(
            "current_path = ?, scraped_at = ?, status = 'scraped', scrape_run_uid = ?",
            (staging_path, scraped_at, run_uid),
            self.hashes_under(staging_path),
        )

    def set_resolution(
        self,
        staging_path: str,
        *,
        state: str,
        resolved_at: int,
        decision_id: int | None = None,
        trigger: str | None = None,
    ) -> None:
        """Project the decision lifecycle onto the tracked folder (F2, advisory).

        Keyed on ``current_path`` (the live staging folder) so the decisions flow —
        which knows the folder, not the info-hash — mirrors its verdict onto the spine
        without a hash lookup. UPDATE-only: a **no-op when the folder is untracked** (a
        manual/direct item has no spine row → its decision lives only in ``scrape_decision``,
        ACC-06 preserved). Best-effort: an error is logged and swallowed, never raised to
        the enqueue/resolve/dismiss caller.

        Args:
            staging_path: The live staging folder (matches ``current_path``).
            state: ``'awaiting'`` | ``'resolved'`` | ``'dismissed'``.
            resolved_at: Epoch of this resolution-state transition.
            decision_id: The ``scrape_decision.id`` back-link (deep-link target), or None.
            trigger: The decision trigger (``below_threshold``/``mid_band``/``ambiguous``).
        """
        nfc, nfd = _path_key_forms(staging_path)
        self._safe_write(
            "UPDATE staging_provenance SET resolution_state = ?, decision_id = ?, "
            "resolution_trigger = ?, resolution_at = ? WHERE current_path IN (?, ?)",
            (state, decision_id, trigger, resolved_at, nfc, nfd),
        )

    # -- reads (fail-soft: None on any error) -----------------------------------

    def by_hash(self, info_hash: str) -> ProvenanceRow | None:
        """Return the row for *info_hash*, or ``None`` (fail-soft)."""
        return self._read_one("WHERE info_hash = ?", (info_hash.lower(),))

    def by_path(self, path: str) -> ProvenanceRow | None:
        """Return the row whose ``current_path`` equals *path*, or ``None``.

        The #30 scrape consumer's join: a staging folder → its provenance seed.
        Matches both unicode forms so a caller holding the NFC path still finds a
        row stored under its NFD form (and vice-versa).
        """
        nfc, nfd = _path_key_forms(path)
        return self._read_one("WHERE current_path IN (?, ?)", (nfc, nfd))

    def path_ref_index(self) -> dict[str, MediaRef]:
        """Snapshot ``{current_path: media_ref}`` for every tracked, identified row.

        The scrape consumer (#30) reads this ONCE at scrape-step start (mirroring
        the #29 grabbed-snapshot) and resolves each folder in-memory. Fail-soft:
        an empty dict on any error (the caller then falls back to #29 → free match).
        """
        out: dict[str, MediaRef] = {}
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT current_path, media_ref_json FROM staging_provenance "
                "WHERE current_path IS NOT NULL AND media_ref_json IS NOT NULL"
            ).fetchall()
            for r in rows:
                out[r["current_path"]] = _media_ref_from_json(r["media_ref_json"])
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error yields the empty snapshot
            log.warning("acquire.provenance.index_failed", error=str(exc))
        return out

    def _read_one(self, where: str, params: tuple[object, ...]) -> ProvenanceRow | None:
        """Fetch one row for *where*/*params*, fail-soft (``None`` on any error)."""
        try:
            self._conn.row_factory = sqlite3.Row
            row = self._conn.execute(
                f"SELECT * FROM staging_provenance {where}",
                params,  # noqa: S608 — fixed literals
            ).fetchone()
            return _row_to_provenance(row) if row is not None else None
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error is a miss, never a crash
            log.warning("acquire.provenance.read_failed", error=str(exc))
            return None

    def list_journeys(self, limit: int = 200) -> list[ProvenanceRow]:
        """Return provenance rows, most-recent (``grabbed_at``) first (F1 journey view).

        Read-only + fail-soft: an empty list on any error. The web journey endpoint
        joins each row's follow title on top of this snapshot.
        """
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT * FROM staging_provenance ORDER BY grabbed_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [_row_to_provenance(r) for r in rows]
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error yields the empty list
            log.warning("acquire.provenance.list_journeys_failed", error=str(exc))
            return []

    def list_journeys_for_run(self, run_uid: str, limit: int = 500) -> list[ProvenanceRow]:
        """Return the acquisitions a given run advanced at ANY stage (F3, fail-soft).

        Matches ``run_uid`` against any of the four per-stage run columns — answers
        « quelles acquisitions ce run a-t-il traitées ? ». Empty list on any error.
        """
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT * FROM staging_provenance WHERE grab_run_uid = ? OR ingest_run_uid = ? "
                "OR scrape_run_uid = ? OR dispatch_run_uid = ? "
                "ORDER BY grabbed_at DESC, rowid DESC LIMIT ?",
                (run_uid, run_uid, run_uid, run_uid, limit),
            ).fetchall()
            return [_row_to_provenance(r) for r in rows]
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error yields the empty list
            log.warning("acquire.provenance.list_journeys_for_run_failed", error=str(exc))
            return []

    def list_stuck(self, older_than: int, exists_fn: Callable[[str], bool], limit: int = 500) -> list[ProvenanceRow]:
        """Return in-flight items stuck past *older_than* whose folder still exists (F4, fail-soft).

        The substrate for targeted re-actions: an in-flight row (grabbed/ingested/scraped)
        whose latest stage is older than *older_than* and whose ``current_path`` still exists
        on disk (checked via *exists_fn*, FS = truth). Oldest first. Empty list on any error.
        """
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT * FROM staging_provenance "
                "WHERE status IN ('grabbed', 'ingested', 'scraped') AND current_path IS NOT NULL "
                "AND COALESCE(scraped_at, ingested_at, grabbed_at) < ? "
                "ORDER BY COALESCE(scraped_at, ingested_at, grabbed_at) ASC LIMIT ?",
                (older_than, limit),
            ).fetchall()
            out = [_row_to_provenance(r) for r in rows]
            return [r for r in out if r.current_path is not None and exists_fn(r.current_path)]
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error yields the empty list
            log.warning("acquire.provenance.list_stuck_failed", error=str(exc))
            return []

    def stage_counts(self) -> dict[str, int]:
        """Return ``{status: count}`` over the whole registry (F5 overview, uncapped).

        An UNCAPPED ``GROUP BY status`` — the honest per-stage rollup the « état de la
        machine » view needs (a frontend count over the 200-capped ``list_journeys`` would
        silently lie). Fail-soft: an empty dict on any error.
        """
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute("SELECT status, COUNT(*) AS n FROM staging_provenance GROUP BY status").fetchall()
            return {r["status"]: r["n"] for r in rows if r["status"] is not None}
        except Exception as exc:  # noqa: BLE001 — fail-soft: a read error yields the empty dict
            log.warning("acquire.provenance.stage_counts_failed", error=str(exc))
            return {}

    def prune_stale(self, exists_fn: Callable[[str], bool]) -> int:
        """Prune ORPHANED in-flight rows whose ``current_path`` no longer exists.

        FS = truth: a mid-pipeline row whose staging folder vanished (a failed /
        abandoned item) is dropped — the FS is NEVER mutated to match the DB, only
        the DB is pruned. ``dispatched`` rows are KEPT: their ``current_path`` is
        legitimately gone (the media moved to disk), and the completed journey is
        an audit record the provenance view (F1) reads. Best-effort (0 on error).

        Args:
            exists_fn: Predicate ``path -> bool`` (typically ``os.path.exists``).

        Returns:
            The count of rows pruned (0 on any error).
        """
        try:
            self._conn.row_factory = sqlite3.Row
            rows = self._conn.execute(
                "SELECT info_hash, current_path FROM staging_provenance "
                "WHERE current_path IS NOT NULL AND status != 'dispatched'"
            ).fetchall()
            stale = [r["info_hash"] for r in rows if not exists_fn(r["current_path"])]
            for info_hash in stale:
                self._safe_write("DELETE FROM staging_provenance WHERE info_hash = ?", (info_hash,))
            return len(stale)
        except Exception as exc:  # noqa: BLE001 — advisory prune never crashes a caller
            log.warning("acquire.provenance.prune_failed", error=str(exc))
            return 0
