"""GET /api/acquisition/to-handle — les bloqués portés par une acquisition (§14.3).

§14.3 : un parcours n'a pas de trou. Un item pris puis ingéré qui cale à
l'identification est au milieu de SON parcours ; il doit rester visible depuis
l'acquisition. Un dépôt manuel, lui, est compté mais jamais listé ici —
il appartient à Contrôle.

Les deux tests de base :
- test_to_handle_route_serves_items_and_orphan_count — un item dont
  l'acquisition est la nôtre apparaît ; un orphelin (même staging_path sans
  provenance) est compté mais pas listé.
- test_to_handle_route_is_fail_soft_without_a_database — route qui survit
  sans ``library.db`` (fail-soft, jamais 500).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.config import Settings
from personalscraper.core.identity import MediaRef
from personalscraper.web.auth.tokens import create_session_token
from personalscraper.web.routes.acquisition_overview import router as overview_router
from tests.unit.web.routes.test_journeys import build_acquire_store_config
from tests.web._web_harness import guarded_client

_COOKIE = {"tm_session": create_session_token("izno", "testsecret", 24)}

GRABBED_AT = 1_785_000_000
INGESTED_AT = 1_785_000_100
STAGING_PATH = "/staging/097-TEMP/Some.Movie.2025.FRENCH.1080p.WEB-DL.H264"
HASH = "abcd1234efab5678cd901234efab5678cd9012ef"


def _seed_library_db(db_path: Path, staging_path: str) -> None:
    """Create a scrape_decision row for a pending blocked item."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE scrape_decision ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  staging_path TEXT UNIQUE NOT NULL,"
            "  media_kind TEXT NOT NULL,"
            "  extracted_title TEXT NOT NULL,"
            "  extracted_year INTEGER,"
            '  "trigger" TEXT NOT NULL,'
            "  candidates_json TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  resolution_json TEXT,"
            "  run_uid TEXT,"
            "  created_at REAL NOT NULL,"
            "  updated_at REAL NOT NULL,"
            "  resolved_at REAL"
            ")"
        )
        conn.execute(
            "INSERT INTO scrape_decision(staging_path, media_kind, extracted_title,"
            '  extracted_year, "trigger", candidates_json, status, created_at, updated_at)'
            "  VALUES (?, 'movie', 'Some Movie', 2025, 'ambiguous',"
            '  \'["candidate1","candidate2","candidate3"]\','
            "  'pending', 1785000000, 1785000000)",
            (staging_path,),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_acquire_store(db_path: Path, staging_path: str, info_hash: str) -> None:
    """Seed a provenance row carrying the blocked item."""
    store = build_acquire_store_config(db_path)
    try:
        fid = store.follow.add(
            FollowedSeries(
                media_ref=MediaRef(tmdb_id=12345),
                title="Some Movie",
                added_at=GRABBED_AT,
                kind="movie",
            )
        )
        store.provenance.upsert_grab(
            info_hash,
            followed_id=fid,
            media_ref=MediaRef(tmdb_id=12345),
            kind="movie",
            grabbed_at=GRABBED_AT,
        )
        store.provenance.set_ingest(
            info_hash,
            ingest_path=staging_path,
            ingested_at=INGESTED_AT,
        )
    finally:
        store.close()


def _client(test_config: Any, tmp_path: Path) -> Any:
    db_path = tmp_path / "acquire.db"
    library_path = tmp_path / "library.db"
    test_config.acquire.db_path = db_path
    test_config.indexer.db_path = library_path
    _seed_library_db(library_path, STAGING_PATH)
    _seed_acquire_store(db_path, STAGING_PATH, HASH)
    return guarded_client(
        config=test_config,
        settings=Settings(web_jwt_secret="testsecret", _env_file=None),  # type: ignore[call-arg]
        routers=[overview_router],
        with_auth=False,
        https=False,
    )


def test_to_handle_route_serves_items_and_orphan_count(test_config: Any, tmp_path: Path) -> None:
    """Un item dont l'acquisition est la nôtre apparaît ; l'orphelin est compté."""
    client = _client(test_config, tmp_path)
    # Add a SECOND scrape_decision WITHOUT provenance → orphan_count = 1
    conn = sqlite3.connect(str(tmp_path / "library.db"))
    try:
        conn.execute(
            "INSERT INTO scrape_decision(staging_path, media_kind, extracted_title,"
            '  extracted_year, "trigger", candidates_json, status, created_at, updated_at)'
            "  VALUES ('/staging/097-TEMP/Orphan.Movie.2025', 'movie', 'Orphan Movie',"
            "  2025, 'ambiguous', '[]', 'pending', 1785000000, 1785000000)"
        )
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/api/acquisition/to-handle", cookies=_COOKIE)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["orphan_count"] == 1
    assert [i["decision_id"] for i in body["items"]] == [1]
    assert body["items"][0]["reason"] == "titre ambigu — 3 candidats proposés"
    assert body["items"][0]["stage"] == "ingere"


def test_to_handle_route_is_fail_soft_without_a_database(test_config: Any, tmp_path: Path) -> None:
    """Route qui survit sans ``library.db`` (fail-soft, jamais 500)."""
    # No library.db at all — build_to_handle returns an empty rollup.
    test_config.acquire.db_path = tmp_path / "acquire.db"
    test_config.indexer.db_path = tmp_path / "nonexistent.db"
    client = guarded_client(
        config=test_config,
        settings=Settings(web_jwt_secret="testsecret", _env_file=None),  # type: ignore[call-arg]
        routers=[overview_router],
        with_auth=False,
        https=False,
    )

    resp = client.get("/api/acquisition/to-handle", cookies=_COOKIE)
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "orphan_count": 0}
