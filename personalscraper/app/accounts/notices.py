"""The signed-in account's in-app notices, as the interface reads them.

A session act with no right to name: an account reads its own notices, and only those. A notice
is a code and its parameters; the interface words it in the account's language.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
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
        read_at: When the account marked it read (epoch seconds); ``None`` while unread.
    """

    id: int
    code: str
    params: Mapping[str, NoticeParam]
    created_at: float
    read_at: float | None = None


class NoticeService:
    """Reads the signed-in account's notices and marks them read."""

    def __init__(self, store: AppStore, *, clock: Callable[[], float] = time.time) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            clock: The epoch clock.
        """
        self._store = store
        self._clock = clock

    @requires("readNotices")
    def read_notices(self, actor: Actor) -> list[NoticeView]:
        """The signed-in account's notices, the newest first.

        Args:
            actor: The signed-in actor.

        Returns:
            At most :data:`NOTICE_READ_LIMIT` of its notices.
        """
        rows = self._store.notices.notices_of(actor.account_id, limit=NOTICE_READ_LIMIT)
        return [
            NoticeView(id=row.id, code=row.code, params=row.params, created_at=row.created_at, read_at=row.read_at)
            for row in rows
        ]

    @requires("markNoticesRead")
    def mark_notices_read(self, actor: Actor, up_to: int) -> int:
        """Mark the signed-in account's notices read, those numbered ``up_to`` or lower.

        "Up to" rather than "one" or "all": Profil marks what it displayed in one call, and a
        notice raised meanwhile (a higher id) is not marked unseen. Repeating it is harmless.

        Args:
            actor: The signed-in actor; authorised by ``@requires``.
            up_to: The highest notice id marked.

        Returns:
            The number of notices newly marked; another account's notices are never touched.

        Raises:
            AppForbidden: ``instance.read_only`` (``@requires``, before anything is written).
        """
        return self._store.notices.mark_read_up_to(actor.account_id, up_to, now=self._clock())
