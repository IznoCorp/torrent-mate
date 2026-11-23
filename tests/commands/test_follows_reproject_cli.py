"""``personalscraper acquisition-follows-reproject`` — the follows' projection written again, on demand.

The floor a requester set stops counting once its role lost the right: the action re-reads the roles
and writes the floor in force on the row the engine reads, as the system actor.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.acquire.domain import FollowedSeries, FollowRequester
from personalscraper.acquire.store import build_acquire_store
from personalscraper.app.accounts.model import Account
from personalscraper.app.store.store import build_app_store
from personalscraper.cli import app as cli_app
from personalscraper.conf.models.config import Config
from personalscraper.core.identity import MediaRef

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


def test_a_stale_floor_is_reprojected(test_config: Config) -> None:
    """A floor stored by a requester whose account is gone is no longer in force once re-projected."""
    app_store = build_app_store(test_config)
    app_store.accounts.insert_account(
        Account(
            id="account-owner",
            name="Owner",
            email="owner@example.org",
            avatar="",
            role_id="admin",
            password_hash=None,
            created_at=1.0,
            updated_at=1.0,
        )
    )
    app_store.close()
    assert test_config.acquire.db_path is not None
    store = build_acquire_store(test_config.acquire)
    row = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=81189), title="Show", added_at=100))
    gone = FollowRequester(followed_id=row, account_id="account-gone", via="follow", floor=2160, paused=False, since=1)
    store.requesters.save_follow(row, [gone], removed_at=None, min_resolution=2160, active=True)
    store.close()

    from tests.conftest import make_cli_runner

    runner: CliRunner = make_cli_runner()
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=test_config),
    ):
        result = runner.invoke(cli_app, ["--format", "json", "acquisition-follows-reproject"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"reprojected": 1}
    store = build_acquire_store(test_config.acquire)
    try:
        reread = store.follow.get(row)
        assert reread is not None and reread.quality_profile_json is not None
        assert json.loads(reread.quality_profile_json)["min_resolution"] is None
    finally:
        store.close()
