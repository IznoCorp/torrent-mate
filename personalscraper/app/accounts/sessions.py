"""v1's sessions: an opaque cookie value, only its sha256 hex kept in ``app.db``.

A session signs one account in until its absolute expiry or its revocation. It never
carries the account's role or rights: :meth:`SessionService.resolve` reads them on every
call, so a role change bites at the next request. v0's ``tm_session`` JWT is another
mechanism entirely; neither ever reads the other.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from typing import Final

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.ceiling import InstanceCeiling, current_ceiling
from personalscraper.app.accounts.repository import AccountRepository, SessionRow

#: ``last_seen_at`` is rewritten at most this often (seconds): a read stays a read.
SESSION_TOUCH_INTERVAL_S: Final = 300.0

#: Bytes of randomness in a cookie value (``secrets.token_urlsafe``: 43 characters).
_TOKEN_BYTES: Final = 32
_SECONDS_PER_HOUR: Final = 3600.0


def _token_hash(token: str) -> str:
    """The stored form of a cookie value.

    Args:
        token: The cookie value.

    Returns:
        Its sha256, hex.
    """
    return hashlib.sha256(token.encode()).hexdigest()


class SessionService:
    """Opens, resolves and closes v1 sessions."""

    def __init__(
        self,
        repo_factory: Callable[[], AccountRepository],
        *,
        ttl_hours: int,
        ceiling: Callable[[], InstanceCeiling] = current_ceiling,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Build the service; nothing is opened until the first call.

        Args:
            repo_factory: Returns the account repository (opening ``app.db`` on first use).
            ttl_hours: A session's absolute lifetime (``config.web.session_ttl_hours``).
            ceiling: Reads the instance ceiling, at each resolution.
            clock: The epoch clock.
        """
        self._repo_factory = repo_factory
        self._ttl_s = ttl_hours * _SECONDS_PER_HOUR
        self._ceiling = ceiling
        self._clock = clock

    def open(self, account_id: str, *, user_agent: str | None) -> str:
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
        self._repo_factory().insert_session(
            SessionRow(
                id=0,
                account_id=account_id,
                token_hash=_token_hash(token),
                created_at=now,
                expires_at=now + self._ttl_s,
                last_seen_at=now,
                revoked_at=None,
                user_agent=user_agent,
            )
        )
        return token

    def _live_session(self, repo: AccountRepository, token: str, now: float) -> SessionRow | None:
        """The live session a cookie value names.

        Args:
            repo: The account repository.
            token: The cookie value.
            now: The current time.

        Returns:
            The session, or ``None`` when unknown, revoked or expired.
        """
        token_hash = _token_hash(token)
        row = repo.session_by_hash(token_hash)
        # The lookup is an index equality; the explicit constant-time comparison keeps
        # the acceptance itself free of a timing difference.
        if row is None or not hmac.compare_digest(row.token_hash, token_hash):
            return None
        if row.revoked_at is not None or now >= row.expires_at:
            return None
        return row

    def resolve(self, token: str) -> Actor | None:
        """The actor a cookie value signs in.

        Args:
            token: The cookie value.

        Returns:
            The actor, with its role and rights read now and the current ceiling; ``None``
            when the session is unknown, expired or revoked, or its account or role is gone.
        """
        repo = self._repo_factory()
        now = self._clock()
        session = self._live_session(repo, token, now)
        if session is None:
            return None
        account = repo.account(session.account_id)
        role = repo.role(account.role_id) if account is not None else None
        if account is None or role is None:
            return None
        if now - session.last_seen_at >= SESSION_TOUCH_INTERVAL_S:
            repo.touch_session(session.id, now=now)
        return Actor(
            account_id=account.id,
            name=account.name,
            role_id=role.id,
            role_kind=role.kind,
            role_rights=role.rights,
            ceiling=self._ceiling(),
        )

    def close(self, token: str) -> None:
        """Revoke the session a cookie value names; idempotent.

        Args:
            token: The cookie value. An unknown, expired or already revoked one is a no-op.
        """
        repo = self._repo_factory()
        now = self._clock()
        session = self._live_session(repo, token, now)
        if session is not None:
            repo.revoke_session(session.id, now=now)
