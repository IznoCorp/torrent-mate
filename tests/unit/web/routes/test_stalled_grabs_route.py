"""GET /api/acquisition/stalled-grabs + the overview counter (§14.1 / §8).

Regression anchor: wanted #95 « Spider-Man : Brand New Day » sat at ``grabbed`` with its
journey stuck at ``ingested`` and NOTHING said so. §14.1 makes « récupéré » a transitory
state; a row that stagnates there is non-conforme, and the interface owes the operator
both the fact AND the reason (§8), plus the release actually grabbed (§13).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.config import Settings
from personalscraper.core.identity import MediaRef
from personalscraper.web.auth.tokens import create_session_token
from personalscraper.web.routes.acquisition_overview import router as overview_router
from tests.unit.web.routes.test_journeys import build_acquire_store_config
from tests.web._web_harness import guarded_client

SOUNDTRACK = (
    "Michael Giacchino Spider-Man_ Brand New Day (Original Motion Picture "
    "Soundtrack).2026.WEB.FLAC.[24bit.44.1khz]- TEAM EICHBAUM"
)
HASH = "1329fe9eef22234bd44cf0d1ce11f3bc76e11a75"

GRABBED_AT = 1_785_954_958
INGESTED_AT = 1_785_955_219
#: The run that ingested it FINISHED 5 s later, with dispatch skipped — the instant the
#: product already knew the item would not be shelved.
RUN_FINISHED_AT = INGESTED_AT + 5

_COOKIE = {"tm_session": create_session_token("izno", "testsecret", 24)}


def _seed_parked_acquisition(db_path: Path) -> None:
    """Reproduce the live incident: wanted at 'grabbed', journey stopped at 'ingested'."""
    store = build_acquire_store_config(db_path)
    try:
        fid = store.follow.add(
            FollowedSeries(
                media_ref=MediaRef(tmdb_id=969681),
                title="Spider-Man : Brand New Day",
                added_at=GRABBED_AT,
                kind="movie",
            )
        )
        wid = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tmdb_id=969681),
                kind="movie",
                status="pending",
                enqueued_at=GRABBED_AT,
                followed_id=fid,
            )
        )
        store.wanted.mark_grabbed(wid, HASH)
        store.provenance.upsert_grab(
            HASH, followed_id=fid, media_ref=MediaRef(tmdb_id=969681), kind="movie", grabbed_at=GRABBED_AT
        )
        store.provenance.set_ingest(HASH, ingest_path=f"/staging/097-TEMP/{SOUNDTRACK}", ingested_at=INGESTED_AT)
        # The pipeline run finished without shelving it — the deterministic trigger.
        store.watch.set_last_successful_run_at(RUN_FINISHED_AT)
    finally:
        store.close()


def _client(test_config: Any, tmp_path: Path) -> Any:
    db_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = db_path
    test_config.indexer.db_path = tmp_path / "library.db"
    _seed_parked_acquisition(db_path)
    return guarded_client(
        config=test_config,
        settings=Settings(web_jwt_secret="testsecret", _env_file=None),  # type: ignore[call-arg]
        routers=[overview_router],
        with_auth=False,
        https=False,
    )


def test_overview_counts_the_parked_acquisition(test_config: Any, tmp_path: Path) -> None:
    """The rollup must SAY that something recovered never reached the library."""
    resp = _client(test_config, tmp_path).get("/api/acquisition/overview", cookies=_COOKIE)

    assert resp.status_code == 200, resp.text
    assert resp.json()["stalled_grabs"] == 1


def test_list_names_the_release_and_the_reason(test_config: Any, tmp_path: Path) -> None:
    """§8 + §13: never a bare count — the reason AND what was really grabbed."""
    resp = _client(test_config, tmp_path).get("/api/acquisition/stalled-grabs", cookies=_COOKIE)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["title"] == "Spider-Man : Brand New Day"
    assert item["reason"] == "un run s'est terminé depuis l'ingestion sans la ranger"
    # The field that made the soundtrack indistinguishable from the film.
    assert item["release_name"] == SOUNDTRACK
    assert item["info_hash"] == HASH


def test_stalled_grabs_requires_auth(test_config: Any, tmp_path: Path) -> None:
    """The list sits under the single guarded_api perimeter like every other route."""
    test_config.acquire.db_path = tmp_path / "acquire.db"
    client = guarded_client(
        config=test_config,
        settings=Settings(web_jwt_secret="testsecret", _env_file=None),  # type: ignore[call-arg]
        routers=[overview_router],
        with_auth=False,
        https=False,
    )

    assert client.get("/api/acquisition/stalled-grabs").status_code in (401, 403)
