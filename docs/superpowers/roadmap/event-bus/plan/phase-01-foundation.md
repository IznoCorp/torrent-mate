# Phase 1 — Foundation (standalone)

**Depends on**: nothing (clean branch).
**Commits expected**: **9** (one per sub-phase; sub-phase 1.9 IS the phase-gate commit).
**Goal**: Land the EventBus + Event base + serialization + ContextVar capture as a fully tested, standalone module with zero pipeline integration. After Phase 1, the bus can be imported and exercised by tests, but nothing in `personalscraper` emits to it yet.

## Scope

**In scope** (DESIGN.md §Architecture, §JSON serialization contract, §Performance notes):

- `personalscraper/core/event_bus.py` — `EventBus`, `Event` base, `SubscriptionToken`, `current_correlation_id` (ContextVar), `event_to_dict`, `event_to_envelope`, `event_from_envelope`, event class registry helpers.
- Unit-test suite covering dispatch, MRO cache, fast path, error isolation, re-entrancy, ContextVar capture, JSON round-trip.
- `tests/fixtures/event_bus.py` — `CollectingSubscriber[E]` generic helper.
- `tests/fixtures/event_samples.py` — `EVENT_SAMPLE_FACTORIES` registry mechanism + `test_every_event_has_factory` (vacuously green in Phase 1 since no concrete events exist yet; mechanism is in place for Phase 3+).

**Out of scope (deferred to later phases — but the mechanism for each is fully built here)**:

- Concrete event subclasses (`PipelineStarted`, …) — Phase 3.
- Any code in `personalscraper/` that emits — Phases 3–4.
- `AppContext` — Phase 2.
- Subscribers (`RichConsoleSubscriber`, …) — Phase 3 / 5.

---

## Sub-phase 1.1 — Module scaffold + Event base + ContextVar

**Files**:

- Create: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/__init__.py`
- Create: `tests/event_bus/test_event_base.py`

**Behavior delivered**:

- `current_correlation_id: ContextVar[str | None]` module-level, default `None`.
- `Event` frozen dataclass with fields: `timestamp` (default_factory `datetime.now(UTC)`), `source: str` (auto-derived in `__post_init__` from `f"{cls.__module__}.{cls.__name__}"` when empty), `event_id: UUID` (default_factory `uuid4`), `correlation_id: str | None` (default_factory `lambda: current_correlation_id.get()`).
- `__post_init__` uses `object.__setattr__` (frozen-safe) to populate auto-derived `source`.

**Tests written**:

- `test_event_default_source_is_module_dot_class`: build a subclass `class Foo(Event): pass`; instantiate; assert `event.source == f"{Foo.__module__}.Foo"`.
- `test_event_explicit_source_is_respected`: build `Foo(source="custom")`; assert `event.source == "custom"`.
- `test_event_timestamp_is_utc_aware`: instantiate; assert `event.timestamp.tzinfo is UTC`.
- `test_event_event_id_is_unique_per_instance`: build 2 events; assert distinct `event_id`.
- `test_event_correlation_id_default_is_none_outside_bound_region`: assert `Event().correlation_id is None`.
- `test_event_correlation_id_captured_inside_bound_region`: set ContextVar to `"abc"` via `set` token; build `Event()` inside; assert `event.correlation_id == "abc"`; reset token; build again, assert `correlation_id is None`.
- `test_event_correlation_id_explicit_overrides_contextvar`: set ContextVar to `"abc"`; build `Event(correlation_id="explicit")`; assert `event.correlation_id == "explicit"`.

**Steps**:

- [ ] Write failing tests in `tests/event_bus/test_event_base.py`.
- [ ] Run `pytest tests/event_bus/test_event_base.py -v` → expect import error / collection failure.
- [ ] Implement `Event` base + `current_correlation_id` in `personalscraper/core/event_bus.py`.
- [ ] Run tests → all pass.
- [ ] `make lint` zero errors.
- [ ] Commit: `feat(event-bus): introduce Event base + current_correlation_id ContextVar`.

---

## Sub-phase 1.2 — SubscriptionToken + subscribe / unsubscribe (no emit yet)

**Files**:

- Modify: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/test_subscribe.py`

**Behavior delivered**:

- `SubscriptionToken` opaque handle (frozen dataclass with internal id + event_type reference; no public mutable fields).
- `EventBus.__init__` initializes `_subscribers: dict[type[Event], tuple[tuple[SubscriptionToken, Callable], ...]]`.
- `EventBus.subscribe(event_type, callback) -> SubscriptionToken`: rebuilds the tuple (copy-on-write) with the new `(token, callback)` appended.
- `EventBus.unsubscribe(token)`: rebuilds the tuple without the matching entry. No-op (no raise) if token not found — idempotent.
- `subscribe` does NOT yet trigger dispatch — emit is the next sub-phase.

**Tests written**:

- `test_subscribe_returns_distinct_tokens`: subscribe twice; assert tokens are distinct objects with distinct internal ids.
- `test_subscribers_stored_per_type`: subscribe to `Event` and a subclass; assert internal dict has two keys.
- `test_subscribe_is_copy_on_write`: subscribe; capture the tuple; subscribe again; assert the previously-captured tuple object is unchanged (still N entries) and the new tuple is a fresh object (N+1).
- `test_unsubscribe_removes_callback`: subscribe; unsubscribe; assert internal tuple is empty (or key removed).
- `test_unsubscribe_unknown_token_is_noop`: build a token-shaped object that was never subscribed; unsubscribe; assert no exception raised and dict unchanged.

**Steps**:

- [ ] Write failing tests.
- [ ] Run → fail.
- [ ] Implement `SubscriptionToken` + `EventBus.subscribe` + `EventBus.unsubscribe`.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): add EventBus.subscribe and unsubscribe with copy-on-write storage`.

---

## Sub-phase 1.3 — emit + MRO cache + fast path

**Files**:

- Modify: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/test_emit.py`

**Behavior delivered**:

- `EventBus.emit(event)`:
  - Fast path: if `_subscribers` dict is empty → return immediately after the single `if` check.
  - Otherwise: resolve the subscriber tuple for `type(event)` via MRO walk; cache the resolution in `_mro_cache: dict[type[Event], tuple[Callable, ...]]`.
  - Invoke each callback in subscription order.
  - Subscribers of ancestor types invoked AFTER subscribers of the concrete type (concrete wins for ordering — see DESIGN §Dispatch semantics #5).
- `subscribe` / `unsubscribe` invalidate `_mro_cache` (clear the cache entirely; rebuilding on next emit is cheap).

**Tests written**:

- `test_emit_invokes_subscriber_of_exact_type`: subscribe to `Foo`; emit `Foo()`; assert callback received the event.
- `test_emit_invokes_subscriber_of_base_event`: subscribe to `Event`; emit `Foo(Event)`; assert callback received the event.
- `test_emit_invokes_subscriber_of_intermediate_ancestor`: define `Bar(Foo)`; subscribe to `Foo`; emit `Bar()`; assert callback received it.
- `test_emit_does_not_invoke_unrelated_type_subscribers`: subscribe to `Baz`; emit `Foo()`; assert `Baz` callback NOT invoked.
- `test_emit_ordering_concrete_before_ancestor`: subscribe `concrete_cb` to `Foo`, then `base_cb` to `Event`; emit `Foo()`; assert call order `[concrete_cb, base_cb]`.
- `test_emit_with_no_subscribers_is_noop`: instantiate bus; emit `Foo()`; assert no exceptions and internal counters show no callback invocations.
- `test_mro_cache_populated_on_first_emit`: emit `Foo()` once; assert `_mro_cache[Foo]` is set.
- `test_mro_cache_invalidated_on_subscribe`: emit `Foo()`; assert cache populated; subscribe new callback to `Foo`; assert cache cleared.
- `test_mro_cache_invalidated_on_unsubscribe`: subscribe; emit (populates cache); unsubscribe; assert cache cleared.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement `emit` + MRO cache + invalidation.
- [ ] Run → pass.
- [ ] `make check` green; module size ≤ 350 LOC.
- [ ] Commit: `feat(event-bus): implement emit with MRO cache and fast path`.

---

## Sub-phase 1.4 — Error isolation + re-entrant emit

**Files**:

- Modify: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/test_emit_safety.py`

**Behavior delivered**:

- **Error isolation**: each callback wrapped in `try/except Exception`. On exception, log via structlog WARNING with fields `event_emit_failed`, `subscriber=<name or callable repr>`, `event_type=<class name>`, `event_id=<UUID>`, `exc_info=True`. Dispatch continues to the next subscriber.
- **Re-entrancy**: `emit` iterates over the **immutable tuple snapshot** captured at dispatch start. If a subscriber emits during its handler, the nested emit dispatches against its own resolved tuple. The outer emit's iteration is unaffected by any `subscribe`/`unsubscribe` performed inside a nested handler.
- Re-entrant emit depth is unbounded (Python's recursion limit governs); if a subscriber emits the same event type causing infinite recursion, Python's `RecursionError` is allowed to propagate (consistent with normal Python semantics — no special handling).

**Tests written**:

- `test_failing_subscriber_does_not_break_dispatch`: register `bad_cb` (always raises) and `good_cb`; emit; assert `good_cb` received the event AND `bad_cb` raised internally.
- `test_failing_subscriber_logged_at_warning`: use a structlog capture fixture; emit; assert log contains `event_emit_failed`, `subscriber=…`, `event_type=…`, `event_id=…`, with `exc_info`.
- `test_subscriber_can_emit_during_handler`: register `cb_a` that emits `Bar()` when receiving `Foo()`; register `cb_b` on `Bar`; emit `Foo()`; assert `cb_b` received exactly one `Bar` event.
- `test_unsubscribe_during_dispatch_does_not_affect_current_emit`: register `cb_x` that unsubscribes itself; register `cb_y` after `cb_x` for the same type; emit; assert BOTH `cb_x` and `cb_y` invoked for THIS emit (snapshot iteration); next emit invokes only `cb_y`.
- `test_subscribe_during_dispatch_does_not_affect_current_emit`: register `cb_x` that subscribes `cb_new` to the same type; emit once; assert `cb_new` NOT invoked for this emit; emit again; assert `cb_new` IS invoked.

**Steps**:

- [ ] Write failing tests (use a structlog testing capture fixture; if none exists, create `tests/event_bus/conftest.py` with a minimal `caplog_structlog` fixture).
- [ ] Implement error isolation + immutable snapshot iteration.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): add error isolation and re-entrant emit safety`.

---

## Sub-phase 1.5 — `event_to_dict` (pure payload)

**Files**:

- Modify: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/test_serialization_dict.py`

**Behavior delivered**:

- `event_to_dict(event: Event) -> dict[str, Any]`: recursive JSON-safe encoder.
- Encoding rules (verbatim from DESIGN §JSON serialization contract):
  - `datetime` → ISO 8601 string (UTC, with timezone).
  - `UUID` → str.
  - `Path` → str.
  - `Enum` → `enum.value`.
  - dataclass → `asdict`-equivalent recursive (calls `event_to_dict` on each field value).
  - list/tuple → list (each element recursively encoded).
  - dict → dict (keys MUST be JSON-safe; otherwise raise `TypeError`).
  - `None`/`str`/`int`/`float`/`bool` → unchanged.
  - Anything else → raise `TypeError(f"Cannot encode {type(value).__name__} for JSON serialization")` (fail-loud, never silent).
- Method `Event.to_dict()` delegates to module-level `event_to_dict(self)`.

**Tests written**:

- `test_to_dict_encodes_datetime_as_iso_8601`: build event; encode; assert `data["timestamp"]` is a string matching `r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$"`.
- `test_to_dict_encodes_uuid_as_str`: assert `data["event_id"]` is a str matching UUID regex.
- `test_to_dict_encodes_path_as_str`: build subclass with `path: Path` field; encode; assert `data["path"]` is a str.
- `test_to_dict_encodes_enum_as_value`: build subclass with `mode: SomeEnum`; encode; assert `data["mode"] == SomeEnum.X.value`.
- `test_to_dict_encodes_nested_dataclass`: subclass with `inner: SomeDataclass`; encode; assert `data["inner"]` is a dict with the inner fields recursively encoded.
- `test_to_dict_encodes_list_of_dataclasses`: subclass with `items: list[SomeDataclass]`; encode; assert each list element is a dict.
- `test_to_dict_encodes_none_int_str_bool_unchanged`: assert primitives pass through.
- `test_to_dict_dict_with_non_safe_key_raises`: subclass with `details: dict[tuple, int]` having a tuple key; encode; assert `TypeError`.
- `test_to_dict_unsupported_type_raises_typeerror`: subclass with `obj: object` field holding a `socket.socket()` mock; encode; assert `TypeError`.
- `test_event_to_dict_method_delegates_to_module_level`: build event; assert `event.to_dict() == event_to_dict(event)`.

**Steps**:

- [ ] Write failing tests with small ad-hoc Event subclasses defined inside the test module.
- [ ] Implement `event_to_dict` (a single dispatch function with isinstance ladder).
- [ ] Run → pass.
- [ ] `make check` green; module size ≤ 350 LOC.
- [ ] Commit: `feat(event-bus): add event_to_dict pure-payload JSON encoder`.

---

## Sub-phase 1.6 — `event_to_envelope` + `event_from_envelope` + class registry

**Files**:

- Modify: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/test_serialization_envelope.py`

**Behavior delivered**:

- Event class registry: `_EVENT_CLASS_REGISTRY: dict[str, type[Event]]` indexed by class name (e.g. `"PipelineStarted"`). **Populated automatically via `Event.__init_subclass__`** (chosen over the `@register_event` decorator approach because it is automatic and impossible to forget — every `class X(Event): ...` definition self-registers). Consequence: **`Event` itself is NOT in the registry** (`__init_subclass__` fires only for subclasses), so `len(_EVENT_CLASS_REGISTRY)` equals the count of concrete event classes (13 at end of Phase 4). This contract is referenced by Phase 4 §4.6 gate item 5.
- `event_to_envelope(event) -> dict[str, Any]`: returns `{"_type": type(event).__name__, "data": event_to_dict(event)}`.
- `event_from_envelope(data) -> Event`:
  - Look up `data["_type"]` in `_EVENT_CLASS_REGISTRY`.
  - If unknown, raise `KeyError(f"Unknown event type: {data['_type']!r}")` (fail-loud).
  - Reconstruct the dataclass: deserialize each field of `data["data"]` back to the proper type (datetime from ISO string, UUID from str, Path from str, Enum from value, nested dataclasses recursively).
- Round-trip identity: `event_from_envelope(event_to_envelope(e))` returns an `Event` equal to `e` modulo timestamp microsecond precision (ISO-8601 round-trip preserves microseconds in Python's `datetime.fromisoformat`).

**Tests written**:

- `test_envelope_contains_type_and_data`: encode; assert keys `{"_type", "data"}` and `data["_type"] == "Foo"` (where `Foo` is the test subclass).
- `test_event_subclass_auto_registered_on_definition`: define `class Bar(Event): ...`; assert `_EVENT_CLASS_REGISTRY["Bar"] is Bar`.
- `test_event_from_envelope_reconstructs_equal_event`: build `Foo(...)`; envelope; reconstruct; assert reconstructed `== original` (compare with `__eq__` provided by dataclass).
- `test_event_from_envelope_unknown_type_raises_keyerror`: pass `{"_type": "Nonexistent", "data": {}}`; assert `KeyError` with the type name in the message.
- `test_envelope_round_trip_through_json`: `e1 = Foo(...)`; `json_str = json.dumps(event_to_envelope(e1))`; `e2 = event_from_envelope(json.loads(json_str))`; assert `e2 == e1`.
- `test_envelope_preserves_correlation_id`: bind ContextVar; build event; envelope round-trip; assert `correlation_id` preserved.
- `test_envelope_preserves_event_id`: assert `event_id` round-trips identically.

**Steps**:

- [ ] Write failing tests with ad-hoc Event subclasses.
- [ ] Implement registry + `event_to_envelope` + `event_from_envelope`.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): add event_to_envelope/from_envelope with class registry`.

---

## Sub-phase 1.7 — ContextVar capture semantics: comprehensive tests

**Files**:

- Create: `tests/event_bus/test_correlation_id.py`

**Behavior delivered** (no production code change — this sub-phase locks the semantics that Sub-phase 1.1 already implemented):

Comprehensive coverage of the ContextVar capture contract, including the **long-lived emitter scenario** which is the hardest case to get right.

**Tests written**:

- `test_correlation_id_none_outside_bound_region`: build event without bind; assert `correlation_id is None`.
- `test_correlation_id_captured_inside_bound_region`: bind `current_correlation_id.set("run-123")` in a try/finally; build event inside; assert `event.correlation_id == "run-123"`; reset token; assert ContextVar is back to `None` and subsequent events have `correlation_id is None`.
- `test_correlation_id_long_lived_emitter`: simulate the CircuitBreaker singleton case — construct a "long-lived emitter" object OUTSIDE any bound region; later, enter a bound region with `set("run-456")`; call a method on the long-lived emitter that constructs an event INSIDE the bound region; assert the resulting `event.correlation_id == "run-456"`. This proves the ContextVar mechanism works for singletons constructed at module-load time.
- `test_correlation_id_emit_does_not_modify`: bind ContextVar; build event INSIDE bound region (correlation_id captured); reset ContextVar; emit event AFTER reset; assert that the event passed to the subscriber still has the originally-captured `correlation_id` (proves emit doesn't re-read the ContextVar, the value is frozen on the event).
- `test_correlation_id_explicit_override`: bind ContextVar to `"abc"`; build `Event(correlation_id="explicit")`; assert `correlation_id == "explicit"` (default_factory not invoked when caller passes a value).
- `test_correlation_id_explicit_none_does_not_capture`: bind ContextVar to `"abc"`; build `Event(correlation_id=None)`; assert `correlation_id is None` (explicit None wins over ContextVar value — this matches dataclass default_factory semantics: factory not invoked when arg supplied).
- `test_correlation_id_isolated_across_asyncio_tasks`: launch two `asyncio.Task`s each binding the ContextVar to a distinct value; each task builds an event inside its bound region; assert each event captured its task-local value (proves ContextVar's per-task isolation).
- `test_correlation_id_isolated_across_threads`: same scenario with two `threading.Thread`s; assert thread-local isolation.

**Steps**:

- [ ] Write tests (all passing immediately since Sub-phase 1.1 implemented the mechanism).
- [ ] If any test fails, that's a bug in Sub-phase 1.1 → fix in place, do NOT defer.
- [ ] `make check` green.
- [ ] Commit: `test(event-bus): lock correlation_id ContextVar capture semantics`.

---

## Sub-phase 1.8 — Test fixtures: `CollectingSubscriber` + `EVENT_SAMPLE_FACTORIES` registry

**Files**:

- Create: `tests/fixtures/__init__.py` (if not existing).
- Create: `tests/fixtures/event_bus.py`
- Create: `tests/fixtures/event_samples.py`
- Create: `tests/fixtures/test_factories_registry.py`

**Behavior delivered**:

- `tests/fixtures/event_bus.py`:
  - `class CollectingSubscriber(Generic[E])` using `typing.Generic[E]` with `E = TypeVar("E", bound=Event)`. **PEP 695 syntax (`[E: Event]`) requires Python 3.12+ and is NOT used** — the project targets Python 3.11 (per CLAUDE.md, pyenv 3.11.9). Verify `pyproject.toml` `requires-python` constraint at impl time; if it gets bumped to ≥ 3.12 in a later feature, this sub-phase's TypeVar pattern can be migrated then.
  - `__init__(self, bus: EventBus, event_type: type[E] = Event)`: subscribes itself on construction.
  - `received: list[E]` — append-only.
  - `close(self) -> None`: unsubscribes via stored token.
  - Context-manager interface (`__enter__` / `__exit__`) for fixtures.
- `tests/fixtures/event_samples.py`:
  - `EVENT_SAMPLE_FACTORIES: dict[type[Event], Callable[[], Event]] = {}` module-level.
  - `def register_factory(event_type: type[Event]) -> Callable[[Callable], Callable]`: decorator that registers a factory.
  - No factories registered yet — Phase 1 has no concrete events to factory.
- `tests/fixtures/test_factories_registry.py`:
  - `test_every_event_has_factory`: iterate over `_EVENT_CLASS_REGISTRY` (the bus's registry); for each concrete event subclass, assert `event_class in EVENT_SAMPLE_FACTORIES`. **Vacuously green in Phase 1** (no concrete events exist yet); becomes the gate from Phase 3 onwards.
  - `test_registered_factories_produce_correct_type`: for each factory in `EVENT_SAMPLE_FACTORIES`, invoke it and assert `isinstance(result, event_type)`.

**Tests written** (testing the fixtures themselves):

- `test_collecting_subscriber_records_events`: instantiate; emit two events of the subscribed type; assert `subscriber.received == [e1, e2]`.
- `test_collecting_subscriber_filters_by_type`: subscribe to `Foo`; emit a `Bar` event (unrelated type); assert `subscriber.received == []`.
- `test_collecting_subscriber_collects_via_base_event`: subscribe to `Event` (base); emit any subclass; assert collected.
- `test_collecting_subscriber_close_unsubscribes`: create + close; emit; assert nothing recorded.
- `test_collecting_subscriber_context_manager`: `with CollectingSubscriber(bus, Foo) as sub:` emit; assert recorded; after exit, emit again, assert NOT recorded (auto-close).
- `test_register_factory_stores_in_registry`: define a stub Event subclass `Tmp`; decorate a factory; assert `EVENT_SAMPLE_FACTORIES[Tmp]` is the factory.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement `CollectingSubscriber` and the factories registry.
- [ ] Run → pass.
- [ ] `make check` green; `tests/fixtures/event_bus.py` ≤ 80 LOC; `tests/fixtures/event_samples.py` initial ≤ 30 LOC (no factories yet; grows in later phases up to ≤ 150).
- [ ] Commit: `test(event-bus): add CollectingSubscriber + factories registry mechanism`.

---

## Sub-phase 1.9 — Phase 1 gate

**Files**:

- Verify: all Phase 1 sub-phases checked.

**No new production code or test code in this sub-phase** — it is a gate-only commit that captures the verified state.

**Hard verification gate** (must ALL pass before committing the gate):

1. **`make lint`** → zero errors.
2. **`make test`** → all tests pass; baseline test count grew by **~50 new tests** (rough estimate: 7 + 5 + 9 + 5 + 10 + 7 + 8 + 6 = 57 new tests). Adjust if implementation merges/splits some.
3. **`make check`** → green.
4. **Module size**: `personalscraper/core/event_bus.py` ≤ 350 LOC (DESIGN budget). Run `python3 scripts/check-module-size.py` (also covered by `make check`).
5. **Smoke import**: `python -c "import personalscraper.core.event_bus; print('ok')"` → prints `ok`.
6. **Smoke import top-level**: `python -c "import personalscraper"` → succeeds.
7. **No emit sites in production code yet** (sanity — Phase 1 is standalone):
   ```bash
   rg '\.emit\(' --type py personalscraper/ | grep -v event_bus.py
   ```
   Expected: zero matches (the only `.emit` is inside `event_bus.py` itself, e.g. internal helpers or comments).
8. **No imports of `personalscraper.core.event_bus` in production code yet**:
   ```bash
   rg 'from personalscraper\.core\.event_bus' --type py personalscraper/ | grep -v test_
   ```
   Expected: zero matches (only tests import).
9. **`pipeline_observer.py` still intact** (Phase 3 removes it; Phase 1 must not touch it):
   ```bash
   ls personalscraper/pipeline_observer.py
   ```
   File exists.

**Steps**:

- [ ] Re-read each sub-phase 1.1–1.8; confirm every checkbox checked.
- [ ] Run gate items 1–9 above; resolve any red.
- [ ] Commit: `chore(event-bus): phase 1 gate — standalone event bus foundation`.

---

## Roll-back plan

Phase 1 is **fully reversible** because nothing in the production tree imports the new module yet.

- To roll back: `git revert <commit-range-for-phase-1>` or `git reset --hard <pre-phase-1-sha>`.
- No schema, no storage, no API contract change.
- A failed Phase 1 leaves no orphan state.

## Open questions left for this phase

None directly from DESIGN §Open Questions. Phase 1 is internal infrastructure; the design decisions (ContextVar mechanism, envelope split, registry approach) are fully locked.

If a new question emerges during implementation (e.g. "should `Event.__init_subclass__` or `@register_event` be the registration mechanism?"), resolve it inline — both are acceptable implementations of the same contract. Document the choice in the sub-phase commit message.
