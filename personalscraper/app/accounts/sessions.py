"""v1's sessions: an opaque cookie value, only its sha256 hex kept in ``app.db``.

A session signs one account in until it goes unused for its idle lifetime
(``config.web.session_idle_days``) or is revoked: the operator's « never forced to sign
in again while the app is used ». Each use renews it — at most once per
:data:`SESSION_RENEWAL_INTERVAL_S` — under a new cookie value, so a value copied once
stops working; the value it replaces keeps signing in until the new one comes back, then
for :data:`SESSION_ROTATION_GRACE_S`. No absolute upper bound caps a session in use.

A replaced value never takes its session over: in its grace it signs in but never renews.
Awaiting its successor — the browser never got the new value — it may renew, and the value
that renewal overwrites joins the replaced ones awaiting the newest, so whoever holds any of
them keeps the session until the newest comes back.

A session never carries the account's role or rights: :meth:`SessionService.use` and
:meth:`SessionService.resolve` read them on every call, so a role change bites at the
next request. v0's ``tm_session`` JWT is another mechanism entirely; neither ever reads
the other.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ceiling import InstanceCeiling, current_ceiling
from personalscraper.app.accounts.ids import AccountId
from personalscraper.app.accounts.session_repository import SessionRow
from personalscraper.app.store.store import AppStore

#: A session is renewed — its expiry moved, its value rotated — at most this often
#: (seconds): a burst of requests is one write, not one per request. An hour is nothing
#: against an idle lifetime counted in days.
SESSION_RENEWAL_INTERVAL_S: Final = 3600.0

#: How long a replaced value keeps signing in once its successor came back (seconds):
#: requests the browser sent before it stored the new cookie are still in flight with the
#: old one, and refusing them would answer 401 to a signed-in user. A minute covers a
#: slow request; past it, a copied old value is worthless.
SESSION_ROTATION_GRACE_S: Final = 60.0

#: Bytes of randomness in a cookie value (``secrets.token_urlsafe``: 43 characters).
_TOKEN_BYTES: Final = 32
_SECONDS_PER_DAY: Final = 86_400


def session_idle_s(idle_days: int) -> int:
    """A session's idle lifetime in seconds: what each renewal adds to now, and its cookie's ``Max-Age``.

    The one conversion both read, so the browser drops the cookie when the server
    stops honouring it.

    Args:
        idle_days: The lifetime in days (``config.web.session_idle_days``).

    Returns:
        The lifetime in seconds.
    """
    return idle_days * _SECONDS_PER_DAY


def _token_hash(token: str) -> str:
    """The stored form of a cookie value.

    Args:
        token: The cookie value.

    Returns:
        Its sha256, hex.
    """
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class SessionUse:
    """A request's use of a session.

    Attributes:
        actor: The actor the session signs in.
        renewed_token: The session's new cookie value when this use renewed it, to hand
            the browser; ``None`` when it was not renewed.
    """

    actor: Actor
    renewed_token: str | None


@dataclass
class _Replaced:
    """A cookie value a renewal replaced, still naming its session for a while.

    Attributes:
        session_id: The session it names.
        replaced_at: When it was replaced (epoch seconds).
        until: When it stops signing in; ``None`` until the new value comes back.
    """

    session_id: int
    replaced_at: float
    until: float | None


class SessionService:
    """Opens, uses, resolves and closes v1 sessions."""

    def __init__(
        self,
        store: AppStore,
        *,
        idle_days: int,
        ceiling: Callable[[], InstanceCeiling] = current_ceiling,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            store: The environment's ``app.db``, opened on first use.
            idle_days: A session's idle lifetime (``config.web.session_idle_days``).
            ceiling: Reads the instance ceiling, at each resolution.
            clock: The epoch clock.
        """
        self._store = store
        self._idle_s = session_idle_s(idle_days)
        self._ceiling = ceiling
        self._clock = clock
        # Replaced values live in memory, not in ``app.db``: the session table keeps one
        # hash per session, and one process serves a host's sessions. A restart forgets
        # them, which costs at most the requests in flight with a value replaced within
        # the restart's minute, or a session whose renewal never reached its browser.
        self._replaced: dict[str, _Replaced] = {}
        # Per session key, the replaced values still awaiting the current value's first use.
        self._awaiting: dict[int, list[str]] = {}
        # Held across a renewal's write and its record here, and across a lookup of a
        # replaced value: a request that missed the new hash in the base finds the old
        # one recorded.
        self._lock = threading.Lock()

    def open(self, account_id: AccountId, *, user_agent: str | None) -> str:
        """Open a session for an account.

        Args:
            account_id: The account signed in.
            user_agent: The browser's user agent, kept for the account's own reading.

        Returns:
            The cookie value — returned once, never stored, never logged.

        Raises:
            sqlite3.IntegrityError: The account does not exist.
        """
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        now = self._clock()
        self._store.sessions.insert_session(
            SessionRow(
                id=0,
                account_id=account_id,
                token_hash=_token_hash(token),
                created_at=now,
                expires_at=now + self._idle_s,
                last_seen_at=now,
                revoked_at=None,
                user_agent=user_agent,
            )
        )
        return token

    def _live_session(self, store: AppStore, token: str, now: float) -> tuple[SessionRow, bool] | None:
        """The live session a cookie value names, by its current value or a replaced one.

        Presenting a session's current value proves its browser holds it: the values it
        replaced then have :data:`SESSION_ROTATION_GRACE_S` left.

        Args:
            store: The ``app`` store.
            token: The cookie value.
            now: The current time.

        Returns:
            The session and whether this value may renew it — the current one, or a
            replaced one still awaiting its successor; never one in its grace. ``None``
            when unknown, revoked or expired, or a replaced value past its grace.
        """
        token_hash = _token_hash(token)
        row = store.sessions.session_by_hash(token_hash)
        # The lookup is an index equality; the explicit constant-time comparison keeps
        # the acceptance itself free of a timing difference.
        if row is not None and hmac.compare_digest(row.token_hash, token_hash):
            self._confirm(row.id, now)
            found: tuple[SessionRow, bool] | None = (row, True)
        else:
            found = self._replaced_session(store, token_hash, now)
        if found is None or found[0].revoked_at is not None or now >= found[0].expires_at:
            return None
        return found

    def _confirm(self, session_id: int, now: float) -> None:
        """Start the grace of the values a session's current one replaced, if they await it.

        Args:
            session_id: The session whose current value was presented.
            now: The current time.
        """
        with self._lock:
            for replaced_hash in self._awaiting.pop(session_id, []):
                replaced = self._replaced.get(replaced_hash)
                if replaced is not None and replaced.until is None:
                    replaced.until = now + SESSION_ROTATION_GRACE_S

    def _replaced_session(self, store: AppStore, token_hash: str, now: float) -> tuple[SessionRow, bool] | None:
        """The session a replaced value still names.

        Args:
            store: The ``app`` store.
            token_hash: The presented value's hash, unknown to the base.
            now: The current time.

        Returns:
            The session and whether the value may renew it — only while it awaits its
            successor, never in its grace; ``None`` when the value was never replaced, its
            grace is over or its session is gone.
        """
        with self._lock:
            replaced = self._replaced.get(token_hash)
            if replaced is None:
                return None
            if replaced.until is not None and now >= replaced.until:
                del self._replaced[token_hash]
                return None
            row = store.sessions.session(replaced.session_id)
            return (row, replaced.until is None) if row is not None else None

    def _actor(self, store: AppStore, session: SessionRow) -> Actor | None:
        """The actor a live session signs in, its role and rights read now.

        Args:
            store: The ``app`` store.
            session: The live session.

        Returns:
            The actor, or ``None`` when its account or role is gone.
        """
        account = store.accounts.account(session.account_id)
        role = store.roles.role(account.role_id) if account is not None else None
        if account is None or role is None:
            return None
        return Actor(
            account_id=account.id,
            name=account.name,
            role_id=role.id,
            role_kind=role.kind,
            role_rights=role.rights,
            ceiling=self._ceiling(),
        )

    def resolve(self, token: str) -> Actor | None:
        """The actor a cookie value signs in, without renewing its session.

        Args:
            token: The cookie value.

        Returns:
            The actor, with its role and rights read now and the current ceiling; ``None``
            when the session is unknown, expired or revoked, or its account or role is gone.
        """
        store = self._store
        found = self._live_session(store, token, self._clock())
        return self._actor(store, found[0]) if found is not None else None

    def use(self, token: str) -> SessionUse | None:
        """A request's use of a session: the actor it signs in, the session renewed when due.

        Args:
            token: The cookie value the request carries.

        Returns:
            The actor and, when this use renewed the session, its new value; ``None`` when
            :meth:`resolve` would answer ``None``.
        """
        store = self._store
        now = self._clock()
        found = self._live_session(store, token, now)
        if found is None:
            return None
        session, renewable = found
        actor = self._actor(store, session)
        if actor is None:
            return None
        renewed = None
        if renewable and now - session.last_seen_at >= SESSION_RENEWAL_INTERVAL_S:
            renewed = self._renew(store, session, now)
        return SessionUse(actor=actor, renewed_token=renewed)

    def _renew(self, store: AppStore, session: SessionRow, now: float) -> str | None:
        """Move a session's expiry to now plus its idle lifetime, under a new value.

        The value the renewal overwrites — the row's, whichever value was presented — is
        recorded as replaced, awaiting the new one: it keeps signing in until the new one
        comes back, then for the grace. A renewal whose answer never reached the browser
        loses nothing: the old value renews again, and the value it never received stays
        valid beside it, so neither holder is orphaned. A replaced value already recorded
        keeps its entry, its grace never reset.

        Args:
            store: The ``app`` store.
            session: The session as this request read it; its ``token_hash`` is the value
                the conditional write overwrites.
            now: The current time.

        Returns:
            The new value, or ``None`` when another request renewed the session first
            (this one then rides on the replaced value) or it was revoked meanwhile.
        """
        new_token = secrets.token_urlsafe(_TOKEN_BYTES)
        with self._lock:
            renewed = store.sessions.renew_session(
                session.id,
                seen_at=session.last_seen_at,
                token_hash=_token_hash(new_token),
                expires_at=now + self._idle_s,
                now=now,
            )
            if not renewed:
                return None
            self._forget_stale(now)
            if session.token_hash not in self._replaced:
                self._replaced[session.token_hash] = _Replaced(session_id=session.id, replaced_at=now, until=None)
                self._awaiting.setdefault(session.id, []).append(session.token_hash)
        return new_token

    def _forget_stale(self, now: float) -> None:
        """Drop the replaced values that can no longer sign in; the caller holds the lock.

        A value past its grace is refused anyway, and one replaced an idle lifetime ago
        names a session expired unless renewed since — renewed, it was replaced again.

        Args:
            now: The current time.
        """
        stale = [
            token_hash
            for token_hash, replaced in self._replaced.items()
            if (replaced.until is not None and now >= replaced.until) or now - replaced.replaced_at >= self._idle_s
        ]
        for token_hash in stale:
            session_id = self._replaced.pop(token_hash).session_id
            awaiting = self._awaiting.get(session_id)
            if awaiting is not None and token_hash in awaiting:
                awaiting.remove(token_hash)
                if not awaiting:
                    del self._awaiting[session_id]

    def live_session_id(self, token: str) -> int | None:
        """The key of the live session a cookie value names, by its current value or a replaced one.

        Args:
            token: The cookie value.

        Returns:
            The session's key, or ``None`` when unknown, revoked or expired.
        """
        found = self._live_session(self._store, token, self._clock())
        return found[0].id if found is not None else None

    def close(self, token: str) -> None:
        """Revoke the session a cookie value names; idempotent.

        Args:
            token: The cookie value, current or replaced. An unknown, expired or already
                revoked one is a no-op.
        """
        store = self._store
        now = self._clock()
        found = self._live_session(store, token, now)
        if found is not None:
            store.sessions.revoke_session(found[0].id, now=now)
