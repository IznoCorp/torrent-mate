#!/usr/bin/env python3
"""§5 acquisition coherence guardrail (P0-B.5, product-intent.md §méthode).

Cross-checks, for every followed series/movie, the four sources of truth the
acquisition lobe relies on and prints one loud line per incoherence:

1. ``acquire.db``  — the follow list + wanted queue + aired-episode cache
   (tables ``followed_series``, ``wanted``, ``aired_episode``), opened READ-ONLY.
2. ``library.db``  — what the library actually owns, via the indexer ownership
   predicate (:func:`personalscraper.indexer.ownership.is_owned` +
   :func:`~personalscraper.indexer.ownership.owned_episode_pairs`), READ-ONLY.
3. The torrent client — the set of info-hashes it actually knows
   (``get_all_hashes``). If the client is unreachable, the client-side checks
   are SKIPPED (announced loudly) — never a hard failure.
4. The wanted rows' own ``media_ref_json`` provider IDs.

Anomaly rules (each printed as ``[RULE] title SxxEyy (wanted #id): explanation``):

- GRABBED_OWNED       — wanted 'grabbed' whose work IS owned (phantom in-flight;
  reconciliation should have closed it).
- GRABBED_HASH_MISSING — wanted 'grabbed' whose grabbed_hash the torrent client
  does not know AND not owned (lost grab; should be requeued).
- PENDING_OWNED       — wanted 'pending'/'searching' whose work IS owned
  (needless future grab).
- ABANDONED_MISSING   — wanted 'abandoned' episode, present in the aired-episode
  cache, NOT owned (an aired episode nobody will ever fetch).
- DUPLICATE_WANTED    — two or more wanted rows sharing
  (followed_id, kind, season, episode) — NULL-safe grouping.
- FOLLOW_NO_REF       — a follow whose media_ref_json has no tvdb/tmdb/imdb id
  (detect silently skips it).
- SHOW_NO_CATALOG     — an ACTIVE show follow with zero aired_episode rows
  (completeness falls back to live provider calls) — severity INFO, printed
  but NOT counted in the exit code.

Exit code = number of counted anomalies (rules 1-6; 0 = coherent).

Usage:
    python scripts/check-acquisition-coherence.py          # human-readable
    python scripts/check-acquisition-coherence.py --json   # JSON anomaly dump
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field

from personalscraper.indexer.ownership import is_owned, owned_episode_pairs

# Statuses that mean "the queue still intends to fetch this in the future".
_FUTURE_STATUSES = ("pending", "searching")


@dataclass
class Anomaly:
    """One acquisition-coherence anomaly.

    Attributes:
        rule: Short rule tag, e.g. ``GRABBED_OWNED``.
        title: Followed title the row belongs to (``(no follow)`` when the
            wanted row has a NULL ``followed_id``).
        kind: ``movie`` / ``episode`` / ``show`` (or ``None`` when unknown).
        season: Season number when the anomaly targets an episode, else None.
        episode: Episode number when the anomaly targets an episode, else None.
        wanted_ids: The wanted row id(s) involved (empty for follow-level rules).
        followed_id: The followed_series row id involved, when known.
        explanation: Human-readable one-line explanation.
        counted: Whether the anomaly counts toward the exit code (rule 7
            SHOW_NO_CATALOG is INFO-only and does not).
    """

    rule: str
    title: str
    kind: str | None
    season: int | None
    episode: int | None
    wanted_ids: list[int] = field(default_factory=list)
    followed_id: int | None = None
    explanation: str = ""
    counted: bool = True

    def line(self) -> str:
        """Render the anomaly as the canonical one-line report.

        Returns:
            ``[RULE] title SxxEyy (wanted #id): explanation`` — the SxxEyy
            locus appears only for episode-scoped anomalies, and the ref part
            says ``follow #id`` for follow-level rules.
        """
        parts = [f"[{self.rule}]", self.title]
        if self.kind == "episode":
            sxx = f"{self.season:02d}" if self.season is not None else "??"
            eyy = f"{self.episode:02d}" if self.episode is not None else "??"
            parts.append(f"S{sxx}E{eyy}")
        elif self.kind:
            parts.append(f"({self.kind})")
        if self.wanted_ids:
            parts.append(f"(wanted {', '.join(f'#{i}' for i in self.wanted_ids)})")
        elif self.followed_id is not None:
            parts.append(f"(follow #{self.followed_id})")
        return f"{' '.join(parts)}: {self.explanation}"


def _parse_ref(raw: str | None) -> tuple[int | None, int | None, str | None]:
    """Parse a ``media_ref_json`` payload into ``(tvdb_id, tmdb_id, imdb_id)``.

    Args:
        raw: The JSON text stored in ``media_ref_json`` (``{"tvdb_id": ..,
            "tmdb_id": .., "imdb_id": ..}``), possibly None or malformed.

    Returns:
        The provider-id triple; a missing/malformed payload yields all-None.
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
    return (
        _as_int(data.get("tvdb_id")),
        _as_int(data.get("tmdb_id")),
        str(imdb) if imdb else None,
    )


class _OwnershipIndex:
    """Ownership lookups over ``library.db`` with a per-series pair cache.

    Movies go through the per-work :func:`is_owned` predicate; episodes go
    through :func:`owned_episode_pairs` (one bulk query per distinct series
    ref, cached) so a long wanted queue costs one round-trip per series
    instead of one per episode.

    Attributes:
        _conn: Open read-only connection to ``library.db``.
        _pairs_cache: ``(tvdb, tmdb, imdb) → owned (season, episode) set``.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialise the index over an open ``library.db`` connection.

        Args:
            conn: Open (read-only) connection to the indexer database.
        """
        self._conn = conn
        self._pairs_cache: dict[tuple[int | None, int | None, str | None], set[tuple[int, int]]] = {}

    def owned(
        self,
        kind: str,
        ref: tuple[int | None, int | None, str | None],
        season: int | None,
        episode: int | None,
    ) -> bool:
        """Return True iff the library owns a live file for this work.

        Args:
            kind: ``"movie"`` or ``"episode"`` (the wanted row's kind).
            ref: ``(tvdb_id, tmdb_id, imdb_id)`` provider-id triple.
            season: Season number (episodes only).
            episode: Episode number (episodes only).

        Returns:
            The ownership verdict; an all-None ref or a NULL season/episode
            on an episode row can never match and returns False.
        """
        tvdb_id, tmdb_id, imdb_id = ref
        if tvdb_id is None and tmdb_id is None and imdb_id is None:
            return False
        if kind == "movie":
            return is_owned(self._conn, kind="movie", tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)
        if season is None or episode is None:
            return False
        if ref not in self._pairs_cache:
            self._pairs_cache[ref] = owned_episode_pairs(self._conn, tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)
        return (season, episode) in self._pairs_cache[ref]


def collect_anomalies(
    acquire_conn: sqlite3.Connection,
    indexer_conn: sqlite3.Connection,
    client_hashes: set[str] | None,
) -> list[Anomaly]:
    """Cross-check acquire.db, library.db and the torrent client hash set.

    Pure core of the guardrail — no config loading, no I/O beyond the two
    open connections, so tests can call it directly against temp databases.

    Args:
        acquire_conn: Open connection to ``acquire.db`` (read access only is
            used; callers should open it read-only).
        indexer_conn: Open connection to ``library.db`` (idem).
        client_hashes: The torrent client's known info-hashes (lowercase),
            or ``None`` when the client is unavailable — the client-side rule
            (GRABBED_HASH_MISSING) is then skipped entirely.

    Returns:
        The anomaly list, in rule-evaluation order (per-wanted rules first,
        then duplicates, then follow-level rules).
    """
    followed: dict[int, sqlite3.Row] = {}
    acquire_conn.row_factory = sqlite3.Row
    for row in acquire_conn.execute("SELECT id, title, active, kind, media_ref_json FROM followed_series"):
        followed[row["id"]] = row

    wanted_rows = acquire_conn.execute(
        "SELECT id, followed_id, media_ref_json, kind, season, episode, status, grabbed_hash FROM wanted ORDER BY id"
    ).fetchall()

    aired_keys: set[tuple[int, int, int]] = set()
    aired_count: dict[int, int] = {}
    for row in acquire_conn.execute("SELECT followed_id, season, episode FROM aired_episode"):
        aired_keys.add((row["followed_id"], row["season"], row["episode"]))
        aired_count[row["followed_id"]] = aired_count.get(row["followed_id"], 0) + 1

    ownership = _OwnershipIndex(indexer_conn)
    anomalies: list[Anomaly] = []

    def _title_of(followed_id: int | None) -> str:
        row = followed.get(followed_id) if followed_id is not None else None
        return row["title"] if row is not None else "(no follow)"

    # ------------------------------------------------------------------
    # Rules 1-4 — per wanted row
    # ------------------------------------------------------------------
    for w in wanted_rows:
        ref = _parse_ref(w["media_ref_json"])
        title = _title_of(w["followed_id"])
        owned = ownership.owned(w["kind"], ref, w["season"], w["episode"])
        common = {
            "title": title,
            "kind": w["kind"],
            "season": w["season"],
            "episode": w["episode"],
            "wanted_ids": [w["id"]],
            "followed_id": w["followed_id"],
        }

        if w["status"] == "grabbed":
            if owned:
                anomalies.append(
                    Anomaly(
                        rule="GRABBED_OWNED",
                        explanation="status='grabbed' but the library already owns it "
                        "(phantom in-flight; reconciliation should have closed it)",
                        **common,
                    )
                )
            elif client_hashes is not None:
                grabbed_hash = (w["grabbed_hash"] or "").lower()
                if grabbed_hash not in client_hashes:
                    shown = grabbed_hash or "<NULL>"
                    anomalies.append(
                        Anomaly(
                            rule="GRABBED_HASH_MISSING",
                            explanation=f"grabbed_hash {shown} unknown to the torrent client and not owned "
                            "(lost grab; should be requeued)",
                            **common,
                        )
                    )
        elif w["status"] in _FUTURE_STATUSES and owned:
            anomalies.append(
                Anomaly(
                    rule="PENDING_OWNED",
                    explanation=f"status='{w['status']}' but the library already owns it (needless future grab)",
                    **common,
                )
            )
        elif (
            w["status"] == "abandoned"
            and w["kind"] == "episode"
            and w["followed_id"] is not None
            and (w["followed_id"], w["season"], w["episode"]) in aired_keys
            and not owned
        ):
            anomalies.append(
                Anomaly(
                    rule="ABANDONED_MISSING",
                    explanation="abandoned but aired (in the detect cache) and not owned "
                    "— an aired episode nobody will ever fetch",
                    **common,
                )
            )

    # ------------------------------------------------------------------
    # Rule 5 — DUPLICATE_WANTED (NULL-safe grouping in Python: None is a
    # perfectly good dict-key component, unlike SQL NULL equality).
    # ------------------------------------------------------------------
    groups: dict[tuple[int | None, str, int | None, int | None], list[int]] = {}
    for w in wanted_rows:
        groups.setdefault((w["followed_id"], w["kind"], w["season"], w["episode"]), []).append(w["id"])
    for (followed_id, kind, season, episode), ids in groups.items():
        if len(ids) >= 2:
            anomalies.append(
                Anomaly(
                    rule="DUPLICATE_WANTED",
                    title=_title_of(followed_id),
                    kind=kind,
                    season=season,
                    episode=episode,
                    wanted_ids=sorted(ids),
                    followed_id=followed_id,
                    explanation=f"{len(ids)} wanted rows share (followed_id, kind, season, episode)",
                )
            )

    # ------------------------------------------------------------------
    # Rules 6-7 — per followed row
    # ------------------------------------------------------------------
    for fid, f in followed.items():
        ref = _parse_ref(f["media_ref_json"])
        if ref == (None, None, None):
            anomalies.append(
                Anomaly(
                    rule="FOLLOW_NO_REF",
                    title=f["title"],
                    kind=f["kind"],
                    season=None,
                    episode=None,
                    followed_id=fid,
                    explanation="media_ref_json has no tvdb_id/tmdb_id/imdb_id — detect silently skips this follow",
                )
            )
        if f["active"] and f["kind"] == "show" and aired_count.get(fid, 0) == 0:
            anomalies.append(
                Anomaly(
                    rule="SHOW_NO_CATALOG",
                    title=f["title"],
                    kind=f["kind"],
                    season=None,
                    episode=None,
                    followed_id=fid,
                    explanation="active show follow with zero aired_episode rows — completeness falls back to "
                    "live provider calls (detect has not cached it yet)",
                    counted=False,
                )
            )

    return anomalies


def _open_ro(path: str) -> sqlite3.Connection:
    """Open a SQLite database strictly read-only (URI ``mode=ro``).

    Args:
        path: Filesystem path to the database file.

    Returns:
        An open read-only connection with dict-style row access.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_client_hashes(config: object) -> set[str] | None:
    """Fetch the torrent client's known info-hashes, fail-soft.

    Args:
        config: The loaded :class:`~personalscraper.conf.models.config.Config`
            (typed as object to keep the import surface of the core minimal).

    Returns:
        The lowercase hash set, or ``None`` when the client is unavailable
        (announced on stderr) — callers must then skip client-side checks.
    """
    from personalscraper.api.torrent._factory import build_active_torrent_client  # noqa: PLC0415

    try:
        client = build_active_torrent_client(config.torrent)  # type: ignore[attr-defined]
        return {h.lower() for h in client.get_all_hashes()}
    except Exception as exc:  # noqa: BLE001 — fail-soft: the guardrail must run without the client
        print(
            f"⚠️  torrent client unavailable ({exc}) — SKIPPING client checks (GRABBED_HASH_MISSING)",
            file=sys.stderr,
        )
        return None


def main() -> int:
    """Run the guardrail against the config-resolved databases.

    Returns:
        The number of counted anomalies (rules 1-6), capped at 255 so the
        process exit code can never wrap back to a false 0.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true", help="Dump the anomaly list as JSON instead of human lines.")
    args = parser.parse_args()

    from personalscraper.conf.loader import load_config  # noqa: PLC0415

    config = load_config()
    acquire_path = config.acquire.db_path
    indexer_path = config.indexer.db_path
    assert acquire_path is not None and indexer_path is not None  # auto-derived by Config
    for label, path in (("acquire.db", acquire_path), ("library.db", indexer_path)):
        if not path.exists():
            print(f"❌ {label} not found at {path}", file=sys.stderr)
            return 2

    client_hashes = _fetch_client_hashes(config)

    acquire_conn = _open_ro(str(acquire_path))
    indexer_conn = _open_ro(str(indexer_path))
    # Rules 4 + 7 read the aired_episode cache (acquire migration 007). A
    # read-only connection cannot migrate, so an out-of-date schema is itself
    # a loud finding — not a traceback.
    has_aired = acquire_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='aired_episode'"
    ).fetchone()
    if has_aired is None:
        print(
            f"❌ acquire.db at {acquire_path} has no aired_episode table (schema < 7) — "
            "run any acquire command to apply migrations, then re-run this guardrail",
            file=sys.stderr,
        )
        return 2
    try:
        anomalies = collect_anomalies(acquire_conn, indexer_conn, client_hashes)
    finally:
        acquire_conn.close()
        indexer_conn.close()

    counted = sum(1 for a in anomalies if a.counted)
    if args.json:
        print(json.dumps([asdict(a) for a in anomalies], indent=2, ensure_ascii=False))
    else:
        for a in anomalies:
            marker = "❌" if a.counted else "ℹ️ "
            print(f"{marker} {a.line()}")
        skipped = " (client checks SKIPPED)" if client_hashes is None else ""
        print(f"\n{len(anomalies)} anomalies ({counted} counted, {len(anomalies) - counted} info){skipped}.")
    return min(counted, 255)


if __name__ == "__main__":
    sys.exit(main())
