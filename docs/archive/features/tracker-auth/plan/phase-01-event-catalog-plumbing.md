# Phase 1 — TrackerAuthFailed event + catalog plumbing

> DESIGN §4.1. **All six pinned count surfaces land in ONE commit** (omitting any one fails a test or silently drops the event cross-process). One sub-phase = one commit unless noted.

## Gate (what this phase starts from)

- Acquisition catalog already ships the base `Event`, `Event.__init_subclass__` auto-registration, the eager-import hub (`personalscraper/events/__init__.py`), the factory + round-trip gates, and the muted Telegram subscriber.
- `_EVENT_CLASS_REGISTRY` currently holds **33** events; `AcquisitionTelegramSubscriber` registers **10** tokens.
- Layering: `acquire/events.py` may import only `core.event_bus` + `core.identity` + stdlib.

## Phase gate (exit criteria)

Event registered; both catalog count-pins green (34); factory round-trips via the parametrized contract test; subscriber subscribes (token-pin 11). `make check` green.

---

### Sub-phase 1.1 — Add the `TrackerAuthFailed` event class

**Files:**

- Modify: `personalscraper/acquire/events.py` (append a new class; the module is already eager-imported so registration fires automatically)

- [ ] **Step 1: Add the event class** at the end of `personalscraper/acquire/events.py`. `MediaRef` is already imported in this module (`from personalscraper.core.identity import MediaRef`).

```python
@dataclass(frozen=True, kw_only=True)
class TrackerAuthFailed(Event):
    """A tracker rejected the grab with an auth error (HTTP 401/403).

    Emitted by the acquisition orchestrator's ``except TrackerAuthError``
    branch when a ``.torrent`` download fails because the tracker credential
    (apikey/passkey/token) is broken. The item is abandoned (a broken
    credential will not self-heal by retrying the same item); this event is
    the operator-routable signal that the credential needs fixing.

    Attributes:
        tracker: Provider wire name the grab targeted (``top.provider``,
            lowercase).
        http_status: The rejecting HTTP status (401 or 403).
        media_ref: The desired item that could not be grabbed.
    """

    tracker: str
    http_status: int
    media_ref: MediaRef
```

- [ ] **Step 2: Verify registration fires.** Run:

```bash
python -c "import personalscraper.events; from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY; assert 'TrackerAuthFailed' in _EVENT_CLASS_REGISTRY; print(len(_EVENT_CLASS_REGISTRY))"
```

Expected: prints `34` (registry now holds the new event).

---

### Sub-phase 1.2 — Re-export through the events hub

**Files:**

- Modify: `personalscraper/events/__init__.py` (re-export block + `__all__`)

- [ ] **Step 1: Add to the acquire re-export block.** In the `from personalscraper.acquire.events import (...)` block (currently ends `...WantedEnqueued,`), add the import alphabetically:

```python
    SeriesUnfollowed,
    TrackerAuthFailed,
    WantedAbandoned,
    WantedEnqueued,
```

- [ ] **Step 2: Add to `__all__`.** Insert `"TrackerAuthFailed",` keeping alphabetical order (between `"TrailerDownloaded",` and `"VerifyItemDone",`):

```python
    "TrailerDownloaded",
    "TrackerAuthFailed",
    "VerifyItemDone",
```

> Note: `"TrackerAuthFailed"` sorts before `"TrailerDownloaded"` (`Trac` < `Trai`). Place it accordingly:
>
> ```python
>     "StepStarted",
>     "TrackerAuthFailed",
>     "TrailerDownloaded",
>     "VerifyItemDone",
> ```

- [ ] **Step 3: Verify the public import path.** Run:

```bash
python -c "from personalscraper.events import TrackerAuthFailed; print(TrackerAuthFailed.__name__)"
```

Expected: prints `TrackerAuthFailed`.

---

### Sub-phase 1.3 — Bump the two catalog count-pins

**Files:**

- Modify: `tests/event_bus/test_pipeline_events.py:130` and `:131`

- [ ] **Step 1: Bump the count literal.** `tests/event_bus/test_pipeline_events.py:130` — change `== 33` → `== 34`:

```python
    assert len(_EVENT_CLASS_REGISTRY) == 34, (
```

- [ ] **Step 2: Bump the message.** `tests/event_bus/test_pipeline_events.py:131` — change `"23 existing + 10 acquire-events"` → `"23 existing + 11 acquire-events"`, and the count word `34`:

```python
        f"Expected 34 events (23 existing + 11 acquire-events), "
```

- [ ] **Step 3: Run the catalog count-pin test.** Run:

```bash
pytest tests/event_bus/test_pipeline_events.py -q
```

Expected: PASS (count-pin 34 satisfied).

---

### Sub-phase 1.4 — Add the event factory (round-trip coverage)

**Files:**

- Modify: `tests/fixtures/event_samples.py` (one `@register_factory(TrackerAuthFailed)` with real field data)

The parametrized round-trip (`tests/architecture/test_registry_events_contract.py`) and `test_every_event_has_factory` cover the new event automatically — **no separate round-trip test needed**.

- [ ] **Step 1: Import the class** in the acquire-import block of `event_samples.py` (the block that already imports `GrabFailed, GrabSucceeded, ...`). Add `TrackerAuthFailed` alphabetically.

- [ ] **Step 2: Add the factory** mirroring the existing acquire factories. Reuse `_BREAKING_BAD_REF` (already defined: `MediaRef(tvdb_id=81189, tmdb_id=1396, imdb_id="tt0903747")`):

```python
@register_factory(TrackerAuthFailed)
def make_tracker_auth_failed() -> TrackerAuthFailed:
    """Realistic TrackerAuthFailed factory — lacale 401, Breaking Bad."""
    return TrackerAuthFailed(
        tracker="lacale",
        http_status=401,
        media_ref=_BREAKING_BAD_REF,
    )
```

- [ ] **Step 3: Run the contract round-trip + factory-coverage tests.** Run:

```bash
pytest tests/architecture/test_registry_events_contract.py -q
```

Expected: PASS. The JSON envelope round-trips equal and `test_every_event_has_factory` finds the new factory.

---

### Sub-phase 1.5 — Subscribe in the acquisition Telegram subscriber

**Files:**

- Modify: `personalscraper/subscribers/acquire.py` (import, `_tokens` entry, `_on_tracker_auth_failed` formatter, three docstrings `:3`, `:43`, `:95` `10`→`11`)
- Modify: `tests/subscribers/test_acquire_subscriber.py:247` (`== 10` → `== 11`)

- [ ] **Step 1: Import the event.** In `personalscraper/subscribers/acquire.py`, add `TrackerAuthFailed` to the `from personalscraper.acquire.events import (...)` block alphabetically.

- [ ] **Step 2: Add the subscription** to the `self._tokens` list (after the last entry, `bus.subscribe(RatioMeasured, self._on_ratio_measured),`):

```python
            bus.subscribe(RatioMeasured, self._on_ratio_measured),
            bus.subscribe(TrackerAuthFailed, self._on_tracker_auth_failed),
        ]
```

- [ ] **Step 3: Add the formatter** alongside the other `_on_*` handlers, calling `self._dispatch(message, event_name)`. Redact the media identity; **never** log a URL or token (DESIGN §10):

```python
    def _on_tracker_auth_failed(self, event: TrackerAuthFailed) -> None:
        """Format a tracker auth-failure notification.

        Args:
            event: The emitted :class:`TrackerAuthFailed`.
        """
        msg = (
            f"🔐 Tracker auth failed on {event.tracker} "
            f"(HTTP {event.http_status}) — credential needs fixing"
        )
        self._dispatch(msg, "tracker_auth_failed")
```

- [ ] **Step 4: Bump the three subscriber docstrings** `10` → `11`. Exact lines/strings:
  - `:3` — `Subscribes to all 10 acquisition events from` → `Subscribes to all 11 acquisition events from`
  - `:43` — `Subscribes to all 10 acquisition event types defined in` → `... 11 acquisition event types ...`
  - `:95` — `Releases all 10 subscriptions registered in ``__init__``.` → `Releases all 11 subscriptions registered in ``__init__``.`

- [ ] **Step 5: Bump the subscriber token-pin.** `tests/subscribers/test_acquire_subscriber.py:247` — change `== 10` → `== 11`:

```python
    assert len(sub._tokens) == 11
```

(Also update the docstring on `test_close_unsubscribes_all` if it says "all 10 subscriptions" → "all 11 subscriptions".)

- [ ] **Step 6: Run the subscriber tests.** Run:

```bash
pytest tests/subscribers/test_acquire_subscriber.py -q
```

Expected: PASS (token-pin 11 satisfied, formatter renders a non-empty message).

---

### Sub-phase 1.6 — Phase gate + commit

- [ ] **Step 1: Full gate.** Run:

```bash
make check
```

Expected: ruff + mypy clean, all tests pass (`NNNN passed`, 0 failed/errors), module-size + typed-api guardrails green.

- [ ] **Step 2: Smoke import.** Run:

```bash
python -c "import personalscraper; from personalscraper.events import TrackerAuthFailed; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Commit** (all six surfaces in one commit):

```bash
git add personalscraper/acquire/events.py personalscraper/events/__init__.py \
        personalscraper/subscribers/acquire.py \
        tests/event_bus/test_pipeline_events.py tests/fixtures/event_samples.py \
        tests/subscribers/test_acquire_subscriber.py
git commit -m "feat(tracker-auth): add TrackerAuthFailed event + catalog plumbing"
```
