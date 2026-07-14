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
"""

from __future__ import annotations

import importlib.util as _util
import json
import sqlite3
import sys
import time
from pathlib import Path

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
) -> None:
    """Insert one followed_series row."""
    conn.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, kind, added_at) VALUES (?,?,?,?,?,?)",
        (followed_id, ref, title, active, kind, NOW),
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
) -> None:
    """Insert one wanted row."""
    conn.execute(
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode, status, enqueued_at,"
        " grabbed_hash) VALUES (?,?,?,?,?,?,?,?,?)",
        (wanted_id, followed_id, ref, kind, season, episode, status, NOW, grabbed_hash),
    )


def _insert_aired(conn: sqlite3.Connection, followed_id: int, season: int, episode: int) -> None:
    """Insert one aired_episode cache row."""
    conn.execute(
        "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) VALUES (?,?,?,?,?,?)",
        (followed_id, season, episode, f"Ep {season}x{episode}", "2026-01-01", NOW),
    )


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
    # Active show follow with no provider ids and no aired cache → both rules.
    _insert_follow(acquire, 1, ref="{}", title="Ghost Follow")
    acquire.commit()

    anomalies = collect_anomalies(acquire, indexer, client_hashes=set())
    assert sorted(a.rule for a in anomalies) == ["FOLLOW_NO_REF", "SHOW_NO_CATALOG"]
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

    anomalies = collect_anomalies(acquire, indexer, client_hashes={"abcd12"})
    assert anomalies == []
