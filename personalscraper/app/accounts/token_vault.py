"""The kept Plex tokens, encrypted in ``app.db`` under keys that live outside it.

A Plex sign-in may keep the user's plex.tv token for a later feature; nothing reads one yet.
The token is sealed with :class:`cryptography.fernet.MultiFernet` over the keys of the
``PLEX_TOKEN_KEYS`` environment variable (comma-separated Fernet keys): the first encrypts,
every one decrypts, so a key is rotated by putting a new one first, re-sealing every row
(:func:`rotate_kept_tokens`) and dropping the old one.

The plaintext names its account (``{"a": account_id, "t": token}``): a ciphertext copied
onto another account's row fails that check and reads as absent, like one no key opens.
Either is logged as ``plex_token.undecryptable`` with the account id alone.

Nothing here writes a token or a key anywhere: not in a log, a ``repr`` or an exception's
text. A malformed key is refused by its position in the list, never by its value.
"""

from __future__ import annotations

import binascii
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.app.accounts.repository import AccountRepository
    from personalscraper.config import Settings

log = get_logger("app.accounts.token_vault")


class MalformedTokenKey(ValueError):
    """A key of ``PLEX_TOKEN_KEYS`` is not a Fernet key.

    Attributes:
        position: The key's 1-based position in the list; its value is never carried.
    """

    def __init__(self, position: int) -> None:
        """Name the malformed key by its position.

        Args:
            position: The key's 1-based position in ``PLEX_TOKEN_KEYS``.
        """
        super().__init__(f"PLEX_TOKEN_KEYS holds a malformed key at position {position}.")
        self.position = position


class TokenVault:
    """Seals and opens kept Plex tokens, each bound to its account."""

    __slots__ = ("_fernet", "_key_count")

    def __init__(self, keys: Sequence[bytes]) -> None:
        """Build the vault over its keys.

        Args:
            keys: Fernet keys, the encrypting one first; every one decrypts.

        Raises:
            ValueError: When no key is given, or one is not a Fernet key (its value is
                never in the text).
        """
        if not keys:
            raise ValueError("A token vault needs at least one key.")
        fernets = []
        for position, key in enumerate(keys, start=1):
            try:
                fernets.append(Fernet(key))
            except (ValueError, TypeError, binascii.Error):
                # ``from None``: the decoding error's context may quote the key.
                raise MalformedTokenKey(position) from None
        self._fernet = MultiFernet(fernets)
        self._key_count = len(fernets)

    @classmethod
    def from_settings(cls, settings: Settings) -> TokenVault | None:
        """Build the vault from ``PLEX_TOKEN_KEYS``.

        Args:
            settings: The env-var settings.

        Returns:
            The vault, or ``None`` when no key is set (the token is then simply not kept).

        Raises:
            MalformedTokenKey: A ``ValueError`` naming the position of a key that is not a
                Fernet key, never its value.
        """
        # Blank entries (a trailing comma, spaces around a key) are not keys.
        keys = [entry.strip().encode() for entry in settings.plex_token_keys.split(",") if entry.strip()]
        if not keys:
            return None
        return cls(keys)

    @property
    def key_count(self) -> int:
        """How many keys the vault holds (a rotation needs two).

        Returns:
            The count.
        """
        return self._key_count

    def seal(self, account_id: str, token: str) -> bytes:
        """Encrypt a token for one account under the first key.

        Args:
            account_id: The account keeping it.
            token: The plex.tv token.

        Returns:
            The ciphertext to store.
        """
        return self._fernet.encrypt(json.dumps({"a": account_id, "t": token}).encode())

    def open(self, account_id: str, blob: bytes) -> str | None:
        """Decrypt one account's stored token.

        Args:
            account_id: The account whose row holds ``blob``.
            blob: The stored ciphertext.

        Returns:
            The token, or ``None`` when no key opens it or it was sealed for another account
            (logged as ``plex_token.undecryptable``, by account id only).
        """
        try:
            plain = json.loads(self._fernet.decrypt(blob))
        except (InvalidToken, ValueError):
            plain = None
        if not isinstance(plain, dict) or plain.get("a") != account_id or not isinstance(plain.get("t"), str):
            log.warning("plex_token.undecryptable", account_id=account_id)
            return None
        token: str = plain["t"]
        return token

    def rotate(self, blob: bytes) -> bytes:
        """Re-seal a ciphertext under the first key.

        Args:
            blob: A ciphertext any key opens.

        Returns:
            The same plaintext, sealed under the first key.

        Raises:
            InvalidToken: When no key opens ``blob`` (its text is empty).
        """
        return self._fernet.rotate(blob)

    def __repr__(self) -> str:
        """Name the vault by its key count alone.

        Returns:
            ``TokenVault(keys=<n>)``.
        """
        return f"TokenVault(keys={self._key_count})"


def rotate_kept_tokens(repo: AccountRepository, vault: TokenVault, *, now: float) -> int:
    """Re-seal every kept token under the vault's first key.

    A row the vault cannot open for its own account (a removed key, a ciphertext moved from
    another row) is left as it is and logged; ``purge_undecryptable`` clears it.

    Args:
        repo: The account rows.
        vault: The vault, the new key first and the old ones after it.
        now: The storage time written on every re-sealed row (epoch seconds).

    Returns:
        How many rows were re-sealed.
    """
    rotated = 0
    with repo.immediate():
        for link in repo.plex_links_with_token():
            assert link.token_ciphertext is not None  # the query keeps only rows holding one
            # Opened first so the account binding is checked: a foreign ciphertext is not re-sealed.
            if vault.open(link.account_id, link.token_ciphertext) is None:
                continue
            repo.set_token_ciphertext(link.account_id, vault.rotate(link.token_ciphertext), now=now)
            rotated += 1
    log.info("plex_token.rotated", count=rotated)
    return rotated


def forget_kept_tokens(repo: AccountRepository, *, account_id: str | None) -> int:
    """Forget kept tokens: one account's, or every one.

    Args:
        repo: The account rows.
        account_id: The account, or ``None`` for every account.

    Returns:
        How many kept tokens were forgotten.
    """
    forgotten = 0
    with repo.immediate():
        for link in repo.plex_links_with_token():
            if account_id is not None and link.account_id != account_id:
                continue
            repo.set_token_ciphertext(link.account_id, None, now=None)
            forgotten += 1
    log.info("plex_token.forgotten", count=forgotten, account_id=account_id)
    return forgotten


def purge_undecryptable(repo: AccountRepository, vault: TokenVault, *, now: float) -> int:
    """Clear every kept token the vault cannot open for its own account.

    Args:
        repo: The account rows.
        vault: The vault over the keys still trusted.
        now: The purge time (epoch seconds), logged.

    Returns:
        How many rows were cleared.
    """
    purged = 0
    with repo.immediate():
        for link in repo.plex_links_with_token():
            assert link.token_ciphertext is not None  # the query keeps only rows holding one
            if vault.open(link.account_id, link.token_ciphertext) is not None:
                continue
            repo.set_token_ciphertext(link.account_id, None, now=None)
            purged += 1
    log.info("plex_token.purged", count=purged, at=now)
    return purged
