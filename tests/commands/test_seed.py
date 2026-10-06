"""Tests for ``personalscraper seed`` CLI group (seed-pure feature, criterion 4).

Verifies that mark/unmark call add_tags/remove_tags with [SEED_PURE] for the
given hash, and that list filters completed torrents by the SEED_PURE tag.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
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


# The destruction journal is a leaf (core.sqlite + the logger), not an indexer internal;
# the purge's journal is wired in commands/seed.py.
_SEED_ALLOWED_INDEXER_MODULES = frozenset({"personalscraper.indexer.destructive_journal"})


def _forbidden_seed_imports(source: str) -> list[str]:
    """Return the indexer or pipeline modules *source* imports, the allowed journal aside."""
    import ast

    forbidden: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        elif isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        else:
            continue
        for module in modules:
            if module in _SEED_ALLOWED_INDEXER_MODULES:
                continue
            if "indexer" in module or "pipeline" in module:
                forbidden.append(module)
    return forbidden


def test_seed_module_does_not_import_indexer():
    """commands/seed.py must not import indexer or pipeline internals (the leaf journal aside)."""
    import importlib
    import pathlib
    import sys

    # Remove cached module if already imported
    for key in list(sys.modules.keys()):
        if "commands.seed" in key:
            del sys.modules[key]

    mod = importlib.import_module("personalscraper.commands.seed")
    src = mod.__file__ or ""
    assert _forbidden_seed_imports(pathlib.Path(src).read_text()) == []


def test_seed_import_guard_still_refuses_other_indexer_and_pipeline_modules():
    """Control: the one exemption is the journal; any other indexer module, or pipeline, is still refused."""
    assert _forbidden_seed_imports("from personalscraper.indexer.db import open_db\n") == ["personalscraper.indexer.db"]
    assert _forbidden_seed_imports("import personalscraper.indexer.deletion\n") == ["personalscraper.indexer.deletion"]
    assert _forbidden_seed_imports("from personalscraper.pipeline import Pipeline\n") == ["personalscraper.pipeline"]
    assert _forbidden_seed_imports("from personalscraper.indexer.destructive_journal import OP_DELETE\n") == []


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


# ---------------------------------------------------------------------------
# Client scope
# ---------------------------------------------------------------------------


def _seed_list_over_shared_client(monkeypatch, scope):
    """Run ``seed list`` over a client whose torrents are all seed-pure.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        scope: The scope the active client resolves to (``None`` = whole client).

    Returns:
        The CLI output.
    """
    from personalscraper.conf.models.api_config import TorrentConfig
    from personalscraper.core.tags import SEED_PURE
    from tests.fixtures.torrent_scope import shared_client

    monkeypatch.setattr(TorrentConfig, "active_scope", lambda self: scope)
    client = shared_client()
    for item in client.get_completed.return_value:
        item.tags = [SEED_PURE]
    obj_config = MagicMock()
    obj_config.torrent = TorrentConfig()
    mock_app_context = MagicMock()
    mock_app_context.torrent_client = client
    from personalscraper.cli_state import AppCtx

    with (
        patch("personalscraper.commands.seed.per_step_boundary") as mock_boundary,
        patch("personalscraper.commands.seed.cli_helpers.get_settings", return_value=MagicMock()),
    ):
        mock_boundary.return_value.__enter__ = MagicMock(return_value=mock_app_context)
        mock_boundary.return_value.__exit__ = MagicMock(return_value=False)
        result = runner.invoke(_make_app(), ["seed", "list"], obj=AppCtx(config=obj_config, config_override=None))
    return result.output


def test_seed_list_under_scope_shows_only_its_own_torrents(monkeypatch):
    """Under a scope the other instance's seed-pure torrent is not listed."""
    from tests.fixtures.torrent_scope import SCOPE

    output = _seed_list_over_shared_client(monkeypatch, SCOPE)
    assert "Movie.bb" in output
    assert "Movie.aa" not in output
    assert "Movie.cc" not in output


def test_seed_list_without_scope_shows_every_seed_pure_torrent(monkeypatch):
    """Characterisation: no scope, every seed-pure torrent is listed."""
    output = _seed_list_over_shared_client(monkeypatch, None)
    assert "Movie.bb" in output
    assert "Movie.aa" in output
    assert "Movie.cc" in output


# ---------------------------------------------------------------------------
# purge
# ---------------------------------------------------------------------------


def _invoke_purge(args, config, app_context, monkeypatch, *, env="staging"):
    """Run ``seed purge`` with *app_context* behind a mocked ``per_step_boundary``.

    Args:
        args: The arguments after ``seed purge``.
        config: The Config placed in ``ctx.obj`` (and returned by the patched loader).
        app_context: What the boundary yields.
        monkeypatch: Pytest's monkeypatch, used to set ``PERSONALSCRAPER_ENV``.
        env: The environment; ``None`` unsets it.

    Returns:
        ``(result, mock_boundary)``.
    """
    from personalscraper.cli_state import AppCtx

    app = _make_app()
    if env is None:
        monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)
    else:
        monkeypatch.setenv("PERSONALSCRAPER_ENV", env)
    with (
        patch("personalscraper.conf.loader.load_config", return_value=config),
        patch("personalscraper.commands.seed.per_step_boundary") as mock_boundary,
        patch("personalscraper.commands.seed.cli_helpers.get_settings", return_value=MagicMock()),
    ):
        mock_boundary.return_value.__enter__ = MagicMock(return_value=app_context)
        mock_boundary.return_value.__exit__ = MagicMock(return_value=False)
        result = runner.invoke(app, ["seed", "purge", *args], obj=AppCtx(config=config, config_override=None))
    return result, mock_boundary


def _fake_context(client="fake"):
    """Return an app context with a mock client, a mock store and a real bus."""
    from types import SimpleNamespace

    from personalscraper.core.event_bus import EventBus

    return SimpleNamespace(
        torrent_client=MagicMock() if client == "fake" else None,
        acquire=SimpleNamespace(store=MagicMock()),
        event_bus=EventBus(),
    )


@pytest.mark.parametrize("env", [None, "prod", "dev"])
def test_seed_purge_outside_staging_exits_2_before_any_client(monkeypatch, env):
    """Outside ``staging`` the command exits 2 with a message and never builds the client."""
    with patch("personalscraper.commands.seed.purge_preprod_downloads") as purge:
        result, boundary = _invoke_purge([], MagicMock(), _fake_context(), monkeypatch, env=env)
    assert result.exit_code == 2, result.output
    assert result.output.strip()
    boundary.assert_not_called()
    purge.assert_not_called()


def test_seed_purge_passes_dry_run_and_max_and_prints_one_line_per_decision(monkeypatch):
    """``--dry-run --max 3`` reach the purge; each decision is one line with its verdict code."""
    from personalscraper.acquire.preprod_purge import PurgeDecision, PurgeVerdict

    decisions = [
        PurgeDecision("aaaa", "Release.A", PurgeVerdict.PURGED, 1),
        PurgeDecision("bbbb", "Release.B", PurgeVerdict.KEPT_UNKNOWN, None),
    ]
    ctx = _fake_context()
    with patch("personalscraper.commands.seed.purge_preprod_downloads", return_value=decisions) as purge:
        result, _ = _invoke_purge(["--dry-run", "--max", "3"], MagicMock(), ctx, monkeypatch)
    assert result.exit_code == 0, result.output
    kwargs = purge.call_args.kwargs
    assert (kwargs["dry_run"], kwargs["max_purged"]) == (True, 3)
    assert purge.call_args.args[:2] == (ctx.acquire.store, ctx.torrent_client)
    lines = result.output.splitlines()
    assert any("purged" in line and "aaaa" in line and "Release.A" in line for line in lines)
    assert any("kept_unknown" in line and "bbbb" in line for line in lines)
    assert "{" not in result.output
    assert "1" in lines[-1]


def test_seed_purge_defaults_to_a_real_run_capped_at_20(monkeypatch):
    """Without options the purge runs for real with a cap of 20."""
    with patch("personalscraper.commands.seed.purge_preprod_downloads", return_value=[]) as purge:
        result, _ = _invoke_purge([], MagicMock(), _fake_context(), monkeypatch)
    assert result.exit_code == 0, result.output
    assert (purge.call_args.kwargs["dry_run"], purge.call_args.kwargs["max_purged"]) == (False, 20)


def test_seed_purge_refuses_a_cap_below_one(monkeypatch):
    """``--max 0`` is a usage error."""
    with patch("personalscraper.commands.seed.purge_preprod_downloads") as purge:
        result, _ = _invoke_purge(["--max", "0"], MagicMock(), _fake_context(), monkeypatch)
    assert result.exit_code == 2
    purge.assert_not_called()


def test_seed_purge_without_client_exits_1(monkeypatch):
    """No torrent client configured: exit 1, no purge."""
    with patch("personalscraper.commands.seed.purge_preprod_downloads") as purge:
        result, _ = _invoke_purge([], MagicMock(), _fake_context(client=None), monkeypatch)
    assert result.exit_code == 1, result.output
    purge.assert_not_called()


def test_seed_purge_guard_refusal_exits_2(monkeypatch):
    """A scope refusal from the purge exits 2 with its message."""
    from personalscraper.conf.sandbox_guard import SandboxGuardError

    refusal = SandboxGuardError("the client scope's category is empty")
    with patch("personalscraper.commands.seed.purge_preprod_downloads", side_effect=refusal):
        result, _ = _invoke_purge([], MagicMock(), _fake_context(), monkeypatch)
    assert result.exit_code == 2, result.output
    assert "category is empty" in result.output


def test_seed_purge_client_failure_exits_1(monkeypatch):
    """A client that cannot list exits 1."""
    from personalscraper.api.torrent._errors import TorrentClientError

    with patch("personalscraper.commands.seed.purge_preprod_downloads", side_effect=TorrentClientError("down", 0)):
        result, _ = _invoke_purge([], MagicMock(), _fake_context(), monkeypatch)
    assert result.exit_code == 1, result.output


def test_seed_purge_journals_each_purge_in_the_preprod_library_db(tmp_path, monkeypatch):
    """A real purge writes one ``destructive_op`` row, actor ``preprod-purge``, in ``library-staging.db``."""
    import sqlite3
    from types import SimpleNamespace

    from personalscraper.acquire.domain import SeedObligation
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.conf import sandbox_guard
    from personalscraper.conf.models.acquire import AcquireConfig
    from personalscraper.core.event_bus import EventBus
    from personalscraper.indexer import migrations as migrations_pkg
    from personalscraper.indexer.db import apply_migrations
    from tests.acquire.test_preprod_purge import FakeClient, Roots, _config, _item

    roots = Roots(tmp_path)
    config = _config(roots)
    library_db = roots.data / "library-staging.db"
    conn = sqlite3.connect(str(library_db), isolation_level=None)
    apply_migrations(conn, Path(migrations_pkg.__file__).parent)
    conn.close()
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire-staging.db"))
    try:
        store.seed.add(SeedObligation("aaaa", "c411", 259_200, 1.0, 5, satisfied_at=10))
        item = _item(roots, "aaaa")
        client = FakeClient([item])
        ctx = SimpleNamespace(torrent_client=client, acquire=SimpleNamespace(store=store), event_bus=EventBus())
        result, _ = _invoke_purge([], config, ctx, monkeypatch)
        assert result.exit_code == 0, result.output
        assert client.deleted == [("aaaa", True)]
        conn = sqlite3.connect(str(library_db))
        try:
            rows = conn.execute("SELECT op, path, actor FROM destructive_op").fetchall()
        finally:
            conn.close()
        assert rows == [("delete", str(item.content_path), "preprod-purge")]
    finally:
        store.close()


@pytest.mark.parametrize("args", [[], ["--dry-run"]])
def test_seed_purge_without_its_journal_db_is_refused_before_any_client_call(tmp_path, monkeypatch, args):
    """Without ``library-staging.db`` the purge is refused, dry run included: nothing listed, deleted or created."""
    from types import SimpleNamespace

    from personalscraper.acquire.domain import SeedObligation
    from personalscraper.acquire.store import build_acquire_store
    from personalscraper.conf import sandbox_guard
    from personalscraper.conf.models.acquire import AcquireConfig
    from personalscraper.core.event_bus import EventBus
    from tests.acquire.test_preprod_purge import FakeClient, Roots, _config, _item

    roots = Roots(tmp_path)
    config = _config(roots)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire-staging.db"))
    try:
        store.seed.add(SeedObligation("aaaa", "c411", 259_200, 1.0, 5, satisfied_at=10))
        client = FakeClient([_item(roots, "aaaa")])
        ctx = SimpleNamespace(torrent_client=client, acquire=SimpleNamespace(store=store), event_bus=EventBus())
        result, _ = _invoke_purge(args, config, ctx, monkeypatch)
        assert result.exit_code == 2, result.output
        assert "library-staging.db" in result.output
        assert client.calls == []
        assert client.deleted == []
        assert not (roots.data / "library-staging.db").exists()
    finally:
        store.close()
