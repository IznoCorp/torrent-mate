"""Tests for the maintenance action registry (sub-phase 1.2).

Covers:
1. Completeness — registry IDs match Typer-registered ``library-*`` commands.
2. Uniqueness — no duplicate ``id`` values.
3. Option-flag validity — every ``options[].name`` maps to a real CLI flag.
4. Destructive → dry-run invariant — every ``risk='destructive'`` action has
   ``dry_run='supported'``.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path
from typing import cast

import pytest

# Import the library commands package to register all @app.command callbacks.
import personalscraper.commands.library  # noqa: F401 — triggers @app.command registration
from personalscraper.cli_app import app
from personalscraper.web.maintenance.registry import REGISTRY

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kebab(name: str) -> str:
    """Convert a snake_case function name to its kebab-case CLI name.

    The Typer ``@app.command`` decorator with an explicit ``name`` argument
    takes precedence; this function handles the common case where the CLI
    name is derived from the function name by replacing underscores with
    hyphens (Typer's default).

    Args:
        name: Function name (snake_case), e.g. ``"library_ghost_audit"``.

    Returns:
        Kebab-case name, e.g. ``"library-ghost-audit"``.
    """
    return name.replace("_", "-")


def _get_cli_command_names() -> set[str]:
    """Return the set of ``library-*`` command names registered on the Typer app.

    Introspects ``app.registered_commands``, deriving each CLI name from
    ``command.name`` (explicit ``@app.command("name")``) or the kebab-cased
    callback ``__name__`` (Typer default).

    Returns:
        Set of strings like ``{"library-status", "library-search", ...}``.
    """
    names: set[str] = set()
    for cmd in app.registered_commands:
        if cmd.name is not None:
            cli_name = cmd.name
        elif cmd.callback is not None:
            cli_name = _kebab(cmd.callback.__name__)
        else:
            continue
        if cli_name.startswith("library-"):
            names.add(cli_name)
    return names


def _source_file_for_command(cli_name: str) -> Path:
    """Find the source file for a library-* command via its Typer callback.

    Uses ``callback.__module__`` to locate the defining module (not the
    re-exporting ``__init__.py``), then resolves ``module.__file__``.

    Args:
        cli_name: Kebab-case CLI name, e.g. ``"library-index"``.

    Returns:
        Absolute ``Path`` to the ``.py`` file that defines the callback.

    Raises:
        ValueError: If the command is not registered or its source file
            cannot be determined.
    """
    for cmd in app.registered_commands:
        resolved = cmd.name if cmd.name is not None else (_kebab(cmd.callback.__name__) if cmd.callback else None)
        if resolved == cli_name and cmd.callback is not None:
            mod = importlib.import_module(cmd.callback.__module__)
            src = mod.__file__
            if src is None:
                raise ValueError(
                    f"Could not resolve source file for {cli_name!r} "
                    f"(module {cmd.callback.__module__} has __file__=None)"
                )
            return Path(src).resolve()
    raise ValueError(f"Command {cli_name!r} not found in registered_commands")


def _extract_param_names(source: str, func_name: str) -> set[str]:
    """Extract parameter names from a function definition in source code.

    Parses the source with ``ast`` and returns the set of parameter names
    (excluding ``ctx``, ``self``, ``*args``, ``**kwargs``). Used to verify
    that positional-argument option names correspond to real function
    parameters.

    Args:
        source: Full source text of the module.
        func_name: Name of the function to find (e.g. ``"library_search"``).

    Returns:
        Set of parameter name strings.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            params: set[str] = set()
            for arg in node.args.args:
                if arg.arg not in ("ctx", "self"):
                    params.add(arg.arg)
            return params
    return set()


def _extract_flag_names(source: str) -> set[str]:
    """Extract all ``--flag`` names mentioned in the source text.

    Uses a regex to find ``--flag-name`` patterns in the source. This is a
    conservative heuristic: it may miss flags constructed dynamically, but
    all 25 library-* commands use literal ``typer.Option(...)`` decorators
    so every flag appears as a ``"--flag-name"`` string literal.

    Args:
        source: Full source text of the module.

    Returns:
        Set of flag name strings (WITHOUT the leading ``--``), e.g.
        ``{"disk", "dry-run", "mode"}``.
    """
    flags: set[str] = set()
    for match in re.finditer(r"--([a-z][a-z0-9_-]*)", source):
        flags.add(match.group(1))
    return flags


# ---------------------------------------------------------------------------
# Test 1 — Completeness vs Typer ground truth
# ---------------------------------------------------------------------------


def test_registry_commands_match_typer_app() -> None:
    """The registry MUST cover every ``library-*`` command registered on the Typer app.

    If a 26th command is added later without a registry entry, this test fails
    loudly — the developer must add the corresponding :class:`MaintenanceAction`.
    """
    cli_names = _get_cli_command_names()
    registry_ids = {a.id for a in REGISTRY}

    missing_from_registry = cli_names - registry_ids
    extra_in_registry = registry_ids - cli_names

    assert not missing_from_registry, (
        f"Commands registered on Typer but missing from REGISTRY: {sorted(missing_from_registry)}"
    )
    assert not extra_in_registry, f"Entries in REGISTRY not found on Typer app: {sorted(extra_in_registry)}"


# ---------------------------------------------------------------------------
# Test 2 — Unique IDs
# ---------------------------------------------------------------------------


def test_registry_ids_unique() -> None:
    """Every :attr:`MaintenanceAction.id` must be unique."""
    ids = [a.id for a in REGISTRY]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"Duplicate registry ids: {sorted(duplicates)}"


# ---------------------------------------------------------------------------
# Test 3 — Every option name maps to a real CLI flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", REGISTRY, ids=lambda a: a.id)
def test_option_names_match_cli_flags(action: object) -> None:
    """For each action, every ``options[].name`` must appear in the CLI source.

    Positional arguments (no ``--`` prefix in the CLI) are verified by
    checking the function's parameter names. Optional flags are verified
    by grepping for ``--<name>`` in the source file.
    """
    from personalscraper.web.maintenance.registry import MaintenanceAction  # noqa: PLC0415

    action = cast(MaintenanceAction, action)
    src_file = _source_file_for_command(action.id)
    source = src_file.read_text(encoding="utf-8")

    # The callback function name is the snake_case version of the CLI name.
    func_name = action.id.replace("-", "_")
    param_names = _extract_param_names(source, func_name)
    flag_names = _extract_flag_names(source)

    for opt in action.options:
        if opt.required:
            # Positional argument — must appear as a function parameter.
            assert opt.name in param_names, (
                f"{action.id}: option {opt.name!r} (required) not found in "
                f"function parameters {sorted(param_names)} in {src_file.name}"
            )
        else:
            # Optional flag — must appear as --<name> in the source.
            assert opt.name in flag_names, (
                f"{action.id}: option --{opt.name!r} not found in flags {sorted(flag_names)} in {src_file.name}"
            )


# ---------------------------------------------------------------------------
# Test 4 — Destructive → dry-run invariant
# ---------------------------------------------------------------------------


def test_destructive_actions_support_dry_run() -> None:
    """Every action with ``risk='destructive'`` MUST have ``dry_run='supported'``.

    This is a backend-enforced invariant: a destructive action without a
    dry-run toggle is a safety hazard in the web UI.
    """
    violations: list[str] = []
    for action in REGISTRY:
        if action.risk == "destructive" and action.dry_run != "supported":
            violations.append(action.id)
    assert not violations, f"Destructive actions without dry_run='supported': {violations}"
