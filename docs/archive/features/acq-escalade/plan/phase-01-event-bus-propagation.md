# Phase 1 — Propagate the process event bus into the post-dispatch scan (D4)

**Defect.** `personalscraper/dispatch/post_maintenance.py:190` builds a brand-new `EventBus()`
and hands it to the post-dispatch incremental scan. That scan's `LibraryScanCompleted` therefore
lands on a throwaway bus with zero subscribers, so `PostDispatchReconcileSubscriber` — subscribed
to the *process* bus — never hears it and never closes owned `wanted` rows.

Live proof: run of 2026-08-04 03:40 completed four scans between 03:46:50 and 03:46:51 with zero
`acquire.*` log lines, and `scripts/check-acquisition-coherence.py` exits 4 with four
`GRABBED_OWNED` phantoms.

**Files:**
- Modify: `personalscraper/dispatch/post_maintenance.py` (`_scan_disk_incremental`,
  `run_post_dispatch_maintenance`, `maybe_run_post_dispatch_maintenance`)
- Modify: `personalscraper/pipeline_steps.py:377` (call site)
- Modify: `personalscraper/commands/pipeline.py:425` (call site)
- Modify: `personalscraper/commands/library/audit.py:538` (call site)
- Test: `tests/dispatch/test_post_maintenance_event_bus.py` (create)

**Interfaces:**
- Produces: `maybe_run_post_dispatch_maintenance(config, results, *, dry_run, event_bus, no_post_maintenance=False)`,
  `run_post_dispatch_maintenance(config, touched_disks, *, event_bus, destinations=None, enabled=True)`,
  `_scan_disk_incremental(config, disk, *, event_bus)`. `event_bus` is keyword-only and
  **required** in all three.

---

- [ ] **Step 1: Write the failing test**

Create `tests/dispatch/test_post_maintenance_event_bus.py`:

```python
"""The post-dispatch scan must emit on the CALLER's bus, not a throwaway one (D4).

A fresh ``EventBus()`` inside ``_scan_disk_incremental`` silently disconnected the
post-dispatch reconciliation: ``PostDispatchReconcileSubscriber`` is subscribed to the
process bus, so a scan emitting elsewhere left owned ``wanted`` rows frozen at 'grabbed'.
"""

from __future__ import annotations

import inspect

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch import post_maintenance


class TestScanUsesCallerBus:
    """``_scan_disk_incremental`` forwards the injected bus verbatim."""

    def test_forwards_caller_bus_to_library_index_command(self, monkeypatch):
        """The bus handed to the scan is the exact object the caller passed."""
        seen: dict[str, object] = {}

        def _fake_library_index_command(**kwargs):
            seen["event_bus"] = kwargs["event_bus"]
            return 0

        monkeypatch.setattr(
            "personalscraper.indexer.commands.scan.library_index_command",
            _fake_library_index_command,
        )
        caller_bus = EventBus()

        post_maintenance._scan_disk_incremental(
            config=_MinimalConfig(),
            disk="disk_1",
            event_bus=caller_bus,
        )

        assert seen["event_bus"] is caller_bus, (
            "the scan must emit on the caller's bus — a fresh EventBus() has no subscribers "
            "and silently drops LibraryScanCompleted (D4)"
        )


class TestEventBusIsRequired:
    """A default would let D4 come back silently — the parameter is required."""

    @pytest.mark.parametrize(
        "func",
        [
            post_maintenance._scan_disk_incremental,
            post_maintenance.run_post_dispatch_maintenance,
            post_maintenance.maybe_run_post_dispatch_maintenance,
        ],
    )
    def test_event_bus_parameter_has_no_default(self, func):
        """``event_bus`` is keyword-only and carries no default value."""
        param = inspect.signature(func).parameters["event_bus"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default is inspect.Parameter.empty, (
            f"{func.__name__} must REQUIRE event_bus — a default is what produced D4"
        )
```

`_MinimalConfig` is the minimal stand-in the module needs; build it from the existing
dispatch-test fixtures rather than inventing one — check `tests/dispatch/conftest.py` for the
config factory already in use and reuse it. If none exists, use the real `Config` produced by
the hermetic config fixture.

- [ ] **Step 2: Run the test to verify it fails**

Run: `command python -m pytest tests/dispatch/test_post_maintenance_event_bus.py -v`
Expected: FAIL — `_scan_disk_incremental` has no `event_bus` parameter (TypeError), and the
signature assertions fail.

- [ ] **Step 3: Make `_scan_disk_incremental` take the bus**

In `personalscraper/dispatch/post_maintenance.py`, change the signature and drop the local
`EventBus` import:

```python
def _scan_disk_incremental(config: Config, disk: str, *, event_bus: EventBus) -> int:
    """Run ``library-index --mode incremental --disk D --no-budget``.

    Uses the programmatic entry point rather than shelling out.

    Args:
        config: Validated application Config.
        disk: Disk label (e.g. ``"disk_1"``) — must exist in ``config.disks``.
        event_bus: The CALLER's process bus, forwarded verbatim to the scan so its
            ``LibraryScanCompleted`` reaches the live subscribers (notably
            ``PostDispatchReconcileSubscriber``). Required: a fresh ``EventBus()`` here
            silently dropped every post-dispatch reconciliation (D4).

    Returns:
        Exit code (0 = success, non-zero = failure).
    """
    import personalscraper.indexer.cli as _cli  # noqa: F401
    from personalscraper.conf.loader import resolve_config_path
    from personalscraper.indexer.commands.scan import library_index_command

    _log.info("post_maintenance_scan_start", disk=disk)
    rc = library_index_command(
        mode="incremental",
        disk=disk,
        no_budget=True,
        event_bus=event_bus,
        config_path=resolve_config_path(),
    )
```

Add the `EventBus` import to the module's `TYPE_CHECKING` block:

```python
if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus
```

- [ ] **Step 4: Thread the bus through the two public functions**

`run_post_dispatch_maintenance` — add the required keyword-only parameter, document it, and
forward it at the `_scan_disk_incremental` call:

```python
def run_post_dispatch_maintenance(
    config: Config,
    touched_disks: set[str],
    *,
    event_bus: EventBus,
    destinations: dict[str, set[Path]] | None = None,
    enabled: bool = True,
) -> None:
```

Add to its `Args:` block:

```
        event_bus: The caller's process bus, forwarded to every disk scan so
            ``LibraryScanCompleted`` reaches live subscribers. Required (D4).
```

`maybe_run_post_dispatch_maintenance` — same, forwarding to `run_post_dispatch_maintenance`:

```python
def maybe_run_post_dispatch_maintenance(
    config: Config,
    results: list[DispatchResult],
    *,
    dry_run: bool,
    event_bus: EventBus,
    no_post_maintenance: bool = False,
) -> None:
```

Grep the module for every internal call of both functions and add `event_bus=event_bus`.

- [ ] **Step 5: Update the three call sites**

`personalscraper/pipeline_steps.py:377`:

```python
        maybe_run_post_dispatch_maintenance(
            ctx.app.config,
            results,
            dry_run=ctx.dry_run,
            event_bus=ctx.app.event_bus,
            no_post_maintenance=bool(ctx.extras.get("no_post_maintenance", False)),
        )
```

`personalscraper/commands/pipeline.py:425` — use the same bus already used to build the
reconcile subscriber a few lines above (read it at line ~394 and pass that exact object):

```python
    maybe_run_post_dispatch_maintenance(
        config,
        results,
        dry_run=dry_run,
        event_bus=event_bus,
        no_post_maintenance=no_post_maintenance,
    )
```

`personalscraper/commands/library/audit.py:538` — this CLI owns its boundary; pass the bus
already in scope there. If none is in scope, take it from the `per_step_boundary` app context
(`app_context.event_bus`); do NOT construct a fresh one.

```python
    run_post_dispatch_maintenance(
        cfg,
        {owning_label},
        event_bus=event_bus,
        destinations={owning_label: {target}},
        enabled=True,
    )
```

- [ ] **Step 6: Run the new test to verify it passes**

Run: `command python -m pytest tests/dispatch/test_post_maintenance_event_bus.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Add the end-to-end regression**

Append to the same test file — this is the test that reproduces the operator-visible bug:

```python
class TestReconcileClosesOwnedRowAfterDispatch:
    """The whole point of D4: a dispatched, owned episode stops being « en cours »."""

    def test_grabbed_row_of_owned_episode_is_closed_by_post_dispatch_scan(self):
        """A subscriber on the caller's bus receives the scan's completion event.

        Regression for the 2026-08-04 03:40 run: four scans completed, the reconcile
        subscriber heard none of them, and four wanted rows stayed 'grabbed' while the
        library already owned the episodes.
        """
        from personalscraper.indexer.events import LibraryScanCompleted

        bus = EventBus()
        received: list[LibraryScanCompleted] = []
        bus.subscribe(LibraryScanCompleted, received.append)

        # Drive the real post-dispatch maintenance over a disk whose scan emits.
        # Use the existing dispatch e2e fixture that produces a touched disk.
        ...  # build via the fixtures already used by tests/dispatch/

        assert received, (
            "the post-dispatch scan must emit LibraryScanCompleted on the caller's bus"
        )
```

Fill the `...` using the fixtures already present under `tests/dispatch/` — do not invent a new
harness. If no fixture produces a scannable disk, assert instead at the seam: monkeypatch
`library_index_command` to emit `LibraryScanCompleted` on the bus it receives, then assert the
subscriber on the caller's bus got it.

- [ ] **Step 8: Run the full acquire + dispatch suites**

Run: `command python -m pytest tests/dispatch/ tests/acquire/ -q`
Expected: all pass, no regression.

- [ ] **Step 9: Phase gate**

```bash
make lint
make test
make check
python3 scripts/check-module-size.py
```

Expected: lint 0 errors; test 0 failed / 0 error; check exit 0; module-size unchanged (this
phase adds only signature lines).

- [ ] **Step 10: Commit**

```bash
git add personalscraper/dispatch/post_maintenance.py \
        personalscraper/pipeline_steps.py \
        personalscraper/commands/pipeline.py \
        personalscraper/commands/library/audit.py \
        tests/dispatch/test_post_maintenance_event_bus.py
git commit -m "fix(acq-escalade): le scan post-dispatch émet sur le bus du processus"
```
