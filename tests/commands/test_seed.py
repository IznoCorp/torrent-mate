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


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------


def _invoke_sweep(tmp_path, test_config, torrents, *, torrent_client="fake", client_error=None):
    """Run ``seed sweep`` over a real tmp acquire.db and a fake torrent client.

    Args:
        tmp_path: Pytest temp directory holding ``acquire.db`` and the run-journal ``library.db``.
        test_config: The ``test_config`` fixture, re-pointed at a synthetic ``library.db`` so the
            run row the command records has a real database to land in.
        torrents: The :class:`TorrentItem` list the fake client holds.
        torrent_client: ``"fake"`` to inject the fake client, ``None`` for « not configured ».
        client_error: When set, the fake client's ``get_by_hashes`` raises it.

    Returns:
        ``(result, store, events, db_path)`` — the CLI result, the store, the events emitted on the
        bus and the path of the ``library.db`` holding the run journal.
    """
    from types import SimpleNamespace

    from personalscraper.acquire.events import SeedObligationReleased, SeedObligationSatisfied
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.cli_state import AppCtx
    from personalscraper.conf.models.acquire import AcquireConfig
    from personalscraper.core.event_bus import EventBus
    from tests.commands._e2e_helpers import make_synthetic_db, make_test_config_with_db

    db_path = make_synthetic_db(tmp_path)
    config = make_test_config_with_db(test_config, db_path)
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    bus = EventBus()
    events: list = []
    bus.subscribe(SeedObligationSatisfied, events.append)
    bus.subscribe(SeedObligationReleased, events.append)
    client = MagicMock()
    client.get_by_hashes.side_effect = (
        client_error if client_error is not None else lambda hashes: [t for t in torrents if t.hash in hashes]
    )
    app_context = SimpleNamespace(
        torrent_client=client if torrent_client == "fake" else None,
        acquire=SimpleNamespace(store=store),
        event_bus=bus,
    )
    with (
        patch("personalscraper.conf.loader.load_config", return_value=config),
        patch("personalscraper.commands.seed.per_step_boundary") as mock_boundary,
        patch("personalscraper.commands.seed.cli_helpers.get_settings", return_value=MagicMock()),
    ):
        mock_boundary.return_value.__enter__ = MagicMock(return_value=app_context)
        mock_boundary.return_value.__exit__ = MagicMock(return_value=False)
        result = runner.invoke(_make_app(), ["seed", "sweep"], obj=AppCtx(config=config, config_override=None))
    return result, store, events, db_path


def test_seed_sweep_writes_satisfied_at_and_prints_one_json_line(tmp_path, test_config):
    """``seed sweep`` stamps ``satisfied_at`` on a seeded-out obligation and reports it as one JSON line."""
    import json

    from personalscraper.acquire.domain import SeedObligation
    from personalscraper.acquire.events import SeedObligationSatisfied

    # The store opens lazily and the command needs the row first: seed it through a twin handle.
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.conf.models.acquire import AcquireConfig

    seed_store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    seed_store.seed.add(SeedObligation("aaaa", "c411", 259_200, 1.0, 5))
    seed_store.close()

    item = _make_torrent_item("Movie", "aaaa", [])
    object.__setattr__(item, "seeding_time_s", 259_200)
    result, store, events, _ = _invoke_sweep(tmp_path, test_config, [item])
    try:
        assert result.exit_code == 0, result.output
        report = json.loads(result.output.strip().splitlines()[-1])
        assert report == {"open": 1, "satisfied": 1, "marked_absent": 0, "released": 0, "client_error": False}
        assert store.seed.list_open() == []
        assert [type(e) for e in events] == [SeedObligationSatisfied]
    finally:
        store.close()


def test_seed_sweep_no_client_exits_nonzero(tmp_path, test_config):
    """``seed sweep`` exits 1 when no torrent client is configured."""
    result, store, _, _ = _invoke_sweep(tmp_path, test_config, [], torrent_client=None)
    store.close()
    assert result.exit_code == 1


def _seed_one_obligation(tmp_path):
    """Insert one open C411 obligation into the tmp ``acquire.db`` the sweep will open."""
    from personalscraper.acquire.domain import SeedObligation
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.conf.models.acquire import AcquireConfig

    seed_store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    seed_store.seed.add(SeedObligation("aaaa", "c411", 259_200, 1.0, 5))
    seed_store.close()


def test_seed_sweep_client_error_prints_the_report_and_exits_one(tmp_path, test_config):
    """A client that raises: one JSON line with ``client_error`` set, exit code 1, nothing written."""
    import json

    _seed_one_obligation(tmp_path)
    result, store, events, _ = _invoke_sweep(tmp_path, test_config, [], client_error=RuntimeError("client down"))
    try:
        assert result.exit_code == 1, result.output
        report = json.loads(result.output.strip().splitlines()[-1])
        assert report == {"open": 1, "satisfied": 0, "marked_absent": 0, "released": 0, "client_error": True}
        assert events == []
    finally:
        store.close()


def test_seed_sweep_records_its_run_like_the_other_scheduled_jobs(tmp_path, test_config):
    """The sweep writes one ``pipeline_run`` row (command ``seed-sweep``) so the System page shows its last run."""
    import sqlite3

    _seed_one_obligation(tmp_path)
    result, store, _, db_path = _invoke_sweep(tmp_path, test_config, [])
    store.close()
    assert result.exit_code == 0, result.output
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT command, kind, outcome FROM pipeline_run").fetchall()
    finally:
        conn.close()
    assert rows == [("seed-sweep", "maintenance", "success")]
