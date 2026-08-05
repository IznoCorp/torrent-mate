"""Tests for scripts/backfill-provenance-spine.py (§13 — l'état existant est réparé).

The correction of a bug is unfinished while the data it falsified is still wrong
(product-intent §13: « le code corrigé, l'état existant réparé, le contrôle exécutable à
zéro anomalie. Les trois, ou rien. »). 57 acquisitions lost their journey row; this script
rebuilds them from the databases that still hold the facts — never from the logs, which
rotate and were already incomplete.

What it must prove:

- it reconstructs the fields that ARE recoverable (identity from ``wanted``, the grab
  instant from ``seed_obligation``, the landing from ``library.db``);
- it leaves NULL every field the deleted staging folders took with them, rather than
  inventing a plausible path — a reconstructed row says « grabbé ici, atterri là, milieu
  inconnu »;
- it is dry-run by default, idempotent, and never touches a row that already exists;
- and, the point of the whole exercise, it takes the coherence guard from firing to silent.
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

_REPO_ROOT = Path(__file__).resolve().parents[2]
ACQUIRE_MIGRATIONS = _REPO_ROOT / "personalscraper" / "acquire" / "migrations"
INDEXER_MIGRATIONS = _REPO_ROOT / "personalscraper" / "indexer" / "migrations"


def _load(name: str, filename: str) -> object:
    """Import a hyphenated script from ``scripts/`` under *name*."""
    spec = _util.spec_from_file_location(name, _REPO_ROOT / "scripts" / filename)
    assert spec is not None and spec.loader is not None
    module = _util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_backfill_mod = _load("backfill_provenance_spine", "backfill-provenance-spine.py")
_coherence_mod = _load("check_acquisition_coherence_for_backfill", "check-acquisition-coherence.py")

backfill_spine = _backfill_mod.backfill_spine  # type: ignore[attr-defined]
collect_anomalies = _coherence_mod.collect_anomalies  # type: ignore[attr-defined]

NOW = int(time.time())
_REF_SHOW = json.dumps({"tvdb_id": 555, "tmdb_id": None, "imdb_id": None})
_REF_MOVIE = json.dumps({"tvdb_id": None, "tmdb_id": 777, "imdb_id": None})


# ---------------------------------------------------------------------------
# Fixtures — REAL migration chains, temp files
# ---------------------------------------------------------------------------


def _acquire_db(tmp_path: Path) -> sqlite3.Connection:
    """Temp ``acquire.db`` with the full real migration chain applied."""
    conn = sqlite3.connect(str(tmp_path / "acquire.db"))
    conn.row_factory = sqlite3.Row
    apply_acquire_migrations(conn, ACQUIRE_MIGRATIONS)
    return conn


def _indexer_db(tmp_path: Path) -> sqlite3.Connection:
    """Temp ``library.db`` with the full real indexer migration chain applied."""
    conn = sqlite3.connect(str(tmp_path / "library.db"))
    conn.row_factory = sqlite3.Row
    apply_indexer_migrations(conn, INDEXER_MIGRATIONS)
    conn.commit()
    return conn


def _follow(conn: sqlite3.Connection, followed_id: int, *, ref: str = _REF_SHOW, kind: str = "show") -> None:
    """Insert one followed_series row."""
    conn.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, kind, added_at, poster_url) "
        "VALUES (?,?,?,1,?,?,'https://x/p.jpg')",
        (followed_id, ref, f"Show {followed_id}", kind, NOW),
    )
    conn.commit()


def _wanted(
    conn: sqlite3.Connection,
    wanted_id: int,
    *,
    followed_id: int,
    ref: str = _REF_SHOW,
    kind: str = "episode",
    season: int | None = None,
    episode: int | None = None,
    status: str = "done",
    grabbed_hash: str | None = None,
) -> None:
    """Insert one wanted row."""
    conn.execute(
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode, status, enqueued_at, "
        "grabbed_hash) VALUES (?,?,?,?,?,?,?,?,?)",
        (wanted_id, followed_id, ref, kind, season, episode, status, NOW, grabbed_hash),
    )
    conn.commit()


def _obligation(conn: sqlite3.Connection, info_hash: str, *, added_at: int, dispatched_path: str | None = None) -> None:
    """Insert one seed_obligation row (written at grab time since 2026-07-15)."""
    conn.execute(
        "INSERT INTO seed_obligation (info_hash, source_tracker, dispatched_path, min_seed_time_s, min_ratio, "
        "added_at) VALUES (?,'t1',?,0,0.0,?)",
        (info_hash, dispatched_path, added_at),
    )
    conn.commit()


def _external_ids_json(*, tvdb_id: int | None = None, tmdb_id: int | None = None) -> str:
    """Build the hierarchical external_ids_json payload (indexer migration 005 shape)."""
    payload: dict[str, dict[str, str | None]] = {}
    if tvdb_id is not None:
        payload["tvdb"] = {"series_id": str(tvdb_id), "episode_id": None}
    if tmdb_id is not None:
        payload["tmdb"] = {"series_id": str(tmdb_id), "episode_id": None}
    return json.dumps(payload)


def _own_episode(
    conn: sqlite3.Connection,
    *,
    tvdb_id: int,
    season: int,
    episode: int,
    dispatch_path: str = "/Volumes/D1/series/Show (2020)",
    verified_at: int | None = None,
) -> None:
    """Make the library own one live episode file, with the dispatcher's own dispatch_path."""
    conn.execute("INSERT OR IGNORE INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1','D1','/Volumes/D1',1)")
    path_id = conn.execute(
        "INSERT INTO path(disk_id, rel_path) VALUES (1, ?)", (f"series/Show (2020)/Saison {season:02d}",)
    ).lastrowid
    found = conn.execute(
        "SELECT id FROM media_item WHERE kind='show' AND json_extract(external_ids_json,'$.tvdb.series_id')=?",
        (str(tvdb_id),),
    ).fetchone()
    if found is None:
        item_id = conn.execute(
            "INSERT INTO media_item(kind, title, title_sort, year, category_id, external_ids_json,"
            " date_created, date_modified) VALUES ('show','Show','Show',2020,'tv_shows',?,?,?)",
            (_external_ids_json(tvdb_id=tvdb_id), NOW, NOW),
        ).lastrowid
        conn.execute(
            "INSERT INTO item_attribute(item_id, key, value) VALUES (?,'dispatch_path',?)", (item_id, dispatch_path)
        )
    else:
        item_id = found["id"]
    season_row = conn.execute("SELECT id FROM season WHERE item_id=? AND number=?", (item_id, season)).fetchone()
    season_id = (
        season_row["id"]
        if season_row
        else conn.execute("INSERT INTO season(item_id, number) VALUES (?,?)", (item_id, season)).lastrowid
    )
    episode_id = conn.execute("INSERT INTO episode(season_id, number) VALUES (?,?)", (season_id, episode)).lastrowid
    release_id = conn.execute("INSERT INTO media_release(item_id, episode_id) VALUES (NULL,?)", (episode_id,)).lastrowid
    conn.execute(
        "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at, deleted_at) VALUES (?,?,?,1000,?,?,1,?,NULL)",
        (release_id, path_id, f"S{season}E{episode}.mkv", NOW * 10**9, f"h{season}{episode}", verified_at or NOW),
    )
    conn.commit()


def _own_movie(
    conn: sqlite3.Connection,
    *,
    tmdb_id: int,
    dispatch_path: str = "/Volumes/D1/films/Marjorie Prime (2017)",
    verified_at: int | None = None,
) -> None:
    """Make the library own one live movie file, with the dispatcher's own dispatch_path."""
    conn.execute("INSERT OR IGNORE INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1','D1','/Volumes/D1',1)")
    path_id = conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1, 'films/Marjorie Prime (2017)')").lastrowid
    item_id = conn.execute(
        "INSERT INTO media_item(kind, title, title_sort, year, category_id, external_ids_json,"
        " date_created, date_modified) VALUES ('movie','M','M',2017,'movies',?,?,?)",
        (_external_ids_json(tmdb_id=tmdb_id), NOW, NOW),
    ).lastrowid
    conn.execute(
        "INSERT INTO item_attribute(item_id, key, value) VALUES (?,'dispatch_path',?)", (item_id, dispatch_path)
    )
    release_id = conn.execute("INSERT INTO media_release(item_id, episode_id) VALUES (?,NULL)", (item_id,)).lastrowid
    conn.execute(
        "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at, deleted_at) VALUES (?,?,'m.mkv',1000,?,'mh',1,?,NULL)",
        (release_id, path_id, NOW * 10**9, verified_at or NOW),
    )
    conn.commit()


def _spine_rows(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    """Snapshot ``staging_provenance`` keyed by info_hash."""
    return {r["info_hash"]: r for r in conn.execute("SELECT * FROM staging_provenance")}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dry_run_reports_the_rows_and_writes_nothing(tmp_path: Path) -> None:
    """The default is a preview: it says what it would rebuild and touches nothing."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _obligation(acquire, "aabb11", added_at=NOW - 500)
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    planned = backfill_spine(acquire, indexer, apply=False)

    assert [r.info_hash for r in planned] == ["aabb11"]
    assert _spine_rows(acquire) == {}


def test_it_reconstructs_identity_grab_instant_and_landing(tmp_path: Path) -> None:
    """Each recoverable field comes from the database that actually holds it."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=3, episode=7, grabbed_hash="AABB11")
    _obligation(acquire, "aabb11", added_at=NOW - 900)
    _own_episode(
        indexer,
        tvdb_id=555,
        season=3,
        episode=7,
        dispatch_path="/Volumes/D1/series/Widow's Bay (2026)",
        verified_at=NOW - 100,
    )

    backfill_spine(acquire, indexer, apply=True)

    row = _spine_rows(acquire)["aabb11"]
    assert row["kind"] == "episode"
    assert row["followed_id"] == 1
    assert json.loads(row["media_ref_json"])["tvdb_id"] == 555
    assert row["grabbed_at"] == NOW - 900, "the grab instant comes from seed_obligation.added_at"
    assert row["dispatch_path"] == "/Volumes/D1/series/Widow's Bay (2026)"
    assert row["dispatched_at"] == NOW - 100, "the landing instant comes from media_file.last_verified_at"
    assert row["status"] == "dispatched"


def test_it_reconstructs_a_movie_and_a_season_pack(tmp_path: Path) -> None:
    """Both other kinds land too — the season kind is the one migration 015 unblocked."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _follow(acquire, 2, ref=_REF_MOVIE, kind="movie")
    _wanted(acquire, 1, followed_id=1, kind="season", season=4, grabbed_hash="5EA50N")
    _wanted(acquire, 2, followed_id=2, ref=_REF_MOVIE, kind="movie", grabbed_hash="M0V1E0")
    _own_episode(indexer, tvdb_id=555, season=4, episode=1, dispatch_path="/Volumes/D1/series/S (2020)")
    _own_movie(indexer, tmdb_id=777)

    backfill_spine(acquire, indexer, apply=True)

    rows = _spine_rows(acquire)
    assert rows["5ea50n"]["kind"] == "season"
    assert rows["5ea50n"]["dispatch_path"] == "/Volumes/D1/series/S (2020)"
    assert rows["m0v1e0"]["kind"] == "movie"
    assert rows["m0v1e0"]["dispatch_path"] == "/Volumes/D1/films/Marjorie Prime (2017)"


def test_unrecoverable_fields_stay_null_rather_than_invented(tmp_path: Path) -> None:
    """The staging folders are gone; a reconstructed row must not pretend otherwise.

    §méthode: « ne rien inventer ». A NULL ``ingest_path`` / ``current_path`` /
    ``scraped_at`` is the honest record of a middle nobody can reconstruct — and it is
    also what keeps ``prune_stale`` (which only considers rows with a ``current_path``)
    from treating these audit rows as orphans.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    backfill_spine(acquire, indexer, apply=True)

    row = _spine_rows(acquire)["aabb11"]
    for column in (
        "ingest_path",
        "current_path",
        "scraped_at",
        "scraped_ref_json",
        "resolution_state",
        "grab_run_uid",
        "ingest_run_uid",
        "scrape_run_uid",
        "dispatch_run_uid",
    ):
        assert row[column] is None, f"{column} is not reconstructable and must stay NULL"
    assert row["grabbed_at"] is None, "no seed_obligation → no provable grab instant"


def test_a_landing_the_library_cannot_confirm_stops_at_grabbed(tmp_path: Path) -> None:
    """Status records the furthest stage that can be PROVEN, never the one hoped for."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")

    backfill_spine(acquire, indexer, apply=True)

    row = _spine_rows(acquire)["aabb11"]
    assert row["status"] == "grabbed"
    assert row["dispatch_path"] is None
    assert row["dispatched_at"] is None


def test_an_open_acquisition_is_rebuilt_as_grabbed_even_when_owned(tmp_path: Path) -> None:
    """A row still in flight has not landed: its journey stops where the queue says it does."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, status="grabbed", grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    backfill_spine(acquire, indexer, apply=True)
    assert _spine_rows(acquire)["aabb11"]["status"] == "grabbed"


def test_it_never_touches_a_row_that_already_exists(tmp_path: Path) -> None:
    """A live journey is authoritative — the backfill only fills holes."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    acquire.execute(
        "INSERT INTO staging_provenance (info_hash, kind, current_path, status, grabbed_at) "
        "VALUES ('aabb11','episode','/stage/live','scraped',42)"
    )
    acquire.commit()
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    planned = backfill_spine(acquire, indexer, apply=True)

    assert planned == []
    row = _spine_rows(acquire)["aabb11"]
    assert (row["status"], row["current_path"], row["grabbed_at"]) == ("scraped", "/stage/live", 42)


def test_rows_without_a_grabbed_hash_are_not_candidates(tmp_path: Path) -> None:
    """Only a grab owes a journey; a pending or abandoned row owes nothing."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, status="pending")
    _wanted(acquire, 2, followed_id=1, season=1, episode=2, status="abandoned")

    assert backfill_spine(acquire, indexer, apply=True) == []
    assert _spine_rows(acquire) == {}


def test_running_it_twice_changes_nothing(tmp_path: Path) -> None:
    """Idempotent: the second pass finds no hole to fill."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    first = backfill_spine(acquire, indexer, apply=True)
    before = dict(_spine_rows(acquire)["aabb11"])
    second = backfill_spine(acquire, indexer, apply=True)

    assert len(first) == 1
    assert second == []
    assert dict(_spine_rows(acquire)["aabb11"]) == before


def _run_row(
    conn: sqlite3.Connection,
    run_uid: str,
    *,
    ingest_reasons: list[str],
    ingest_ended: float,
    scrape_ended: float | None = None,
    dispatch_ended: float | None = None,
) -> None:
    """Insert one ``pipeline_run`` whose steps_json names the releases it ingested.

    That ``reasons`` list is what ties a torrent name back to the run that carried it —
    and therefore to the instants of that run's scrape and dispatch steps.
    """
    steps: list[dict[str, object]] = [
        {"name": "ingest", "ended_at": ingest_ended, "reasons": ingest_reasons},
    ]
    if scrape_ended is not None:
        steps.append({"name": "scrape", "ended_at": scrape_ended, "reasons": []})
    if dispatch_ended is not None:
        steps.append({"name": "dispatch", "ended_at": dispatch_ended, "reasons": []})
    conn.execute(
        "INSERT INTO pipeline_run (run_uid, trigger, dry_run, started_at, ended_at, outcome, steps_json) "
        "VALUES (?,?,0,?,?, 'success', ?)",
        (run_uid, "completion", ingest_ended - 100, dispatch_ended or ingest_ended, json.dumps(steps)),
    )
    conn.commit()


def test_the_ingest_instant_is_recovered_from_the_ingest_tracker(tmp_path: Path) -> None:
    """« inconnue » n'est légitime que pour ce qui l'est vraiment.

    ``ingested_torrents.json`` porte la date d'ingestion EXACTE, par hash. La déclarer
    perdue sans l'avoir regardée, puis afficher « Ingéré · inconnue », c'est renoncer à
    une donnée qui existe — l'inverse de §13.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)
    tracker = {"AABB11": {"name": "Show.S01E01-GRP", "action": "copied", "date": "2026-08-05T03:42:47.238007"}}

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000, ingest_tracker=tracker)

    row = _spine_rows(acquire)["aabb11"]
    assert row["ingested_at"] == int(
        __import__("datetime").datetime.fromisoformat("2026-08-05T03:42:47.238007").timestamp()
    )


def test_the_scrape_instant_and_run_links_come_from_the_run_journal(tmp_path: Path) -> None:
    """Le journal des runs rattache une release à SON run — donc au scraping de ce run.

    L'étape d'ingestion d'un run nomme les releases qu'elle a copiées ; le même run a
    scrapé puis dispatché ces mêmes items. C'est une jointure, pas une supposition.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)
    _run_row(
        indexer,
        "f7162f2c" + "0" * 24,
        ingest_reasons=["Show.S01E01-GRP → copied"],
        ingest_ended=1_785_886_000.0,
        scrape_ended=1_785_886_396.5,
        dispatch_ended=1_785_886_900.0,
    )
    tracker = {"AABB11": {"name": "Show.S01E01-GRP", "action": "copied", "date": "2026-08-05T03:42:47.238007"}}

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000, ingest_tracker=tracker)

    row = _spine_rows(acquire)["aabb11"]
    assert row["scraped_at"] == 1_785_886_396
    assert row["ingest_run_uid"] == "f7162f2c" + "0" * 24
    assert row["scrape_run_uid"] == "f7162f2c" + "0" * 24


def test_what_is_genuinely_unrecoverable_stays_null(tmp_path: Path) -> None:
    """Aucune source, aucun instant : la ligne reste honnêtement muette.

    Le contre-cas qui empêche la récupération de dégénérer en invention.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000, ingest_tracker={})

    row = _spine_rows(acquire)["aabb11"]
    assert row["ingested_at"] is None
    assert row["scraped_at"] is None
    assert row["reconstructed_at"] == 1_785_900_000


def test_a_tracker_date_that_cannot_be_parsed_is_ignored_not_guessed(tmp_path: Path) -> None:
    """Une date illisible ne devient pas « maintenant » : elle reste inconnue."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    backfill_spine(
        acquire,
        indexer,
        apply=True,
        now=1_785_900_000,
        ingest_tracker={"AABB11": {"name": "X", "date": "pas une date"}},
    )
    assert _spine_rows(acquire)["aabb11"]["ingested_at"] is None


def test_every_rebuilt_row_is_marked_as_rebuilt(tmp_path: Path) -> None:
    """§14.3 — une ligne reconstruite le DIT, pour que l'interface distingue les NULL.

    Sans ce marqueur, les instants d'ingestion et de scraping laissés NULL (honnêtement,
    puisqu'ils sont perdus) se lisent « étape pas faite » : un média « Rangé » posé sur des
    étapes éteintes, un chemin qui ne peut pas exister. Le marqueur est ce qui permet de
    dire « inconnue ».
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000)

    row = _spine_rows(acquire)["aabb11"]
    assert row["reconstructed_at"] == 1_785_900_000
    assert row["ingested_at"] is None and row["scraped_at"] is None


def test_the_backfill_takes_the_coherence_guard_from_firing_to_silent(tmp_path: Path) -> None:
    """§13 closed: code corrigé, état réparé, contrôle exécutable à zéro anomalie.

    This is the whole point of the script, asserted end to end against the REAL guard
    rather than against the script's own bookkeeping.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=1, episode=1, grabbed_hash="AABB11")
    _wanted(acquire, 2, followed_id=1, kind="season", season=2, grabbed_hash="5EA50N")
    _own_episode(indexer, tvdb_id=555, season=1, episode=1)
    _own_episode(indexer, tvdb_id=555, season=2, episode=1)
    for season, episode in ((1, 1), (2, 1)):
        acquire.execute(
            "INSERT INTO aired_episode (followed_id, season, episode, title, air_date, updated_at) "
            "VALUES (1,?,?,'t','2026-01-01',?)",
            (season, episode, NOW),
        )
    acquire.commit()

    before = {a.rule for a in collect_anomalies(acquire, indexer, client_hashes=None)}
    assert "SPINE_ROW_MISSING" in before

    backfill_spine(acquire, indexer, apply=True)

    after = {a.rule for a in collect_anomalies(acquire, indexer, client_hashes=None)}
    assert "SPINE_ROW_MISSING" not in after
    assert "SPINE_DISPATCH_MISSING" not in after


def test_the_grab_instant_falls_back_to_the_search_that_produced_it(tmp_path: Path) -> None:
    """Sans obligation de seed, la recherche qui a grabbé date le grab.

    23 parcours sur 59 affichaient « Récupéré · inconnue » — l'étape la plus absurde à
    laisser vide, puisqu'un parcours commence par là. L'obligation de seed n'existe que
    depuis 2026-07-15 ; ``wanted.last_search_at`` couvre les autres, à 25 s près (écart
    maximal mesuré sur les 35 lignes où les deux sources coexistent).
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    acquire.execute(
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode, status, enqueued_at, "
        "grabbed_hash, last_search_at) VALUES (1,1,?,'episode',3,7,'done',?,'AABB11',?)",
        (_REF_SHOW, NOW, 1_785_800_000),
    )
    acquire.commit()
    _own_episode(indexer, tvdb_id=555, season=3, episode=7)

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000)

    assert _spine_rows(acquire)["aabb11"]["grabbed_at"] == 1_785_800_000


def test_the_seed_obligation_still_wins_when_both_exist(tmp_path: Path) -> None:
    """La source posée AU grab prime sur celle qui l'approche — jamais l'inverse."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    acquire.execute(
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode, status, enqueued_at, "
        "grabbed_hash, last_search_at) VALUES (1,1,?,'episode',3,7,'done',?,'AABB11',?)",
        (_REF_SHOW, NOW, 1_785_800_000),
    )
    acquire.commit()
    _obligation(acquire, "aabb11", added_at=1_785_800_025)
    _own_episode(indexer, tvdb_id=555, season=3, episode=7)

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000)

    assert _spine_rows(acquire)["aabb11"]["grabbed_at"] == 1_785_800_025


def test_each_rebuilt_journey_carries_its_episode(tmp_path: Path) -> None:
    """Différenciable : deux acquisitions d'une même série ne sont pas la même carte.

    Quatre parcours « Silo » partageaient exactement la même identité affichable (l'id de
    série), donc quatre cartes identiques — que l'opérateur a lues comme des doublons.
    """
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 1)
    _wanted(acquire, 1, followed_id=1, season=3, episode=5, grabbed_hash="AABB11")
    _wanted(acquire, 2, followed_id=1, season=3, episode=6, grabbed_hash="CCDD22")
    _own_episode(indexer, tvdb_id=555, season=3, episode=5)

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000)

    rows = _spine_rows(acquire)
    assert (rows["aabb11"]["season"], rows["aabb11"]["episode"]) == (3, 5)
    assert (rows["ccdd22"]["season"], rows["ccdd22"]["episode"]) == (3, 6)


def test_a_movie_carries_no_episode_identity(tmp_path: Path) -> None:
    """Le contre-cas : un film n'a pas d'épisode, et on n'en invente pas."""
    acquire, indexer = _acquire_db(tmp_path), _indexer_db(tmp_path)
    _follow(acquire, 2, ref=_REF_MOVIE, kind="movie")
    _wanted(acquire, 1, followed_id=2, ref=_REF_MOVIE, kind="movie", grabbed_hash="M0V1E0")
    _own_movie(indexer, tmdb_id=777)

    backfill_spine(acquire, indexer, apply=True, now=1_785_900_000)

    row = _spine_rows(acquire)["m0v1e0"]
    assert row["season"] is None and row["episode"] is None
