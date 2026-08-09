"""The two facts « Terminé » rests on must survive the trip to the API.

The rule itself is pinned in ``tests/unit/web/acquisition/test_termine_state.py``.
What this file guards is the plumbing between it and the operator: a route that
forgets to pass ``series_status`` or ``announced_count`` would never fail a
derivation test — it would simply serve ``None`` for both, and « Terminé » would
never appear on any card, silently.

The schema is the REAL one (``build_acquire_store`` runs the migration chain, 023
included), so a column that exists only in a fixture cannot make this pass.
"""

from __future__ import annotations

import sqlite3
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

TVDB_ID = 371572


def _auth() -> dict[str, str]:
    """Return a ``tm_session`` cookie for the synthetic operator."""
    return {"tm_session": create_session_token("izno", "testsecret", 24)}


@pytest.fixture
def seeded_client(test_config: Any, tmp_path: Path) -> TestClient:
    """A client whose acquire.db is a REAL migrated store holding one follow.

    The follow is « Ended » with two aired episodes and one still ahead, so both
    new facts have a non-default value: a route that dropped either would serve
    ``None`` / ``0`` and be caught here.
    """
    acquire_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = acquire_path
    test_config.indexer.db_path = tmp_path / "library.db"
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    store = build_acquire_store(test_config.acquire)
    now = int(time.time())
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tvdb_id=TVDB_ID), title="Silo", added_at=now, kind="show")
    )
    store.aired.replace_for_followed(
        followed_id,
        [
            (1, 1, "Freedom Day", "2024-01-01"),
            (1, 2, "Holston's Pick", "2024-01-08"),
            (2, 1, "Un futur", "2099-12-31"),
        ],
        now=now,
    )
    store.follow.set_series_status(followed_id, "Ended")
    store.close()

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    return web_client(test_config, settings)


def test_series_status_and_announced_count_reach_the_payload(seeded_client: TestClient) -> None:
    """Both facts are served — the card cannot derive « Terminé » without them."""
    resp = seeded_client.get("/api/acquisition/followed", cookies=_auth())

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["series_status"] == "Ended"
    assert item["announced_count"] == 1, "the future episode must be counted, not dropped"


def test_a_follow_never_polled_serves_no_status(test_config: Any, tmp_path: Path) -> None:
    """No poll → ``None``, which the derivation reads as « not known to have ended ».

    A follow created before migration 023, or one the detect pass has never
    reached, must not arrive with an invented status.
    """
    acquire_path = tmp_path / "acquire.db"
    test_config.acquire.db_path = acquire_path
    test_config.indexer.db_path = tmp_path / "library.db"
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)

    store = build_acquire_store(test_config.acquire)
    store.follow.add(
        FollowedSeries(media_ref=MediaRef(tvdb_id=TVDB_ID), title="Silo", added_at=int(time.time()), kind="show")
    )
    store.close()

    settings = Settings(web_jwt_secret="testsecret", _env_file=None)  # type: ignore[call-arg]
    client = web_client(test_config, settings)

    item = client.get("/api/acquisition/followed", cookies=_auth()).json()["items"][0]

    assert item["series_status"] is None
    # And the column really is there — a NULL from a MISSING column would read
    # the same, which would hide a broken migration behind a passing test.
    conn = sqlite3.connect(str(acquire_path))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(followed_series)")}
    finally:
        conn.close()
    assert "series_status" in cols
