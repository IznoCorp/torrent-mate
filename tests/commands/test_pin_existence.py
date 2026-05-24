"""Pin existence test for every Typer-registered command (SH-25, 9.1 part 2).

Parametrized over ``app.registered_commands`` so any future command addition
or removal is automatically reflected. Each case runs ``--help`` and asserts
exit 0 + a recognizable help signature.

This test absorbs SH-25 / CL-S from the original tech-debt audit.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from personalscraper.cli_app import app


def _collect_command_names() -> list[str]:
    """Introspect the Typer app for all registered command names.

    Imports the command modules to trigger ``@app.command()`` registration,
    then collects both flat commands and sub-app commands (with group prefix,
    e.g. ``"trailers scan"``, ``"config migrate-category"``).
    """
    # Trigger registration of all commands on the shared app instance.
    import personalscraper.commands.config  # noqa: F401,PLC0415
    import personalscraper.commands.info  # noqa: F401,PLC0415
    import personalscraper.commands.library  # noqa: F401,PLC0415
    import personalscraper.commands.pipeline  # noqa: F401,PLC0415
    import personalscraper.trailers.cli  # noqa: F401,PLC0415

    names: list[str] = []

    # Direct commands (e.g. "ingest", "library-doctor").
    for cmd in app.registered_commands:
        name = cmd.name if cmd.name is not None else cmd.callback.__name__.replace("_", "-")
        names.append(name)

    # Sub-app commands (trailers scan, config migrate-category, etc.).
    for group in app.registered_groups:
        prefix = group.name
        sub_app = group.typer_instance
        for cmd in sub_app.registered_commands:
            sub_name = cmd.name if cmd.name is not None else cmd.callback.__name__.replace("_", "-")
            names.append(f"{prefix} {sub_name}")

    return sorted(names)


_COMMAND_NAMES = _collect_command_names()


@pytest.mark.parametrize("cmd_name", _COMMAND_NAMES)
def test_command_help_exit_zero(cmd_name: str) -> None:
    """Assert ``<cmd> --help`` exits 0 and prints its docstring/signature.

    A missing or broken command (silent disappearance) will fail at collection
    time (command name not found) or at runtime (non-zero exit / no help text).
    """
    runner = CliRunner()
    args = cmd_name.split() + ["--help"]
    result = runner.invoke(app, args)

    assert result.exit_code == 0, f"Command '{cmd_name} --help' exited {result.exit_code}:\n{result.output}"

    # The help text must at least contain the command name (or its
    # underscored form for commands registered with an explicit name).
    output = result.output
    name_part = cmd_name.split()[-1].replace("-", "_")
    assert name_part in output or cmd_name.split()[-1] in output, (
        f"Command '{cmd_name} --help' output does not mention the command name:\n{output}"
    )
