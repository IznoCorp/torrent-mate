# Phase 2 — `seed` CLI group

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Create `commands/seed.py` with the `seed_app` Typer sub-group exposing `mark`, `unmark`, and `list` sub-commands; register it in `cli.py`; add tests. Tests cover DESIGN criterion 4.

**Architecture:** Mirrors `commands/follow.py` exactly: a module-level `seed_app = typer.Typer(...)`, sub-commands decorated with `@seed_app.command("name")` + `@handle_cli_errors`, and `_root_app.add_typer(seed_app, name="seed")` as a side-effect at module bottom. Uses `per_step_boundary(config, settings, build_torrent_client=True)` — True because all three sub-commands touch the torrent client. Registration in `cli.py` is one new import line.

**Tech Stack:** Python 3.11+, `typer`, `rich`, `pytest`, `unittest.mock`

---

## Gate

**Previous phase produced:**

- `personalscraper/core/tags.py` with `SEED_PURE = "seed-pure"` importable.
- `TorrentTagger` protocol in `personalscraper/api/torrent/_contracts.py`.
- `QBitClient` and `TransmissionClient` each implement `add_tags` / `remove_tags`.
- `pytest tests/api/torrent/test_tagger.py` passes (0 failed).

Verify before starting:

```bash
python -c "from personalscraper.core.tags import SEED_PURE; from personalscraper.api.torrent._contracts import TorrentTagger; print('gate ok')"
pytest tests/api/torrent/test_tagger.py --tb=short -q
```

Expected: `gate ok` then all tests pass.

---

## Sub-phase 2.1 — `commands/seed.py`

**Files:**

- Create: `personalscraper/commands/seed.py`
- Modify: `personalscraper/cli.py`

### Task 1: Create `personalscraper/commands/seed.py`

- [ ] **Step 1: Write failing tests first**

Create `tests/commands/test_seed.py`:

```python
"""Tests for ``personalscraper seed`` CLI group (seed-pure feature, criterion 4).

Verifies that mark/unmark call add_tags/remove_tags with [SEED_PURE] for the
given hash, and that list filters completed torrents by the SEED_PURE tag.
"""
from __future__ import annotations

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
    from datetime import datetime

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

    with patch("personalscraper.commands.seed.per_step_boundary") as mock_boundary, \
         patch("personalscraper.commands.seed._cli_compat.get_settings", return_value=MagicMock()):
        mock_boundary.return_value.__enter__ = MagicMock(return_value=mock_app_context)
        mock_boundary.return_value.__exit__ = MagicMock(return_value=False)

        obj = AppCtx(config=MagicMock(), config_override=None)
        result = runner.invoke(app, args, obj=obj)

    return result, mock_app_context


def test_seed_mark_calls_add_tags():
    """seed mark <hash> calls torrent_client.add_tags(hash, [SEED_PURE])."""
    from personalscraper.core.tags import SEED_PURE

    mock_client = MagicMock()
    app = _make_app()
    result, _ = _invoke_seed(app, ["seed", "mark", "deadbeef"], torrent_client=mock_client)

    assert result.exit_code == 0, result.output
    mock_client.add_tags.assert_called_once_with("deadbeef", [SEED_PURE])


def test_seed_mark_no_client_exits_nonzero():
    """seed mark exits 1 when torrent_client is None (not configured)."""
    app = _make_app()
    result, _ = _invoke_seed(app, ["seed", "mark", "deadbeef"], torrent_client=None)

    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# unmark
# ---------------------------------------------------------------------------


def test_seed_unmark_calls_remove_tags():
    """seed unmark <hash> calls torrent_client.remove_tags(hash, [SEED_PURE])."""
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
    """seed list shows only torrents whose tags contain SEED_PURE."""
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
    """seed list with no seed-pure torrents prints a message and exits 0."""
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
    import ast, pathlib

    tree = ast.parse(pathlib.Path(src).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in getattr(node, "names", [])]
            module = getattr(node, "module", "") or ""
            assert "indexer" not in module, f"Forbidden import of indexer in {module}"
            assert "pipeline" not in module, f"Forbidden import of pipeline in {module}"
```

- [ ] **Step 2: Run tests to confirm they FAIL (module missing)**

```bash
pytest tests/commands/test_seed.py --tb=short -q 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or `ImportError` — `personalscraper.commands.seed` does not exist yet.

- [ ] **Step 3: Create `personalscraper/commands/seed.py`**

```python
"""CLI command group: ``personalscraper seed`` — manual seed-pure tagger (O1).

Sub-commands:
- ``seed mark <info_hash>``   — apply the ``seed-pure`` tag to a torrent.
- ``seed unmark <info_hash>`` — remove the ``seed-pure`` tag from a torrent.
- ``seed list``               — list all completed torrents tagged ``seed-pure``.

Registered as a Typer sub-group (``seed_app = typer.Typer(...)`` mounted via
``_root_app.add_typer``). Sub-commands use ``@seed_app.command("name")``
(NOT ``@command_with_telemetry`` which is root-app-only).
Uses ``@handle_cli_errors``, ``per_step_boundary``,
``build_torrent_client=True`` (all three sub-commands touch the torrent client;
the guard ``torrent_client is not None`` is checked at command entry and exits 1
with a clear message otherwise).

Import direction: commands/ imports core/, api/torrent/, cli_app, cli_helpers only.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from personalscraper import cli as _cli_compat
from personalscraper.cli_app import app as _root_app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.core.tags import SEED_PURE
from personalscraper.logger import get_logger

log = get_logger("cli.seed")

# Typer sub-group for the ``seed`` command.
seed_app = typer.Typer(help="Tag torrents as seed-only (seed-pure) or inspect the list.")

console = Console()


@seed_app.command("mark")
@handle_cli_errors
def seed_mark(
    ctx: typer.Context,
    info_hash: str = typer.Argument(..., help="Lowercase-hex info hash of the torrent to tag."),
) -> None:
    """Apply the ``seed-pure`` tag to a torrent already in the client.

    Idempotent: tagging a torrent that already carries ``seed-pure`` is a
    no-op at the client level.
    """
    config = ctx.obj.config
    settings = _cli_compat.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_mark_no_client", info_hash=info_hash)
            console.print("[red]Error:[/red] No torrent client configured. Check config/torrent.json5.")
            raise typer.Exit(code=1)
        app_context.torrent_client.add_tags(info_hash, [SEED_PURE])
        log.info("seed_marked", info_hash=info_hash, tag=SEED_PURE)
        console.print(f"[green]Marked[/green] {info_hash} as [bold]{SEED_PURE}[/bold].")


@seed_app.command("unmark")
@handle_cli_errors
def seed_unmark(
    ctx: typer.Context,
    info_hash: str = typer.Argument(..., help="Lowercase-hex info hash of the torrent to untag."),
) -> None:
    """Remove the ``seed-pure`` tag from a torrent in the client.

    Idempotent: removing the tag from a torrent that does not carry it is a
    no-op at the client level.
    """
    config = ctx.obj.config
    settings = _cli_compat.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_unmark_no_client", info_hash=info_hash)
            console.print("[red]Error:[/red] No torrent client configured. Check config/torrent.json5.")
            raise typer.Exit(code=1)
        app_context.torrent_client.remove_tags(info_hash, [SEED_PURE])
        log.info("seed_unmarked", info_hash=info_hash, tag=SEED_PURE)
        console.print(f"[green]Unmarked[/green] {info_hash} — [bold]{SEED_PURE}[/bold] tag removed.")


@seed_app.command("list")
@handle_cli_errors
def seed_list(ctx: typer.Context) -> None:
    """List all completed torrents currently tagged ``seed-pure``.

    Queries the torrent client for completed torrents and filters those
    whose ``tags`` list contains ``SEED_PURE``. Output is a Rich table
    with columns: Hash, Name, Tags, State.
    """
    config = ctx.obj.config
    settings = _cli_compat.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_list_no_client")
            console.print("[red]Error:[/red] No torrent client configured. Check config/torrent.json5.")
            raise typer.Exit(code=1)
        torrents = app_context.torrent_client.get_completed()
        seed_pure_torrents = [t for t in torrents if SEED_PURE in t.tags]
        log.info("seed_list", total=len(torrents), seed_pure=len(seed_pure_torrents))
        if not seed_pure_torrents:
            console.print(f"No completed torrents tagged [bold]{SEED_PURE}[/bold].")
            return
        table = Table(title=f"Torrents tagged '{SEED_PURE}'", show_lines=True)
        table.add_column("Hash", style="dim", no_wrap=True)
        table.add_column("Name")
        table.add_column("Tags")
        table.add_column("State")
        for t in seed_pure_torrents:
            table.add_row(
                t.hash,
                t.name,
                ", ".join(t.tags),
                t.state,
            )
        console.print(table)


# Register the seed sub-group on the root Typer app (import side-effect, called by cli.py).
_root_app.add_typer(seed_app, name="seed")

__all__ = ["seed_app", "seed_list", "seed_mark", "seed_unmark"]
```

- [ ] **Step 4: Register in `personalscraper/cli.py`**

In `personalscraper/cli.py`, the import block (lines 111-115) registers command modules as side-effects:

```python
import personalscraper.commands.config  # noqa: E402,F401
import personalscraper.commands.follow  # noqa: E402,F401
import personalscraper.commands.grab  # noqa: E402,F401
import personalscraper.commands.library  # noqa: E402,F401 — re-exports from library/{scan,query,maintenance,audit,analyze}
import personalscraper.commands.pipeline  # noqa: E402,F401
```

Add one line after `pipeline`:

```python
import personalscraper.commands.seed  # noqa: E402,F401
```

Also add `"seed_app"` to `__all__` in `cli.py` if that list is maintained — or leave it if it only lists helpers (check first with `rg "__all__" --type py personalscraper/cli.py`).

- [ ] **Step 5: Smoke-test the CLI registration**

```bash
python -c "import personalscraper.cli; print('import ok')"
personalscraper seed --help
```

Expected: import prints `import ok`; `--help` shows `mark`, `unmark`, `list` sub-commands.

- [ ] **Step 6: Run the seed CLI tests**

```bash
pytest tests/commands/test_seed.py -v
```

Expected: all tests pass, `0 failed`.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/commands/seed.py personalscraper/cli.py tests/commands/test_seed.py
git commit -m "feat(seed-pure): add seed CLI group (mark/unmark/list) + registration + tests"
```

---

## Phase 2 Gate

- [ ] **Run `make lint`** — must exit 0 (ruff + mypy zero errors, including `check_logging.py`).
- [ ] **Run `make test`** — must show `0 failed`, `0 errors`.
- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must print nothing and exit 0.
- [ ] **CLI help check:** `personalscraper seed --help` — must list `mark`, `unmark`, `list`.
- [ ] **Layering check:** `rg "indexer|pipeline_steps|sorter|ingest|process" --type py personalscraper/commands/seed.py` — must return no matches.
