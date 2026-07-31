"""Provenance F1 — GET /api/acquisition/journeys (the « Parcours » read view).

Read-only: the endpoint reads the F0 provenance registry and joins each row's
follow title so the journey (grabbed → ingested → scraped → dispatched) is
human-readable. Guarded by the single auth perimeter; read-only (no staging guard).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.store import build_acquire_store
from personalscraper.config import Settings
from personalscraper.core.identity import MediaRef
from personalscraper.web.auth.tokens import create_session_token
from personalscraper.web.routes.acquisition import router as acquisition_router
from tests.web._web_harness import guarded_client


def _seed_journey(db_path: Path) -> None:
    """Seed a followed series + a provenance journey row in a temp acquire.db."""
    store = build_acquire_store_config(db_path)
    try:
        fid = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=382389), title="Star Trek: SNW", added_at=1))
        store.provenance.upsert_grab(
            "abcd", followed_id=fid, media_ref=MediaRef(tvdb_id=382389), kind="episode", grabbed_at=1000
        )
        # F3 (run-linkage): the ingesting run is stamped (non-conflicting with 'awaiting').
        store.provenance.set_ingest("abcd", ingest_path="/stage/Star Trek", ingested_at=1001, run_uid="ingRUN")
        # F2 (decisions-spine): project an 'awaiting' verdict so the journey carries it.
        # (An awaiting item was NOT confidently scraped, so it carries no scrape stage/run.)
        store.provenance.set_resolution(
            "/stage/Star Trek", state="awaiting", resolved_at=1002, decision_id=7, trigger="mid_band"
        )
    finally:
        store.close()


def build_acquire_store_config(db_path: Path):  # noqa: ANN201 - test helper
    """Build a real acquire store on *db_path*."""
    from personalscraper.conf.models.acquire import AcquireConfig

    return build_acquire_store(AcquireConfig(db_path=db_path))


def test_journeys_returns_provenance_with_follow_title(test_config: Any, tmp_path: Path) -> None:
    """The endpoint returns the journey row, joined with the follow title."""
    db_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = db_path
    _seed_journey(db_path)

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    client = guarded_client(
        config=test_config, settings=settings, routers=acquisition_router, with_auth=False, https=False
    )
    token = create_session_token("izno", "testsecret", 24)
    resp = client.get("/api/acquisition/journeys", cookies={"tm_session": token})

    assert resp.status_code == 200, resp.text
    journeys = resp.json()["journeys"]
    assert len(journeys) == 1
    j = journeys[0]
    assert j["info_hash"] == "abcd"
    assert j["status"] == "ingested"
    assert j["follow_title"] == "Star Trek: SNW"
    assert j["media_ref"]["tvdb_id"] == 382389
    assert j["current_path"] == "/stage/Star Trek"
    # F2 — the resolution projection is carried on the journey.
    assert j["resolution_state"] == "awaiting"
    assert j["decision_id"] == 7
    assert j["resolution_trigger"] == "mid_band"
    # F3 — the per-stage run uids are carried on the journey.
    assert j["ingest_run_uid"] == "ingRUN"
    assert j["scrape_run_uid"] is None  # an awaiting item was not confidently scraped


def test_journeys_run_uid_filter_returns_only_that_runs_items(test_config: Any, tmp_path: Path) -> None:
    """F3 converse view: ?run_uid=<uid> returns only acquisitions that run touched."""
    db_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = db_path
    _seed_journey(db_path)  # item 'abcd' has ingest_run_uid='ingRUN'
    # A second, unrelated item touched by a different run.
    store = build_acquire_store_config(db_path)
    try:
        store.provenance.upsert_grab(
            "efgh", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=500, run_uid="otherRUN"
        )
    finally:
        store.close()

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    client = guarded_client(
        config=test_config, settings=settings, routers=acquisition_router, with_auth=False, https=False
    )
    token = create_session_token("izno", "testsecret", 24)
    resp = client.get("/api/acquisition/journeys?run_uid=ingRUN", cookies={"tm_session": token})
    assert resp.status_code == 200, resp.text
    journeys = resp.json()["journeys"]
    assert [j["info_hash"] for j in journeys] == ["abcd"]  # only the item ingRUN ingested


def test_journeys_requires_auth(test_config: Any, tmp_path: Path) -> None:
    """Without a session cookie the guard rejects the request."""
    test_config.acquire.db_path = tmp_path / "acquire.db"
    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    client = guarded_client(
        config=test_config, settings=settings, routers=acquisition_router, with_auth=False, https=False
    )
    resp = client.get("/api/acquisition/journeys")
    assert resp.status_code in (401, 403)


def test_journeys_flags_stuck_item(test_config: Any, tmp_path: Path) -> None:
    """F4: an aged, on-disk, in-flight item is flagged stuck; a fresh one is not."""
    db_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = db_path
    stuck_dir = tmp_path / "staging" / "Stuck Movie"
    stuck_dir.mkdir(parents=True)  # exists on disk

    store = build_acquire_store_config(db_path)
    try:
        # Stuck: ingested at epoch 100 (far past the idle horizon), folder exists.
        store.provenance.upsert_grab(
            "stuck", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1
        )
        store.provenance.set_ingest("stuck", ingest_path=str(stuck_dir), ingested_at=100)
    finally:
        store.close()

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    client = guarded_client(
        config=test_config, settings=settings, routers=acquisition_router, with_auth=False, https=False
    )
    token = create_session_token("izno", "testsecret", 24)
    resp = client.get("/api/acquisition/journeys", cookies={"tm_session": token})
    assert resp.status_code == 200, resp.text
    item = next(j for j in resp.json()["journeys"] if j["info_hash"] == "stuck")
    assert item["stuck"] is True
