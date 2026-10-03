"""``personalscraper accounts set-password`` — the password door of last resort, on the server.

The password is prompted twice, hidden, and never read from the command line; only its
scrypt hash reaches ``app.db``. Every line the command prints comes from the translation
layer, in the process's language; a refusal of the account service is worded from the
CLI's own ``cli_refusals`` catalogue.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from personalscraper.app.accounts.passwords import verify_password
from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.cli import app as cli_app
from personalscraper.conf.models.config import Config
from personalscraper.i18n import Language, use_language

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_EMAIL = "owner@example.org"
_CATALOGUES = Path(__file__).resolve().parents[2] / "personalscraper" / "i18n"
_PASSWORD = "a long fallback password"


@pytest.fixture
def cli_runner() -> CliRunner:
    """A runner separating stdout from stderr.

    Returns:
        The runner.
    """
    from tests.conftest import make_cli_runner

    return make_cli_runner()


@pytest.fixture
def store(test_config: Config) -> Iterator[AppStore]:
    """The environment's ``app.db``, holding one account without a password.

    Args:
        test_config: The synthetic configuration.

    Yields:
        The store.
    """
    app_store = build_app_store(test_config)
    app_store.accounts.insert_account(
        AccountRow(
            id="account-owner",
            name="Owner",
            email=_EMAIL,
            avatar="",
            role_id="admin",
            password_hash=None,
            created_at=1.0,
            updated_at=1.0,
        )
    )
    try:
        yield app_store
    finally:
        app_store.close()


def _invoke(cli_runner: CliRunner, test_config: Config, args: list[str], typed: str = ""):  # noqa: ANN202
    """Run the CLI over the synthetic configuration.

    Args:
        cli_runner: The runner.
        test_config: The synthetic configuration.
        args: The arguments after ``personalscraper``.
        typed: What the operator types at the prompts.

    Returns:
        The run's result.
    """
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=test_config),
    ):
        return cli_runner.invoke(cli_app, args, input=typed)


def _stored_hash(store: AppStore) -> str | None:
    """The account's stored hash.

    Args:
        store: The store.

    Returns:
        The hash, or ``None``.
    """
    row = store.accounts.account("account-owner")
    assert row is not None
    return row.password_hash


class TestSetPassword:
    """The command's behaviour."""

    def test_prompts_twice_and_stores_only_a_hash(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore
    ) -> None:
        """Two hidden prompts; the hash verifies; the password is printed nowhere."""
        result = _invoke(cli_runner, test_config, ["accounts", "set-password", _EMAIL], f"{_PASSWORD}\n{_PASSWORD}\n")

        assert result.exit_code == 0, result.output
        assert result.stdout.count("New password") == 1
        assert result.stdout.count("Repeat the new password") == 1
        assert _PASSWORD not in result.output
        stored = _stored_hash(store)
        assert stored is not None and verify_password(_PASSWORD, stored)
        assert result.stdout.strip().endswith(f"Password set for {_EMAIL}.")

    def test_the_email_is_matched_whatever_its_case(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore
    ) -> None:
        """``OWNER@EXAMPLE.ORG`` names the account stored in lower case."""
        typed = f"{_PASSWORD}\n{_PASSWORD}\n"
        result = _invoke(cli_runner, test_config, ["accounts", "set-password", _EMAIL.upper()], typed)

        assert result.exit_code == 0, result.output
        assert _stored_hash(store) is not None

    def test_two_different_entries_change_nothing(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore
    ) -> None:
        """A confirmation that differs: exit 1, one line, nothing stored."""
        result = _invoke(cli_runner, test_config, ["accounts", "set-password", _EMAIL], "one password\nanother\n")

        assert result.exit_code == 1
        assert "The two passwords differ; nothing was changed." in result.stderr
        assert _stored_hash(store) is None

    def test_an_unknown_email_exits_1_with_the_cli_refusal(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore
    ) -> None:
        """No such account: exit 1 and the ``cli_refusals`` line for ``account.unknown``."""
        typed = f"{_PASSWORD}\n{_PASSWORD}\n"
        result = _invoke(cli_runner, test_config, ["accounts", "set-password", "nobody@example.org"], typed)

        assert result.exit_code == 1
        assert "No account has the e-mail given as EMAIL." in result.stderr.splitlines()
        assert _PASSWORD not in result.output
        assert _stored_hash(store) is None

    def test_the_password_is_never_an_argument(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore
    ) -> None:
        """``--help`` names no password option, and a second argument is refused before any prompt."""
        help_result = _invoke(cli_runner, test_config, ["accounts", "set-password", "--help"])
        extra = _invoke(cli_runner, test_config, ["accounts", "set-password", _EMAIL, _PASSWORD])

        assert help_result.exit_code == 0
        assert "EMAIL" in help_result.stdout
        assert "password" not in help_result.stdout.split("Options")[1].lower()
        assert extra.exit_code == 2
        assert "New password" not in extra.output
        assert _stored_hash(store) is None


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
    """The command speaks the process's language."""

    @pytest.mark.parametrize("language", list(Language))
    def test_one_line_in_each_language(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, language: Language
    ) -> None:
        """The success line and a refusal, each the catalogue's line of the language in use."""
        done = _catalogue_line(language, "cli_accounts", "set_password", "done").replace("{{email}}", _EMAIL)
        unknown = _catalogue_line(language, "cli_refusals", "account", "unknown")
        typed = f"{_PASSWORD}\n{_PASSWORD}\n"
        with use_language(language):
            set_result = _invoke(cli_runner, test_config, ["accounts", "set-password", _EMAIL], typed)
            unknown_result = _invoke(cli_runner, test_config, ["accounts", "set-password", "nobody@example.org"], typed)

        assert set_result.stdout.strip().endswith(done)
        assert unknown in unknown_result.stderr.splitlines()

    def test_the_two_languages_differ(self) -> None:
        """The French lines are not the English ones copied over."""
        for namespace, path in (("cli_accounts", ("set_password", "done")), ("cli_refusals", ("account", "unknown"))):
            assert _catalogue_line(Language.FR, namespace, *path) != _catalogue_line(Language.EN, namespace, *path)
