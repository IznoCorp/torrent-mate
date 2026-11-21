"""Report the provider ids that two or more follows hold (``acquisition-follow-duplicates``).

Read only: opens ``acquire.db`` ``query_only`` (never migrated, never created) and prints
one record per shared id (provider, id, the rowids of the follows holding it, oldest
first) and the totals. Nothing is merged or deleted: what becomes of a duplicate is the
operator's decision, and this report is its measure.

Examples:
    personalscraper acquisition-follow-duplicates
    personalscraper --format json acquisition-follow-duplicates --db /path/to/acquire-copy.db
"""

from __future__ import annotations

from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.i18n import t


@app.command("acquisition-follow-duplicates", help=t("cli_acquisition.follow_duplicates.command_help"))
@handle_cli_errors
def acquisition_follow_duplicates(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", "-c", help=t("cli_acquisition.follow_duplicates.config_help")),
    db: Path | None = typer.Option(None, "--db", help=t("cli_acquisition.follow_duplicates.db_help")),
) -> None:
    """Report the provider ids held by two or more ``followed_series`` rows.

    Read only. The output carries codes and counts: per shared id the provider, the id
    and the ``followed_ids`` holding it; then ``groups`` (shared ids) and ``follows``
    (distinct rows involved).

    Args:
        ctx: Typer context carrying the loaded configuration.
        config: Path of the configuration, when the context carries none.
        db: The ``acquire.db`` to read, overriding the configured one.

    Raises:
        typer.Exit: Exit code 1 when no store is configured or the file does not exist.
    """
    from personalscraper.acquire.follow_duplicates import find_follow_duplicates, open_follows_read_only
    from personalscraper.conf.loader import load_config

    if db is not None:
        db_path = db
    else:
        cfg = ctx.obj.config if ctx.obj is not None else load_config(config)
        if cfg.acquire.db_path is None:
            typer.echo(t("cli_acquisition.follow_duplicates.db_path_not_configured"), err=True)
            raise typer.Exit(code=1)
        db_path = Path(cfg.acquire.db_path)

    if not db_path.is_file():
        typer.echo(t("cli_acquisition.follow_duplicates.db_not_found", path=str(db_path)), err=True)
        raise typer.Exit(code=1)

    with open_follows_read_only(db_path) as follows:
        groups = find_follow_duplicates(follows)

    emit(
        {
            "groups": len(groups),
            "follows": len({followed_id for group in groups for followed_id in group.followed_ids}),
            "duplicates": [
                {"provider": group.provider, "provider_id": group.provider_id, "followed_ids": list(group.followed_ids)}
                for group in groups
            ],
        }
    )
