"""Package wiring smoke test: every load-bearing module imports cleanly.

This guards the whole hexagon's import graph in one place. A circular import, a typo in a
``from kanbanmate...`` path, or a broken downward edge surfaces here as an :class:`ImportError`
rather than only when a daemon tick first touches the module at runtime. The list spans one module
per layer (core, app, daemon, cli) plus the two purest core modules (``domain``, ``diff``) so a
regression anywhere in the spine fails fast.

The test imports modules only — it constructs nothing and performs no I/O — so it stays a fast,
side-effect-free guard that runs in CI without tmux/git/network.
"""

from __future__ import annotations

import importlib

import pytest

# One module per layer of the hexagon (DESIGN §3.2) plus the two purest core modules. Importing
# each must not raise: this is the package-wiring contract.
SPINE_MODULES = [
    "kanbanmate",
    "kanbanmate.core.domain",
    "kanbanmate.core.diff",
    "kanbanmate.app.tick",
    "kanbanmate.daemon.loop",
    "kanbanmate.cli.app",
]


@pytest.mark.parametrize("module_name", SPINE_MODULES)
def test_module_imports_without_error(module_name: str) -> None:
    """Assert a spine module imports without raising.

    Args:
        module_name: The dotted module path to import via :func:`importlib.import_module`.
    """
    module = importlib.import_module(module_name)
    assert module is not None


def test_cli_app_importable_without_side_effects() -> None:
    """Assert the CLI module exposes a callable ``main`` and a Typer ``app`` without running them.

    Importing ``kanbanmate.cli.app`` must register commands but start no daemon; we only check the
    entry symbols exist and are callable (we do not invoke them, which would block in the loop).
    """
    cli = importlib.import_module("kanbanmate.cli.app")
    assert callable(cli.main)
    assert cli.app is not None
