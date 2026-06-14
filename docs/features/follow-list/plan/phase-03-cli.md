# Phase 3 — `follow` CLI Command Group (`commands/follow.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `personalscraper follow add/list/remove` as a Typer sub-group mirroring `commands/grab.py`. Wire `SeriesFollowed`/`SeriesUnfollowed` event emission. Register in `cli.py`. Cover with e2e tests using a real seeded `acquire.db`.

**Architecture:** `commands/follow.py` is a CLI adapter (consumer layer). It calls `acquire/` store methods and `acquire/title_resolver.py`. It creates a `follow_app = typer.Typer(...)` sub-group and registers individual commands with `@follow_app.command("add")` etc. (same pattern as `trailers/cli.py` and `commands/info.py` — NOT `@command_with_telemetry`, which is root-app-only). Uses `@handle_cli_errors` and `per_step_boundary` from `personalscraper/cli_helpers/__init__.py`, `state` from `personalscraper/cli_state.py`. The sub-group is mounted via `_root_app.add_typer(follow_app, name="follow")` at import time. Events (`SeriesFollowed`, `SeriesUnfollowed`) are emitted on `app_context.event_bus`. `build_torrent_client=False` — follow management needs no torrent daemon.

**Tech Stack:** Typer, Rich (table + console), `CliRunner` for e2e tests, frozen dataclasses, `EventBus`.

## Gate (start of phase)

Phase 1 + 2 delivered: `_FollowSubStore` CRUD complete, `FollowSubStore` Protocol updated, `resolve_series_title` helper. Verify:

```bash
python -m pytest tests/acquire/ -v
# Expected: all pass, 0 errors.

python -c "from personalscraper.acquire.title_resolver import resolve_series_title; print('ok')"
# Expected: ok
```

---

## Task 6: Create `commands/follow.py` with `follow add`

**Files:**

- Create: `personalscraper/commands/follow.py`
- Create: `tests/commands/test_follow.py`

### Sub-phase 3.1 — `follow add`

- [ ] **Step 3.1.1: Write failing e2e test for `follow add`**

  Create `tests/commands/test_follow.py`:

  ```python
  """E2E CLI tests for ``personalscraper follow`` command group."""

  from __future__ import annotations

  import time
  from contextlib import contextmanager
  from pathlib import Path
  from unittest.mock import MagicMock

  import pytest
  from typer.testing import CliRunner

  from personalscraper.acquire.context import AcquireContext
  from personalscraper.acquire.store import build_acquire_store
  from personalscraper.cli import app
  from personalscraper.conf.models.acquire import AcquireConfig
  from personalscraper.core.app_context import AppContext
  from personalscraper.core.event_bus import EventBus
  from personalscraper.core.identity import MediaRef

  runner = CliRunner()


  def _make_app_context(*, acquire: AcquireContext, event_bus: EventBus) -> AppContext:
      """Build a minimal AppContext with the given acquire context and event_bus."""
      return AppContext(
          config=MagicMock(),
          settings=MagicMock(),
          event_bus=event_bus,
          provider_registry=MagicMock(),
          acquire=acquire,
      )


  def _fake_boundary(app_ctx: AppContext):
      """Return a context manager that yields app_ctx (replaces per_step_boundary)."""

      @contextmanager
      def _boundary(config, settings, *, build_torrent_client=False):
          yield app_ctx

      return _boundary


  def _acquire_ctx_for(db_path: Path, event_bus: EventBus) -> AcquireContext:
      """Build a real AcquireContext with a seeded store and a mock title resolver."""
      store = build_acquire_store(AcquireConfig(db_path=db_path))
      return AcquireContext(
          tracker_registry=MagicMock(),
          store=store,
      )


  # ---------------------------------------------------------------------------
  # Smoke tests
  # ---------------------------------------------------------------------------


  def test_follow_command_registered() -> None:
      """The ``follow`` sub-group must appear in the app help output."""
      result = runner.invoke(app, ["--help"])
      assert "follow" in result.output, f"Expected 'follow' in help; got:\n{result.output}"


  def test_follow_add_help_exits_zero() -> None:
      """``follow add --help`` exits 0 and mentions --tvdb."""
      result = runner.invoke(app, ["follow", "add", "--help"])
      assert result.exit_code == 0, result.output
      assert "--tvdb" in result.output


  def test_follow_list_help_exits_zero() -> None:
      """``follow list --help`` exits 0 and mentions --all."""
      result = runner.invoke(app, ["follow", "list", "--help"])
      assert result.exit_code == 0, result.output
      assert "--all" in result.output


  def test_follow_remove_help_exits_zero() -> None:
      """``follow remove --help`` exits 0 and mentions --tvdb."""
      result = runner.invoke(app, ["follow", "remove", "--help"])
      assert result.exit_code == 0, result.output
      assert "--tvdb" in result.output


  # ---------------------------------------------------------------------------
  # follow add — idempotent dedup (LOAD-BEARING)
  # ---------------------------------------------------------------------------


  def test_follow_add_inserts_one_row(tmp_path: Path, monkeypatch) -> None:
      """follow add --tvdb 81189 inserts a row in followed_series."""
      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      # Title resolver: patch resolve_series_title to return a fixed title
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      result = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

      assert result.exit_code == 0, f"Expected exit 0; got:\n{result.output}"
      # Verify the row is actually in the DB (LOAD-BEARING: real row count).
      store2 = build_acquire_store(AcquireConfig(db_path=db_path))
      all_rows = store2.follow.list_all()
      assert len(all_rows) == 1, f"Expected 1 row, got {len(all_rows)}: {all_rows}"
      assert all_rows[0].media_ref.tvdb_id == 81189
      assert all_rows[0].title == "Breaking Bad"
      assert all_rows[0].active is True
      store2.close()
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_add_idempotent_double_add_one_row(tmp_path: Path, monkeypatch) -> None:
      """LOAD-BEARING: follow add twice with same --tvdb → exactly 1 row (dedup)."""
      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
      result2 = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

      assert result2.exit_code == 0, result2.output

      store2 = build_acquire_store(AcquireConfig(db_path=db_path))
      all_rows = store2.follow.list_all()
      assert len(all_rows) == 1, (
          f"LOAD-BEARING: expected exactly 1 row after double add, got {len(all_rows)}: {all_rows}"
      )
      store2.close()
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_add_emits_series_followed_event(tmp_path: Path, monkeypatch) -> None:
      """LOAD-BEARING: follow add emits SeriesFollowed on the event bus."""
      from personalscraper.acquire.events import SeriesFollowed

      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      received: list[SeriesFollowed] = []
      event_bus.subscribe(SeriesFollowed, lambda e: received.append(e))

      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

      assert len(received) == 1, f"Expected 1 SeriesFollowed event, got {len(received)}"
      assert received[0].media_ref.tvdb_id == 81189
      assert received[0].title == "Breaking Bad"
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_add_noop_when_already_active(tmp_path: Path, monkeypatch) -> None:
      """follow add on an already-active series is a no-op (no duplicate row, no duplicate event)."""
      from personalscraper.acquire.events import SeriesFollowed

      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      received: list[SeriesFollowed] = []
      event_bus.subscribe(SeriesFollowed, lambda e: received.append(e))

      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
      result2 = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

      assert result2.exit_code == 0, result2.output
      # Second add is a no-op: still only 1 event (first add only)
      assert len(received) == 1, f"Expected 1 SeriesFollowed event total (no-op), got {len(received)}"
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_add_metadata_failure_still_follows(tmp_path: Path, monkeypatch) -> None:
      """LOAD-BEARING: title resolution failure → follow still succeeds with fallback title."""
      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      # Simulate title resolution failure: resolver raises (should not propagate)
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: kw.get("fallback_title") or f"tvdb:{ref.tvdb_id}",
      )

      result = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

      assert result.exit_code == 0, f"Expected exit 0 even on title failure; got:\n{result.output}"
      store2 = build_acquire_store(AcquireConfig(db_path=db_path))
      all_rows = store2.follow.list_all()
      assert len(all_rows) == 1, "Series must still be followed despite title resolution failure"
      assert all_rows[0].title == "tvdb:81189", (
          f"LOAD-BEARING: expected fallback title 'tvdb:81189', got {all_rows[0].title!r}"
      )
      store2.close()
      acquire.store.close()  # type: ignore[union-attr]
  ```

- [ ] **Step 3.1.2: Run tests to confirm they fail**

  ```bash
  python -m pytest tests/commands/test_follow.py -v
  ```

  Expected: FAIL (ImportError — `personalscraper.commands.follow` does not exist).

- [ ] **Step 3.1.3: Create `commands/follow.py` with `follow add`**

  Create `personalscraper/commands/follow.py`:

  ```python
  """CLI command group: ``personalscraper follow`` — followed-series management (Follow D1).

  Sub-commands:
  - ``follow add --tvdb/--tmdb/--imdb/--title`` — follow a series (idempotent).
  - ``follow list [--all]`` — list followed series.
  - ``follow remove --tvdb/--id`` — soft-unfollow a series.

  Registered as a Typer sub-group (``follow_app = typer.Typer(...)`` mounted via
  ``_root_app.add_typer``). Sub-commands use ``@follow_app.command("name")``
  (NOT ``@command_with_telemetry`` which is root-app-only).
  Uses ``@handle_cli_errors``, ``per_step_boundary``,
  ``build_torrent_client=False`` (follow management needs no torrent daemon).

  Events emitted on ``app_context.event_bus``:
  - :class:`~personalscraper.acquire.events.SeriesFollowed` on add (new or reactivated).
  - :class:`~personalscraper.acquire.events.SeriesUnfollowed` on remove.

  Import direction: commands/ imports acquire/, api/, core/, conf/, events/ only.
  """

  from __future__ import annotations

  import time
  from typing import Optional

  import typer
  from rich.console import Console
  from rich.table import Table

  from personalscraper import cli as cli_compat
  from personalscraper.acquire.events import SeriesFollowed, SeriesUnfollowed
  from personalscraper.acquire.title_resolver import resolve_series_title
  from personalscraper.cli_app import app as _root_app
  from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
  from personalscraper.cli_state import state
  from personalscraper.core.identity import MediaRef
  from personalscraper.logger import get_logger

  log = get_logger("cli.follow")

  # Typer sub-group for the ``follow`` command.
  follow_app = typer.Typer(help="Manage the followed-series list.")


  @follow_app.command("add")
  @handle_cli_errors
  def follow_add(
      ctx: typer.Context,
      tvdb_id: Optional[int] = typer.Option(None, "--tvdb", help="TVDB series ID (primary)."),
      tmdb_id: Optional[int] = typer.Option(None, "--tmdb", help="TMDB series ID."),
      imdb_id: Optional[str] = typer.Option(None, "--imdb", help="IMDB series ID (e.g. tt0903747)."),
      title: Optional[str] = typer.Option(None, "--title", help="Human-readable title (fallback when metadata unavailable)."),
  ) -> None:
      """Follow a TV series by provider ID (idempotent).

      At least one of --tvdb, --tmdb, or --imdb is required. --tvdb is preferred
      (primary identifier). The canonical title is resolved via the metadata
      provider registry; --title is used as a fallback when resolution fails.
      """
      if tvdb_id is None and tmdb_id is None and imdb_id is None:
          typer.echo("Error: at least one of --tvdb, --tmdb, or --imdb is required.", err=True)
          raise typer.Exit(code=2)

      config = ctx.obj.config
      assert config is not None
      console: Console = state["console"]
      settings = cli_compat.get_settings()

      with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
          acquire = app_context.acquire
          if acquire is None or acquire.store is None:
              console.print("[red]AcquireContext/store not available.[/red]")
              raise typer.Exit(1)

          store = acquire.store
          media_ref = MediaRef(tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)

          # Resolve title fail-soft — never block a follow.
          resolved_title = resolve_series_title(
              media_ref,
              app_context.provider_registry,
              fallback_title=title,
          )

          existing = store.follow.find_by_ref(media_ref)
          if existing is not None and existing.active:
              console.print(f"[yellow]Already following:[/yellow] {existing.title} (id={existing.id})")
              return

          if existing is not None and not existing.active:
              # Reactivate (refollow after remove).
              assert existing.id is not None
              store.follow.set_active(existing.id, True)
              app_context.event_bus.emit(SeriesFollowed(media_ref=media_ref, title=existing.title))
              console.print(f"[green]Refollowing:[/green] {existing.title} (id={existing.id})")
              log.info("cli.follow.refollowed", tvdb_id=tvdb_id, title=existing.title)
              return

          # New follow.
          from personalscraper.acquire.domain import FollowedSeries  # noqa: PLC0415

          new_series = FollowedSeries(
              media_ref=media_ref,
              title=resolved_title,
              added_at=int(time.time()),
              active=True,
          )
          row_id = store.follow.add(new_series)
          app_context.event_bus.emit(SeriesFollowed(media_ref=media_ref, title=resolved_title))
          console.print(f"[green]Now following:[/green] {resolved_title} (id={row_id})")
          log.info("cli.follow.added", tvdb_id=tvdb_id, title=resolved_title, row_id=row_id)


  @follow_app.command("list")
  @handle_cli_errors
  def follow_list(
      ctx: typer.Context,
      all_series: bool = typer.Option(False, "--all", help="Include inactive (unfollowed) series."),
  ) -> None:
      """List followed series.

      By default shows only active series. Use --all to include unfollowed ones.
      """
      config = ctx.obj.config
      assert config is not None
      console: Console = state["console"]
      settings = cli_compat.get_settings()

      with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
          acquire = app_context.acquire
          if acquire is None or acquire.store is None:
              console.print("[red]AcquireContext/store not available.[/red]")
              raise typer.Exit(1)

          store = acquire.store
          rows = store.follow.list_all() if all_series else store.follow.list_active()

          if not rows:
              console.print("[yellow]No followed series.[/yellow]")
              return

          table = Table(title="Followed Series", show_header=True)
          table.add_column("ID", style="dim", justify="right")
          table.add_column("Title")
          table.add_column("TVDB", justify="right")
          table.add_column("TMDB", justify="right")
          table.add_column("IMDB")
          table.add_column("Active")

          for s in rows:
              table.add_row(
                  str(s.id) if s.id is not None else "-",
                  s.title,
                  str(s.media_ref.tvdb_id) if s.media_ref.tvdb_id else "-",
                  str(s.media_ref.tmdb_id) if s.media_ref.tmdb_id else "-",
                  s.media_ref.imdb_id or "-",
                  "[green]yes[/green]" if s.active else "[red]no[/red]",
              )
          console.print(table)


  @follow_app.command("remove")
  @handle_cli_errors
  def follow_remove(
      ctx: typer.Context,
      tvdb_id: Optional[int] = typer.Option(None, "--tvdb", help="TVDB series ID."),
      followed_id: Optional[int] = typer.Option(None, "--id", help="followed_series row ID."),
  ) -> None:
      """Soft-unfollow a series (sets active=False, preserves history).

      Provide --tvdb <id> or --id <followed_id>.
      """
      if tvdb_id is None and followed_id is None:
          typer.echo("Error: provide --tvdb or --id.", err=True)
          raise typer.Exit(code=2)

      config = ctx.obj.config
      assert config is not None
      console: Console = state["console"]
      settings = cli_compat.get_settings()

      with per_step_boundary(config, settings, build_torrent_client=False) as app_context:
          acquire = app_context.acquire
          if acquire is None or acquire.store is None:
              console.print("[red]AcquireContext/store not available.[/red]")
              raise typer.Exit(1)

          store = acquire.store

          if tvdb_id is not None:
              series = store.follow.find_by_ref(MediaRef(tvdb_id=tvdb_id))
          else:
              series = store.follow.get(followed_id)  # type: ignore[arg-type]

          if series is None:
              console.print("[yellow]Series not found — nothing to remove.[/yellow]")
              return

          if not series.active:
              console.print(f"[yellow]Already inactive:[/yellow] {series.title} (id={series.id})")
              return

          assert series.id is not None
          store.follow.set_active(series.id, False)
          app_context.event_bus.emit(SeriesUnfollowed(media_ref=series.media_ref))
          console.print(f"[green]Unfollowed:[/green] {series.title} (id={series.id})")
          log.info("cli.follow.removed", series_id=series.id, title=series.title)


  # Register the follow sub-group on the root Typer app (import side-effect, called by cli.py).
  _root_app.add_typer(follow_app, name="follow")

  __all__ = ["follow_add", "follow_app", "follow_list", "follow_remove"]
  ```

- [ ] **Step 3.1.4: Register in `cli.py`**

  Add the import line at the bottom of `personalscraper/cli.py` (after the existing command imports, ~L114):

  ```python
  import personalscraper.commands.follow  # noqa: E402,F401
  ```

- [ ] **Step 3.1.5: Run tests to confirm they pass**

  ```bash
  python -m pytest tests/commands/test_follow.py -v
  ```

  Expected: all tests PASS.

- [ ] **Step 3.1.6: Commit**

  ```bash
  git add personalscraper/commands/follow.py personalscraper/cli.py tests/commands/test_follow.py
  git commit -m "feat(follow-list): add follow add/list/remove CLI command group"
  ```

---

## Task 7: e2e tests for `follow remove` + reactivate-after-remove + list filters

**Files:**

- Modify: `tests/commands/test_follow.py` (add more tests)

### Sub-phase 3.2 — remove + reactivate + list filter tests

- [ ] **Step 3.2.1: Write failing e2e tests**

  Append to `tests/commands/test_follow.py`:

  ```python
  def test_follow_remove_soft_unfollows(tmp_path: Path, monkeypatch) -> None:
      """follow remove sets active=False; the row is preserved (soft delete)."""
      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
      result = runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])

      assert result.exit_code == 0, result.output

      store2 = build_acquire_store(AcquireConfig(db_path=db_path))
      # Row still exists (soft delete) but active=False.
      all_rows = store2.follow.list_all()
      assert len(all_rows) == 1, f"Expected row preserved after soft delete, got {all_rows}"
      assert all_rows[0].active is False, f"Expected active=False after remove, got {all_rows[0].active}"
      store2.close()
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_remove_emits_series_unfollowed_event(tmp_path: Path, monkeypatch) -> None:
      """LOAD-BEARING: follow remove emits SeriesUnfollowed on the event bus."""
      from personalscraper.acquire.events import SeriesUnfollowed

      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      unfollowed: list[SeriesUnfollowed] = []
      event_bus.subscribe(SeriesUnfollowed, lambda e: unfollowed.append(e))

      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
      runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])

      assert len(unfollowed) == 1, f"Expected 1 SeriesUnfollowed event, got {len(unfollowed)}"
      assert unfollowed[0].media_ref.tvdb_id == 81189
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_reactivate_after_remove_one_row(tmp_path: Path, monkeypatch) -> None:
      """LOAD-BEARING: add → remove → add again reactivates the existing row (not a new row)."""
      from personalscraper.acquire.events import SeriesFollowed

      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      followed_events: list[SeriesFollowed] = []
      event_bus.subscribe(SeriesFollowed, lambda e: followed_events.append(e))

      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
      runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])
      result3 = runner.invoke(app, ["follow", "add", "--tvdb", "81189"])

      assert result3.exit_code == 0, result3.output

      store2 = build_acquire_store(AcquireConfig(db_path=db_path))
      all_rows = store2.follow.list_all()
      assert len(all_rows) == 1, (
          f"LOAD-BEARING: add→remove→add must produce exactly 1 row, got {len(all_rows)}"
      )
      assert all_rows[0].active is True, "Re-added row must be active"
      store2.close()

      # Two SeriesFollowed events total (first add + refollow after remove).
      assert len(followed_events) == 2, (
          f"Expected 2 SeriesFollowed events (add + reactivate), got {len(followed_events)}"
      )
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_list_hides_inactive_by_default(tmp_path: Path, monkeypatch) -> None:
      """LOAD-BEARING: follow list (no --all) hides inactive series."""
      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))
      monkeypatch.setattr(
          "personalscraper.commands.follow.resolve_series_title",
          lambda ref, registry, **kw: "Breaking Bad",
      )

      runner.invoke(app, ["follow", "add", "--tvdb", "81189"])
      runner.invoke(app, ["follow", "remove", "--tvdb", "81189"])

      result_list = runner.invoke(app, ["follow", "list"])

      assert result_list.exit_code == 0, result_list.output
      # LOAD-BEARING: inactive series must NOT appear in default list.
      assert "Breaking Bad" not in result_list.output, (
          f"LOAD-BEARING: 'Breaking Bad' (inactive) must not appear in 'follow list'; got:\n{result_list.output}"
      )
      assert "No followed series" in result_list.output, (
          f"Expected 'No followed series' message; got:\n{result_list.output}"
      )

      result_all = runner.invoke(app, ["follow", "list", "--all"])
      assert result_all.exit_code == 0, result_all.output
      assert "Breaking Bad" in result_all.output, (
          f"Expected 'Breaking Bad' in 'follow list --all'; got:\n{result_all.output}"
      )
      acquire.store.close()  # type: ignore[union-attr]


  def test_follow_remove_not_found_prints_message(tmp_path: Path, monkeypatch) -> None:
      """follow remove on unknown series prints a friendly message, exits 0."""
      db_path = tmp_path / "acquire.db"
      event_bus = EventBus()
      acquire = _acquire_ctx_for(db_path, event_bus)
      app_ctx = _make_app_context(acquire=acquire, event_bus=event_bus)

      monkeypatch.setattr("personalscraper.commands.follow.per_step_boundary", _fake_boundary(app_ctx))

      result = runner.invoke(app, ["follow", "remove", "--tvdb", "99999"])

      assert result.exit_code == 0, result.output
      assert "not found" in result.output.lower(), f"Expected 'not found' message; got:\n{result.output}"
      acquire.store.close()  # type: ignore[union-attr]
  ```

- [ ] **Step 3.2.2: Run all follow tests**

  ```bash
  python -m pytest tests/commands/test_follow.py -v
  ```

  Expected: all tests PASS (the implementation from Task 6 covers these).

  If any fail, fix `commands/follow.py` before proceeding.

- [ ] **Step 3.2.3: Run lint on the new files**

  ```bash
  python -m ruff check personalscraper/commands/follow.py
  python -m mypy personalscraper/commands/follow.py
  ```

  Expected: 0 errors each.

- [ ] **Step 3.2.4: Run the full command test suite to check no regressions**

  ```bash
  python -m pytest tests/commands/ -v
  ```

  Expected: all pass, 0 errors.

- [ ] **Step 3.2.5: Commit**

  ```bash
  git add tests/commands/test_follow.py
  git commit -m "test(follow-list): e2e tests for follow remove, reactivate, list filter, event emission"
  ```

---

## Phase 3 completion check

```bash
python -m pytest tests/commands/test_follow.py -v
# Expected: all pass, 0 errors.

# Smoke: all three sub-commands registered.
python -m pytest tests/commands/test_follow.py -k "help_exits_zero or registered" -v
# Expected: 4 tests pass.

# Verify SeriesFollowed/SeriesUnfollowed imports are not circular.
python -c "import personalscraper.commands.follow; print('ok')"
# Expected: ok

make lint
# Expected: 0 errors.
```

---

## Plan-drift notes (2026-06-12 — Phase 3 gate)

**Commit**: `761e2955` — `feat(follow-list): add follow add/list/remove CLI command group`

**Drifts from plan**:

1. `follow_add` `--title` help string (line 52) was >120 chars (E501). Wrapped `typer.Option` across 5 lines (same pattern as `follow_remove`'s `--tvdb`/`--id` which were already multi-line).
2. `ruff format` reformatted `tests/commands/test_follow.py` after initial write — file was committed post-reformat to keep a clean tree (`git status --short` clean after commit per CI rule).

**Non-drift notes**:

- All plan tests passed first-run without modification (14/14).
- Plan's `test_config` fixture (conftest autouse) does NOT cover `tests/commands/test_follow.py` — but real `config/` is present at the repo root so `load_config` succeeds. Tests rely on `per_step_boundary` + `resolve_series_title` monkeypatch to avoid real AppContext construction.
- `make check` GREEN (0 errors, 91.37% coverage, ruff/mypy/format all clean).
- Smoked idempotent double-add → 1 row (verbatim Python assertion).
