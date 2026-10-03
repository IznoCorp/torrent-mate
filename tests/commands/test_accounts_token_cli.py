"""``personalscraper accounts token-key rotate`` / ``token forget`` / ``token purge-undecryptable``.

The server's hand on the kept Plex tokens: the keys are read from ``PLEX_TOKEN_KEYS`` in the
environment and never from an argument; a rotation re-seals every kept token under the first
key and refuses with fewer than two; a forget nulls one account's ciphertext or every one; a
purge clears what no key opens. Every line comes from the translation layer, and no output
carries a token or a key.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from typer.testing import CliRunner

from personalscraper.app.accounts.repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.token_vault import TokenVault
from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.cli import app as cli_app
from personalscraper.conf.models.config import Config
from personalscraper.config import get_settings
from personalscraper.i18n import Language, use_language

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_CATALOGUES = Path(__file__).resolve().parents[2] / "personalscraper" / "i18n"
_ALICE = "account-alice"
_BOB = "account-bob"
_ALICE_EMAIL = "alice@example.org"
_TOKEN = "tok-PLANTED-0b7d3c5e91"


@pytest.fixture
def cli_runner() -> CliRunner:
    """A runner separating stdout from stderr.

    Returns:
        The runner.
    """
    from tests.conftest import make_cli_runner

    return make_cli_runner()


@pytest.fixture
def keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[bytes]]:
    """Two fresh Fernet keys, ``[new, old]``, set as ``PLEX_TOKEN_KEYS``; the test may reset the variable.

    Args:
        monkeypatch: Sets and restores the environment.

    Yields:
        The keys, the encrypting one first.
    """
    pair = [Fernet.generate_key(), Fernet.generate_key()]
    monkeypatch.setenv("PLEX_TOKEN_KEYS", ",".join(key.decode() for key in pair))
    get_settings.cache_clear()
    try:
        yield pair
    finally:
        get_settings.cache_clear()


def _set_keys(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Replace ``PLEX_TOKEN_KEYS`` and drop the cached settings.

    Args:
        monkeypatch: Sets the environment.
        value: The variable's new value.
    """
    monkeypatch.setenv("PLEX_TOKEN_KEYS", value)
    get_settings.cache_clear()


@pytest.fixture
def store(test_config: Config, keys: list[bytes]) -> Iterator[AppStore]:
    """The environment's ``app.db``: Alice and Bob Plex-linked, each keeping a token sealed under the old key.

    Args:
        test_config: The synthetic configuration.
        keys: ``[new, old]``.

    Yields:
        The store.
    """
    app_store = build_app_store(test_config)
    old = TokenVault([keys[1]])
    for plex_id, account_id in enumerate((_ALICE, _BOB), start=1):
        app_store.accounts.insert_account(
            AccountRow(
                id=account_id,
                name=account_id,
                email=f"{account_id.removeprefix('account-')}@example.org",
                avatar="",
                role_id="household",
                password_hash=None,
                created_at=1.0,
                updated_at=1.0,
            )
        )
        app_store.accounts.upsert_plex_link(
            PlexLinkRow(
                account_id=account_id,
                plex_id=plex_id,
                plex_uuid=f"uuid-{plex_id}",
                plex_username=account_id,
                server_access="shared",
                token_ciphertext=old.seal(account_id, _TOKEN),
                token_stored_at=1.0,
                linked_at=1.0,
                last_sign_in_at=None,
            )
        )
    try:
        yield app_store
    finally:
        app_store.close()


def _invoke(cli_runner: CliRunner, test_config: Config, args: list[str]):  # noqa: ANN202
    """Run the CLI over the synthetic configuration.

    Args:
        cli_runner: The runner.
        test_config: The synthetic configuration.
        args: The arguments after ``personalscraper``.

    Returns:
        The run's result.
    """
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=test_config),
    ):
        return cli_runner.invoke(cli_app, args)


def _kept(store: AppStore, account_id: str) -> bytes | None:
    """An account's stored ciphertext.

    Args:
        store: The store.
        account_id: The account.

    Returns:
        The ciphertext, or ``None``.
    """
    link = store.accounts.plex_link(account_id)
    assert link is not None
    return link.token_ciphertext


def _assert_no_secret(output: str, keys: list[bytes]) -> None:
    """Neither the planted token nor a key appears in a command's output.

    Args:
        output: stdout and stderr together.
        keys: The keys in use.
    """
    assert _TOKEN not in output
    for key in keys:
        assert key.decode() not in output


class TestRotate:
    """``token-key rotate``."""

    def test_rotates_every_kept_token_under_the_first_key(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes]
    ) -> None:
        """Two rows re-sealed and counted; the new key alone opens them."""
        result = _invoke(cli_runner, test_config, ["accounts", "token-key", "rotate"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "2 kept tokens re-sealed under the first key."
        new = TokenVault([keys[0]])
        for account_id in (_ALICE, _BOB):
            blob = _kept(store, account_id)
            assert blob is not None and new.open(account_id, blob) == _TOKEN
        _assert_no_secret(result.output, keys)

    def test_one_key_is_refused(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes], monkeypatch
    ) -> None:
        """A single key: exit 1, nothing re-sealed."""
        _set_keys(monkeypatch, keys[0].decode())
        before = _kept(store, _ALICE)

        result = _invoke(cli_runner, test_config, ["accounts", "token-key", "rotate"])

        assert result.exit_code == 1
        assert "Rotation needs at least two keys in PLEX_TOKEN_KEYS" in result.stderr
        assert _kept(store, _ALICE) == before
        _assert_no_secret(result.output, keys)

    def test_no_key_is_refused(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes], monkeypatch
    ) -> None:
        """No key at all: exit 1 with its own line."""
        _set_keys(monkeypatch, "")

        result = _invoke(cli_runner, test_config, ["accounts", "token-key", "rotate"])

        assert result.exit_code == 1
        assert "PLEX_TOKEN_KEYS is empty" in result.stderr

    def test_a_malformed_key_is_refused_without_its_material(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes], monkeypatch
    ) -> None:
        """A malformed second key: exit 1, its position named, its text and the good key printed nowhere."""
        planted = "not-a-key-PLANTED-77aa"
        _set_keys(monkeypatch, f"{keys[0].decode()},{planted}")

        result = _invoke(cli_runner, test_config, ["accounts", "token-key", "rotate"])

        assert result.exit_code == 1
        assert "position 2" in result.stderr
        assert planted not in result.output
        assert "Traceback" not in result.output
        _assert_no_secret(result.output, keys)

    def test_the_key_is_never_an_argument(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes]
    ) -> None:
        """``--help`` lists no option but help, and an extra argument is refused."""
        help_result = _invoke(cli_runner, test_config, ["accounts", "token-key", "rotate", "--help"])
        extra = _invoke(cli_runner, test_config, ["accounts", "token-key", "rotate", keys[0].decode()])

        assert help_result.exit_code == 0
        assert "PLEX_TOKEN_KEYS" in help_result.stdout
        options = help_result.stdout.split("Options")[1]
        assert "--help" in options
        assert options.count("--") == 1
        assert extra.exit_code == 2


class TestForget:
    """``token forget``."""

    def test_forgets_one_account_by_email_whatever_its_case(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes]
    ) -> None:
        """Alice's ciphertext nulled; Bob's kept."""
        result = _invoke(cli_runner, test_config, ["accounts", "token", "forget", _ALICE_EMAIL.upper()])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "1 kept token forgotten."
        assert _kept(store, _ALICE) is None
        assert _kept(store, _BOB) is not None
        _assert_no_secret(result.output, keys)

    def test_forget_all_nulls_every_ciphertext_and_counts_them(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes]
    ) -> None:
        """``--all``: both nulled, counted."""
        result = _invoke(cli_runner, test_config, ["accounts", "token", "forget", "--all"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "2 kept tokens forgotten."
        assert store.accounts.plex_links_with_token() == []

    def test_forget_needs_no_key(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, monkeypatch
    ) -> None:
        """Forgetting reads no token: it works with ``PLEX_TOKEN_KEYS`` empty (a lost key)."""
        _set_keys(monkeypatch, "")

        result = _invoke(cli_runner, test_config, ["accounts", "token", "forget", "--all"])

        assert result.exit_code == 0, result.output
        assert store.accounts.plex_links_with_token() == []

    def test_an_unknown_email_exits_1_with_the_cli_refusal(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore
    ) -> None:
        """No such account: exit 1, the ``account.unknown`` line, nothing forgotten."""
        result = _invoke(cli_runner, test_config, ["accounts", "token", "forget", "nobody@example.org"])

        assert result.exit_code == 1
        assert "No account has the e-mail given as EMAIL." in result.stderr.splitlines()
        assert len(store.accounts.plex_links_with_token()) == 2

    @pytest.mark.parametrize("args", [[], [_ALICE_EMAIL, "--all"]])
    def test_exactly_one_target(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, args: list[str]
    ) -> None:
        """Neither an e-mail nor ``--all``, or both: exit 2, nothing forgotten."""
        result = _invoke(cli_runner, test_config, ["accounts", "token", "forget", *args])

        assert result.exit_code == 2
        assert "Name one EMAIL or pass --all" in result.stderr
        assert len(store.accounts.plex_links_with_token()) == 2


class TestPurge:
    """``token purge-undecryptable``."""

    def test_clears_what_no_key_opens(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes], monkeypatch
    ) -> None:
        """The old key dropped: Alice (re-sealed under the new key) stays, Bob (old key) is cleared and counted."""
        store.accounts.set_token_ciphertext(_ALICE, TokenVault([keys[0]]).seal(_ALICE, _TOKEN), now=2.0)
        _set_keys(monkeypatch, keys[0].decode())

        result = _invoke(cli_runner, test_config, ["accounts", "token", "purge-undecryptable"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "1 undecryptable kept token cleared."
        assert _kept(store, _ALICE) is not None
        assert _kept(store, _BOB) is None
        _assert_no_secret(result.output, keys)

    def test_keeps_what_a_key_opens(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes]
    ) -> None:
        """Both keys still set: nothing cleared."""
        result = _invoke(cli_runner, test_config, ["accounts", "token", "purge-undecryptable"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "0 undecryptable kept tokens cleared."
        assert len(store.accounts.plex_links_with_token()) == 2

    def test_no_key_is_refused(self, cli_runner: CliRunner, test_config: Config, store: AppStore, monkeypatch) -> None:
        """No key: refused rather than clearing every row (``forget --all`` does that on purpose)."""
        _set_keys(monkeypatch, "")

        result = _invoke(cli_runner, test_config, ["accounts", "token", "purge-undecryptable"])

        assert result.exit_code == 1
        assert "PLEX_TOKEN_KEYS is empty" in result.stderr
        assert len(store.accounts.plex_links_with_token()) == 2

    def test_a_wrong_key_set_refuses_the_purge(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes], monkeypatch
    ) -> None:
        """A well-formed key opening nothing: exit 1, a line saying so, rows unchanged."""
        before = {account_id: _kept(store, account_id) for account_id in (_ALICE, _BOB)}
        _set_keys(monkeypatch, Fernet.generate_key().decode())

        result = _invoke(cli_runner, test_config, ["accounts", "token", "purge-undecryptable"])

        assert result.exit_code == 1
        assert "No kept token opens under the current PLEX_TOKEN_KEYS" in result.stderr
        assert {account_id: _kept(store, account_id) for account_id in (_ALICE, _BOB)} == before

    def test_force_clears_every_row_under_a_wrong_key_set(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes], monkeypatch
    ) -> None:
        """The same wrong keys with ``--force``: both rows cleared."""
        _set_keys(monkeypatch, Fernet.generate_key().decode())

        result = _invoke(cli_runner, test_config, ["accounts", "token", "purge-undecryptable", "--force"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "2 undecryptable kept tokens cleared."
        assert store.accounts.plex_links_with_token() == []

    def test_one_readable_row_needs_no_force(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, keys: list[bytes], monkeypatch
    ) -> None:
        """Alice opens under the current key, Bob does not: only Bob is cleared, no ``--force``."""
        store.accounts.set_token_ciphertext(_ALICE, TokenVault([keys[0]]).seal(_ALICE, _TOKEN), now=2.0)
        _set_keys(monkeypatch, keys[0].decode())

        result = _invoke(cli_runner, test_config, ["accounts", "token", "purge-undecryptable"])

        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == "1 undecryptable kept token cleared."
        assert _kept(store, _ALICE) is not None
        assert _kept(store, _BOB) is None


def _catalogue_line(language: Language, namespace: str, *path: str) -> str:
    """One line of a shipped catalogue file, read straight from the JSON (not through the lookup).

    Args:
        language: The catalogue's language.
        namespace: The namespace file.
        *path: The nested keys.

    Returns:
        The line, placeholders unfilled.
    """
    words = json.loads((_CATALOGUES / language.value / f"{namespace}.json").read_text(encoding="utf-8"))
    for key in path:
        words = words[key]
    assert isinstance(words, str)
    return words


class TestLanguage:
    """The commands speak the process's language."""

    @pytest.mark.parametrize("language", list(Language))
    def test_one_line_in_each_language(
        self,
        cli_runner: CliRunner,
        test_config: Config,
        store: AppStore,
        keys: list[bytes],
        monkeypatch,
        language: Language,
    ) -> None:
        """The forget count and the one-key refusal, each the catalogue's line of the language in use."""
        forgotten = _catalogue_line(language, "cli_accounts", "token", "forget", "done_one").replace("{{count}}", "1")
        needs_two = _catalogue_line(language, "cli_accounts", "token_key", "rotate", "needs_two")
        with use_language(language):
            forget = _invoke(cli_runner, test_config, ["accounts", "token", "forget", _ALICE_EMAIL])
            _set_keys(monkeypatch, keys[0].decode())
            rotate = _invoke(cli_runner, test_config, ["accounts", "token-key", "rotate"])

        assert forget.stdout.strip() == forgotten
        assert needs_two in rotate.stderr.splitlines()

    def test_the_two_languages_differ(self) -> None:
        """The French lines are not the English ones copied over."""
        for path in (("token", "forget", "done_one"), ("token_key", "rotate", "needs_two")):
            assert _catalogue_line(Language.FR, "cli_accounts", *path) != _catalogue_line(
                Language.EN, "cli_accounts", *path
            )
