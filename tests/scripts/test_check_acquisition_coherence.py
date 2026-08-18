"""Tests for scripts/check-acquisition-coherence.py (P0-B.5 §5 guardrail).

Exercises ``collect_anomalies`` directly against a temp ``acquire.db`` and a
temp ``library.db`` both built with the REAL migration chains (no hand-rolled
schema), asserting the exact rule tags:

- GRABBED_OWNED fires for a 'grabbed' row whose episode IS in the library.
- DUPLICATE_WANTED fires for two wanted rows sharing the NULL-safe key.
- ABANDONED_MISSING fires for an abandoned + aired + unowned episode.
- GRABBED_HASH_MISSING fires only when the client hash set is available and
  is SKIPPED (no anomaly) when ``client_hashes is None``.
- PENDING_OWNED fires for pending episode AND movie rows the library owns.
- FOLLOW_NO_REF fires for a follow with an empty media_ref_json.
- SHOW_NO_CATALOG is emitted with ``counted=False`` (INFO — not in exit code).
- A coherent seeding yields zero anomalies (rules do not overfire).

Plus the five-state rules (acq-states phase 9), each with a violating fixture
AND a clean one — a rule that only ever fires proves nothing about the day it
should stay quiet:

- ACTIVE_A_JOUR_NO_CATALOG fires on the founding incident (active show, empty
  aired catalog) and stays silent on a primed catalog, a paused follow, a film.
- INCONCLUSIVE_WITH_FOUND fires when a non-concluding verdict stored a count,
  and stays silent on the contracted NULL and on closed (history) rows.
- SEARCHED_WITHOUT_VERDICT fires on a search that recorded no outcome.
- AVAILABLE_VERDICT_DESYNC fires on a disagreeing verdict AND on a missing one.
- AVAILABLE_STALE fires past the 24h hand-off window, as a counted WARNING.
- FOLLOW_MISSING_POSTER fires for an active follow with no poster_url.

Plus the two provenance-spine rules (spine-truth), each with its violating fixture,
its silent counterpart, AND the proof that they never report the same row:

- SPINE_ROW_MISSING fires when a grab left no journey row at all, and stays silent
  on a seeded row (case-insensitively) and on rows that were never grabbed.
- SPINE_DISPATCH_MISSING fires on a 'done' acquisition whose journey never reached
  the library, and stays silent on dispatched/reconciled rows and on open ones.

Plus the queue's own surface rule (file-absorbee, ticket 411):

- QUEUE_ABSORBED_DANGLING fires when an ``absorbed`` row's pointer is NULL or names a
  missing row, stays SILENT on the resolvable pointer (the shape of the 31 live rows),
  and is a ``warning`` — an unsupported claim is not a proven lie.
"""

from __future__ import annotations

import importlib.util as _util
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from personalscraper.acquire.domain import OPEN_WANTED_STATUSES
from personalscraper.acquire.orchestrator import INCONCLUSIVE_OUTCOMES
from personalscraper.core.sqlite import apply_migrations as apply_acquire_migrations
from personalscraper.indexer.db import apply_migrations as apply_indexer_migrations

# ---------------------------------------------------------------------------
# Locate and import the script under test (hyphen in filename → importlib)
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check-acquisition-coherence.py"

_spec = _util.spec_from_file_location("check_acquisition_coherence", SCRIPT)
assert _spec is not None, f"Could not load spec from {SCRIPT}"
_mod = _util.module_from_spec(_spec)
assert _spec.loader is not None
# Register in sys.modules BEFORE exec_module so @dataclass can resolve
# cls.__module__ back to sys.modules (same pattern as test_audit_fk_orphans).
sys.modules["check_acquisition_coherence"] = _mod
_spec.loader.exec_module(_mod)

collect_anomalies = _mod.collect_anomalies
Anomaly = _mod.Anomaly

_REPO_ROOT = Path(__file__).resolve().parents[2]
ACQUIRE_MIGRATIONS = _REPO_ROOT / "personalscraper" / "acquire" / "migrations"
INDEXER_MIGRATIONS = _REPO_ROOT / "personalscraper" / "indexer" / "migrations"

NOW = int(time.time())

_REF_SHOW = json.dumps({"tvdb_id": 555, "tmdb_id": None, "imdb_id": None})
_REF_MOVIE = json.dumps({"tvdb_id": None, "tmdb_id": 777, "imdb_id": None})


# ---------------------------------------------------------------------------
# Fixture helpers — REAL migration chains, temp files
# ---------------------------------------------------------------------------


def _acquire_db(tmp_path: Path) -> sqlite3.Connection:
    """Create a temp ``acquire.db`` with the full real migration chain applied."""
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    apply_acquire_migrations(conn, ACQUIRE_MIGRATIONS)
    return conn


def _indexer_db(tmp_path: Path) -> sqlite3.Connection:
    """Create a temp ``library.db`` with the full real indexer migration chain."""
    conn = sqlite3.connect(str(tmp_path / "library.db"))
    apply_indexer_migrations(conn, INDEXER_MIGRATIONS)
    conn.commit()
    return conn


def _insert_follow(
    conn: sqlite3.Connection,
    followed_id: int,
    *,
    ref: str = _REF_SHOW,
    title: str = "House Test",
    kind: str = "show",
    active: int = 1,
    poster_url: str | None = "https://example.com/poster.jpg",
) -> None:
    """Insert one followed_series row."""
    conn.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, kind, added_at, poster_url) "
        "VALUES (?,?,?,?,?,?,?)",
        (followed_id, ref, title, active, kind, NOW, poster_url),
    )


def _insert_wanted(
    conn: sqlite3.Connection,
    wanted_id: int,
    *,
    followed_id: int | None,
    ref: str = _REF_SHOW,
    kind: str = "episode",
    season: int | None = None,
    episode: int | None = None,
    status: str = "pending",
    grabbed_hash: str | None = None,
    last_search_at: int | None = None,
    last_search_outcome: str | None = None,
    last_search_found: int | None = None,
    absorbed_by: int | None = None,
) -> None:
    """Insert one wanted row."""
    conn.execute(
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode, status, enqueued_at,"
        " grabbed_hash, last_search_at, last_search_outcome, last_search_found, absorbed_by)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            wanted_id,
            followed_id,
            ref,
            kind,
            season,
            episode,
            status,
            NOW,
            grabbed_hash,
            last_search_at,
            last_search_outcome,
            last_search_found,
            absorbed_by,
        ),
    )


def _insert_aired(conn: sqlite3.Connection, followed_id: int, season: int, episode: int) -> None:
    """Insert one aired_episode cache row."""
    conn.execute(
        "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) VALUES (?,?,?,?,?,?)",
        (followed_id, season, episode, f"Ep {season}x{episode}", "2026-01-01", NOW),
    )


def _insert_spine(
    conn: sqlite3.Connection,
    info_hash: str,
    *,
    status: str = "dispatched",
    kind: str = "episode",
) -> None:
    """Insert one ``staging_provenance`` row for *info_hash* (the acquisition's journey).

    Every follow-driven grab writes one, so any fixture that sets a ``grabbed_hash``
    must seed it too — otherwise SPINE_ROW_MISSING correctly fires on that fixture.
    """
    conn.execute(
        "INSERT INTO staging_provenance (info_hash, kind, grabbed_at, status) VALUES (?,?,?,?)",
        (info_hash.lower(), kind, NOW, status),
    )
    conn.commit()


def _external_ids_json(*, tvdb_id: int | None = None, tmdb_id: int | None = None) -> str:
    """Build the hierarchical external_ids_json payload (migration 005 shape)."""
    payload: dict[str, dict[str, str | None]] = {}
    if tvdb_id is not None:
        payload["tvdb"] = {"series_id": str(tvdb_id), "episode_id": None}
    if tmdb_id is not None:
        payload["tmdb"] = {"series_id": str(tmdb_id), "episode_id": None}
    return json.dumps(payload)


def _own_episode(conn: sqlite3.Connection, *, tvdb_id: int, season: int, episode: int) -> None:
    """Make the library own one live episode file for a tvdb-identified show."""
    conn.execute("INSERT OR IGNORE INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1','D1','/Volumes/D1',1)")
    path_id = conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1, ?)", (f"tv/S{season}E{episode}",)).lastrowid
    item_id = conn.execute(
        "SELECT id FROM media_item WHERE kind='show' AND json_extract(external_ids_json,'$.tvdb.series_id')=?",
        (str(tvdb_id),),
    ).fetchone()
    if item_id is None:
        item_id = conn.execute(
            "INSERT INTO media_item(kind, title, title_sort, year, category_id, external_ids_json,"
            " date_created, date_modified) VALUES ('show','Show','Show',2020,'tv_shows',?,?,?)",
            (_external_ids_json(tvdb_id=tvdb_id), NOW, NOW),
        ).lastrowid
    else:
        item_id = item_id[0]
    season_row = conn.execute(
        "SELECT id FROM season WHERE item_id=? AND number=?",
        (item_id, season),
    ).fetchone()
    season_id = (
        season_row[0]
        if season_row
        else conn.execute("INSERT INTO season(item_id, number) VALUES (?,?)", (item_id, season)).lastrowid
    )
    episode_id = conn.execute("INSERT INTO episode(season_id, number) VALUES (?,?)", (season_id, episode)).lastrowid
    release_id = conn.execute("INSERT INTO media_release(item_id, episode_id) VALUES (NULL,?)", (episode_id,)).lastrowid
    conn.execute(
        "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at, deleted_at) VALUES (?,?,'ep.mkv',1000,?,?,1,?,NULL)",
        (release_id, path_id, NOW * 10**9, f"hash{season}{episode}", NOW),
    )
    conn.commit()


def _own_movie(conn: sqlite3.Connection, *, tmdb_id: int) -> None:
    """Make the library own one live movie file for a tmdb-identified movie."""
    conn.execute("INSERT OR IGNORE INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1','D1','/Volumes/D1',1)")
    path_id = conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1, 'movies/M')").lastrowid
    item_id = conn.execute(
        "INSERT INTO media_item(kind, title, title_sort, year, category_id, external_ids_json,"
        " date_created, date_modified) VALUES ('movie','Movie','Movie',2020,'movies',?,?,?)",
        (_external_ids_json(tmdb_id=tmdb_id), NOW, NOW),
    ).lastrowid
    release_id = conn.execute("INSERT INTO media_release(item_id, episode_id) VALUES (?,NULL)", (item_id,)).lastrowid
    conn.execute(
        "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at, deleted_at) VALUES (?,?,'movie.mkv',1000,?,'mhash',1,?,NULL)",
        (release_id, path_id, NOW * 10**9, NOW),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_standard_seed_fires_exactly_grabbed_owned_duplicate_and_abandoned(tmp_path: Path) -> None:
    """The mandated seed fires exactly rules 1, 4 and 5 with the right rows.

    Seed: a grabbed S01E01 the library owns (rule 1), a pending S01E03
    duplicate pair (rule 5), an abandoned S01E02 that aired but is unowned
    (rule 4). Aired cache is populated so SHOW_NO_CATALOG must NOT fire.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)

    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_aired(acquire, 1, 1, 2)
    _insert_wanted(acquire, 10, followed_id=1, season=1, episode=1, status="grabbed", grabbed_hash="aaaa")
    _insert_wanted(acquire, 11, followed_id=1, season=1, episode=3, status="pending")
    _insert_wanted(acquire, 12, followed_id=1, season=1, episode=3, status="pending")
    _insert_wanted(acquire, 13, followed_id=1, season=1, episode=2, status="abandoned")
    acquire.commit()
    _insert_spine(acquire, "aaaa", status="grabbed")  # every grab has its journey row

    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    anomalies = collect_anomalies(acquire, indexer, client_hashes=None)

    assert sorted(a.rule for a in anomalies) == ["ABANDONED_MISSING", "DUPLICATE_WANTED", "GRABBED_OWNED"]
    by_rule = {a.rule: a for a in anomalies}
    assert by_rule["GRABBED_OWNED"].wanted_ids == [10]
    assert (by_rule["GRABBED_OWNED"].season, by_rule["GRABBED_OWNED"].episode) == (1, 1)
    assert by_rule["DUPLICATE_WANTED"].wanted_ids == [11, 12]
    assert by_rule["ABANDONED_MISSING"].wanted_ids == [13]
    assert all(a.counted for a in anomalies), "rules 1/4/5 must all count toward the exit code"
    assert all(a.title == "House Test" for a in anomalies)


def test_grabbed_hash_missing_fires_with_client_and_skips_without(tmp_path: Path) -> None:
    """Rule 2 fires only when the client hash set is available.

    An unowned grabbed row whose hash the client does not know is a lost grab;
    with ``client_hashes=None`` the client-side check is skipped entirely.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 4)
    _insert_wanted(acquire, 20, followed_id=1, season=1, episode=4, status="grabbed", grabbed_hash="deadbeef")
    acquire.commit()
    _insert_spine(acquire, "deadbeef", status="grabbed")  # the grab landed on the spine

    with_client = collect_anomalies(acquire, indexer, client_hashes={"otherhash"})
    assert [a.rule for a in with_client] == ["GRABBED_HASH_MISSING"]
    assert with_client[0].wanted_ids == [20]

    without_client = collect_anomalies(acquire, indexer, client_hashes=None)
    assert without_client == [], "client checks must be skipped when the client is unavailable"


def test_pending_owned_fires_for_episode_and_movie(tmp_path: Path) -> None:
    """Rule 3 fires for pending/searching rows the library already owns — both kinds."""
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 2, 1)
    _insert_follow(acquire, 2, ref=_REF_MOVIE, title="Film Test", kind="movie")
    _insert_wanted(acquire, 30, followed_id=1, season=2, episode=1, status="searching")
    _insert_wanted(acquire, 31, followed_id=2, ref=_REF_MOVIE, kind="movie", status="pending")
    acquire.commit()

    _own_episode(indexer, tvdb_id=555, season=2, episode=1)
    _own_movie(indexer, tmdb_id=777)

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert sorted(a.rule for a in anomalies) == ["PENDING_OWNED", "PENDING_OWNED"]
    assert sorted(i for a in anomalies for i in a.wanted_ids) == [30, 31]


def test_follow_no_ref_and_show_no_catalog(tmp_path: Path) -> None:
    """Rule 6 counts; rule 7 is INFO-only (printed but counted=False)."""
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    # Active show follow with no provider ids and no aired cache → rules 6, 7
    # and — because an empty catalog is exactly the founding incident — 12.
    _insert_follow(acquire, 1, ref="{}", title="Ghost Follow")
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert sorted(a.rule for a in anomalies) == [
        "ACTIVE_A_JOUR_NO_CATALOG",
        "FOLLOW_NO_REF",
        "SHOW_NO_CATALOG",
    ]
    by_rule = {a.rule: a for a in anomalies}
    assert by_rule["FOLLOW_NO_REF"].counted is True
    assert by_rule["SHOW_NO_CATALOG"].counted is False, "SHOW_NO_CATALOG must not count in the exit code"
    assert by_rule["FOLLOW_NO_REF"].followed_id == 1


def test_coherent_state_yields_zero_anomalies(tmp_path: Path) -> None:
    """A coherent seeding fires nothing — the rules must not overfire.

    Grabbed-but-unowned with a client-known hash (case-insensitive), a done
    row, and an abandoned row that never aired are all coherent states.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_wanted(acquire, 40, followed_id=1, season=1, episode=1, status="grabbed", grabbed_hash="ABCD12")
    _insert_wanted(acquire, 41, followed_id=1, season=1, episode=2, status="done")
    _insert_wanted(acquire, 42, followed_id=1, season=1, episode=99, status="abandoned")  # never aired
    acquire.commit()
    _insert_spine(acquire, "ABCD12", status="grabbed")  # hash matching is case-insensitive

    anomalies = collect_anomalies(acquire, indexer, client_hashes={"abcd12"})
    assert anomalies == []


# ---------------------------------------------------------------------------
# The five states (acq-states phase 9)
# ---------------------------------------------------------------------------


def _rules(acquire: sqlite3.Connection, indexer: sqlite3.Connection) -> set[str]:
    """Collect the rule tags fired for one acquire/library pair."""
    return {a.rule for a in collect_anomalies(acquire, indexer, client_hashes=set())}


def _other_ref(tvdb_id: int) -> str:
    """Build a distinct show ref — ``followed_series.media_ref_json`` is UNIQUE."""
    return json.dumps({"tvdb_id": tvdb_id, "tmdb_id": None, "imdb_id": None})


def test_active_up_to_date_no_catalog_fires_on_an_empty_catalog(tmp_path: Path) -> None:
    """Rule 12 fires for the founding incident: an active show, no aired catalog.

    The card derivation, asked about zero knowledge, answers « À jour » — so an
    active show follow whose catalog priming never landed is an ERROR, not the
    INFO note SHOW_NO_CATALOG was in phase 8.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1, title="Furious")
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    fired = {a.rule: a for a in anomalies}
    assert "ACTIVE_A_JOUR_NO_CATALOG" in fired
    assert fired["ACTIVE_A_JOUR_NO_CATALOG"].severity == "error"
    assert fired["ACTIVE_A_JOUR_NO_CATALOG"].counted is True
    assert fired["ACTIVE_A_JOUR_NO_CATALOG"].followed_id == 1
    assert fired["ACTIVE_A_JOUR_NO_CATALOG"].title == "Furious"


def test_active_up_to_date_no_catalog_silent_when_the_catalog_exists(tmp_path: Path) -> None:
    """Rule 12 is silent on a primed catalog, an inactive follow and a film.

    A film has no aired catalog by construction — flagging it would be the
    guard inventing a defect — and a paused follow renders ``disabled``, so
    neither can read « À jour » on missing knowledge.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1, title="Primed")
    _insert_aired(acquire, 1, 1, 1)
    _insert_follow(acquire, 2, ref=_other_ref(556), title="Paused", active=0)
    _insert_follow(acquire, 3, ref=_REF_MOVIE, title="A Film", kind="movie")
    acquire.commit()

    assert "ACTIVE_A_JOUR_NO_CATALOG" not in _rules(acquire, indexer)


def test_inconclusive_with_found_fires_when_a_count_is_stored(tmp_path: Path) -> None:
    """Rule 8 fires when an inconclusive verdict stored a count instead of NULL.

    ``record_search_outcome`` contracts NULL for every non-concluding exit:
    ``found=0`` claims « I looked, there is nothing » about trackers that were
    never reached, and a non-zero count is just as much a claim.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_aired(acquire, 1, 1, 2)
    _insert_wanted(
        acquire,
        10,
        followed_id=1,
        season=1,
        episode=1,
        status="pending",
        last_search_at=NOW,
        last_search_outcome="circuit_open",
        last_search_found=0,
    )
    _insert_wanted(
        acquire,
        11,
        followed_id=1,
        season=1,
        episode=2,
        status="searching",
        last_search_at=NOW,
        last_search_outcome="trackers_unavailable",
        last_search_found=4,
    )
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert {a.rule for a in anomalies} == {"INCONCLUSIVE_WITH_FOUND"}
    assert sorted(i for a in anomalies for i in a.wanted_ids) == [10, 11]
    assert all(a.severity == "error" for a in anomalies)


def test_inconclusive_with_found_silent_on_null_and_on_closed_rows(tmp_path: Path) -> None:
    """Rule 8 is silent on the contracted NULL, and on rows that are history.

    A ``done`` row's verdict answers for nothing — ``select_wanted_facts``
    skips it — so a stale count there is noise, not an incoherence.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_wanted(
        acquire,
        12,
        followed_id=1,
        season=1,
        episode=1,
        status="pending",
        last_search_at=NOW,
        last_search_outcome="circuit_open",
        last_search_found=None,
    )
    _insert_wanted(
        acquire,
        13,
        followed_id=1,
        season=1,
        episode=2,
        status="done",
        last_search_at=NOW,
        last_search_outcome="circuit_open",
        last_search_found=0,
    )
    acquire.commit()

    assert _rules(acquire, indexer) == set()


def test_searched_without_verdict_fires_on_a_forgotten_exit_path(tmp_path: Path) -> None:
    """Rule 9 fires for an OPEN row searched without a recorded verdict.

    The search ran (``last_search_at`` is set) but no exit path wrote its
    outcome, so the item reads « Non vérifié » forever — a lie by omission.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_wanted(
        acquire,
        20,
        followed_id=1,
        season=1,
        episode=1,
        status="searching",
        last_search_at=NOW,
        last_search_outcome=None,
    )
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert {a.rule for a in anomalies} == {"SEARCHED_WITHOUT_VERDICT"}
    assert anomalies[0].wanted_ids == [20]
    assert anomalies[0].severity == "error"


def test_searched_without_verdict_silent_when_recorded_or_never_searched(tmp_path: Path) -> None:
    """Rule 9 is silent with a verdict recorded, and on a never-searched row."""
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_wanted(
        acquire,
        21,
        followed_id=1,
        season=1,
        episode=1,
        status="searching",
        last_search_at=NOW,
        last_search_outcome="no_candidates",
        last_search_found=0,
    )
    _insert_wanted(acquire, 22, followed_id=1, season=1, episode=2, status="pending")
    acquire.commit()

    assert _rules(acquire, indexer) == set()


def test_available_verdict_desync_fires_on_a_disagreeing_verdict(tmp_path: Path) -> None:
    """Rule 10 fires when 'available' is not backed by an 'available' verdict.

    Both shapes are covered: a concluding verdict that says something else, and
    no verdict at all (the status was written, the verdict write was lost).
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_aired(acquire, 1, 1, 2)
    _insert_wanted(
        acquire,
        30,
        followed_id=1,
        season=1,
        episode=1,
        status="available",
        last_search_at=NOW,
        last_search_outcome="no_candidates",
        last_search_found=0,
    )
    _insert_wanted(acquire, 31, followed_id=1, season=1, episode=2, status="available")
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert {a.rule for a in anomalies} == {"AVAILABLE_VERDICT_DESYNC"}
    assert sorted(i for a in anomalies for i in a.wanted_ids) == [30, 31]
    by_id = {a.wanted_ids[0]: a for a in anomalies}
    assert "'no_candidates'" in by_id[30].explanation
    assert "NULL" in by_id[31].explanation, "a missing verdict must be named, not rendered as 'None'"


def test_available_verdict_desync_silent_when_the_verdict_matches(tmp_path: Path) -> None:
    """Rule 10 is silent when status and verdict were written by the same pass."""
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_wanted(
        acquire,
        32,
        followed_id=1,
        season=1,
        episode=1,
        status="available",
        last_search_at=NOW,
        last_search_outcome="available",
        last_search_found=2,
    )
    acquire.commit()

    assert _rules(acquire, indexer) == set()


def test_available_stale_fires_past_the_window_as_a_warning(tmp_path: Path) -> None:
    """Rule 11 fires — as a WARNING — for an 'available' row older than 24h.

    'available' hands the item to the grab pass; a row still waiting a day
    later means that pass is dead or its cron is gone. That needs an operator,
    not a code change, hence ``warning`` — but it still counts in the exit code.
    """
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_wanted(
        acquire,
        40,
        followed_id=1,
        season=1,
        episode=1,
        status="available",
        last_search_at=NOW - 25 * 3600,
        last_search_outcome="available",
        last_search_found=3,
    )
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert {a.rule for a in anomalies} == {"AVAILABLE_STALE"}
    assert anomalies[0].wanted_ids == [40]
    assert anomalies[0].severity == "warning"
    assert anomalies[0].counted is True, "a warning still counts toward the exit code"


def test_available_stale_silent_inside_the_window(tmp_path: Path) -> None:
    """Rule 11 is silent for a row still inside the 24h hand-off window."""
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_aired(acquire, 1, 1, 1)
    _insert_wanted(
        acquire,
        41,
        followed_id=1,
        season=1,
        episode=1,
        status="available",
        last_search_at=NOW - 23 * 3600,
        last_search_outcome="available",
        last_search_found=2,
    )
    acquire.commit()

    assert _rules(acquire, indexer) == set()


def test_follow_missing_poster_fires_as_a_warning(tmp_path: Path) -> None:
    """Rule 13 fires — as a WARNING — for an active follow with no poster_url."""
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1, title="No Poster Show", poster_url=None)
    _insert_aired(acquire, 1, 1, 1)
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert {a.rule for a in anomalies} == {"FOLLOW_MISSING_POSTER"}
    assert anomalies[0].followed_id == 1
    assert anomalies[0].severity == "warning"
    assert anomalies[0].counted is True


def test_follow_missing_poster_silent_with_a_poster_or_when_paused(tmp_path: Path) -> None:
    """Rule 13 is silent with a poster, and on a paused follow (no card to render)."""
    acquire = _acquire_db(tmp_path)
    indexer = _indexer_db(tmp_path)
    _insert_follow(acquire, 1, title="Has Poster", poster_url="https://img.example.com/p.jpg")
    _insert_aired(acquire, 1, 1, 1)
    _insert_follow(acquire, 2, ref=_other_ref(556), title="Paused", active=0, poster_url=None)
    acquire.commit()

    assert "FOLLOW_MISSING_POSTER" not in _rules(acquire, indexer)


def test_the_guard_reads_the_engine_constants_rather_than_copying_them() -> None:
    """The guard must not carry its own copy of the engine's taxonomies.

    A mirrored ``INCONCLUSIVE_OUTCOMES`` (or open-status set) would keep
    passing its tests while silently disagreeing with the engine the day a new
    outcome is added — so identity, not equality, is what is asserted here.
    """
    assert _mod.INCONCLUSIVE_OUTCOMES is INCONCLUSIVE_OUTCOMES
    assert _mod.OPEN_WANTED_STATUSES is OPEN_WANTED_STATUSES


def test_counted_is_derived_from_severity_and_cannot_be_overridden() -> None:
    """``counted`` follows ``severity`` alone, so marker and exit code agree.

    It is an ``init=False`` field: no call site can print a ⚠️ while quietly
    keeping the anomaly out of the exit code.
    """
    common = {"title": "T", "kind": None, "season": None, "episode": None}
    assert Anomaly(rule="R", severity="error", **common).counted is True
    assert Anomaly(rule="R", severity="warning", **common).counted is True
    assert Anomaly(rule="R", severity="info", **common).counted is False
    assert Anomaly(rule="R", **common).severity == "error", "error is the default severity"
    with pytest.raises(TypeError):
        Anomaly(rule="R", severity="info", counted=True, **common)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# The provenance spine (spine-truth) — the two shapes that erased 57 journeys
# ---------------------------------------------------------------------------


def test_spine_row_missing_fires_when_a_grab_left_no_provenance_row(tmp_path: Path) -> None:
    """G2 — a wanted row carrying a hash with NO spine row at all.

    The exact shape produced by the swallowed CHECK rejection: ``upsert_grab`` was called,
    the write was refused, the error was logged at warning level and the acquisition simply
    never existed on the spine. This rule is the executable form of « le rejet d'écriture
    n'est plus muet » — it would have screamed on 2026-08-02 instead of hiding four days.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, kind="season", season=15, status="grabbed", grabbed_hash="DEADBEEF")
    acquire.commit()

    assert "SPINE_ROW_MISSING" in _rules(acquire, indexer)


def test_spine_row_missing_stays_silent_when_the_row_exists(tmp_path: Path) -> None:
    """A grab whose spine row landed is not an anomaly — even matched case-insensitively."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, kind="season", season=15, status="grabbed", grabbed_hash="DEADBEEF")
    acquire.commit()
    _insert_spine(acquire, "DEADBEEF", status="grabbed", kind="season")

    assert "SPINE_ROW_MISSING" not in _rules(acquire, indexer)


def test_spine_row_missing_ignores_rows_that_were_never_grabbed(tmp_path: Path) -> None:
    """No hash, no spine row expected — the rule must not fire on the whole queue."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=1, episode=1, status="pending")
    _insert_wanted(acquire, 2, followed_id=1, season=1, episode=2, status="abandoned")
    acquire.commit()

    assert "SPINE_ROW_MISSING" not in _rules(acquire, indexer)


def test_spine_dispatch_missing_fires_on_a_journey_that_never_completed(tmp_path: Path) -> None:
    """G3 — a closed acquisition whose spine row never reached ``dispatched``.

    The exact shape of cause B: the media landed in the library (the wanted row closed
    ``done``) but the dispatch could not correlate the folder back to the grab, so the
    journey stopped mid-spine. « Dispatchés » under-counts by exactly these rows.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=1, episode=1, status="done", grabbed_hash="AABB11")
    acquire.commit()
    _insert_spine(acquire, "AABB11", status="scraped")

    assert "SPINE_DISPATCH_MISSING" in _rules(acquire, indexer)


def test_spine_dispatch_missing_stays_silent_on_a_completed_journey(tmp_path: Path) -> None:
    """A dispatched spine row is the healthy case, and a reconciled one too."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=1, episode=1, status="done", grabbed_hash="AABB11")
    _insert_wanted(acquire, 2, followed_id=1, season=1, episode=2, status="done", grabbed_hash="CCDD22")
    acquire.commit()
    _insert_spine(acquire, "AABB11", status="dispatched")
    _insert_spine(acquire, "CCDD22", status="reconciled")

    assert "SPINE_DISPATCH_MISSING" not in _rules(acquire, indexer)


def test_spine_dispatch_missing_ignores_a_still_open_acquisition(tmp_path: Path) -> None:
    """An in-flight grab has not landed yet — an un-dispatched spine row is correct there."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=1, episode=1, status="grabbed", grabbed_hash="AABB11")
    acquire.commit()
    _insert_spine(acquire, "AABB11", status="ingested")

    assert "SPINE_DISPATCH_MISSING" not in _rules(acquire, indexer)


def test_the_two_spine_rules_never_report_the_same_row(tmp_path: Path) -> None:
    """One rule = one failure mode: a missing row is G2's, never also G3's.

    Without the split, a wiped registry would be reported twice per acquisition and the
    exit code would say twice the truth.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=1, episode=1, status="done", grabbed_hash="AABB11")
    acquire.commit()

    fired = _rules(acquire, indexer)
    assert "SPINE_ROW_MISSING" in fired
    assert "SPINE_DISPATCH_MISSING" not in fired


# ---------------------------------------------------------------------------
# §14.3 — un garde-fou couvre les DEUX workflows en entier, saisons comprises
# ---------------------------------------------------------------------------


def test_grabbed_owned_sees_a_season_row_whose_season_is_owned(tmp_path: Path) -> None:
    """La règle voit une ligne `season` possédée — pas seulement les épisodes.

    Forme réelle du 2026-08-05 : les packs American Dad S15/S17 avaient atterri en
    médiathèque et la file affichait encore « récupéré » huit heures plus tard. Aucune
    règle n'a crié, parce que la possession d'une ligne `season` n'avait pas de réponse :
    la voie épisode exige un numéro d'épisode, qu'une ligne saison n'a pas. §14.3 : une
    règle qui ne voit qu'un genre de ligne laisse passer ce qu'elle prétend garder.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    for episode in (1, 2):
        _insert_aired(acquire, 1, 15, episode)
    _insert_wanted(acquire, 1, followed_id=1, kind="season", season=15, status="grabbed", grabbed_hash="5EA50N")
    acquire.commit()
    _insert_spine(acquire, "5EA50N", status="dispatched", kind="season")
    for episode in (1, 2):
        _own_episode(indexer, tvdb_id=555, season=15, episode=episode)

    assert "GRABBED_OWNED" in _rules(acquire, indexer)


def test_a_season_only_partly_owned_is_not_reported_as_owned(tmp_path: Path) -> None:
    """Tout-ou-rien : un seul épisode diffusé manquant, et la saison n'est PAS possédée.

    Sans ce contre-cas la règle fermerait des saisons incomplètes — exactement le
    mensonge inverse.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    for episode in (1, 2, 3):
        _insert_aired(acquire, 1, 15, episode)
    _insert_wanted(acquire, 1, followed_id=1, kind="season", season=15, status="grabbed", grabbed_hash="5EA50N")
    acquire.commit()
    _insert_spine(acquire, "5EA50N", status="grabbed", kind="season")
    for episode in (1, 2):  # le 3 manque
        _own_episode(indexer, tvdb_id=555, season=15, episode=episode)

    assert "GRABBED_OWNED" not in _rules(acquire, indexer)


def test_a_season_with_an_empty_catalog_is_never_declared_owned(tmp_path: Path) -> None:
    """Zéro connaissance n'est pas une possession : un catalogue vide ne ferme rien."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, kind="season", season=15, status="grabbed", grabbed_hash="5EA50N")
    acquire.commit()
    _insert_spine(acquire, "5EA50N", status="grabbed", kind="season")

    assert "GRABBED_OWNED" not in _rules(acquire, indexer)


# ---------------------------------------------------------------------------
# QUEUE_ABSORBED_DANGLING — the absorption pointer must be followable (#411)
# ---------------------------------------------------------------------------


def test_absorbed_dangling_fires_when_the_pointer_is_null(tmp_path: Path) -> None:
    """``absorbed`` with no ``absorbed_by``: nothing to follow, so the queue claims blind.

    The queue resolves an absorbed row onto the season wanted carrying its acquisition.
    With a NULL pointer that resolution cannot happen and the row keeps reading
    « En cours d'acquisition » — an assertion with nothing behind it.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=15, episode=21, status="absorbed", absorbed_by=None)
    acquire.commit()

    assert "QUEUE_ABSORBED_DANGLING" in _rules(acquire, indexer)


def test_absorbed_dangling_fires_when_the_pointer_names_a_missing_row(tmp_path: Path) -> None:
    """``absorbed_by`` naming a row that does not exist — the column carries no FK."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=15, episode=21, status="absorbed", absorbed_by=9999)
    acquire.commit()

    assert "QUEUE_ABSORBED_DANGLING" in _rules(acquire, indexer)


def test_absorbed_dangling_silent_when_the_season_row_exists(tmp_path: Path) -> None:
    """A resolvable pointer is the NORMAL case — the rule must stay quiet.

    This is the shape of the 31 live rows on 2026-08-05: every one of them points at a
    season row that exists and is ``done``. A rule that shouted here would take the guard
    from mute to deafening, which is just as unusable.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 88, followed_id=1, kind="season", season=15, status="done")
    _insert_wanted(acquire, 5, followed_id=1, season=15, episode=21, status="absorbed", absorbed_by=88)
    _insert_wanted(acquire, 6, followed_id=1, season=15, episode=22, status="absorbed", absorbed_by=88)
    acquire.commit()

    assert "QUEUE_ABSORBED_DANGLING" not in _rules(acquire, indexer)


def test_absorbed_dangling_is_a_warning_not_an_error(tmp_path: Path) -> None:
    """Severity is deliberate: the carrying season MIGHT be in flight.

    An unsupported claim is not a proven lie, and the exit code must not treat it as one.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _insert_follow(acquire, 1)
    _insert_wanted(acquire, 1, followed_id=1, season=15, episode=21, status="absorbed", absorbed_by=None)
    acquire.commit()

    fired = [a for a in collect_anomalies(acquire, indexer, client_hashes=set()) if a.rule == "QUEUE_ABSORBED_DANGLING"]
    assert len(fired) == 1
    assert fired[0].severity == "warning"
