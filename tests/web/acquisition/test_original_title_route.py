"""The original title must survive the trip to the API (#435).

The cross-language identity fix stores the movie's original-language title on
the follow row; the UI shows it on the card/sheet so the operator can tell WHY
a release named `Before.I.Go.To.Sleep...` satisfied « Avant d'aller dormir ».
A route that forgets to pass ``original_title`` would never fail a filter test
— it would simply serve ``None`` and the surface would stay blank, silently.

The schema is the REAL one (``build_acquire_store`` runs the migration chain,
024 included), so a column that exists only in a fixture cannot make this pass.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.acquire.domain import FollowedSeries, MediaRef
from personalscraper.acquire.store import build_acquire_store
from personalscraper.config import Settings
from personalscraper.web.auth.tokens import create_session_token
from tests.web._web_harness import web_client

TMDB_ID = 204922


def _auth() -> dict[str, str]:
    """Return a ``tm_session`` cookie for the synthetic operator."""
    return {"tm_session": create_session_token("izno", "testsecret", 24)}


@pytest.fixture
def seeded_client(test_config: Any, tmp_path: Path) -> TestClient:
    """A client whose acquire.db holds the prod #435 movie follow, healed."""
    acquire_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = acquire_path
    test_config.indexer.db_path = tmp_path / "library.db"
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    store = build_acquire_store(test_config.acquire)
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tmdb_id=TMDB_ID),
            title="Avant d'aller dormir",
            added_at=int(time.time()),
            kind="movie",
            year=2014,
            original_title="Before I Go to Sleep",
        )
    )
    store.close()

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    return web_client(test_config, settings)


def test_original_title_reaches_the_payload(seeded_client: TestClient) -> None:
    """The healed value is served on the followed list item."""
    resp = seeded_client.get("/api/acquisition/followed", cookies=_auth())

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["original_title"] == "Before I Go to Sleep"


def test_an_unhealed_follow_serves_none(test_config: Any, tmp_path: Path) -> None:
    """A follow the detect pass has not healed yet serves ``None``, not an invention."""
    acquire_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = acquire_path
    test_config.indexer.db_path = tmp_path / "library.db"
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    store = build_acquire_store(test_config.acquire)
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tmdb_id=TMDB_ID),
            title="Avant d'aller dormir",
            added_at=int(time.time()),
            kind="movie",
        )
    )
    store.close()

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    client = web_client(test_config, settings)

    item = client.get("/api/acquisition/followed", cookies=_auth()).json()["items"][0]

    assert item["original_title"] is None
