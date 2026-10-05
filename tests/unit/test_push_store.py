"""Unit tests for ``personalscraper.push.store`` — the push subscriptions, over an ``AppStore`` on ``tmp_path``."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.api.notify.fcm import PushOutcome, PushResult
from personalscraper.app.accounts.account_repository import AccountRow
from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.conf.models.config import Config
from personalscraper.push.store import STALE_AFTER_SECONDS, SqlitePushSubscriptionStore

TOKEN = "device-token-A-0123456789"
OTHER = "device-token-B-9876543210"


def _seed_accounts(app_store: AppStore, *account_ids: str) -> None:
    """Insert the accounts the subscriptions belong to (a subscription names an existing account).

    Args:
        app_store: The store.
        account_ids: The accounts' keys, also their names and e-mail local parts.
    """
    for account_id in account_ids:
        app_store.accounts.insert_account(
            AccountRow(
                id=account_id,
                name=account_id,
                email=f"{account_id}@example.org",
                avatar="",
                role_id="local-guest",
                password_hash=None,
                created_at=0.0,
                updated_at=0.0,
            )
        )


@pytest.fixture
def store(test_config: Config, tmp_path: Path) -> Iterator[SqlitePushSubscriptionStore]:
    """A fresh push store, from an ``AppStore`` on ``tmp_path``.

    Args:
        test_config: The synthetic Config fixture.
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    cfg = test_config.model_copy(update={"paths": test_config.paths.model_copy(update={"data_dir": tmp_path})})
    app_store = build_app_store(cfg)
    _seed_accounts(app_store, "alice", "bob", "a")
    try:
        yield app_store.push
    finally:
        app_store.close()


def _add(store: SqlitePushSubscriptionStore, token: str = TOKEN, account: str = "alice", now: float = 100.0):
    """Upserts one subscription.

    Args:
        store: The store.
        token: The token.
        account: The account.
        now: Epoch seconds.

    Returns:
        The stored subscription.
    """
    return store.upsert(account_id=account, token=token, platform="android", user_agent="UA", now=now)


def test_upsert_creates_a_live_subscription(store: SqlitePushSubscriptionStore) -> None:
    """A first upload is live, timestamps set, no failure."""
    sub = _add(store)
    assert (sub.account_id, sub.platform, sub.created_at, sub.refreshed_at) == ("alice", "android", 100.0, 100.0)
    assert sub.revoked_at is None and sub.failure_count == 0
    assert [s.token for s in store.live_for("alice")] == [TOKEN]


def test_re_upsert_refreshes_without_duplicating(store: SqlitePushSubscriptionStore) -> None:
    """The client re-sends at every start: one row, ``refreshed_at`` moves, ``created_at`` stays."""
    _add(store, now=100.0)
    sub = _add(store, now=500.0)
    assert (sub.created_at, sub.refreshed_at) == (100.0, 500.0)
    assert len(store.live_for("alice")) == 1


def test_a_token_moves_to_the_account_presenting_it(store: SqlitePushSubscriptionStore) -> None:
    """One browser, one owner: another account presenting the token takes it, count reset."""
    _add(store, account="alice")
    store.record(TOKEN, PushResult(PushOutcome.REJECTED), now=110.0)
    sub = _add(store, account="bob", now=120.0)
    assert sub.account_id == "bob" and sub.failure_count == 0
    assert store.live_for("alice") == []
    assert [s.token for s in store.live_for("bob")] == [TOKEN]


def test_revoke_excludes_and_a_re_upsert_revives(store: SqlitePushSubscriptionStore) -> None:
    """A revoked token is never listed; the client presenting it again revives it."""
    _add(store)
    store.revoke(TOKEN, reason="signed_out", now=150.0)
    assert store.live_for("alice") == []
    sub = _add(store, now=160.0)
    assert sub.revoked_at is None and sub.revoked_reason is None
    assert len(store.live_for("alice")) == 1


def test_revoke_keeps_the_first_reason(store: SqlitePushSubscriptionStore) -> None:
    """Revoking twice does not overwrite why it was revoked; an unknown token is a no-op."""
    _add(store)
    store.revoke(TOKEN, reason="token_dead", now=150.0)
    store.revoke(TOKEN, reason="stale", now=160.0)
    store.revoke("never-seen", reason="stale", now=160.0)
    row = store._conn.execute("SELECT revoked_at, revoked_reason FROM push_subscription").fetchone()
    assert row == (150.0, "token_dead")


def test_record_counts_consecutive_failures(store: SqlitePushSubscriptionStore) -> None:
    """Rejected / unreachable add up; a deferral or our misconfiguration leaves it; a delivery resets it."""
    _add(store)
    for outcome, expected in [
        (PushOutcome.REJECTED, 1),
        (PushOutcome.UNREACHABLE, 2),
        (PushOutcome.RETRY_LATER, 2),
        (PushOutcome.MISCONFIGURED, 2),
        (PushOutcome.DELIVERED, 0),
    ]:
        store.record(TOKEN, PushResult(outcome), now=200.0)
        (sub,) = store.live_for("alice")
        assert sub.failure_count == expected and sub.last_outcome == outcome.value and sub.last_sent_at == 200.0


def test_revoke_stale_at_270_days(store: SqlitePushSubscriptionStore) -> None:
    """Only the subscriptions not refreshed since the cut-off go, as ``stale``."""
    now = 1_000_000_000.0
    _add(store, token=TOKEN, now=now - STALE_AFTER_SECONDS - 1)
    _add(store, token=OTHER, now=now - STALE_AFTER_SECONDS + 1)
    assert store.revoke_stale(not_refreshed_since=now - STALE_AFTER_SECONDS, now=now) == 1
    assert [s.token for s in store.live_for("alice")] == [OTHER]
    assert store.revoke_stale(not_refreshed_since=now - STALE_AFTER_SECONDS, now=now) == 0


def test_an_unknown_platform_is_refused(store: SqlitePushSubscriptionStore) -> None:
    """The platform set is closed, in Python and in the table."""
    with pytest.raises(ValueError):
        store.upsert(account_id="a", token=TOKEN, platform="windows-phone", user_agent=None, now=1.0)  # type: ignore[arg-type]
    with pytest.raises(sqlite3.IntegrityError):
        store._conn.execute(
            "INSERT INTO push_subscription (account_id, token, platform, created_at, refreshed_at) "
            "VALUES ('a', 't', 'windows-phone', 1, 1)"
        )


def test_the_token_stays_out_of_the_repr(store: SqlitePushSubscriptionStore) -> None:
    """A subscription's ``repr`` (what a log or a traceback shows) carries no token."""
    assert TOKEN not in repr(_add(store))
