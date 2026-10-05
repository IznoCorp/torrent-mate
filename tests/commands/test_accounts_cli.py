"""``personalscraper accounts set-password`` — the password door of last resort, on the server.

The password is prompted twice, hidden, and never read from the command line; only its
scrypt hash reaches ``app.db``. Every line the command prints comes from the translation
layer, in the process's language; a refusal of the account service is worded from the
CLI's own ``cli_refusals`` catalogue.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from personalscraper.app.accounts.account_repository import AccountRow, PlexLinkRow
from personalscraper.app.accounts.passwords import verify_password
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.cli import app as cli_app
from personalscraper.conf.isolation import ENVIRONMENT_MARKER
from personalscraper.conf.models.config import Config
from personalscraper.i18n import Language, use_language
from tests.conftest import LoggedEvents

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_EMAIL = "owner@example.org"
_CATALOGUES = Path(__file__).resolve().parents[2] / "personalscraper" / "i18n"
_PASSWORD = "A long fallback password 1!"


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


_OWNER_ARGS = [
    "accounts",
    "create-owner",
    _EMAIL,
    "--name",
    "Owner",
    "--plex-id",
    "4242",
    "--plex-uuid",
    "0f1e2d3c4b5a6978",
    "--plex-username",
    "owner",
]


@pytest.fixture
def dev_data_dir(test_config: Config, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run as ``dev`` on the synthetic config's ``data_dir``, marked for ``dev``.

    Args:
        test_config: The synthetic configuration.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The data directory, where ``app-dev.db`` lives.
    """
    data_dir = test_config.paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / ENVIRONMENT_MARKER).write_text("dev\n", encoding="utf-8")
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    return data_dir


def _accounts_in(db: Path) -> list[AccountRow]:
    """The accounts a store file holds.

    Args:
        db: The store file.

    Returns:
        Its accounts.
    """
    app_store = AppStore(db)
    try:
        return app_store.accounts.accounts()
    finally:
        app_store.close()


class TestCreateOwner:
    """``accounts create-owner`` — the server's owner seeded on an environment's empty ``app.db``."""

    def test_seeds_the_owner_in_the_environments_store(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path
    ) -> None:
        """The environment and the store path come first; two hidden prompts; ``app-dev.db`` holds the owner."""
        typed = f"{_PASSWORD}\n{_PASSWORD}\n"
        result = _invoke(cli_runner, test_config, _OWNER_ARGS, typed)

        assert result.exit_code == 0, result.output
        store_file = dev_data_dir / "app-dev.db"
        lines = result.stdout.splitlines()
        assert lines[0] == "Environment: dev"
        assert lines[1] == f"App store: {store_file}"
        assert result.stdout.count("Owner's password") == 1
        assert result.stdout.count("Repeat the owner's password") == 1
        assert _PASSWORD not in result.output
        assert lines[-1].startswith(f"Owner {_EMAIL} created")
        assert not (dev_data_dir / "app.db").exists()
        (account,) = _accounts_in(store_file)
        assert account.email == _EMAIL and account.role_id == "admin"
        assert account.password_hash is not None and verify_password(_PASSWORD, account.password_hash)

    def test_two_different_entries_create_nothing(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path
    ) -> None:
        """A confirmation that differs: exit 1, the mismatch line, no store opened."""
        result = _invoke(cli_runner, test_config, _OWNER_ARGS, "one password\nanother\n")

        assert result.exit_code == 1
        assert "The two passwords differ; nothing was changed." in result.stderr
        assert not (dev_data_dir / "app-dev.db").exists()

    @pytest.mark.parametrize("value", ["", "prod"])
    def test_production_is_refused(
        self, cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Under production: exit 1 before any prompt, no store created.

        Args:
            cli_runner: The runner.
            test_config: The synthetic configuration.
            monkeypatch: Pytest monkeypatch fixture.
            value: ``PERSONALSCRAPER_ENV``, empty or ``prod``.
        """
        monkeypatch.setenv("PERSONALSCRAPER_ENV", value)

        result = _invoke(cli_runner, test_config, _OWNER_ARGS, f"{_PASSWORD}\n{_PASSWORD}\n")

        assert result.exit_code == 1
        assert _catalogue_line(Language.EN, "cli_accounts", "create_owner", "refused_prod") in result.stderr
        assert "Owner's password" not in result.output
        assert not (test_config.paths.data_dir / "app.db").exists()

    @pytest.mark.parametrize("language", list(Language))
    def test_a_second_owner_is_refused_and_the_store_untouched(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path, language: Language
    ) -> None:
        """The owner already seeded: exit 1, the command's own line in the language in use, the store as it was.

        Args:
            cli_runner: The runner.
            test_config: The synthetic configuration.
            dev_data_dir: The marked ``dev`` data directory.
            language: The process's language.
        """
        typed = f"{_PASSWORD}\n{_PASSWORD}\n"
        _invoke(cli_runner, test_config, _OWNER_ARGS, typed)
        store_file = dev_data_dir / "app-dev.db"
        before = _accounts_in(store_file)
        other = [*_OWNER_ARGS[:2], "other@example.org", *_OWNER_ARGS[3:]]

        with use_language(language):
            result = _invoke(cli_runner, test_config, other, typed)

        assert result.exit_code == 1
        refusal = _catalogue_line(language, "cli_accounts", "create_owner", "owner_exists")
        assert refusal in result.stderr.splitlines()
        assert _PASSWORD not in result.output
        assert _accounts_in(store_file) == before

    def test_the_password_is_never_an_argument(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path
    ) -> None:
        """``--help`` names no password option; ``--password`` and an extra argument are refused before any prompt."""
        help_result = _invoke(cli_runner, test_config, ["accounts", "create-owner", "--help"])
        option = _invoke(cli_runner, test_config, [*_OWNER_ARGS, "--password", _PASSWORD])
        extra = _invoke(cli_runner, test_config, [*_OWNER_ARGS, _PASSWORD])

        assert help_result.exit_code == 0
        assert "password" not in help_result.stdout.split("Options")[1].lower()
        for refused in (option, extra):
            assert refused.exit_code == 2
            assert "Owner's password" not in refused.output
        assert not (dev_data_dir / "app-dev.db").exists()

    def test_the_lines_exist_in_both_languages(self) -> None:
        """Every line of the command is worded in French and English, and they differ."""
        catalogue = json.loads((_CATALOGUES / "en" / "cli_accounts.json").read_text(encoding="utf-8"))
        for key in catalogue["create_owner"]:
            assert _catalogue_line(Language.FR, "cli_accounts", "create_owner", key) != _catalogue_line(
                Language.EN, "cli_accounts", "create_owner", key
            ), key


class TestPasswordPolicy:
    """Both CLI doors hold a password to the policy every local door applies (the operator, 2026-10-04)."""

    @pytest.mark.parametrize("language", list(Language))
    @pytest.mark.parametrize(
        ("weak", "code"),
        [("Short 1!", "too_short"), ("a long fallback password", "too_weak")],
        ids=["too-short", "too-weak"],
    )
    def test_set_password_refuses_a_password_breaking_the_policy(
        self, cli_runner: CliRunner, test_config: Config, store: AppStore, language: Language, weak: str, code: str
    ) -> None:
        """Exit 1, the ``cli_refusals`` line naming the minimum in the language in use, nothing stored."""
        line = _catalogue_line(language, "cli_refusals", "password", code).replace("{{minimum}}", "12")
        with use_language(language):
            result = _invoke(cli_runner, test_config, ["accounts", "set-password", _EMAIL], f"{weak}\n{weak}\n")

        assert result.exit_code == 1
        assert line in result.stderr.splitlines()
        assert weak not in result.output
        assert _stored_hash(store) is None

    @pytest.mark.parametrize(
        ("weak", "code"),
        [("Short 1!", "too_short"), ("a long fallback password", "too_weak")],
        ids=["too-short", "too-weak"],
    )
    def test_create_owner_refuses_a_password_breaking_the_policy(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path, weak: str, code: str
    ) -> None:
        """Exit 1, the ``cli_refusals`` line, and no owner created."""
        line = _catalogue_line(Language.EN, "cli_refusals", "password", code).replace("{{minimum}}", "12")
        with use_language(Language.EN):
            result = _invoke(cli_runner, test_config, _OWNER_ARGS, f"{weak}\n{weak}\n")

        assert result.exit_code == 1
        assert line in result.stderr.splitlines()
        assert weak not in result.output
        store_file = dev_data_dir / "app-dev.db"
        assert not store_file.exists() or _accounts_in(store_file) == []

    def test_the_policy_lines_differ_between_the_languages(self) -> None:
        """The French policy line is not the English one copied over."""
        assert _catalogue_line(Language.FR, "cli_refusals", "password", "too_weak") != _catalogue_line(
            Language.EN, "cli_refusals", "password", "too_weak"
        )


def _seed_owner(db: Path, *, allowed: bool = True, owner_link: bool = True) -> str:
    """Seed an Admin account in a store file, linked as the Plex server's owner unless told not to.

    Args:
        db: The store file.
        allowed: Whether the account may sign in.
        owner_link: Whether the account is linked as the server's owner.

    Returns:
        The account's key.
    """
    app_store = AppStore(db)
    try:
        repo = app_store.accounts
        repo.insert_account(
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
        if owner_link:
            repo.upsert_plex_link(
                PlexLinkRow(
                    account_id="account-owner",
                    plex_id=4242,
                    plex_uuid="0f1e2d3c4b5a6978",
                    plex_username="owner",
                    server_access="owner",
                    token_ciphertext=None,
                    token_stored_at=None,
                    linked_at=1.0,
                    last_sign_in_at=None,
                )
            )
        if not allowed:
            repo.set_sign_in_allowed("account-owner", allowed=False, now=2.0)
    finally:
        app_store.close()
    return "account-owner"


def _session_user_agents(db: Path) -> list[str]:
    """The user agent of every session row a store file holds.

    Args:
        db: The store file.

    Returns:
        One user agent per session row, in creation order.
    """
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return [row[0] for row in connection.execute("SELECT user_agent FROM session ORDER BY id")]
    finally:
        connection.close()


_OPEN_SESSION_ARGS = ["accounts", "open-session", "--owner"]


class TestOpenSession:
    """``accounts open-session --owner`` — the design host's smoke check signs in with no stored secret."""

    @pytest.mark.parametrize("value", ["", "prod"])
    def test_production_is_refused(
        self, cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """Under production: exit 1, the command's refusal line, nothing on stdout, no store created.

        Args:
            cli_runner: The runner.
            test_config: The synthetic configuration.
            monkeypatch: Pytest monkeypatch fixture.
            value: ``PERSONALSCRAPER_ENV``, empty or ``prod``.
        """
        monkeypatch.setenv("PERSONALSCRAPER_ENV", value)

        result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code == 1
        assert _catalogue_line(Language.EN, "cli_accounts", "open_session", "refused_prod") in result.stderr
        assert result.stdout == ""
        assert not (test_config.paths.data_dir / "app.db").exists()

    def test_staging_is_refused(
        self, cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dev only: preprod holds a full owner session, so ``staging`` is refused with its own line, no store created.

        Args:
            cli_runner: The runner.
            test_config: The synthetic configuration.
            monkeypatch: Pytest monkeypatch fixture.
        """
        monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")

        result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code == 1
        assert _catalogue_line(Language.EN, "cli_accounts", "open_session", "refused_not_dev") in result.stderr
        assert result.stdout == ""
        assert not (test_config.paths.data_dir / "app-staging.db").exists()

    def test_an_unknown_environment_is_refused(
        self, cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail closed: a value that is no environment opens nothing, whatever refuses it.

        Args:
            cli_runner: The runner.
            test_config: The synthetic configuration.
            monkeypatch: Pytest monkeypatch fixture.
        """
        monkeypatch.setenv("PERSONALSCRAPER_ENV", "bogus")

        result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code != 0
        assert result.stdout == ""

    @pytest.mark.usefixtures("kept_log_capture")
    def test_dev_prints_a_token_the_session_service_accepts(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path, logged_events: LoggedEvents
    ) -> None:
        """The token alone on stdout; it resolves to the owner; the journal names the account, never the token."""
        store_file = dev_data_dir / "app-dev.db"
        owner_id = _seed_owner(store_file)

        with logged_events() as events:
            result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code == 0, result.output
        token = result.stdout.strip()
        assert token and result.stdout == f"{token}\n"
        app_store = AppStore(store_file)
        try:
            actor = SessionService(app_store, idle_days=30).resolve(token)
        finally:
            app_store.close()
        assert actor is not None and actor.account_id == owner_id
        # The row the command opened says who opened it: the smoke check's own user agent.
        assert _session_user_agents(store_file) == ["design-host-smoke"]
        opened = [event for event in events if event["event"] == "v1_session_opened_by_cli"]
        assert opened == [{"event": "v1_session_opened_by_cli", "account_id": owner_id, "log_level": "info"}]
        assert all(token not in repr(event) for event in events)

    @pytest.mark.usefixtures("kept_log_capture")
    def test_the_token_is_never_in_the_log(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Whatever the logger, no record carries the token, and stderr does not either."""
        _seed_owner(dev_data_dir / "app-dev.db")
        caplog.set_level(logging.DEBUG)

        result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code == 0, result.output
        token = result.stdout.strip()
        # The capture saw the run: an empty one would prove nothing.
        events = [record.msg.get("event") for record in caplog.records if isinstance(record.msg, dict)]
        assert "v1_signed_in" in events
        assert token not in caplog.text
        assert all(token not in repr(record.msg) for record in caplog.records)
        assert token not in result.stderr

    @pytest.mark.parametrize("language", list(Language))
    def test_a_cut_owner_is_refused(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path, language: Language
    ) -> None:
        """The owner's access cut in the store: exit 1, the ``auth.access_disabled`` line, no session opened.

        Args:
            cli_runner: The runner.
            test_config: The synthetic configuration.
            dev_data_dir: The marked ``dev`` data directory.
            language: The process's language.
        """
        store_file = dev_data_dir / "app-dev.db"
        _seed_owner(store_file, allowed=False)
        sessions_before = len(_session_user_agents(store_file))

        with use_language(language):
            result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code == 1
        assert _catalogue_line(language, "cli_refusals", "auth", "access_disabled") in result.stderr.splitlines()
        assert result.stdout == ""
        assert len(_session_user_agents(store_file)) == sessions_before

    @pytest.mark.parametrize("owner_link", [True, False], ids=["empty-store", "admin-without-owner-link"])
    def test_no_owner_exits_1(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path, owner_link: bool
    ) -> None:
        """No account linked as the server's owner: exit 1, the command's line, nothing on stdout.

        Args:
            cli_runner: The runner.
            test_config: The synthetic configuration.
            dev_data_dir: The marked ``dev`` data directory.
            owner_link: ``False`` seeds an Admin with no owner link; ``True`` seeds nothing.
        """
        if not owner_link:
            _seed_owner(dev_data_dir / "app-dev.db", owner_link=False)

        result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code == 1
        assert _catalogue_line(Language.EN, "cli_accounts", "open_session", "no_owner") in result.stderr.splitlines()
        assert result.stdout == ""

    def test_several_owner_links_are_refused(
        self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path
    ) -> None:
        """Two accounts linked as the owner: exit 1, the ambiguity line, nothing on stdout, no session opened."""
        store_file = dev_data_dir / "app-dev.db"
        _seed_owner(store_file)
        app_store = AppStore(store_file)
        try:
            repo = app_store.accounts
            repo.insert_account(
                AccountRow(
                    id="account-former-owner",
                    name="Former owner",
                    email="former@example.test",
                    avatar="",
                    role_id="admin",
                    password_hash=None,
                    created_at=1.0,
                    updated_at=1.0,
                )
            )
            repo.upsert_plex_link(
                PlexLinkRow(
                    account_id="account-former-owner",
                    plex_id=4343,
                    plex_uuid="1a2b3c4d5e6f7089",
                    plex_username="former",
                    server_access="owner",
                    token_ciphertext=None,
                    token_stored_at=None,
                    linked_at=2.0,
                    last_sign_in_at=None,
                )
            )
        finally:
            app_store.close()

        result = _invoke(cli_runner, test_config, _OPEN_SESSION_ARGS)

        assert result.exit_code == 1
        assert _catalogue_line(Language.EN, "cli_accounts", "open_session", "ambiguous_owner") in result.stderr
        assert result.stdout == ""
        assert _session_user_agents(store_file) == []

    def test_the_owner_flag_is_required(self, cli_runner: CliRunner, test_config: Config, dev_data_dir: Path) -> None:
        """Without ``--owner``: exit 2, the command's line, no session opened."""
        _seed_owner(dev_data_dir / "app-dev.db")

        result = _invoke(cli_runner, test_config, ["accounts", "open-session"])

        assert result.exit_code == 2
        assert _catalogue_line(Language.EN, "cli_accounts", "open_session", "owner_required") in result.stderr
        assert result.stdout == ""

    def test_the_lines_exist_in_both_languages(self) -> None:
        """Every line of the command is worded in French and English, and they differ."""
        catalogue = json.loads((_CATALOGUES / "en" / "cli_accounts.json").read_text(encoding="utf-8"))
        for key in catalogue["open_session"]:
            assert _catalogue_line(Language.FR, "cli_accounts", "open_session", key) != _catalogue_line(
                Language.EN, "cli_accounts", "open_session", key
            ), key
