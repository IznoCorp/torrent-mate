"""The signed-in account's in-app notices, as the interface reads them.

A session act with no right to name: an account reads its own notices, and only those. A notice
is a code and its parameters; the interface words it in the account's language.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.accounts.notice_repository import NoticeParam
from personalscraper.app.store.store import AppStore

#: The most notices one read answers, the newest kept.
NOTICE_READ_LIMIT: Final = 50


@dataclass(frozen=True)
class NoticeView:
    """One notice of the signed-in account, as the interface reads it.

    Attributes:
        id: Its key.
        code: What it tells, as a code the interface words.
        params: The code's parameters.
        created_at: When it was raised (epoch seconds).
    """

    id: int
    code: str
    params: Mapping[str, NoticeParam]
    created_at: float


class NoticeService:
    """Reads the signed-in account's notices."""

    def __init__(self, store: AppStore) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
        """
        self._store = store

    @requires("readNotices")
    def read_notices(self, actor: Actor) -> list[NoticeView]:
        """The signed-in account's notices, the newest first.

        Args:
            actor: The signed-in actor.

        Returns:
            At most :data:`NOTICE_READ_LIMIT` of its notices.
        """
        rows = self._store.notices.notices_of(actor.account_id, limit=NOTICE_READ_LIMIT)
        return [NoticeView(id=row.id, code=row.code, params=row.params, created_at=row.created_at) for row in rows]
