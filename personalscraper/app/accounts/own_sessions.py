"""The account's own sessions: what it reads of them in Profil, and the revocation of one.

A Plex sign-in can be phished — someone who gets a person to confirm a PIN signs in as them —
so every account sees where it is signed in and ends what it does not recognise (the operator's
ruling Q4 A). Both acts are the account's own, session acts with no right to name; the
revocation is a write, refused on a read-only instance (``@requires``).

Only the caller's sessions are ever read or touched: a session id it does not hold — another
account's, an unknown one, one already ended — is refused ``session.unknown`` (404), the same
answer for all, so the route never tells that another account's session exists. The session
the caller calls with is not revoked here (``session.current``): signing out is ``signOut``'s.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.accounts.device import device_label
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.errors import AppConflict, AppNotFound, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.logger import get_logger

log = get_logger("app.accounts.own_sessions")


@dataclass(frozen=True)
class OwnSessionView:
    """One live session of the signed-in account, as Profil reads it.

    Attributes:
        id: Its key, the one ``revokeOwnSession`` takes.
        device: The browser and system its user agent names; ``None`` when it names neither.
        created_at: When it was opened (epoch seconds).
        last_seen_at: Its last renewal (epoch seconds) — a use is written at most hourly.
        current: Whether it is the session the request was made with.
    """

    id: int
    device: str | None
    created_at: float
    last_seen_at: float
    current: bool


class OwnSessionService:
    """Lists and revokes the signed-in account's own sessions."""

    def __init__(self, store: AppStore, sessions: SessionService, *, clock: Callable[[], float] = time.time) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            sessions: The session service, which names the session a cookie value holds.
            clock: The epoch clock.
        """
        self._store = store
        self._sessions = sessions
        self._clock = clock

    @requires("readOwnSessions")
    def read_own_sessions(self, actor: Actor, token: str) -> list[OwnSessionView]:
        """The signed-in account's live sessions, the newest first.

        Args:
            actor: The signed-in actor.
            token: The request's session value, which flags the current session.

        Returns:
            Its live sessions.
        """
        current = self._sessions.live_session_id(token)
        rows = self._store.sessions.live_sessions_of(actor.account_id, now=self._clock())
        return [
            OwnSessionView(
                id=row.id,
                device=device_label(row.user_agent),
                created_at=row.created_at,
                last_seen_at=row.last_seen_at,
                current=row.id == current,
            )
            for row in rows
        ]

    @requires("revokeOwnSession")
    def revoke_own_session(self, actor: Actor, token: str, session_id: int) -> None:
        """End one of the signed-in account's other sessions, at once: its next request is refused.

        Args:
            actor: The signed-in actor; authorised by ``@requires``.
            token: The request's session value — the session never revoked here.
            session_id: The session to end.

        Raises:
            AppForbidden: ``instance.read_only`` (``@requires``, before anything is read).
            AppNotFound: ``session.unknown`` — no live session of the account holds that id.
            AppConflict: ``session.current`` — it is the session the request was made with.
        """
        store = self._store
        current = self._sessions.live_session_id(token)
        with store.immediate():
            now = self._clock()
            row = store.sessions.session(session_id)
            live = row is not None and row.revoked_at is None and now < row.expires_at
            if row is None or not live or row.account_id != actor.account_id:
                raise AppNotFound("No live session of this account holds that id.", code=RefusalCode.SESSION_UNKNOWN)
            if row.id == current:
                raise AppConflict("The current session is ended by signing out.", code=RefusalCode.SESSION_CURRENT)
            store.sessions.revoke_session(row.id, now=now)
        log.info("own_session_revoked", account_id=actor.account_id, session_id=session_id)
