"""Tests for ``personalscraper seed`` CLI group (seed-pure feature, criterion 4).

Verifies that mark/unmark call add_tags/remove_tags with [SEED_PURE] for the
given hash, and that list filters completed torrents by the SEED_PURE tag.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

runner = CliRunner()


def _make_app():
    """Import the root CLI app (triggers seed registration)."""
    # Import cli.py which registers all command groups as side-effects.
    import personalscraper.cli as _cli  # noqa: F401
    from personalscraper.cli_app import app

    return app


def _make_torrent_item(name: str, hash_: str, tags: list[str]):
    """Build a minimal TorrentItem for use in list tests."""
    from personalscraper.api.torrent._base import TorrentItem

    return TorrentItem(
        hash=hash_,
        name=name,
        size_bytes=1024,
        progress=1.0,
        state="uploading",
        tags=tags,
    )


# ---------------------------------------------------------------------------
# mark
# ---------------------------------------------------------------------------


def _invoke_seed(app, args: list[str], torrent_client=None):
    """Invoke a seed sub-command with a mocked per_step_boundary and app_context.

    Patches ``per_step_boundary`` so no real config/client is needed.
    The ``ctx.obj`` is set to a MagicMock with a ``config`` attribute so
    Typer's callback injects it correctly.

    Args:
        app: The root Typer app.
        args: CLI args (e.g. ``["seed", "mark", "deadbeef"]``).
        torrent_client: The mock torrent client to inject into app_context
            (None simulates "not configured").

    Returns:
        The typer.testing.Result.
    """
    from personalscraper.cli_state import AppCtx

    mock_app_context = MagicMock()
    mock_app_context.torrent_client = torrent_client

    with (
        patch("personalscraper.commands.seed.per_step_boundary") as mock_boundary,
        patch("personalscraper.commands.seed.cli_helpers.get_settings", return_value=MagicMock()),
    ):
        mock_boundary.return_value.__enter__ = MagicMock(return_value=mock_app_context)
        mock_boundary.return_value.__exit__ = MagicMock(return_value=False)

        obj = AppCtx(config=MagicMock(), config_override=None)
        result = runner.invoke(app, args, obj=obj)

    return result, mock_app_context


def test_seed_mark_calls_add_tags():
    """Seed mark <hash> calls torrent_client.add_tags(hash, [SEED_PURE])."""
    from personalscraper.core.tags import SEED_PURE

    mock_client = MagicMock()
    app = _make_app()
    result, _ = _invoke_seed(app, ["seed", "mark", "deadbeef"], torrent_client=mock_client)

    assert result.exit_code == 0, result.output
    mock_client.add_tags.assert_called_once_with("deadbeef", [SEED_PURE])


def test_seed_mark_no_client_exits_nonzero():
    """Seed mark exits 1 when torrent_client is None (not configured)."""
    app = _make_app()
    result, _ = _invoke_seed(app, ["seed", "mark", "deadbeef"], torrent_client=None)

    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# unmark
# ---------------------------------------------------------------------------


def test_seed_unmark_calls_remove_tags():
    """Seed unmark <hash> calls torrent_client.remove_tags(hash, [SEED_PURE])."""
    from personalscraper.core.tags import SEED_PURE

    mock_client = MagicMock()
    app = _make_app()
    result, _ = _invoke_seed(app, ["seed", "unmark", "deadbeef"], torrent_client=mock_client)

    assert result.exit_code == 0, result.output
    mock_client.remove_tags.assert_called_once_with("deadbeef", [SEED_PURE])


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_seed_list_filters_by_seed_pure_tag():
    """Seed list shows only torrents whose tags contain SEED_PURE."""
    from personalscraper.core.tags import SEED_PURE

    tagged = _make_torrent_item("Movie.2024", "aaaa", [SEED_PURE])
    untagged = _make_torrent_item("Show.S01", "bbbb", [])

    mock_client = MagicMock()
    mock_client.get_completed.return_value = [tagged, untagged]

    app = _make_app()
    result, _ = _invoke_seed(app, ["seed", "list"], torrent_client=mock_client)

    assert result.exit_code == 0, result.output
    assert "Movie.2024" in result.output
    assert "Show.S01" not in result.output
    # Verify the client was queried exactly once
    mock_client.get_completed.assert_called_once()


def test_seed_list_no_tagged_torrents_shows_empty():
    """Seed list with no seed-pure torrents prints a message and exits 0."""
    mock_client = MagicMock()
    mock_client.get_completed.return_value = []

    app = _make_app()
    result, _ = _invoke_seed(app, ["seed", "list"], torrent_client=mock_client)

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Layering guard
# ---------------------------------------------------------------------------


def test_seed_module_does_not_import_indexer():
    """commands/seed.py must not import indexer or pipeline internals."""
    import importlib
    import sys

    # Remove cached module if already imported
    for key in list(sys.modules.keys()):
        if "commands.seed" in key:
            del sys.modules[key]

    mod = importlib.import_module("personalscraper.commands.seed")
    src = mod.__file__ or ""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(src).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", "") or ""
            assert "indexer" not in module, f"Forbidden import of indexer in {module}"
            assert "pipeline" not in module, f"Forbidden import of pipeline in {module}"
