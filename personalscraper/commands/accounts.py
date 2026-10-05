"""Accounts command group — ``personalscraper accounts``.

The server's own hand on this environment's ``app.db``: what no web operation may do.
``set-password`` is the password door of last resort — the Plex server owner's fallback
password is set here and nowhere else. A password is typed at a hidden prompt, twice, and
is never an argument (a shell's history and ``ps`` would keep it). ``open-session --owner``
opens the server owner's session with no password, outside production only, for the design
host's smoke check: the token is printed alone on stdout and never logged. ``token-key rotate``,
``token forget`` and ``token purge-undecryptable`` manage the Plex tokens a sign-in keeps,
under the keys of ``PLEX_TOKEN_KEYS`` — read from the environment only, never from an
argument. Every line goes through the translation layer; a refusal of the account service
is worded from ``cli_refusals``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, NoReturn

import typer

from personalscraper.app.accounts.service import AmbiguousOwner, OwnerAlreadySeeded, OwnerPlexIdentity
from personalscraper.app.accounts.token_vault import (
    MalformedTokenKey,
    NoKeptTokenOpens,
    TokenVault,
    forget_kept_tokens,
    purge_undecryptable,
    rotate_kept_tokens,
)
from personalscraper.app.composition import build_app_services
from personalscraper.app.errors import AppRefusal, RefusalCode
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.conf.environment import Environment, StoreName, current_environment, store_path
from personalscraper.config import get_settings
from personalscraper.core.event_bus import EventBus
from personalscraper.i18n import t, t_code
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("commands.accounts")

#: The user agent kept on a session this command opens, naming its one caller.
_SMOKE_USER_AGENT = "design-host-smoke"

accounts_app = typer.Typer(name="accounts", help=t("cli_accounts.help"), no_args_is_help=True)
token_key_app = typer.Typer(name="token-key", help=t("cli_accounts.token_key.help"), no_args_is_help=True)
token_app = typer.Typer(name="token", help=t("cli_accounts.token.help"), no_args_is_help=True)
accounts_app.add_typer(token_key_app, name="token-key")
accounts_app.add_typer(token_app, name="token")


@accounts_app.command("set-password", help=t("cli_accounts.set_password.help"))
@handle_cli_errors
def set_password(
    ctx: typer.Context,
    email: str = typer.Argument(..., metavar="EMAIL", help=t("cli_accounts.set_password.email_help")),
) -> None:
    """Set an account's password, typed twice at a hidden prompt.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        email: The account's e-mail, whatever its case.

    Raises:
        typer.Exit: Code 1 when the two entries differ or the account service refuses.
    """
    config: Config = ctx.obj.config
    assert config is not None

    password = typer.prompt(t("cli_accounts.set_password.prompt"), hide_input=True)
    repeated = typer.prompt(t("cli_accounts.set_password.confirm"), hide_input=True)
    if password != repeated:
        typer.echo(t("cli_accounts.set_password.mismatch"), err=True)
        raise typer.Exit(code=1)

    services = build_app_services(config, get_settings(), event_bus=EventBus())
    try:
        services.accounts.set_password(email, password)
    except AppRefusal as exc:
        _refuse(exc)
    finally:
        services.close()
    typer.echo(t("cli_accounts.set_password.done", email=email))


@accounts_app.command("create-owner", help=t("cli_accounts.create_owner.help"))
@handle_cli_errors
def create_owner(
    ctx: typer.Context,
    email: str = typer.Argument(..., metavar="EMAIL", help=t("cli_accounts.create_owner.email_help")),
    name: str = typer.Option(..., "--name", help=t("cli_accounts.create_owner.name_help")),
    plex_id: int = typer.Option(..., "--plex-id", help=t("cli_accounts.create_owner.plex_id_help")),
    plex_uuid: str = typer.Option(..., "--plex-uuid", help=t("cli_accounts.create_owner.plex_uuid_help")),
    plex_username: str = typer.Option(..., "--plex-username", help=t("cli_accounts.create_owner.plex_username_help")),
) -> None:
    """Seed the Plex server's owner: an Admin account with a fallback password, linked as the owner.

    Refused under production. The environment and the store it writes come first, so the
    operator sees where the account lands before typing the password, twice, hidden.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        email: The owner's e-mail.
        name: The display name.
        plex_id: The owner's plex.tv id.
        plex_uuid: The owner's plex.tv uuid.
        plex_username: The owner's plex.tv username.

    Raises:
        typer.Exit: Code 1 under production, when the two entries differ, when the owner
            is already an account, or when the account service refuses.
    """
    config: Config = ctx.obj.config
    assert config is not None

    environment = current_environment()
    if environment is Environment.PROD:
        typer.echo(t("cli_accounts.create_owner.refused_prod"), err=True)
        raise typer.Exit(code=1)
    typer.echo(t("cli_accounts.create_owner.environment", environment=environment.value))
    typer.echo(
        t("cli_accounts.create_owner.store", path=str(store_path(config.paths.data_dir, StoreName.APP, environment)))
    )

    password = typer.prompt(t("cli_accounts.create_owner.prompt"), hide_input=True)
    repeated = typer.prompt(t("cli_accounts.create_owner.confirm"), hide_input=True)
    if password != repeated:
        typer.echo(t("cli_accounts.set_password.mismatch"), err=True)
        raise typer.Exit(code=1)

    plex = OwnerPlexIdentity(plex_id=plex_id, plex_uuid=plex_uuid, plex_username=plex_username)
    services = build_app_services(config, get_settings(), event_bus=EventBus())
    try:
        services.accounts.create_owner(email=email, name=name, password=password, plex=plex)
    except OwnerAlreadySeeded:
        typer.echo(t("cli_accounts.create_owner.owner_exists"), err=True)
        raise typer.Exit(code=1) from None
    except AppRefusal as exc:
        _refuse(exc)
    finally:
        services.close()
    typer.echo(t("cli_accounts.create_owner.done", email=email))


@accounts_app.command("open-session", help=t("cli_accounts.open_session.help"))
@handle_cli_errors
def open_session(
    ctx: typer.Context,
    owner: bool = typer.Option(False, "--owner", help=t("cli_accounts.open_session.owner_help")),
) -> None:
    """Open a session for the Plex server's owner, with no password, and print its token alone on stdout.

    Dev only: every other environment is refused, preprod included, where it would be a full
    owner session. The session is opened through the same proven-session step
    every sign-in door ends in, so a cut owner is refused like anywhere else. The token is
    printed once and never logged: the journal names the account only. Whoever runs this can
    already read the environment's ``app.db``, so it opens nothing they could not reach.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        owner: Open the owner's session, the only one this command opens.

    Raises:
        typer.Exit: Code 2 without ``--owner``; code 1 outside ``dev``, when no account
            is linked as the owner, when several are, or when the account service refuses (a cut owner).
    """
    config: Config = ctx.obj.config
    assert config is not None

    # The flag names whose session opens, so a later account option never changes what a bare call does.
    if not owner:
        typer.echo(t("cli_accounts.open_session.owner_required"), err=True)
        raise typer.Exit(code=2)
    environment = current_environment()
    # Fail closed: only an explicit ``dev`` opens a session; preprod holds a full owner session, so it is refused too.
    if environment is not Environment.DEV:
        line = "refused_prod" if environment is Environment.PROD else "refused_not_dev"
        typer.echo(t(f"cli_accounts.open_session.{line}"), err=True)
        raise typer.Exit(code=1)

    services = build_app_services(config, get_settings(), event_bus=EventBus())
    try:
        owner_id = services.accounts.owner_account_id()
        if owner_id is None:
            typer.echo(t("cli_accounts.open_session.no_owner"), err=True)
            raise typer.Exit(code=1)
        result = services.accounts.open_proven_session(owner_id, user_agent=_SMOKE_USER_AGENT)
    except AmbiguousOwner:
        typer.echo(t("cli_accounts.open_session.ambiguous_owner"), err=True)
        raise typer.Exit(code=1) from None
    except AppRefusal as exc:
        _refuse(exc)
    finally:
        services.close()
    log.info("v1_session_opened_by_cli", account_id=owner_id)
    typer.echo(result.session_token)


def _refuse(exc: AppRefusal) -> NoReturn:
    """Word an account service refusal from ``cli_refusals`` and exit.

    Args:
        exc: The refusal.

    Raises:
        typer.Exit: Code 1, always.
    """
    code = exc.code if exc.code is not None else RefusalCode.INTERNAL
    # A list fact (``right.missing``'s rights) is never a placeholder: only scalars are passed.
    params: dict[str, Any] = {name: value for name, value in exc.params.items() if isinstance(value, (str, int, float))}
    typer.echo(t_code("cli_refusals", code, **params), err=True)
    raise typer.Exit(code=1) from None


def _vault() -> TokenVault:
    """Build the vault from ``PLEX_TOKEN_KEYS``, or say why not and exit.

    Returns:
        The vault.

    Raises:
        typer.Exit: Code 1 when no key is set or one is malformed (named by its position).
    """
    try:
        vault = TokenVault.from_settings(get_settings())
    except MalformedTokenKey as exc:
        typer.echo(t("cli_accounts.token.keys_malformed", position=exc.position), err=True)
        raise typer.Exit(code=1) from None
    if vault is None:
        typer.echo(t("cli_accounts.token.keys_missing"), err=True)
        raise typer.Exit(code=1)
    return vault


@token_key_app.command("rotate", help=t("cli_accounts.token_key.rotate.help"))
@handle_cli_errors
def rotate_token_key(ctx: typer.Context) -> None:
    """Re-seal every kept Plex token under the first key of ``PLEX_TOKEN_KEYS``.

    A row no key opens is left as it is and warned about: it will not open once the old key
    is dropped.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.

    Raises:
        typer.Exit: Code 1 with fewer than two keys, or a malformed one.
    """
    config: Config = ctx.obj.config
    assert config is not None

    vault = _vault()
    # One key re-seals under itself: the operator meant to put the new key first.
    if vault.key_count < 2:
        typer.echo(t("cli_accounts.token_key.rotate.needs_two"), err=True)
        raise typer.Exit(code=1)
    services = build_app_services(config, get_settings(), event_bus=EventBus())
    try:
        result = rotate_kept_tokens(services.app_store.accounts, vault, now=time.time())
    finally:
        services.close()
    typer.echo(t("cli_accounts.token_key.rotate.done", count=result.rotated))
    if result.skipped:
        typer.echo(t("cli_accounts.token_key.rotate.skipped", count=result.skipped), err=True)


@token_app.command("forget", help=t("cli_accounts.token.forget.help"))
@handle_cli_errors
def forget_token(
    ctx: typer.Context,
    email: str | None = typer.Argument(None, metavar="EMAIL", help=t("cli_accounts.token.forget.email_help")),
    every: bool = typer.Option(False, "--all", help=t("cli_accounts.token.forget.all_help")),
) -> None:
    """Forget one account's kept Plex token, or every one with ``--all``.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        email: The account's e-mail, whatever its case; ``None`` with ``--all``.
        every: Forget every kept token.

    Raises:
        typer.Exit: Code 2 unless exactly one of ``EMAIL`` and ``--all`` is given; code 1
            when no account has the e-mail.
    """
    config: Config = ctx.obj.config
    assert config is not None

    if (email is None) == (not every):
        typer.echo(t("cli_accounts.token.forget.target_required"), err=True)
        raise typer.Exit(code=2)
    # Forgetting reads no token, so it needs no key: it still works once a key is lost.
    services = build_app_services(config, get_settings(), event_bus=EventBus())
    try:
        repo = services.app_store.accounts
        account_id: str | None = None
        if email is not None:
            account = repo.account_by_email(email)
            if account is None:
                typer.echo(t_code("cli_refusals", RefusalCode.ACCOUNT_UNKNOWN), err=True)
                raise typer.Exit(code=1)
            account_id = account.id
        count = forget_kept_tokens(repo, account_id=account_id)
    finally:
        services.close()
    typer.echo(t("cli_accounts.token.forget.done", count=count))


@token_app.command("purge-undecryptable", help=t("cli_accounts.token.purge.help"))
@handle_cli_errors
def purge_undecryptable_tokens(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help=t("cli_accounts.token.purge.force_help")),
) -> None:
    """Clear every kept Plex token no key of ``PLEX_TOKEN_KEYS`` opens for its own account.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.
        force: Clear the tokens even when none opens (the keys are probably wrong).

    Raises:
        typer.Exit: Code 1 when no key is set (every token would read as undecryptable:
            ``token forget --all`` does that on purpose), one is malformed, or no kept
            token opens under the keys and ``--force`` is not given.
    """
    config: Config = ctx.obj.config
    assert config is not None

    vault = _vault()
    services = build_app_services(config, get_settings(), event_bus=EventBus())
    try:
        count = purge_undecryptable(services.app_store.accounts, vault, now=time.time(), force=force)
    except NoKeptTokenOpens:
        typer.echo(t("cli_accounts.token.purge.none_opens"), err=True)
        raise typer.Exit(code=1) from None
    finally:
        services.close()
    typer.echo(t("cli_accounts.token.purge.done", count=count))
