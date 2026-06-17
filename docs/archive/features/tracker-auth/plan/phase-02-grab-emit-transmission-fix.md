# Phase 2 — Grab emit + Transmission add() fix

> DESIGN §4.2 / §8. Two changes inside the resolve/add `try` ladder at `personalscraper/acquire/orchestrator.py:241-259`. One sub-phase = one commit.

## Gate (what this phase starts from)

- **Phase 1 is complete:** `TrackerAuthFailed(tracker, http_status, media_ref)` exists, is registered, re-exported via `personalscraper.events`, has a factory, and the subscriber subscribes. Phase 2 imports and emits it.
- The orchestrator currently builds `tags = (top.provider,)` and calls `self._torrent_client.add(source, category=category, tags=tags)` inside an outer `try` whose ladder is, in order: `CircuitOpenError → TrackerAuthError → TorrentFetchError → ApiError`.
- The `except TrackerAuthError:` branch today is a **silent** `return self._terminal(media_ref, "tracker_auth", chosen=top)`.
- A Transmission client rejects `add(category=None, tags=(provider,))` with `ValueError` (`transmission.py:227-235`, flat `labels=[category, *tags]`). qBit + Transmission both handle the category-less `add_tags` case via the seed-pure empty-string sentinel.

## Phase gate (exit criteria)

`make check` green. Emit-on-401 and Transmission no-crash tests are mutation-proof.

---

### Sub-phase 2.1 — Emit `TrackerAuthFailed` on the auth-error branch

**Files:**

- Modify: `personalscraper/acquire/orchestrator.py` (import + the `except TrackerAuthError` branch at `:250`)
- Test: `tests/acquire/test_grab_auth_event.py` (new)

- [ ] **Step 1: Write the failing tests** in `tests/acquire/test_grab_auth_event.py`. Use a **real/captured EventBus**, not a bare `MagicMock`, so the emission is actually observed. Mirror the existing grab-test fixtures (look at the current `tests/acquire/` grab tests for the orchestrator + fake torrent-client/transports setup).

```python
def test_grab_emits_tracker_auth_failed_on_401(grab_orchestrator, captured_bus):
    """resolve_source raising TrackerAuthError(401) emits exactly one event."""
    # Arrange: resolve_source raises TrackerAuthError(http_status=401).
    outcome = grab_orchestrator.grab(WANTED_ITEM)

    # Disposition unchanged: terminal abandon, reason 'tracker_auth'.
    assert outcome.is_terminal
    assert outcome.reason == "tracker_auth"

    # Exactly one TrackerAuthFailed with the right payload.
    events = [e for e in captured_bus.events if isinstance(e, TrackerAuthFailed)]
    assert len(events) == 1
    assert events[0].tracker == TOP_PROVIDER          # == top.provider
    assert events[0].http_status == 401
    assert events[0].media_ref == EXPECTED_MEDIA_REF


def test_grab_non_auth_failures_emit_no_auth_event(grab_orchestrator, captured_bus):
    """TorrentFetchError -> 'fetch_failed', ApiError -> 'add_failed': zero auth events."""
    outcome = grab_orchestrator.grab(WANTED_ITEM)  # resolve_source raises TorrentFetchError

    assert outcome.is_retryable
    assert outcome.reason == "fetch_failed"
    assert not any(isinstance(e, TrackerAuthFailed) for e in captured_bus.events)
```

> Adjust attribute names (`is_terminal`/`reason`) to the actual `GrabOutcome` API used by the existing grab tests — read one neighbouring test first. Add an `ApiError` variant asserting `reason == "add_failed"` + zero auth events.

- [ ] **Step 2: Run to verify failure.** Run:

```bash
pytest tests/acquire/test_grab_auth_event.py -q
```

Expected: FAIL (no `TrackerAuthFailed` emitted yet).

- [ ] **Step 3: Import the event** at the top of `orchestrator.py`:

```python
from personalscraper.acquire.events import TrackerAuthFailed
```

- [ ] **Step 4: Emit before the terminal return.** Change the `except TrackerAuthError:` branch (`:250`) to bind the exception and emit:

```python
        except TrackerAuthError as exc:
            # 401/403: passkey/config broken — won't self-heal → abandon.
            # Emit the operator-routable signal BEFORE abandoning (follows the
            # orchestrator's self-emit-on-failure convention; correlation_id
            # propagates via the Event base ContextVar).
            self._event_bus.emit(
                TrackerAuthFailed(
                    tracker=top.provider,
                    http_status=exc.http_status,
                    media_ref=media_ref,
                )
            )
            return self._terminal(media_ref, "tracker_auth", chosen=top)
```

> Confirm the bus attribute name (`self._event_bus`) matches how the orchestrator already emits/holds the bus — grep the file: `rg "self\._event_bus|self\._bus" -g '*.py' personalscraper/acquire/orchestrator.py`. Use whichever it actually is.

- [ ] **Step 5: Run to verify pass.** Run:

```bash
pytest tests/acquire/test_grab_auth_event.py -q
```

Expected: PASS.

- [ ] **Step 6: Mutation check (mutation-proof requirement).** Temporarily delete the `self._event_bus.emit(...)` call, re-run the test, confirm `test_grab_emits_tracker_auth_failed_on_401` **FAILS**, then restore the emit.

- [ ] **Step 7: Commit.**

```bash
git add personalscraper/acquire/orchestrator.py tests/acquire/test_grab_auth_event.py
git commit -m "feat(tracker-auth): emit TrackerAuthFailed on grab 401/403"
```

---

### Sub-phase 2.2 — Transmission `add()` fix: add first, then tag

**Files:**

- Modify: `personalscraper/acquire/orchestrator.py` (the `try` body at `:243-246`)
- Test: `tests/acquire/test_grab_transmission_add.py` (new)

- [ ] **Step 1: Write the failing tests** in `tests/acquire/test_grab_transmission_add.py`. Three behaviours:

```python
def test_grab_transmission_adds_without_crash_and_tags(grab_orchestrator_transmission):
    """Against a Transmission client: add() succeeds and the provider tag is applied."""
    client = grab_orchestrator_transmission.client  # fake Transmission (TorrentTagger)
    outcome = grab_orchestrator_transmission.grab(WANTED_ITEM)

    assert outcome.is_success
    # Readable back via the seed-pure sentinel: category is None, provider tag present.
    added = client.added[0]
    assert added.category is None
    assert TOP_PROVIDER in client.tags_for(added.info_hash)


def test_grab_add_tags_failure_after_add_is_non_fatal(grab_orchestrator_tag_raises):
    """add() succeeds, add_tags raises ApiError -> item grabbed, logged, NOT re-bucketed."""
    outcome = grab_orchestrator_tag_raises.grab(WANTED_ITEM)

    # Item is grabbed (success), NOT a retryable 'add_failed' (which would
    # cause a duplicate add next run).
    assert outcome.is_success
    assert getattr(outcome, "reason", None) != "add_failed"
```

> The first test is **mutation-proof**: reverting the production change to `add(category=None, tags=(provider,))` reproduces the Transmission `ValueError`. Read a neighbouring grab test to wire the fake Transmission client (a `TorrentTagger`) and a tag-raising variant.

- [ ] **Step 2: Run to verify failure.** Run:

```bash
pytest tests/acquire/test_grab_transmission_add.py -q
```

Expected: FAIL — `add(category=None, tags=(provider,))` raises `ValueError` on the Transmission client; the tag-failure test fails because there is no inner swallow yet.

- [ ] **Step 3: Add the import** at module top of `orchestrator.py`. **RUNTIME import — NOT under `if TYPE_CHECKING:`** (it is used in a runtime `isinstance`; the file's existing `_contracts` import is TYPE_CHECKING-only, so do NOT add it there). Verified path (not re-exported at the package level):

```python
from personalscraper.api.torrent._contracts import TorrentTagger
```

> `TorrentTagger` is `@runtime_checkable` (`_contracts.py:180`), so the `isinstance` is valid. `ApiError` is already imported in this file — reuse it (do not re-import). Confirm with `rg "class TorrentTagger" -g '*.py' personalscraper/api/torrent/_contracts.py`.

- [ ] **Step 4: Replace the try body.** Change the two-line resolve/add inside the **same outer `try`** to add-first-then-tag. Drop the `tags` local (no longer passed to `add`); keep `category = None`:

```python
        try:
            source = resolve_source(top, self._transports)
            info_hash = self._torrent_client.add(source, category=category)
            if isinstance(self._torrent_client, TorrentTagger):
                try:
                    self._torrent_client.add_tags(info_hash, [top.provider])
                except ApiError as exc:
                    # Torrent is ADDED; the provider tag is provenance metadata.
                    # A tag failure must NOT bubble to the outer `except ApiError`
                    # (that would re-bucket an already-added torrent as
                    # add_failed -> retryable -> a duplicate add next run).
                    # Swallow + log; end state 'added' stands.
                    log.warning(
                        "acquire.grab.tag_failed",
                        hash=info_hash,
                        provider=top.provider,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
        except CircuitOpenError:
            return self._retryable(media_ref, "circuit_open", chosen=top)
        except TrackerAuthError as exc:
            ...  # (unchanged — emits TrackerAuthFailed, from 2.1)
        except TorrentFetchError:
            return self._retryable(media_ref, "fetch_failed", chosen=top)
        except ApiError:
            return self._retryable(media_ref, "add_failed", chosen=top)
```

> **Invariants (verify by reading the final file):** `resolve_source` and `add()` stay inside the SAME outer `try`; ladder order `CircuitOpenError → TrackerAuthError → TorrentFetchError → ApiError` preserved (`CircuitOpenError` is NOT an `ApiError` subclass and must precede it); `category` stays `None`. The inner `try` around `add_tags` is the ONLY new swallow.
> Remove the now-dead `tags: tuple[str, ...] = (top.provider,)` line. Confirm `log` is the module logger already in scope (it is used elsewhere in the file — grep `rg "^log = |get_logger" -g '*.py' personalscraper/acquire/orchestrator.py`).

- [ ] **Step 5: Run to verify pass.** Run:

```bash
pytest tests/acquire/test_grab_transmission_add.py -q
```

Expected: PASS (no crash, tag applied, tag-failure non-fatal).

- [ ] **Step 6: Mutation check (mutation-proof requirement).** Temporarily revert the `add` call to `self._torrent_client.add(source, category=category, tags=(top.provider,))`, re-run, confirm `test_grab_transmission_adds_without_crash_and_tags` **FAILS** with `ValueError`, then restore.

- [ ] **Step 7: Commit.**

```bash
git add personalscraper/acquire/orchestrator.py tests/acquire/test_grab_transmission_add.py
git commit -m "fix(tracker-auth): add torrent then tag to avoid Transmission ValueError"
```

---

### Sub-phase 2.3 — Phase gate

- [ ] **Step 1: Full gate.** Run:

```bash
make check
```

Expected: ruff + mypy clean, all tests pass (`NNNN passed`, 0 failed/errors), guardrails green.

- [ ] **Step 2: Smoke import.** Run:

```bash
python -c "import personalscraper; print('ok')"
```

Expected: prints `ok`.

- [ ] **Step 3: Acceptance re-exercise** (DESIGN §9):

```bash
python -c "from personalscraper.events import TrackerAuthFailed"
pytest tests/event_bus/test_pipeline_events.py -q
pytest tests/acquire/test_grab_auth_event.py -q
pytest tests/acquire/test_grab_transmission_add.py -q
pytest tests/subscribers/test_acquire_subscriber.py -q
```

Expected: all PASS (count-pin 34, emit-on-401 + non-auth-no-event, no-crash + tag-applied + tag-failure-soft, token-pin 11).
