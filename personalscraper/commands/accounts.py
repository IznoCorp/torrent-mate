"""Accounts command group — ``personalscraper accounts``.

The server's own hand on this environment's ``app.db``: what no web operation may do.
``set-password`` is the password door of last resort — the Plex server owner's fallback
password is set here and nowhere else. A password is typed at a hidden prompt, twice, and
is never an argument (a shell's history and ``ps`` would keep it). Every line goes through
the translation layer; a refusal of the account service is worded from ``cli_refusals``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer

from personalscraper.app.composition import build_app_services
from personalscraper.app.errors import AppRefusal, RefusalCode
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.config import get_settings
from personalscraper.i18n import t, t_code

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

accounts_app = typer.Typer(name="accounts", help=t("cli_accounts.help"), no_args_is_help=True)


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
