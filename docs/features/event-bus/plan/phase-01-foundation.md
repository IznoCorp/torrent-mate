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
- `test_emit_no_subscribers_zero_allocation` (fast-path allocation contract — DESIGN §Testing strategy line "no allocation beyond the event itself"): use `tracemalloc` to snapshot before and after emitting 100 events on an empty bus; assert the delta in tracked block count is ≤ 1 block per emit (the event instance itself; the bus allocates nothing). Concrete: `tracemalloc.start(); s1 = tracemalloc.take_snapshot(); for _ in range(100): bus.emit(Foo()); s2 = tracemalloc.take_snapshot(); diff = sum(stat.count_diff for stat in s2.compare_to(s1, 'lineno') if 'event_bus.py' in stat.traceback[0].filename); assert diff == 0, f'fast path allocated {diff} blocks in event_bus.py'`. Asserts the fast path is genuinely allocation-free in `event_bus.py`'s code path (event construction in user code is excluded by filename filter).
- `test_mro_cache_populated_on_first_emit`: emit `Foo()` once; assert `_mro_cache[Foo]` is set.
- `test_mro_cache_invalidated_on_subscribe`: emit `Foo()`; assert cache populated; subscribe new callback to `Foo`; assert cache cleared.
- `test_mro_cache_invalidated_on_unsubscribe`: subscribe; emit (populates cache); unsubscribe; assert cache cleared.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement `emit` + MRO cache + invalidation.
- [ ] Run → pass.
- [ ] `make check` green; module size ≤ 400 LOC.
- [ ] Commit: `feat(event-bus): implement emit with MRO cache and fast path`.

---

## Sub-phase 1.4 — Error isolation + re-entrant emit

**Files**:

- Modify: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/test_emit_safety.py`

**Behavior delivered**:

- **Error isolation**: each callback wrapped in `try/except Exception`. On exception, log via structlog WARNING with fields `event_emit_failed`, `subscriber=<name or callable repr>`, `event_type=<class name>`, `event_id=<UUID>`, `exc_info=True`. Dispatch continues to the next subscriber.
- **Re-entrancy**: `emit` iterates over the **immutable tuple snapshot** captured at dispatch start. If a subscriber emits during its handler, the nested emit dispatches against its own resolved tuple. The outer emit's iteration is unaffected by any `subscribe`/`unsubscribe` performed inside a nested handler.
- **Recursion policy (DESIGN §Dispatch semantics #4)**: re-entrant emit depth is unbounded. If a subscriber emits an event whose dispatch eventually re-invokes that same subscriber (subscribing to its own type, or to `Event` base), `RecursionError` IS caught by the per-subscriber `try/except Exception` block (since `RecursionError` ⊂ `Exception`). The bus logs `event_emit_failed` at WARNING and dispatch continues with the next subscriber. Caller responsibility to avoid this pattern; documented.

**Tests written**:

- `test_failing_subscriber_does_not_break_dispatch`: register `bad_cb` (always raises) and `good_cb`; emit; assert `good_cb` received the event AND `bad_cb` raised internally.
- `test_failing_subscriber_logged_at_warning`: use a structlog capture fixture; emit; assert log contains `event_emit_failed`, `subscriber=…`, `event_type=…`, `event_id=…`, with `exc_info`.
- `test_subscriber_can_emit_during_handler`: register `cb_a` that emits `Bar()` when receiving `Foo()`; register `cb_b` on `Bar`; emit `Foo()`; assert `cb_b` received exactly one `Bar` event.
- `test_unsubscribe_during_dispatch_does_not_affect_current_emit`: register `cb_x` that unsubscribes itself; register `cb_y` after `cb_x` for the same type; emit; assert BOTH `cb_x` and `cb_y` invoked for THIS emit (snapshot iteration); next emit invokes only `cb_y`.
- `test_subscribe_during_dispatch_does_not_affect_current_emit`: register `cb_x` that subscribes `cb_new` to the same type; emit once; assert `cb_new` NOT invoked for this emit; emit again; assert `cb_new` IS invoked.
- `test_recursive_subscriber_caught_as_error_isolation`: register `cb_loop` on `Foo` that emits a new `Foo()` from inside its own handler (unbounded recursion). Set `sys.setrecursionlimit(100)` for test isolation. Emit `Foo()`; assert (a) `emit` does NOT raise, (b) a structlog `event_emit_failed` WARNING was logged with `subscriber=<repr of cb_loop>` and an `exc_info` whose exception class is `RecursionError`, (c) dispatch returned normally and subsequent emits without the loop subscriber work fine. **Documents the caller-responsibility contract from DESIGN §Dispatch semantics #4: `RecursionError` ⊂ `Exception` is caught by the bus, not propagated; subscribers MUST NOT subscribe to their own emit type.**

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
- [ ] `make check` green; module size ≤ 400 LOC.
- [ ] Commit: `feat(event-bus): add event_to_dict pure-payload JSON encoder`.

---

## Sub-phase 1.6 — `event_to_envelope` + `event_from_envelope` + class registry

**Files**:

- Modify: `personalscraper/core/event_bus.py`
- Create: `tests/event_bus/test_serialization_envelope.py`

**Behavior delivered**:

- Event class registry: `_EVENT_CLASS_REGISTRY: dict[str, type[Event]]` indexed by class name (e.g. `"PipelineStarted"`). **Populated automatically via `Event.__init_subclass__`** (chosen over the `@register_event` decorator approach because it is automatic and impossible to forget — every `class X(Event): ...` definition self-registers). Consequence: **`Event` itself is NOT in the registry** (`__init_subclass__` fires only for subclasses), so `len(_EVENT_CLASS_REGISTRY)` equals the count of concrete event classes (13 at end of Phase 4). This contract is referenced by Phase 4 §4.6 gate item 5.

- **Registry hygiene for test stubs** (Invariant 9 in INDEX): `__init_subclass__` MUST filter by module path to prevent pytest-collected test stubs from polluting the production registry:

  ```python
  class Event:
      def __init_subclass__(cls, **kwargs):
          super().__init_subclass__(**kwargs)
          # Only register production events. Test stubs (modules under
          # tests/, scripts/, or anywhere outside personalscraper.*) are
          # excluded — see Invariant 9.
          if cls.__module__.startswith("personalscraper."):
              _EVENT_CLASS_REGISTRY[cls.__name__] = cls
  ```

  This makes the Phase 4.6 and Phase 5.6 gate assertions on `len(_EVENT_CLASS_REGISTRY)` deterministic regardless of pytest collection order. Test stubs defined inline in `tests/event_bus/test_*.py` (e.g. `class Foo(Event): pass`) are allowed and do NOT need to provide factories — they live outside the production registry.

- `event_to_envelope(event) -> dict[str, Any]`: returns `{"_type": type(event).__name__, "data": event_to_dict(event)}`.
- `event_from_envelope(data) -> Event`:
  - Look up `data["_type"]` in `_EVENT_CLASS_REGISTRY`.
  - If unknown, raise `KeyError(f"Unknown event type: {data['_type']!r}")` (fail-loud).
  - Reconstruct the dataclass per the **nested-dataclass decoding contract from DESIGN §JSON serialization contract**: resolve each field's annotation via `typing.get_type_hints(EventClass, globalns=sys.modules[EventClass.__module__].__dict__)`; decode field values recursively according to the inverse encoding table (`datetime.fromisoformat`, `UUID(value)`, `Path(value)`, `EnumClass(value)`, dataclass → recursive decode of its fields via the same algorithm, `list[T]` / `dict[K, V]` → recurse on elements). The decoder is **symmetric with the encoder** — no per-type adapter is needed because the field annotation suffices.
- **Round-trip equality is field-by-field**, NOT `==`: a helper `assert_event_round_trip(original, reconstructed)` in `tests/fixtures/event_bus.py` asserts every field except `timestamp` is exactly equal, AND `abs((reconstructed.timestamp - original.timestamp).total_seconds()) <= 1e-6` (1 µs tolerance for ISO-8601 round-trip). Dataclass `__eq__` is NOT used because it compares all fields strictly including `timestamp`.

**Tests written**:

- `test_envelope_contains_type_and_data`: encode; assert keys `{"_type", "data"}` and `data["_type"] == "Foo"` (where `Foo` is the test subclass).
- `test_event_subclass_auto_registered_on_definition_production_module`: define a `class Bar(Event): ...` whose `__module__` is monkey-patched to `"personalscraper.fake_module"`; assert `_EVENT_CLASS_REGISTRY["Bar"] is Bar`. (Real production events get this for free because they live under `personalscraper.*`.)
- `test_event_subclass_NOT_registered_when_module_is_test`: define `class Foo(Event): ...` inside the test module (whose `__module__` starts with `"tests."` or `"test_…"`); assert `"Foo" not in _EVENT_CLASS_REGISTRY`. This locks Invariant 9.
- `test_event_from_envelope_reconstructs_via_assert_event_round_trip`: build `Foo(...)`; envelope; reconstruct; call `assert_event_round_trip(original, reconstructed)` (the field-by-field helper). NEVER use raw `==` — `timestamp` rounding would make it flaky.
- `test_event_from_envelope_unknown_type_raises_keyerror`: pass `{"_type": "Nonexistent", "data": {}}`; assert `KeyError` with the type name in the message.
- `test_envelope_round_trip_through_json`: `e1 = Foo(...)`; `json_str = json.dumps(event_to_envelope(e1))`; `e2 = event_from_envelope(json.loads(json_str))`; `assert_event_round_trip(e1, e2)`.
- `test_envelope_preserves_correlation_id`: bind ContextVar; build event; envelope round-trip; assert `e2.correlation_id == e1.correlation_id` (exact, not via timestamp tolerance).
- `test_envelope_preserves_event_id`: assert `e2.event_id == e1.event_id` exactly.
- `test_envelope_round_trip_nested_dataclass`: define a test Event with a nested `@dataclass(frozen=True) class Inner` field carrying `datetime`, `UUID`, `Path`, and `Enum` fields. Round-trip; assert each nested field is reconstructed to its proper type AND value (proves the nested-dataclass decoder works recursively per DESIGN §JSON serialization contract). This test is the gate that exercises the `event_from_envelope` decode path against the encode path of `event_to_dict`'s `dataclass → asdict` rule.
- `test_envelope_timestamp_tolerance_is_one_microsecond`: build an event with a precisely-known timestamp; round-trip; assert delta ≤ 1 µs. Bound test for the `assert_event_round_trip` helper.

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
  - `class CollectingSubscriber(Generic[E])` using `typing.Generic[E]` with `E = TypeVar("E", bound=Event)`. **PEP 695 syntax (`[E: Event]`) requires Python 3.12+ and is NOT used** — `pyproject.toml` declares `requires-python = ">=3.10"`, so the codebase must remain Python 3.10-compatible (pyenv 3.11.9 is the dev shell, not the runtime floor). If `pyproject.toml` is bumped to ≥ 3.12 in a later feature, this sub-phase's TypeVar pattern can be migrated then.
  - `__init__(self, bus: EventBus, event_type: type[E] = Event)`: subscribes itself on construction.
  - `received: list[E]` — append-only.
  - `close(self) -> None`: unsubscribes via stored token.
  - Context-manager interface (`__enter__` / `__exit__`) for fixtures.
- `tests/fixtures/event_samples.py`:
  - `EVENT_SAMPLE_FACTORIES: dict[type[Event], Callable[[], Event]] = {}` module-level.
  - `def register_factory(event_type: type[Event]) -> Callable[[Callable], Callable]`: decorator that registers a factory.
  - No factories registered yet — Phase 1 has no concrete events to factory.
- `tests/fixtures/test_factories_registry.py`:
  - `test_every_event_has_factory`: iterate over `_EVENT_CLASS_REGISTRY` (the bus's registry, ALREADY filtered to production modules by `Event.__init_subclass__` per Invariant 9 — see Phase 1.6); for each concrete event subclass, assert `event_class in EVENT_SAMPLE_FACTORIES`. **Vacuously green in Phase 1** (no concrete events exist yet); becomes the gate from Phase 3 onwards. Because the registry is module-filtered, test-only stubs defined in `tests/` do NOT need factories.
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
2. **`make test`** → all tests pass; baseline test count MUST have grown by **at least 50** new tests (target ~61 by per-sub-phase enumeration: 1.1=7 + 1.2=5 + 1.3=9 (+ allocation contract) + 1.4=6 + 1.5=10 + 1.6=10 + 1.7=8 + 1.8=6 = 61). A lower count means a test was silently skipped or deleted — investigate which one and restore it; do NOT lower the minimum. Test count CANNOT regress.
3. **No new skips / xfails** — per Invariant 3 item 3: `rg -c '@pytest\.mark\.(skip|xfail|skipif)' tests/ -g '*.py' | awk -F: '{s+=$2} END{print s}'` MUST equal `<SKIP_BASELINE>` from INDEX Pre-flight #9.
4. **`make check`** → green.
5. **Module size**: `personalscraper/core/event_bus.py` ≤ 400 LOC (DESIGN budget, uplifted from 350 to accommodate MRO cache + COW + ContextVar + envelope encode/decode + registry + `__init_subclass__` hook). Run `python3 scripts/check-module-size.py` (also covered by `make check`).
6. **Smoke import**: `python -c "import personalscraper.core.event_bus; print('ok')"` → prints `ok`.
7. **Smoke import top-level**: `python -c "import personalscraper"` → succeeds.
8. **No emit sites in production code yet** (sanity — Phase 1 is standalone):
   ```bash
   rg 'event_bus\.emit\(|app\.event_bus\.emit\(' --type py personalscraper/
   ```
   Expected: zero matches (the only `.emit` is inside `event_bus.py` itself, e.g. internal helpers or comments).
9. **No imports of `personalscraper.core.event_bus` in production code yet**:
   ```bash
   rg 'from personalscraper\.core\.event_bus' --type py personalscraper/ | grep -v test_
   ```
   Expected: zero matches (only tests import).
10. **`pipeline_observer.py` still intact** (Phase 3 removes it; Phase 1 must not touch it):
    ```bash
    ls personalscraper/pipeline_observer.py
    ```
    File exists.

**Steps**:

- [ ] Re-read each sub-phase 1.1–1.8; confirm every checkbox checked.
- [ ] Run gate items 1–10 above; resolve any red.
- [ ] Commit: `chore(event-bus): phase 1 gate — standalone event bus foundation`.

---

## Roll-back plan

Phase 1 is **fully reversible** because nothing in the production tree imports the new module yet.

- To roll back: `git revert <commit-range-for-phase-1>` or `git reset --hard <pre-phase-1-sha>`.
- No schema, no storage, no API contract change.
- A failed Phase 1 leaves no orphan state.

## Open questions left for this phase

None directly from DESIGN §Open Questions. Phase 1 is internal infrastructure; the design decisions (ContextVar mechanism, envelope split, registry approach) are fully locked.

All design decisions for Phase 1 are LOCKED. The registration mechanism is `Event.__init_subclass__` with module-path filtering (Invariant 9). The serialization split (`event_to_dict` pure vs `event_to_envelope` tagged) is locked in DESIGN §JSON serialization contract. The ContextVar capture happens at event construction via `field(default_factory=...)`, never at emit. No "decide at implementation time" decisions remain.
