"""Accounts command group — ``personalscraper accounts``.

The server's own hand on this environment's ``app.db``: what no web operation may do.
``set-password`` is the password door of last resort — the Plex server owner's fallback
password is set here and nowhere else. A password is typed at a hidden prompt, twice, and
is never an argument (a shell's history and ``ps`` would keep it). ``token-key rotate``,
``token forget`` and ``token purge-undecryptable`` manage the Plex tokens a sign-in keeps,
under the keys of ``PLEX_TOKEN_KEYS`` — read from the environment only, never from an
argument. Every line goes through the translation layer; a refusal of the account service
is worded from ``cli_refusals``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import typer

from personalscraper.app.accounts.token_vault import (
    MalformedTokenKey,
    TokenVault,
    forget_kept_tokens,
    purge_undecryptable,
    rotate_kept_tokens,
)
from personalscraper.app.composition import build_app_services
from personalscraper.app.errors import AppRefusal, RefusalCode
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.config import get_settings
from personalscraper.i18n import t, t_code

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

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

    services = build_app_services(config, get_settings())
    try:
        services.accounts.set_password(email, password)
    except AppRefusal as exc:
        code = exc.code if exc.code is not None else RefusalCode.INTERNAL
        # A list fact (``right.missing``'s rights) is never a placeholder: only scalars are passed.
        params: dict[str, Any] = {
            name: value for name, value in exc.params.items() if isinstance(value, (str, int, float))
        }
        typer.echo(t_code("cli_refusals", code, **params), err=True)
        raise typer.Exit(code=1) from None
    finally:
        services.close()
    typer.echo(t("cli_accounts.set_password.done", email=email))


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
    services = build_app_services(config, get_settings())
    try:
        count = rotate_kept_tokens(services.app_store.accounts, vault, now=time.time())
    finally:
        services.close()
    typer.echo(t("cli_accounts.token_key.rotate.done", count=count))


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
    services = build_app_services(config, get_settings())
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
def purge_undecryptable_tokens(ctx: typer.Context) -> None:
    """Clear every kept Plex token no key of ``PLEX_TOKEN_KEYS`` opens for its own account.

    Args:
        ctx: Typer context carrying the loaded ``Config`` on ``ctx.obj``.

    Raises:
        typer.Exit: Code 1 when no key is set (every token would read as undecryptable:
            ``token forget --all`` does that on purpose), or one is malformed.
    """
    config: Config = ctx.obj.config
    assert config is not None

    vault = _vault()
    services = build_app_services(config, get_settings())
    try:
        count = purge_undecryptable(services.app_store.accounts, vault, now=time.time())
    finally:
        services.close()
    typer.echo(t("cli_accounts.token.purge.done", count=count))
