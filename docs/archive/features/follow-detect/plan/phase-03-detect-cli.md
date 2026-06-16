# Phase 3 — DETECT logic + `follow detect` CLI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add `@follow_app.command("detect")` to `commands/follow.py`. The command calls `list_active` → ONE `poll_aired(active, ...)` over the active set → map each aired episode back to its series by `media_ref` → ownership filter → dedup → `store.wanted.add` + emit `WantedEnqueued`. Flags: `--dry-run` (no writes/emits), `--series` (filter active set). Rich table output. Tests: criteria 5-6, 8 (boundary), 9 (layering).

**Architecture:** All logic in one command function; no separate module. Reuses `per_step_boundary(build_torrent_client=False)` exactly like `follow list`. `poll_aired` and `ownership.owns` are fail-soft (log + continue). `now` is a real `int(time.time())` call (tests need NOT pin `now`).

> **Ground-truth corrections applied at implementation (plan-drift, same commit):**
>
> - The provider registry is **`app_context.provider_registry`** (an `AppContext` field), NOT `acquire.provider_registry` (the `AcquireContext` has no such field — it would raise `AttributeError`).
> - `poll_aired(series, registry, *, today)` takes a **`Sequence[FollowedSeries]`**, NOT a single series — the command issues ONE `poll_aired(active, ...)` call and maps results back by `media_ref` (Stage A, DESIGN §2).
> - Stage A (this phase) does NOT import `cadence_from_config` / `cadence_from_json` / `effective_cadence` — cadence is Phase 4.
> - Tests: the `patch(... .int)` / `mock_int` lines were removed (patching builtin `int` is wrong and unneeded). A NON-VACUOUS real-store integration test was added that catches the two bugs above.

**Tech Stack:** Python 3.11+, `typer`, `rich`, `pytest`, `unittest.mock`, `make test`

---

## Gate

Phase 2 must be complete:

- [ ] `personalscraper/acquire/_ports.py` `WantedSubStore` protocol has `find`.
- [ ] `personalscraper/acquire/store.py` `_WantedSubStore` implements `find`.
- [ ] `pytest tests/acquire/test_store_wanted_find.py` passes with 0 failures.

---

## Sub-phase 3.1 — `follow detect` command

**Files:**

- Modify: `personalscraper/commands/follow.py`
- Create: `tests/commands/test_follow_detect.py`

### Task 1: Write failing tests first (TDD)

- [ ] **Step 1: Create `tests/commands/test_follow_detect.py` (golden + dry-run + non-vacuous integration)**

The implemented test file is the source of truth — see `tests/commands/test_follow_detect.py`. It contains **8 tests** (the original 7 mock-based + 1 non-vacuous real-store integration). Corrections vs the original draft:

- `_make_ctx` sets the registry on **`app_context.provider_registry`** (the real `AppContext` field), NOT `acquire.provider_registry`; `app_context.event_bus` carries the bus; `acquire` exposes only `store` + `ownership`.
- `_run_detect` patches **only** `per_step_boundary` (yielding `app_context`) and `poll_aired` (returning the aired list). The `patch(... .int)` / `mock_int` lines are **removed** — patching builtin `int` is wrong and the assertions never check `enqueued_at`.
- The boundary test installs an explicit `grab` MagicMock on `acquire` and asserts `assert_not_called()` + no `method_calls` (a bare auto-speccing MagicMock would make the original `.called` check vacuously pass).
- The 7 mock assertions are kept: golden enqueue (asserts the `WantedItem` has `followed_id` mapped via `by_ref`, `kind='episode'`, `status='pending'`, `season`, `episode`; `WantedEnqueued` emitted once with the right `season`/`episode`), skip-owned, skip-dup, dry-run no-writes, empty-set, boundary-no-grab, ast-layering-no-indexer.
- **`test_detect_integration_enqueues_into_real_store` (NON-VACUOUS, mandatory):** builds a REAL `build_acquire_store(AcquireConfig(db_path=tmp_path/'acquire.db'))`, adds a real `FollowedSeries` (captures its id), wraps it in a real `AcquireContext(store=<real>, ownership=NullOwnershipChecker())`, exposes it behind a `SimpleNamespace` app-context with the REAL attribute names (`provider_registry` stub, real `EventBus`, `acquire`). Patches `per_step_boundary` to yield it and `poll_aired` to return one `AiredEpisode` whose `media_ref` equals the followed series' `media_ref`. Invokes `follow_detect(ctx, dry_run=False, series=None)`, then asserts `store.wanted.find(followed_id=<id>, kind='episode', season=.., episode=..)` returns a real `WantedItem` with `status='pending'`. This test FAILS (verified) if anyone reverts to `acquire.provider_registry` (real `AttributeError`) or `poll_aired(fs, ...)` (the poll-spy asserts ONE call over the Sequence). The store is closed in `finally`.

- [ ] **Step 2: Confirm tests FAIL (command not yet defined)**

```bash
pytest tests/commands/test_follow_detect.py -v 2>&1 | head -20
```

Expected: `ImportError` or `AttributeError` — `follow_detect` does not exist yet.

### Task 2: Implement `follow_detect` in `commands/follow.py`

- [ ] **Step 3: Add required imports to `follow.py`** (after existing imports)

```python
from datetime import date

from personalscraper.acquire.airing import poll_aired
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import WantedEnqueued
```

Note: `Table`, `Console`, `time`, `Optional` are already imported in `follow.py` — add only `date`, `poll_aired`, `WantedItem`, and merge `WantedEnqueued` into the existing `acquire.events` import line. Do **NOT** import `cadence_from_config` / `cadence_from_json` / `effective_cadence` — Stage A does not use cadence (Phase 4 territory).

- [ ] **Step 4: Add the `follow_detect` command before `_root_app.add_typer`**

```python
@follow_app.command("detect")
@handle_cli_errors
def follow_detect(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing or emitting."),
    series: Optional[str] = typer.Option(None, "--series", help="Filter active set by title substring or followed_id."),
) -> None:
    """Detect aired episodes for followed series and enqueue them as wanted items.

    For each active followed series, polls aired episodes via the calendar
    provider (RP9), skips owned episodes (RP6) and duplicates already in the
    wanted queue, then enqueues the remainder as WantedItem(kind='episode',
    status='pending') and emits WantedEnqueued per enqueue.

    Use --dry-run to preview without any writes or events.
    Use --series to restrict detection to a single series (title substring or row ID).
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
        ownership = acquire.ownership
        bus = app_context.event_bus
        registry = app_context.provider_registry  # AppContext field — NOT acquire.*
        today = date.today()
        now = int(time.time())

        active = store.follow.list_active()
        if not active:
            console.print("[yellow]No active followed series.[/yellow]")
            return

        # Optional filter: integer followed_id, else case-insensitive title substring.
        if series is not None:
            try:
                filter_id = int(series)
                active = [s for s in active if s.id == filter_id]
            except ValueError:
                active = [s for s in active if series.lower() in s.title.lower()]
            if not active:
                console.print("[yellow]No matching series.[/yellow]")
                return

        # MediaRef is a frozen dataclass → hashable; map aired episodes back to series.
        by_ref = {s.media_ref: s for s in active}

        # ONE poll over the active SET (Stage A, DESIGN §2). poll_aired takes a
        # Sequence[FollowedSeries] and is fail-soft per series internally, so the
        # broad except here is purely defensive.
        try:
            aired = poll_aired(active, registry, today=today)
        except Exception as exc:  # noqa: BLE001 — defensive; poll_aired already fail-soft
            log.warning("cli.follow.detect.poll_failed", error=str(exc))
            aired = []

        table = Table(title="Follow Detect", show_header=True)
        table.add_column("Series")
        table.add_column("Season", justify="right")
        table.add_column("Episode", justify="right")
        table.add_column("AirDate")
        table.add_column("Title")
        table.add_column("Action")

        enqueued = skipped_owned = skipped_dup = 0

        for ep in aired:
            fs = by_ref.get(ep.media_ref)
            if fs is None or fs.id is None:
                continue

            # Ownership check (fail-soft: error → treat as not-owned).
            try:
                owned = ownership.owns(ep.media_ref, kind="episode", season=ep.season, episode=ep.episode)
            except Exception as exc:  # noqa: BLE001 — fail-soft → treat as not-owned
                log.warning("cli.follow.detect.ownership_error", error=str(exc))
                owned = False

            if owned:
                table.add_row(fs.title, str(ep.season), str(ep.episode), str(ep.air_date), ep.title, "[yellow]skipped-owned[/yellow]")
                skipped_owned += 1
                continue

            # Dedup against the wanted queue.
            if store.wanted.find(followed_id=fs.id, kind="episode", season=ep.season, episode=ep.episode) is not None:
                table.add_row(fs.title, str(ep.season), str(ep.episode), str(ep.air_date), ep.title, "[dim]skipped-dup[/dim]")
                skipped_dup += 1
                continue

            action = "[dim]dry-run[/dim]" if dry_run else "[green]enqueued[/green]"
            table.add_row(fs.title, str(ep.season), str(ep.episode), str(ep.air_date), ep.title, action)
            enqueued += 1

            if not dry_run:
                store.wanted.add(WantedItem(
                    media_ref=ep.media_ref,
                    kind="episode",
                    status="pending",
                    enqueued_at=now,
                    followed_id=fs.id,
                    season=ep.season,
                    episode=ep.episode,
                ))
                bus.emit(WantedEnqueued(
                    media_ref=ep.media_ref,
                    kind="episode",
                    season=ep.season,
                    episode=ep.episode,
                ))
                log.info("cli.follow.detect.enqueued", series=fs.title, season=ep.season, episode=ep.episode)

        console.print(table)
        console.print(
            f"{enqueued} enqueued, {skipped_owned} skipped-owned, {skipped_dup} skipped-dup"
            + (" [dim](dry-run)[/dim]" if dry_run else "")
        )
```

- [ ] **Step 5: Update `__all__` in `follow.py`**

```python
__all__ = ["follow_add", "follow_app", "follow_detect", "follow_list", "follow_remove"]
```

- [ ] **Step 6: Run detect tests — all must PASS**

```bash
pytest tests/commands/test_follow_detect.py -v
```

Expected: `8 passed`, `0 failed` (7 mock-based + 1 non-vacuous real-store integration).

- [ ] **Step 7: Commit**

```bash
git add personalscraper/commands/follow.py tests/commands/test_follow_detect.py
git commit -m "feat(follow-detect): add follow detect CLI command with --dry-run/--series"
```

---

## Phase 3 Gate

- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must exit 0.
- [ ] **CLI registration check:**

```bash
python -c "
from personalscraper.commands.follow import follow_app
cmds = [c.name for c in follow_app.registered_commands]
assert 'detect' in cmds, f'detect missing: {cmds}'
print('OK:', cmds)
"
```

Expected: `OK: [... 'detect' ...]`.
