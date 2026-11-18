"""Unit tests for ``personalscraper.app.accounts.token_vault`` — the kept Plex tokens, encrypted.

A token is sealed with the first key of ``PLEX_TOKEN_KEYS`` and opened with any of them; its
plaintext names its account, so a ciphertext moved onto another row reads as absent; a row
no key opens reads as absent and is logged by account id alone. The leak suite plants a
token and a key and proves neither reaches a log record, a ``repr``, a ``str`` or an
exception's text.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

from personalscraper.app.accounts.account_repository import AccountRepository
from personalscraper.app.accounts.model import Account, PlexLink
from personalscraper.app.accounts.token_vault import (
    NoKeptTokenOpens,
    RotationResult,
    TokenVault,
    forget_kept_tokens,
    purge_undecryptable,
    rotate_kept_tokens,
)
from personalscraper.app.store.store import AppStore
from personalscraper.config import Settings

_ALICE = "account-alice"
_BOB = "account-bob"
_TOKEN = "tok-PLANTED-4f1c9e2a7b"
_NOW = 5_000.0


@pytest.fixture
def store(tmp_path: Path) -> Iterator[AppStore]:
    """A fresh ``app.db`` holding two Plex-linked accounts that keep no token.

    Args:
        tmp_path: The test's temporary directory.

    Yields:
        The store.
    """
    app_store = AppStore(tmp_path / "app.db")
    for plex_id, account_id in enumerate((_ALICE, _BOB), start=1):
        app_store.accounts.insert_account(
            Account(
                id=account_id,
                name=account_id,
                email=f"{account_id}@example.org",
                avatar="",
                role_id="household",
                password_hash=None,
                created_at=1.0,
                updated_at=1.0,
            )
        )
        app_store.accounts.upsert_plex_link(
            PlexLink(
                account_id=account_id,
                plex_id=plex_id,
                plex_uuid=f"uuid-{plex_id}",
                plex_username=account_id,
                server_access="shared",
                token_ciphertext=None,
                token_stored_at=None,
                linked_at=1.0,
                last_sign_in_at=None,
            )
        )
    try:
        yield app_store
    finally:
        app_store.close()


@pytest.fixture
def repo(store: AppStore) -> AccountRepository:
    """The store's account rows.

    Args:
        store: The store.

    Returns:
        The repository.
    """
    return store.accounts


#: The keys every structlog record carries, whatever was logged.
_LOG_FRAME = frozenset({"event", "level", "log_level", "logger", "timestamp"})


def _vault_events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    """The vault's structlog events, read from the stdlib records they are rendered through.

    ``structlog.testing.capture_logs`` misses a logger cached before it (``cache_logger_on_first_use``,
    as after a CLI run in the same process); the stdlib records see every event.

    Args:
        caplog: pytest's log capture.

    Returns:
        The event dicts of ``app.accounts.token_vault``, in order.
    """
    return [
        dict(record.msg)
        for record in caplog.records
        if record.name == "app.accounts.token_vault" and isinstance(record.msg, dict)
    ]


def _kept(repo: AccountRepository, account_id: str) -> bytes | None:
    """An account's stored ciphertext.

    Args:
        repo: The repository.
        account_id: The account.

    Returns:
        The ciphertext, or ``None``.
    """
    link = repo.plex_link(account_id)
    assert link is not None
    return link.token_ciphertext


class TestSealAndOpen:
    """The vault's round trip and its binding to an account."""

    def test_seal_then_open_round_trips(self) -> None:
        """A token sealed for an account opens for that account, and the blob does not hold it."""
        vault = TokenVault([Fernet.generate_key()])

        blob = vault.seal(_ALICE, _TOKEN)

        assert _TOKEN.encode() not in blob
        assert vault.open(_ALICE, blob) == _TOKEN

    def test_a_ciphertext_on_another_account_reads_as_absent(self, caplog: pytest.LogCaptureFixture) -> None:
        """Alice's blob copied onto Bob's row: ``None``, and one log naming Bob's id only."""
        vault = TokenVault([Fernet.generate_key()])
        blob = vault.seal(_ALICE, _TOKEN)

        assert vault.open(_BOB, blob) is None

        logs = _vault_events(caplog)
        assert [entry["event"] for entry in logs] == ["plex_token.undecryptable"]
        assert logs[0]["account_id"] == _BOB
        assert _ALICE not in str(logs)

    def test_a_blob_sealed_under_the_old_key_opens_and_rotates_to_the_new(self) -> None:
        """Keys ``[new, old]``: an ``old`` blob opens; ``rotate`` re-seals it so ``[new]`` alone opens it."""
        old, new = Fernet.generate_key(), Fernet.generate_key()
        sealed_under_old = TokenVault([old]).seal(_ALICE, _TOKEN)
        both = TokenVault([new, old])

        assert both.open(_ALICE, sealed_under_old) == _TOKEN
        rotated = both.rotate(sealed_under_old)
        assert TokenVault([new]).open(_ALICE, rotated) == _TOKEN
        assert TokenVault([old]).open(_ALICE, rotated) is None

    def test_a_removed_key_reads_as_absent_and_logs_the_account_id_only(self, caplog: pytest.LogCaptureFixture) -> None:
        """A blob no key opens: ``None`` and one ``plex_token.undecryptable`` record with the account id alone."""
        blob = TokenVault([Fernet.generate_key()]).seal(_ALICE, _TOKEN)

        assert TokenVault([Fernet.generate_key()]).open(_ALICE, blob) is None

        logs = _vault_events(caplog)
        assert len(logs) == 1
        assert logs[0]["event"] == "plex_token.undecryptable"
        assert {key for key in logs[0] if key not in _LOG_FRAME} == {"account_id"}
        assert logs[0]["account_id"] == _ALICE

    def test_a_vault_needs_a_key(self) -> None:
        """No key: refused at construction."""
        with pytest.raises(ValueError):
            TokenVault([])

    def test_rotating_a_blob_no_key_opens_raises(self) -> None:
        """``rotate`` cannot re-seal what it cannot read."""
        blob = TokenVault([Fernet.generate_key()]).seal(_ALICE, _TOKEN)

        with pytest.raises(InvalidToken):
            TokenVault([Fernet.generate_key()]).rotate(blob)


class TestFromSettings:
    """The keys come from ``PLEX_TOKEN_KEYS`` only."""

    def test_the_keys_are_a_masked_setting(self) -> None:
        """``PLEX_TOKEN_KEYS`` is read into ``plex_token_keys`` and masked by ``repr``/``str``."""
        key = Fernet.generate_key().decode()
        settings = Settings(plex_token_keys=key)

        assert settings.plex_token_keys == key
        assert "plex_token_keys=<masked>" in repr(settings)
        assert "plex_token_keys=<masked>" in str(settings)
        assert ("plex_token_keys", "<masked>") in list(settings.__rich_repr__())

    def test_no_key_means_no_vault(self) -> None:
        """An empty ``PLEX_TOKEN_KEYS``: ``None`` — the token is simply not kept."""
        assert TokenVault.from_settings(Settings(plex_token_keys="")) is None

    def test_comma_separated_keys_the_first_encrypts(self) -> None:
        """``new,old``: the first seals, both open."""
        old, new = Fernet.generate_key(), Fernet.generate_key()
        vault = TokenVault.from_settings(Settings(plex_token_keys=f" {new.decode()} , {old.decode()} "))

        assert vault is not None
        assert repr(vault) == "TokenVault(keys=2)"
        assert TokenVault([new]).open(_ALICE, vault.seal(_ALICE, _TOKEN)) == _TOKEN
        assert vault.open(_ALICE, TokenVault([old]).seal(_ALICE, _TOKEN)) == _TOKEN

    def test_a_malformed_key_is_refused_without_its_material(self) -> None:
        """A key that is not a Fernet key: ``ValueError`` naming its position, never its text."""
        good = Fernet.generate_key().decode()
        planted = "not-a-fernet-key-PLANTED-9d2e"

        with pytest.raises(ValueError) as caught:
            TokenVault.from_settings(Settings(plex_token_keys=f"{good},{planted}"))

        assert "2" in str(caught.value)
        assert planted not in str(caught.value)
        assert good not in str(caught.value)
        assert caught.value.__cause__ is None
        assert caught.value.__suppress_context__


class TestRows:
    """The three operations over the stored rows."""

    def test_rotate_reseals_every_row_under_the_first_key(self, store: AppStore, repo: AccountRepository) -> None:
        """Two rows under ``old``: both re-sealed, counted, and ``[new]`` alone opens them."""
        old, new = Fernet.generate_key(), Fernet.generate_key()
        for account_id in (_ALICE, _BOB):
            repo.set_token_ciphertext(account_id, TokenVault([old]).seal(account_id, _TOKEN), now=1.0)

        assert rotate_kept_tokens(store, TokenVault([new, old]), now=_NOW) == RotationResult(rotated=2, skipped=0)

        for account_id in (_ALICE, _BOB):
            blob = _kept(repo, account_id)
            assert blob is not None
            assert TokenVault([new]).open(account_id, blob) == _TOKEN
            link = repo.plex_link(account_id)
            assert link is not None and link.token_stored_at == _NOW

    def test_rotate_leaves_an_undecryptable_row_alone(
        self, store: AppStore, repo: AccountRepository, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A row no key opens is not counted, not changed, and logged by account id."""
        old, new, lost = (Fernet.generate_key() for _ in range(3))
        repo.set_token_ciphertext(_ALICE, TokenVault([old]).seal(_ALICE, _TOKEN), now=1.0)
        lost_blob = TokenVault([lost]).seal(_BOB, _TOKEN)
        repo.set_token_ciphertext(_BOB, lost_blob, now=1.0)

        result = rotate_kept_tokens(store, TokenVault([new, old]), now=_NOW)

        assert result == RotationResult(rotated=1, skipped=1)
        assert _kept(repo, _BOB) == lost_blob
        undecryptable = [
            entry["account_id"] for entry in _vault_events(caplog) if entry["event"] == "plex_token.undecryptable"
        ]
        assert undecryptable == [_BOB]

    def test_rotate_does_not_launder_a_foreign_ciphertext(self, store: AppStore, repo: AccountRepository) -> None:
        """Alice's blob on Bob's row stays unread after a rotation: the binding survives it."""
        old, new = Fernet.generate_key(), Fernet.generate_key()
        repo.set_token_ciphertext(_BOB, TokenVault([old]).seal(_ALICE, _TOKEN), now=1.0)

        assert rotate_kept_tokens(store, TokenVault([new, old]), now=_NOW) == RotationResult(rotated=0, skipped=1)
        blob = _kept(repo, _BOB)
        assert blob is not None
        assert TokenVault([new, old]).open(_BOB, blob) is None

    def test_forget_one_account(self, store: AppStore, repo: AccountRepository) -> None:
        """One account: its ciphertext nulled, the other's kept."""
        vault = TokenVault([Fernet.generate_key()])
        for account_id in (_ALICE, _BOB):
            repo.set_token_ciphertext(account_id, vault.seal(account_id, _TOKEN), now=1.0)

        assert forget_kept_tokens(store, account_id=_ALICE) == 1

        alice = repo.plex_link(_ALICE)
        assert alice is not None and alice.token_ciphertext is None and alice.token_stored_at is None
        assert _kept(repo, _BOB) is not None

    def test_forget_an_account_keeping_nothing_counts_zero(self, store: AppStore, repo: AccountRepository) -> None:
        """Nothing kept: nothing forgotten."""
        assert forget_kept_tokens(store, account_id=_ALICE) == 0

    def test_forget_all_nulls_every_ciphertext_and_counts_them(self, store: AppStore, repo: AccountRepository) -> None:
        """``--all``: every row nulled, the count of those that held one."""
        vault = TokenVault([Fernet.generate_key()])
        for account_id in (_ALICE, _BOB):
            repo.set_token_ciphertext(account_id, vault.seal(account_id, _TOKEN), now=1.0)

        assert forget_kept_tokens(store, account_id=None) == 2
        assert repo.plex_links_with_token() == []

    def test_purge_clears_only_what_no_key_opens(self, store: AppStore, repo: AccountRepository) -> None:
        """A row under a removed key and a foreign row are cleared; a readable row stays."""
        key, removed = Fernet.generate_key(), Fernet.generate_key()
        vault = TokenVault([key])
        repo.set_token_ciphertext(_ALICE, vault.seal(_ALICE, _TOKEN), now=1.0)
        repo.set_token_ciphertext(_BOB, TokenVault([removed]).seal(_BOB, _TOKEN), now=1.0)

        assert purge_undecryptable(store, vault, now=_NOW) == 1

        assert _kept(repo, _BOB) is None
        alice = _kept(repo, _ALICE)
        assert alice is not None and vault.open(_ALICE, alice) == _TOKEN

    def test_purge_refuses_when_no_kept_token_opens(self, store: AppStore, repo: AccountRepository) -> None:
        """Every row unreadable (a wrong key set): refused, every row unchanged."""
        wrong, removed = Fernet.generate_key(), Fernet.generate_key()
        blobs = {}
        for account_id in (_ALICE, _BOB):
            blobs[account_id] = TokenVault([removed]).seal(account_id, _TOKEN)
            repo.set_token_ciphertext(account_id, blobs[account_id], now=1.0)

        with pytest.raises(NoKeptTokenOpens):
            purge_undecryptable(store, TokenVault([wrong]), now=_NOW)

        for account_id in (_ALICE, _BOB):
            assert _kept(repo, account_id) == blobs[account_id]

    def test_purge_force_clears_every_row_even_when_none_opens(self, store: AppStore, repo: AccountRepository) -> None:
        """The same vault with ``force``: every row cleared."""
        wrong, removed = Fernet.generate_key(), Fernet.generate_key()
        for account_id in (_ALICE, _BOB):
            repo.set_token_ciphertext(account_id, TokenVault([removed]).seal(account_id, _TOKEN), now=1.0)

        assert purge_undecryptable(store, TokenVault([wrong]), now=_NOW, force=True) == 2
        assert repo.plex_links_with_token() == []

    def test_purge_with_nothing_kept_is_not_a_refusal(self, store: AppStore, repo: AccountRepository) -> None:
        """No kept token at all: nothing to refuse over, zero cleared."""
        assert purge_undecryptable(store, TokenVault([Fernet.generate_key()]), now=_NOW) == 0


class TestLeaks:
    """A planted token and a planted key reach no log, ``repr``, ``str`` or exception text."""

    def test_the_token_and_key_are_never_written_out(
        self, store: AppStore, repo: AccountRepository, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Every path of the vault, logged at DEBUG: neither secret appears anywhere."""
        key, other = Fernet.generate_key(), Fernet.generate_key()
        secrets = (_TOKEN, key.decode(), other.decode())
        settings = Settings(plex_token_keys=f"{key.decode()},{other.decode()}", plex_token=_TOKEN)
        texts: list[str] = [repr(settings), str(settings)]

        caplog.set_level(logging.DEBUG)
        vault = TokenVault.from_settings(settings)
        assert vault is not None
        texts.append(repr(vault))
        texts.append(str(vault))
        blob = vault.seal(_ALICE, _TOKEN)
        repo.set_token_ciphertext(_ALICE, blob, now=1.0)
        repo.set_token_ciphertext(_BOB, blob, now=1.0)
        vault.open(_BOB, blob)
        TokenVault([Fernet.generate_key()]).open(_ALICE, blob)
        rotate_kept_tokens(store, vault, now=_NOW)
        purge_undecryptable(store, vault, now=_NOW)
        forget_kept_tokens(store, account_id=None)
        texts.extend(repr(link) for link in [repo.plex_link(_ALICE), repo.plex_link(_BOB)])
        for raw in (f"{key.decode()},{_TOKEN}", key.decode()[:-2]):
            with pytest.raises(ValueError) as caught:
                TokenVault.from_settings(Settings(plex_token_keys=raw))
            texts.append(str(caught.value))
            texts.append(repr(caught.value))
        with pytest.raises(InvalidToken) as invalid:
            TokenVault([Fernet.generate_key()]).rotate(blob)
        texts.append(str(invalid.value))
        texts.append(repr(invalid.value))

        vault_events = _vault_events(caplog)
        assert {entry["event"] for entry in vault_events} >= {"plex_token.undecryptable", "plex_token.rotated"}
        texts.extend(str(entry) for entry in vault_events)
        texts.extend(record.getMessage() for record in caplog.records)
        texts.append(caplog.text)
        for secret in secrets:
            for text in texts:
                assert secret not in text
