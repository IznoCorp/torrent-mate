"""The notices' rows: the read mark, and the bounds that keep the table small.

Everything is scoped to one account: a mark or a purge never reaches another account's rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.notice_repository import NOTICE_CAP_PER_ACCOUNT, NOTICE_RETENTION_S
from personalscraper.app.store.store import AppStore

_NOW = 10_000_000.0
_MINE = "account-mine"
_OTHER = "account-other"


def _account(account_id: str) -> Account:
    """An account with nothing but its key.

    Args:
        account_id: Its key.

    Returns:
        The account.
    """
    return Account(
        id=account_id,
        name=account_id,
        email=f"{account_id}@example.org",
        avatar="",
        role_id="household",
        password_hash=None,
        created_at=1.0,
        updated_at=1.0,
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` holding two accounts.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    app_store.accounts.insert_account(_account(_MINE))
    app_store.accounts.insert_account(_account(_OTHER))
    try:
        yield app_store
    finally:
        app_store.close()


class TestReadMark:
    """``mark_read_up_to``: the account's notices up to one, marked read."""

    def test_a_new_notice_is_unread(self, store: AppStore) -> None:
        """No mark is written on insert."""
        store.notices.insert_notice(_MINE, "account.sign_in.unknown_device", {}, now=_NOW)

        (row,) = store.notices.notices_of(_MINE, limit=10)

        assert row.read_at is None

    def test_marks_the_notices_up_to_the_given_one_and_not_the_later_ones(self, store: AppStore) -> None:
        """A notice raised after the one the account saw stays unread."""
        first = store.notices.insert_notice(_MINE, "account.sign_in.device", {}, now=_NOW)
        second = store.notices.insert_notice(_MINE, "account.sign_in.device", {}, now=_NOW + 1)
        third = store.notices.insert_notice(_MINE, "account.sign_in.device", {}, now=_NOW + 2)

        marked = store.notices.mark_read_up_to(_MINE, second, now=_NOW + 5)

        assert marked == 2
        read_at = {row.id: row.read_at for row in store.notices.notices_of(_MINE, limit=10)}
        assert read_at == {first: _NOW + 5, second: _NOW + 5, third: None}

    def test_a_second_mark_keeps_the_first_read_time_and_marks_nothing(self, store: AppStore) -> None:
        """Marking again is a no-op: the first read time stands."""
        notice = store.notices.insert_notice(_MINE, "account.sign_in.device", {}, now=_NOW)
        store.notices.mark_read_up_to(_MINE, notice, now=_NOW + 5)

        marked = store.notices.mark_read_up_to(_MINE, notice, now=_NOW + 9)

        assert marked == 0
        assert store.notices.notices_of(_MINE, limit=10)[0].read_at == _NOW + 5

    def test_never_marks_another_accounts_notice(self, store: AppStore) -> None:
        """Another account's notice, even under the given id, stays unread."""
        theirs = store.notices.insert_notice(_OTHER, "account.sign_in.device", {}, now=_NOW)

        marked = store.notices.mark_read_up_to(_MINE, theirs, now=_NOW + 5)

        assert marked == 0
        assert store.notices.notices_of(_OTHER, limit=10)[0].read_at is None


class TestBounds:
    """The table is bounded: by age, and by a count per account."""

    def test_a_notice_past_the_retention_is_purged_on_the_next_insert(self, store: AppStore) -> None:
        """Older than the retention goes; a younger one stays."""
        store.notices.insert_notice(_MINE, "account.sign_in.device", {"n": "old"}, now=_NOW)
        young = store.notices.insert_notice(_MINE, "account.sign_in.device", {"n": "young"}, now=_NOW + 10)

        newest = store.notices.insert_notice(_MINE, "account.sign_in.device", {}, now=_NOW + NOTICE_RETENTION_S + 1)

        assert [row.id for row in store.notices.notices_of(_MINE, limit=10)] == [newest, young]

    def test_the_table_keeps_at_most_the_cap_per_account_the_newest(self, store: AppStore) -> None:
        """One over the cap drops the oldest."""
        ids = [
            store.notices.insert_notice(_MINE, "account.sign_in.device", {}, now=_NOW + step)
            for step in range(NOTICE_CAP_PER_ACCOUNT + 1)
        ]

        kept = [row.id for row in store.notices.notices_of(_MINE, limit=NOTICE_CAP_PER_ACCOUNT + 10)]

        assert kept == ids[:0:-1]

    def test_a_purge_never_touches_another_accounts_notices(self, store: AppStore) -> None:
        """Another account's old notice survives this account's insert."""
        theirs = store.notices.insert_notice(_OTHER, "account.sign_in.device", {}, now=_NOW)

        store.notices.insert_notice(_MINE, "account.sign_in.device", {}, now=_NOW + NOTICE_RETENTION_S + 1)

        assert [row.id for row in store.notices.notices_of(_OTHER, limit=10)] == [theirs]
