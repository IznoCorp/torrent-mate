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

Ownership and queue shape:

- GRABBED_OWNED       — wanted 'grabbed' whose work IS owned (phantom in-flight;
  reconciliation should have closed it).
- UI_ACQUIRING_NO_TORRENT — an episode the INTERFACE reports « En cours d'acquisition »
  with no live torrent behind it. This rule runs the SAME derivation the web read
  model runs, then confronts it with the torrent client: it is the executable form
  of §13 (« l'interface reflète l'état réel des données »). It is what would have
  caught the 2026-08-04 incident, where four absorbed American Dad episodes kept
  reading « En cours d'acquisition » after the reswitch had emptied the client.
- GRABBED_HASH_MISSING — wanted 'grabbed' whose grabbed_hash the torrent client
  does not know AND not owned (lost grab; should be requeued).
- PENDING_OWNED       — wanted 'pending'/'searching' whose work IS owned
  (needless future grab).
- ABANDONED_MISSING   — wanted 'abandoned' episode, present in the aired-episode
  cache, NOT owned (an aired episode nobody will ever fetch).
- QUEUE_ABSORBED_DANGLING — an ``absorbed`` row whose ``absorbed_by`` is NULL or names
  a row that does not exist. ``absorbed`` is a POINTER to the season wanted carrying the
  acquisition, and the queue follows it (#411); a pointer it cannot follow leaves the row
  reading « En cours d'acquisition » on an ignorance. Severity ``warning``: the carrying
  season might genuinely be in flight, so this is an unsupported claim, not a proven lie.
  The column carries no FK — the table is advisory — so dangling is a real possibility.
  NOTE the deliberate absence of a « the queue claims an acquisition with no torrent »
  rule: once the pointer is followed, the only in-flight readings left are ``grabbed``
  (already GRABBED_HASH_MISSING) and this one. A rule that can only ever duplicate another
  is a false witness — it suggests coverage it does not provide.
- DUPLICATE_WANTED    — two or more wanted rows sharing
  (followed_id, kind, season, episode) — NULL-safe grouping.
- FOLLOW_NO_REF       — a follow whose media_ref_json has no tvdb/tmdb/imdb id
  (detect silently skips it).
- SHOW_NO_CATALOG     — an ACTIVE show follow with zero aired_episode rows
  (completeness falls back to live provider calls) — severity ``info``, not
  counted in the exit code.

The provenance spine (spine-truth) — every grab owes a journey. The spine's writes
are ADVISORY and swallow their errors, so both halves of the invariant broke in
silence for four days and the « Dispatchés » tile read 1 while dozens of items had
landed. One rule per failure mode; they never report the same row:

- SPINE_ROW_MISSING   — a wanted row carrying a ``grabbed_hash`` with NO
  ``staging_provenance`` row at all: the grab's provenance write never landed (the
  shape a rejected INSERT produces, e.g. a ``kind`` the table's CHECK refused).
- SPINE_DISPATCH_MISSING — a wanted row closed ``done`` with a ``grabbed_hash``
  whose spine row exists but never reached ``dispatched``/``reconciled``: the media
  is in the library but the journey stopped mid-pipeline.

The five states (acq-states phase 9) — every rule below audits the columns the
state derivation reads, on OPEN wanted rows only (a closed row is history, and
:func:`~personalscraper.web.acquisition.states.select_wanted_facts` ignores it):

- INCONCLUSIVE_WITH_FOUND — OPEN row whose last_search_outcome did not conclude
  (it is in ``INCONCLUSIVE_OUTCOMES``) yet stored a last_search_found instead of
  NULL. Storing 0 there claims « I looked, there is nothing » about trackers
  that were never reached — panne ≠ absence.
- SEARCHED_WITHOUT_VERDICT — OPEN row with last_search_at set but
  last_search_outcome NULL: a search exit path forgot to record its verdict, so
  the item reads « Non vérifié » forever (a lie by omission).
- AVAILABLE_VERDICT_DESYNC — 'available' row whose last_search_outcome is not
  'available': the status and the verdict that produced it disagree.
- AVAILABLE_STALE — 'available' for more than 24h against last_search_at. That
  status is a hand-off to the grab pass, not a resting state — severity
  ``warning`` (an operator fixes it, not a code change).
- ACTIVE_A_JOUR_NO_CATALOG — active show follow with an empty aired catalog, for
  which the SHARED card derivation reads « À jour ». The founding incident made
  executable: Furious was followed at 09:18, detect had last run at 03:00, and
  its card declared « À jour » with three aired episodes missing.
- FOLLOW_MISSING_POSTER — active follow with poster_url NULL: its card renders
  without artwork — severity ``warning``.

Severity: ``error`` (broken invariant) and ``warning`` (degraded state needing
an operator) are counted; ``info`` is printed but never counted.

Exit code = number of counted anomalies; 0 = coherent.

Usage:
    python scripts/check-acquisition-coherence.py          # human-readable
    python scripts/check-acquisition-coherence.py --json   # JSON anomaly dump
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES
from personalscraper.acquire.orchestrator import INCONCLUSIVE_OUTCOMES
from personalscraper.indexer.ownership import is_owned, owned_episode_pairs
from personalscraper.web.acquisition.states import (
    derive_episode_state,
    governing_facts_by_episode,
)

# Statuses that mean "the queue still intends to fetch this in the future".
_FUTURE_STATUSES = ("pending", "searching")

#: Stale-available threshold: 'available' hands an item to the grab pass, so a
#: row still waiting a day later means that pass is dead or its cron is gone.
_STALE_AVAILABLE_S = 24 * 3600

#: Printed marker per severity. The exit code derives from that SAME severity
#: (see :class:`Anomaly`), so the marker and the code can never disagree.
_MARKERS = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}


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
        severity: ``"error"`` (a broken invariant), ``"warning"`` (a degraded
            state that needs an operator, not a code fix) or ``"info"`` (a
            note). Set at construction — it is the ONLY knob.
        counted: Whether the anomaly counts toward the exit code. Derived from
            :attr:`severity`, never passed: ``error`` and ``warning`` count,
            ``info`` does not. A single source keeps the printed marker and
            the exit code from ever disagreeing.
    """

    rule: str
    title: str
    kind: str | None
    season: int | None
    episode: int | None
    wanted_ids: list[int] = field(default_factory=list)
    followed_id: int | None = None
    explanation: str = ""
    severity: str = "error"
    counted: bool = field(init=False, default=True)

    def __post_init__(self) -> None:
        """Derive :attr:`counted` from :attr:`severity`.

        Kept a real field rather than a property so ``asdict`` (and therefore
        the ``--json`` dump, a stable consumer contract) still carries it.
        """
        self.counted = self.severity != "info"

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


def _season_owned(
    ownership: "_OwnershipIndex",
    ref: tuple[int | None, int | None, str | None],
    followed_id: int | None,
    season: int | None,
    aired_keys: set[tuple[int, int, int]],
) -> bool:
    """Return True iff EVERY aired episode of *season* is owned (the season-level answer).

    Mirrors :func:`personalscraper.acquire.reconcile._season_fully_owned` — same rule,
    two readers, so the guard can never disagree with the engine about what closes a
    season row. Every blind spot answers ``False``: a missing ``followed_id``/``season``,
    an empty catalog for that season, or partial ownership. Declaring a season owned on
    zero knowledge would be the mirror-image lie.

    Args:
        ownership: The per-work ownership index over ``library.db``.
        ref: The wanted row's ``(tvdb_id, tmdb_id, imdb_id)`` triple.
        followed_id: The follow the row belongs to, or None.
        season: The season number, or None.
        aired_keys: The ``(followed_id, season, episode)`` set from the aired cache.

    Returns:
        ``True`` iff the catalog is non-empty for the season and every episode is owned.
    """
    if followed_id is None or season is None:
        return False
    episodes = [e for (f, s, e) in aired_keys if f == followed_id and s == season]
    if not episodes:
        return False
    return all(ownership.owned("episode", ref, season, episode) for episode in episodes)


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
    for row in acquire_conn.execute("SELECT id, title, active, kind, media_ref_json, poster_url FROM followed_series"):
        followed[row["id"]] = row

    wanted_rows = acquire_conn.execute(
        "SELECT id, followed_id, media_ref_json, kind, season, episode, status, grabbed_hash, "
        "last_search_at, last_search_outcome, last_search_found, absorbed_by FROM wanted ORDER BY id"
    ).fetchall()
    #: Every wanted id that EXISTS — the referent set an ``absorbed_by`` pointer is
    #: checked against (the column carries no FK; the table is advisory).
    known_wanted_ids = {row["id"] for row in wanted_rows}

    aired_keys: set[tuple[int, int, int]] = set()
    aired_count: dict[int, int] = {}
    for row in acquire_conn.execute("SELECT followed_id, season, episode FROM aired_episode"):
        aired_keys.add((row["followed_id"], row["season"], row["episode"]))
        aired_count[row["followed_id"]] = aired_count.get(row["followed_id"], 0) + 1

    ownership = _OwnershipIndex(indexer_conn)
    anomalies: list[Anomaly] = []
    # Sampled once so every staleness verdict in one report shares a clock.
    now = int(time.time())

    def _title_of(followed_id: int | None) -> str:
        row = followed.get(followed_id) if followed_id is not None else None
        return row["title"] if row is not None else "(no follow)"

    # ------------------------------------------------------------------
    # Rule 0 — §13: what the INTERFACE says, confronted with the torrent client
    # ------------------------------------------------------------------
    # Runs the read model's OWN derivation (same seam the card and the matrix use)
    # and asks the only question a screen cannot answer for itself: is there really
    # a torrent behind « En cours d'acquisition »? A UI state is a claim about
    # reality; this is where the claim is checked against it.
    if client_hashes is not None:
        by_follow_ep: dict[int, list] = {}
        by_follow_se: dict[int, list] = {}
        hash_of_row: dict[int, str | None] = {}
        for w in wanted_rows:
            hash_of_row[w["id"]] = (w["grabbed_hash"] or "").lower() or None
            if w["kind"] == "episode" and w["season"] is not None and w["episode"] is not None:
                by_follow_ep.setdefault(w["followed_id"], []).append(
                    (
                        w["id"],
                        w["season"],
                        w["episode"],
                        w["status"],
                        w["last_search_outcome"],
                        w["last_search_found"],
                        w["absorbed_by"],
                    )
                )
            elif w["kind"] == "season":
                by_follow_se.setdefault(w["followed_id"], []).append(
                    (w["id"], w["status"], w["last_search_outcome"], w["last_search_found"])
                )
        for followed_id, eps in by_follow_ep.items():
            facts = governing_facts_by_episode(eps, by_follow_se.get(followed_id, []))
            fref = _parse_ref(followed[followed_id]["media_ref_json"]) if followed_id in followed else None
            # Which row ends up governing decides which hash must back the claim.
            season_hash = {sid: hash_of_row.get(sid) for sid, *_ in by_follow_se.get(followed_id, [])}
            for (season, episode), (status, outcome, found) in facts.items():
                owned_ep = ownership.owned("episode", fref, season, episode) if fref else False
                state = derive_episode_state(
                    owned=owned_ep,
                    wanted_status=status,
                    last_search_outcome=outcome,
                    last_search_found=found,
                )
                # BOTH states read « En cours d'acquisition » on screen: ``absorbed``
                # is the season-carried variant, and the card sums the two
                # (truth.py: en_acquisition + absorbed). Checking only the literal
                # ``en_acquisition`` would leave the exact shape of the 2026-08-04
                # incident invisible — the rule must read what the OPERATOR reads.
                if state not in ("en_acquisition", "absorbed"):
                    continue
                live = [
                    h
                    for h in (
                        *season_hash.values(),
                        *(hash_of_row[e[0]] for e in eps if e[1] == season and e[2] == episode),
                    )
                    if h
                ]
                # A row that HAS a hash the client lost is GRABBED_HASH_MISSING's
                # failure mode — one rule per mode, no double-reporting. What only
                # THIS rule can see is the screen claiming an acquisition with NO
                # hash anywhere behind it: the absorbed episode whose season row was
                # requeued and now carries nothing at all (the 2026-08-04 shape).
                if not live:
                    anomalies.append(
                        Anomaly(
                            rule="UI_ACQUIRING_NO_TORRENT",
                            severity="error",
                            title=_title_of(followed_id),
                            kind="episode",
                            season=season,
                            episode=episode,
                            explanation=(
                                "the interface reports « En cours d'acquisition » but no live "
                                "torrent backs it (§13: the UI must reflect the real data)"
                            ),
                        )
                    )

    # ------------------------------------------------------------------
    # Rules 1-4 — per wanted row
    # ------------------------------------------------------------------
    for w in wanted_rows:
        ref = _parse_ref(w["media_ref_json"])
        title = _title_of(w["followed_id"])
        # §14.3 — la possession doit avoir une réponse pour CHAQUE genre de ligne. Une
        # ligne `season` n'a pas de numéro d'épisode, donc la voie épisode ne peut rien en
        # dire : sa possession se lit sur le catalogue diffusé, exactement comme le fait
        # ``reconcile._season_fully_owned`` (une seule règle, deux lecteurs). Sans ça, deux
        # packs American Dad atterris en médiathèque ont affiché « récupéré » huit heures
        # sans qu'aucune règle ne crie.
        if w["kind"] == "season":
            owned = _season_owned(ownership, ref, w["followed_id"], w["season"], aired_keys)
        else:
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

        # The absorption pointer must be FOLLOWABLE. The queue resolves an
        # absorbed row onto the season wanted that carries its acquisition
        # (#411); when the pointer leads nowhere, the resolution cannot happen
        # and the row goes on reading « En cours d'acquisition » — a claim with
        # nothing behind it. Checked here, outside the OPEN-rows section below,
        # because `absorbed` is precisely NOT an open status.
        if w["status"] == "absorbed":
            carrier = w["absorbed_by"]
            if carrier is None or carrier not in known_wanted_ids:
                shown = "NULL" if carrier is None else f"#{carrier} (absent)"
                anomalies.append(
                    Anomaly(
                        rule="QUEUE_ABSORBED_DANGLING",
                        severity="warning",
                        explanation=f"absorbed_by={shown}: the absorption pointer cannot be followed, "
                        "so the queue reports « En cours d'acquisition » on an ignorance "
                        "(§13: follow the pointer, never report it)",
                        **common,
                    )
                )

        # --------------------------------------------------------------
        # Rules 8-11 — the search-verdict columns (acq-states phase 9).
        # Independent of the status chain above: those rules audit
        # ownership, these audit what the last search pass persisted.
        # --------------------------------------------------------------
        if w["status"] not in OPEN_WANTED_STATUSES:
            # A 'done'/'abandoned' row is HISTORY, not state: no surface
            # reads its verdict (select_wanted_facts skips it), so a stale
            # verdict there is noise rather than an incoherence.
            continue

        outcome = w["last_search_outcome"]
        found = w["last_search_found"]
        searched_at = w["last_search_at"]

        # Rule 8 — the search did not conclude, yet it stored a count.
        # ``record_search_outcome`` contracts ``found=None`` for every
        # inconclusive exit: storing 0 claims « I looked, there is
        # nothing » about trackers we never reached (panne ≠ absence).
        if outcome in INCONCLUSIVE_OUTCOMES and found is not None:
            anomalies.append(
                Anomaly(
                    rule="INCONCLUSIVE_WITH_FOUND",
                    explanation=f"last_search_outcome='{outcome}' did not conclude but "
                    f"last_search_found={found} is stored (must be NULL — panne ≠ absence)",
                    **common,
                )
            )

        # Rule 9 — a search ran and no exit path recorded its verdict, so
        # the item reads « Non vérifié » forever: a lie by omission.
        if searched_at is not None and outcome is None:
            anomalies.append(
                Anomaly(
                    rule="SEARCHED_WITHOUT_VERDICT",
                    explanation=f"status='{w['status']}' with last_search_at set but no "
                    "last_search_outcome — a search exit path forgot to record its verdict",
                    **common,
                )
            )

        if w["status"] == "available":
            # Rule 10 — 'available' is written by the very pass that
            # produced the verdict, so the two can only disagree if one
            # of the two writes was lost.
            if outcome != "available":
                shown = f"'{outcome}'" if outcome is not None else "NULL"
                anomalies.append(
                    Anomaly(
                        rule="AVAILABLE_VERDICT_DESYNC",
                        explanation=f"status='available' but last_search_outcome={shown} "
                        "— the status and the verdict that produced it disagree",
                        **common,
                    )
                )
            # Rule 11 — 'available' is a hand-off, not a resting state:
            # the grab pass is the only consumer, so a row still waiting
            # a day later means that pass is dead or its cron is gone.
            if searched_at is not None and (now - searched_at) > _STALE_AVAILABLE_S:
                anomalies.append(
                    Anomaly(
                        rule="AVAILABLE_STALE",
                        explanation=f"status='available' and last_search_at is "
                        f"{(now - searched_at) // 3600}h old — the grab pass is not "
                        "consuming it (dead pass or missing cron)",
                        severity="warning",
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
    # Rules 14-15 — the provenance spine: every grab must have a journey
    # ------------------------------------------------------------------
    # ``_grab_pass`` writes a ``staging_provenance`` row for every FOLLOW-DRIVEN grab,
    # which is exactly the population of ``wanted``. So the invariant is total: a wanted
    # row carrying a ``grabbed_hash`` HAS a spine row, and once that acquisition closes
    # ``done`` the row HAS reached ``dispatched``. Both halves were broken in silence
    # until 0.80.0 — the writes are advisory and swallow their errors — and the « Vue
    # d'ensemble » tile read 1 while dozens of items had landed.
    #
    # Two rules, two failure modes, never both on the same row:
    #   SPINE_ROW_MISSING     — the grab's write never landed (a rejected INSERT).
    #   SPINE_DISPATCH_MISSING — it landed but the journey stopped mid-pipeline
    #                            (the dispatch could not correlate the folder back).
    spine_status: dict[str, str | None] = {}
    try:
        for row in acquire_conn.execute("SELECT info_hash, status FROM staging_provenance"):
            spine_status[(row["info_hash"] or "").lower()] = row["status"]
    except sqlite3.Error:
        # A database predating migration 010 has no spine at all — skip both rules
        # rather than report every grab ever made as an anomaly.
        spine_status = {}
        spine_available = False
    else:
        spine_available = True

    if spine_available:
        for w in wanted_rows:
            grabbed_hash = (w["grabbed_hash"] or "").lower()
            if not grabbed_hash:
                continue
            common = {
                "title": _title_of(w["followed_id"]),
                "kind": w["kind"],
                "season": w["season"],
                "episode": w["episode"],
                "wanted_ids": [w["id"]],
                "followed_id": w["followed_id"],
            }
            if grabbed_hash not in spine_status:
                anomalies.append(
                    Anomaly(
                        rule="SPINE_ROW_MISSING",
                        explanation=f"grabbed_hash {grabbed_hash[:12]}… has no staging_provenance row — "
                        "the grab's provenance write never landed (advisory writes swallow their "
                        "errors, so a rejected INSERT is invisible without this rule)",
                        **common,
                    )
                )
            elif w["status"] == "done" and spine_status[grabbed_hash] not in ("dispatched", "reconciled"):
                anomalies.append(
                    Anomaly(
                        rule="SPINE_DISPATCH_MISSING",
                        explanation=f"the acquisition closed 'done' but its spine row is "
                        f"'{spine_status[grabbed_hash]}' — the journey never reached the "
                        "library, so « Dispatchés » under-counts it (§13)",
                        **common,
                    )
                )

    # ------------------------------------------------------------------
    # Rules 6-7 + 12-13 — per followed row
    # ------------------------------------------------------------------
    # Imported here, not at module scope: ``personalscraper.web`` eagerly builds
    # the FastAPI app in its ``__init__``, and this guard must stay runnable as
    # a plain CLI script — same reason ``load_config`` is imported locally below.
    from personalscraper.web.acquisition.states import derive_follow_status  # noqa: PLC0415

    # Would the SHARED card derivation say « À jour » about a follow whose
    # aired catalog is empty? The question is ASKED, never assumed: today the
    # answer is yes, and only truth.py's all-None sentinel stands between an
    # empty catalog and the founding lie. The day the derivation itself
    # refuses ``aired_count == 0``, this guard falls silent on its own instead
    # of drifting into a rule the product no longer has.
    empty_catalog_reads_a_jour = (
        derive_follow_status(
            active=True,
            aired_count=0,
            a_recuperer_count=0,
            en_acquisition_count=0,
            en_attente_count=0,
            non_verifie_count=0,
        )
        == "a_jour"
    )

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
                    severity="info",
                )
            )
            # Rule 12 — the founding incident, made executable: Furious was
            # followed at 09:18, detect had last run at 03:00, and the card
            # declared « À jour » with three aired episodes missing. Priming
            # (phase 6) is supposed to fill the catalog at follow time, so an
            # active show still without one is a failure, not a note.
            if empty_catalog_reads_a_jour:
                anomalies.append(
                    Anomaly(
                        rule="ACTIVE_A_JOUR_NO_CATALOG",
                        title=f["title"],
                        kind=f["kind"],
                        season=None,
                        episode=None,
                        followed_id=fid,
                        explanation="active show follow with an empty aired catalog — the shared card "
                        "derivation reads « À jour » on that zero knowledge (founding incident); "
                        "priming should have written the catalog at follow time",
                    )
                )

        # Rule 13 — a card with no poster is a card the operator has to read
        # instead of recognise. The provider exposes one; a NULL here means
        # the follow-time metadata fetch failed and was never retried.
        if f["active"] and f["poster_url"] is None:
            anomalies.append(
                Anomaly(
                    rule="FOLLOW_MISSING_POSTER",
                    title=f["title"],
                    kind=f["kind"],
                    season=None,
                    episode=None,
                    followed_id=fid,
                    explanation="active follow with poster_url NULL — its card renders without artwork "
                    "(the provider exposes one; the follow-time metadata fetch never landed)",
                    severity="warning",
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
        The number of counted anomalies (error + warning severities),
        capped at 255 so the process exit code can never wrap back to a
        false 0.
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
            print(f"{_MARKERS.get(a.severity, '❓')} {a.line()}")
        tally = ", ".join(
            f"{sum(1 for a in anomalies if a.severity == level)} {level}" for level in ("error", "warning", "info")
        )
        skipped = " (client checks SKIPPED)" if client_hashes is None else ""
        print(f"\n{len(anomalies)} anomalies — {tally} ({counted} counted){skipped}.")
    return min(counted, 255)


if __name__ == "__main__":
    sys.exit(main())
