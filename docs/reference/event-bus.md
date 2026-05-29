# Event Bus — reference

The in-process event bus is the runtime spine that connects pipeline,
indexer, scraper, dispatcher, and trailer components to their
subscribers (RichConsole, Telegram, structured debug log, future Web
UI). This document is the **how**; for the **why**, design rationale,
and rollback discipline see
[`docs/features/event-bus/DESIGN.md`](../features/event-bus/DESIGN.md).

## Purpose & high-level architecture

The bus replaces the pre-0.13 `PipelineObserver` / `StepEvent`
duck-typed registry with a typed dataclass-event bus organised around
five primitives:

- **`Event`** — frozen, keyword-only dataclass base in
  `personalscraper.core.event_bus`. Carries five
  framework-managed fields (`timestamp`, `event_id`, `source`,
  `correlation_id`, `schema_version`). Concrete events subclass it.

  | Field            | Type  | Default | Notes                                                                                                                                          |
  | ---------------- | ----- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
  | `schema_version` | `int` | `1`     | Schema version — bumped on the first breaking event-shape change after a cross-process consumer exists. Default `1` for all events in v0.17.0. |

- **`EventBus`** — the multicast dispatcher. Each emit walks the
  event's MRO; every registered callback for an ancestor type is
  invoked. Subscriber registration uses a copy-on-write tuple per
  type, so callbacks added mid-emit do not see the in-flight event.
- **`SubscriptionToken`** — opaque handle returned by `subscribe`,
  required by `unsubscribe` for clean teardown.
- **`event_to_dict` / `event_to_envelope` / `event_from_envelope`** —
  JSON-safe serialization helpers. Envelopes carry a `_type` discriminator
  so subscribers persisting events (e.g. an outbox queue) can round-trip
  the exact class without reflection.
- **`current_correlation_id`** — `ContextVar[str | None]` captured at
  event construction time. Long-lived emitters (singletons, breakers
  outside a pipeline run) inherit the calling run's correlation id
  automatically.

The bus is process-scoped: every CLI invocation builds one
`AppContext`, the AppContext holds one `EventBus`, and every component
that emits or subscribes shares that bus by dependency injection. There
is no module-level singleton in the production path — every emit site
takes `event_bus: EventBus` as a required keyword argument — every
emit site is enforced by
`tests/architecture/test_event_bus_required_signatures.py`.

## API reference

Every public symbol of the bus lives in
`personalscraper.core.event_bus`. The module is intentionally narrow:
the three runtime primitives (`Event`, `EventBus`, `SubscriptionToken`),
the three serialization helpers (`event_to_dict`, `event_to_envelope`,
`event_from_envelope`), and the `current_correlation_id` ContextVar.
The internal `_EVENT_CLASS_REGISTRY` (populated by
`Event.__init_subclass__` when each event module is imported) is not
part of the public surface — consumers reach event classes via the
`personalscraper.events` package re-exports.

The import surface intentionally matches what subscribers and emitters
need — there are no helper factories, no event registry mutators, no
async variants. New API symbols require updating the v1 catalog
section above and bumping the registry pin in the gate.

```python
from personalscraper.core.event_bus import (
    Event,
    EventBus,
    SubscriptionToken,
    current_correlation_id,
    event_to_dict,
    event_to_envelope,
    event_from_envelope,
)
```

The sub-sections below document each entry point. Behaviour that
differs between subscribe-time and emit-time (e.g. the MRO cache
build) is called out explicitly so callers know which cost lives
where. Every assertion below is pinned by at least one test under
`tests/event_bus/` or `tests/core/test_circuit_events.py`.

### `EventBus.subscribe(event_type, callback) -> SubscriptionToken`

Register `callback(event)` for every emit whose runtime class is
`event_type` **or any subclass**. The MRO walk happens at emit time,
not at subscribe time, so a subscription to `Event` catches every
concrete event class (used by `DebugLogSubscriber`).

### `EventBus.unsubscribe(token: SubscriptionToken) -> None`

Remove the subscription identified by `token`. Idempotent: a second
call is a no-op. Tokens issued for already-removed subscriptions stay
inert.

### `EventBus.emit(event: Event) -> None`

Synchronously invoke every callback registered for any class in the
event's MRO. Callback order is concrete-class-first then ancestor types,
FIFO within each class — so a subscriber on `Event` runs after subscribers
on `event.__class__` for the same emit (see `_resolve_mro_chain` in
`personalscraper/core/event_bus.py`). A callback that
raises is logged at `WARNING` (`event_emit_failed`) and isolated:
later subscribers still receive the event. Re-entrant emits (a
callback that calls `bus.emit` again) are supported — each emit gets
its own snapshot of the subscriber tuple.

### `Event` base fields

| Field            | Type          | Default behaviour                                                                              |
| ---------------- | ------------- | ---------------------------------------------------------------------------------------------- |
| `timestamp`      | `datetime`    | `field(default_factory=lambda: datetime.now(timezone.utc))` — set per instance, UTC-aware.     |
| `event_id`       | `UUID`        | `field(default_factory=uuid.uuid4)` — set per instance.                                        |
| `source`         | `str`         | Filled in `__post_init__` from the class's module path when empty (overridable per emit).      |
| `correlation_id` | `str \| None` | `field(default_factory=lambda: current_correlation_id.get())` — captured at construction time. |

Every concrete event class is `@dataclass(frozen=True, kw_only=True)`
and inherits these four fields. Subclasses add their domain payload.

### `event_to_dict(event) -> dict[str, Any]`

Recursively coerce dataclasses, paths, UUIDs, datetimes, enums, and
nested mappings into JSON-safe primitives. Use this when you want the
payload **without** the `_type` discriminator — e.g. debug logging.

### `event_to_envelope(event) -> dict[str, Any]`

Wrap `event_to_dict(event)` under a `"data"` key alongside a top-level
`_type` discriminator equal to `type(event).__name__`. The envelope shape
is exactly `{"_type": <class-name>, "data": {<payload>}}` — the payload
is **nested**, never flattened. The envelope is what subscribers persist
to an outbox / write to a wire protocol.

### `event_from_envelope(envelope: dict) -> Event`

Inverse of `event_to_envelope`. Looks up `envelope["_type"]` in
`_EVENT_CLASS_REGISTRY` (populated at import time by every event
module), reads the payload from `envelope["data"]`, and reconstructs
the instance. Raises `KeyError` (fail-loud) when `envelope["_type"]`
is not in the registry.

### `current_correlation_id: ContextVar[str | None]`

Bind a per-run correlation id with the standard `ContextVar` pattern:

```python
token = current_correlation_id.set(run_id)
try:
    ...
finally:
    current_correlation_id.reset(token)
```

Every `Event(...)` constructed inside the `try` block captures
`run_id` in its `correlation_id` field — including emits from
long-lived breakers / orchestrators that pre-existed the run.

## Event catalog (v1)

The v1 catalog defines exactly 23 production event classes, all
imported eagerly by `personalscraper.events` (plus the registry events
re-exported via `personalscraper.api.metadata.registry`) so they
self-register before any envelope round-trip. The count is pinned by
`tests/event_bus/test_pipeline_events.py` (`len(_EVENT_CLASS_REGISTRY) == 23`).

| Class                        | Module                                          | Payload fields                                                                                                                  | Producer                                                                                           |
| ---------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `PipelineStarted`            | `personalscraper.pipeline_events`               | `report: PipelineReport`                                                                                                        | `Pipeline.run` at entry                                                                            |
| `PipelineEnded`              | `personalscraper.pipeline_events`               | `report: PipelineReport`                                                                                                        | `Pipeline.run` at exit                                                                             |
| `StepStarted`                | `personalscraper.pipeline_events`               | `step: str`                                                                                                                     | `Pipeline._run_step` around each step                                                              |
| `StepCompleted`              | `personalscraper.pipeline_events`               | `step: str`, `report: StepReport`, `elapsed_s: float`                                                                           | `Pipeline._run_step` on success                                                                    |
| `StepErrored`                | `personalscraper.pipeline_events`               | `step: str`, `error_class: str`, `error_message: str`                                                                           | `Pipeline._run_step` on exception                                                                  |
| `ItemProgressed`             | `personalscraper.pipeline_events`               | `step: str`, `item: str`, `status: str`, `details: dict`                                                                        | Every step's per-item lifecycle (ingest, sort, dispatch…)                                          |
| `ItemDispatched`             | `personalscraper.dispatch.events`               | `item: str`, `target_disk: Path`, `category_id: str`, `action: Literal["moved","merged","replaced"]`                            | `dispatch._movie.dispatch_movie` + `dispatch._tv.dispatch_tvshow` after a successful real transfer |
| `CircuitBreakerOpened`       | `personalscraper.core.circuit`                  | `breaker: str`, `failure_count: int`, `last_error_class: str`, `last_error_message: str`                                        | `CircuitBreaker.record_failure` on transition                                                      |
| `CircuitBreakerClosed`       | `personalscraper.core.circuit`                  | `breaker: str`                                                                                                                  | `CircuitBreaker.record_success` after recovery                                                     |
| `CircuitBreakerHalfOpened`   | `personalscraper.core.circuit`                  | `breaker: str`                                                                                                                  | `CircuitBreaker.state` getter after cooldown elapses                                               |
| `DiskFullWarning`            | `personalscraper.indexer.events`                | `disk_path: Path`, `free_bytes: int`, `threshold_bytes: int`                                                                    | `check_free_space` and `handle_disk_full`                                                          |
| `TrailerDownloaded`          | `personalscraper.trailers.events`               | `media_path: Path`, `trailer_path: Path`, `source_url: str`                                                                     | `TrailersOrchestrator.run` success branch                                                          |
| `LibraryScanCompleted`       | `personalscraper.indexer.events`                | `mode: str`, `scanned: int`, `errors: int`, `elapsed_s: float`                                                                  | `indexer.scanner.scan` emit inside the function's outer `finally` block                            |
| `BackfillStarted`            | `personalscraper.indexer.events`                | `scope: str`, `item_count: int`                                                                                                 | `run_backfill_ids` at entry                                                                        |
| `BackfillItemCompleted`      | `personalscraper.indexer.events`                | `item_id: int`, `item_title: str`, `ids_added: tuple[str, ...]`, `ratings_added: tuple[str, ...]`                               | `run_backfill_ids` per row written                                                                 |
| `BackfillSkipped`            | `personalscraper.indexer.events`                | `item_id: int`, `item_title: str`, `reason: str`                                                                                | `run_backfill_ids` per row left untouched                                                          |
| `BackfillCompleted`          | `personalscraper.indexer.events`                | `scope: str`, `scanned: int`, `updated: int`, `skipped: int`, `failed: int`, `ids_added_count: int`, `ratings_added_count: int` | `run_backfill_ids` at return                                                                       |
| `ProviderFallbackTriggered`  | `personalscraper.api.metadata.registry._events` | Chain moved to next provider                                                                                                    | registry `chain` dispatch fallback                                                                 |
| `ProviderExhaustedEvent`     | `personalscraper.api.metadata.registry._events` | All chain providers failed                                                                                                      | registry `chain` dispatch exhaustion                                                               |
| `LockedCapabilityUnresolved` | `personalscraper.api.metadata.registry._events` | `locked()` cannot bind via IDCrossRef                                                                                           | registry `locked` dispatch                                                                         |
| `RegistryFanOutCompleted`    | `personalscraper.api.metadata.registry._events` | `fan_out` returned (success or failure)                                                                                         | registry `fan_out` dispatch                                                                        |
| `RegistryBootValidated`      | `personalscraper.api.metadata.registry._events` | Registry boot completed successfully                                                                                            | `ProviderRegistry.__init__` (`api/metadata/registry/__init__.py`)                                  |
| `VerifyItemDone`             | `personalscraper.verify.events`                 | `item: str`, `status: str`, `errors: list[str]`, `checks_passed: int`, `checks_total: int`                                      | `verify.run.run_verify` once per media item after the check → fix → re-check → classify cycle      |

The set is pinned by `test_every_event_has_factory` in `tests/fixtures/test_factories_registry.py`; adding a new event requires extending both the registry and the factories in the same commit.

## Boundary-only AppContext rule

`AppContext` is a frozen dataclass holding the three process-scoped
singletons (`config`, `settings`, `event_bus`). Only **CLI / launchd
boundaries** are allowed to construct one. Domain modules receive what
they need through their own constructor / function parameters; passing
`AppContext` deeper is a design violation.

The rule is enforced by `tests/architecture/test_app_context_boundary.py`:
an AST allowlist scan walks every source file, finds every
`_build_app_context` call, and asserts it lives in a function listed in
the allowlist. Currently the allowlist contains:

- `personalscraper.cli_helpers._build_app_context` (the constructor)
- `personalscraper.cli.callback` (the typer top-level callback)
- `personalscraper.commands.pipeline.run` (the full-pipeline CLI)
- `personalscraper.commands.library.scan.library_index` (the launchd command)
- the four `personalscraper.trailers.cli.*` subcommands

To add a new boundary, append its qualified name to the allowlist in
`tests/architecture/test_app_context_boundary.py` and write a short
justification in the commit body — the AST test fails on every other
construction site, including indirect ones through helpers.

## JSON serialization contract

Subscribers that persist events (the indexer outbox, future WebSocket
relay) need a deterministic JSON shape. The contract:

| Value kind          | Encoded as                                                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `datetime`          | ISO-8601 string with timezone (`2026-05-12T14:23:11+00:00`)                                                                    |
| `UUID`              | Plain string (`5e4c8b3d-...`)                                                                                                  |
| `Path`              | Plain string (POSIX, never `repr`)                                                                                             |
| `Enum`              | The member's `.value`                                                                                                          |
| dataclass instances | Recursive `event_to_dict` (no `_type`); fields preserved in declared order                                                     |
| `list` / `tuple`    | JSON array (tuples collapse to arrays)                                                                                         |
| `dict`              | JSON object; keys must be `str`, `int`, `float`, `bool`, or `None` — anything else raises `TypeError` (fail-loud, no coercion) |
| `None`              | JSON `null`                                                                                                                    |
| Anything else       | Raises `TypeError` — fail-loud. Add an explicit coercion in `event_to_dict` if a new value kind needs to flow through.         |

`event_to_dict(event)` produces a flat dict with the event's domain
fields plus the four base fields. `event_to_envelope(event)` wraps that
flat dict under a `"data"` key and adds a top-level `_type` discriminator:

```json
{
  "_type": "PipelineStarted",
  "data": {
    "timestamp": "2026-05-12T16:23:11+00:00",
    "event_id": "5e4c8b3d-d6c4-43d3-bc0e-7f5a9b8c1234",
    "source": "personalscraper.pipeline_events.PipelineStarted",
    "correlation_id": "run-20260512T1623",
    "report": { ... }
  }
}
```

**Decision guide.** Use `event_to_dict` for transient logging
(`DebugLogSubscriber`); use `event_to_envelope` whenever the receiver
needs to round-trip back to a concrete class
(`event_from_envelope`). The indexer outbox uses envelopes; the
debug log uses dicts.

## current_correlation_id ContextVar convention

`current_correlation_id` is a Python `contextvars.ContextVar[str |
None]` that every `Event.__post_init__` reads to populate the
`correlation_id` field. The ContextVar is scoped per asyncio task /
per thread, so emitting from inside a `ThreadPoolExecutor` worker
inherits the parent thread's binding automatically — provided the
binding is set before the executor is launched.

The bind/reset pattern is the same in every boundary; only the
binding scope differs. The four scenarios below cover every emitter
in the pipeline.

The key invariant: **bind once at the run boundary, reset once at
the end**. Never bind inside a domain function — that scopes the
correlation id to that function only, and breakers that emit from
inside a deeper call stack will not see it. Every CLI boundary
listed in the AppContext allowlist (§Boundary-only rule above)
binds the ContextVar; deeper code never touches it.

A subtler point: `current_correlation_id.get()` returns `None` when
no binding is active (e.g. during module import, smoke tests). The
`Event.__post_init__` stores `None` faithfully — `correlation_id`
is `str | None`, not `str`, precisely so the test envelope still
round-trips when no run is bound.

### CLI bootstrap (`personalscraper run`)

The actual bind/reset lives **inside** `Pipeline.run` (see
`personalscraper/pipeline.py:225` for `set` and `:370` for `reset`), not
in the CLI command itself. The CLI command is a thin wrapper that
constructs `AppContext`, instantiates subscribers, and calls
`pipeline.run(...)`; the ContextVar lifecycle is one layer down so
every event constructed during the run captures the same `run_id`:

```python
# personalscraper/pipeline.py — inside Pipeline.run(...)
run_id = uuid4().hex
token = current_correlation_id.set(run_id)
try:
    # … emit PipelineStarted, run every step, emit PipelineEnded …
finally:
    current_correlation_id.reset(token)
```

structlog's context binding (`bind_contextvars(run_id=...)`) is wired
in parallel at the CLI boundary (`personalscraper/commands/pipeline.py`
inside the `run` command) so log records also carry the same id.

### launchd scan bootstrap (`personalscraper library-index`)

The `library_index_command` binds `current_correlation_id` for the
duration of the scan with a fresh `run_id`. Long-lived breakers (HTTP
circuit, disk circuit) that pre-existed the scan capture this id on
emit even though they themselves were constructed earlier — the
ContextVar is read at `Event.__post_init__` time, not at breaker
construction.

### Trailers standalone bootstrap (`personalscraper trailers run`)

Same pattern. The `trailers run` Typer command binds
`current_correlation_id` around the `TrailersOrchestrator.run` call;
the YouTube breaker constructed inside the orchestrator emits
events that carry the run's id.

### Long-lived emitter scenario

A breaker constructed at module load (the `_GLOBAL_DISK_BREAKER`
singleton, for instance) has no correlation id of its own. When the
scanner calls into it from inside a `library-index` invocation, the
ContextVar resolves to the scan's `run_id` and the emitted
`CircuitBreakerOpened` carries that id. Tests pin this in
`test_circuit_breaker_long_lived_singleton_captures_correlation_id`.

## Writing a new event

1. **Decide on the module.** Domain events live in `<domain>/events.py`
   (e.g. `dispatch/events.py`, `trailers/events.py`). Pipeline-wide
   lifecycle events live in `pipeline_events.py`. Core /
   cross-cutting events live in `core/circuit.py` or
   `indexer/events.py`.
2. **Define the dataclass.**

   ```python
   from dataclasses import dataclass
   from personalscraper.core.event_bus import Event

   @dataclass(frozen=True, kw_only=True)
   class MyDomainEvent(Event):
       """One-line summary for the event catalog.

       Attributes:
           foo: What it carries.
           bar: What it carries.
       """

       foo: str
       bar: int
   ```

3. **Register via import.** Add the new class to the eager-import list
   in `personalscraper.events.__init__` so the class registry knows
   about it before the first `event_from_envelope` call.
4. **Add a factory.** Open `tests/fixtures/event_samples.py` and add
   the new class to `EVENT_SAMPLE_FACTORIES` with a real-data
   factory (no `MagicMock`). The `test_every_event_has_factory` gate
   fails otherwise.
5. **Write the round-trip test.** Add the class to the parametrize
   list of the envelope round-trip test in your domain's test
   module. The assertion is `event_to_envelope` then
   `event_from_envelope` reconstructs an equal instance.
6. **Update the v1 catalog table.** Append a row to the table in this
   document and to the design doc; bump the gate's expected event
   count in the test registry assertion.

## Writing a new subscriber

Subscribers are simple: a class with an `__init__(bus, ...)` that
self-registers, a method per event type, and an optional `close()`
for lifecycle management.

```python
from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.pipeline_events import PipelineStarted, PipelineEnded


class MyAlerter:
    """Send a Slack message when the pipeline starts and ends."""

    name = "slack-alerter"

    def __init__(self, bus: EventBus, slack: SlackClient) -> None:
        self._slack = slack
        self._tokens: list[SubscriptionToken] = [
            bus.subscribe(PipelineStarted, self._on_start),
            bus.subscribe(PipelineEnded, self._on_end),
        ]
        self._bus = bus

    def _on_start(self, event: PipelineStarted) -> None:
        self._slack.send(f":rocket: pipeline started — {event.correlation_id}")

    def _on_end(self, event: PipelineEnded) -> None:
        self._slack.send(f":checkered_flag: pipeline ended — {event.correlation_id}")

    def close(self) -> None:
        for token in self._tokens:
            self._bus.unsubscribe(token)
```

**Lifecycle rules.**

- Self-subscribe in `__init__`; never lazy-subscribe later.
- Store every token on `self`; never let one leak.
- `close()` is the only place the subscriber removes itself.
- The CLI run command wraps subscribers in `try / finally` so
  `close()` runs even on errors.

If your subscriber needs to react to **every** event type, subscribe
to `Event` (single subscription) — the bus's MRO walk routes every
concrete subclass to your handler. `DebugLogSubscriber` is the
canonical example — fewer than 40 non-blank lines.

## Testing patterns

The bus is engineered to be cheap to test: a fresh `EventBus()` is a
no-op construction, subscribers are simple classes, and every event
class has a real-data factory in
`tests/fixtures/event_samples.py`. The patterns below are the
canonical ones used across the test tree — copying them keeps new
tests consistent with the existing project suite (run `make test` for
the current count).

There are four reusable infrastructures, each documented below: the
`CollectingSubscriber` for emit assertions, the factories registry
for parametrized tests over the full catalog, the AST boundary test
for the AppContext rule, and the required-bus signature test for
the required-bus contract. Reach for them before writing ad-hoc
fakes — each one is gated by its own test so regressions are caught
immediately.

A general note on test hygiene: every `CircuitBreaker(...)` and
every required-bus entry point requires `event_bus=` explicitly.
Pass `event_bus=EventBus()` from a fixture or inline when the test
doesn't care about emit; the bus is so lightweight that per-test
instances cost nothing. The AST sweep test forbids any signature
without an explicit required `event_bus`, so consistency is
mechanically enforced.

### `CollectingSubscriber[E]`

A test-only subscriber that stores received events for assertions.
Live in `tests/fixtures/event_bus.py`. Used everywhere we need to
prove an emit happened without wiring a full mock:

```python
from tests.fixtures.event_bus import CollectingSubscriber

bus = EventBus()
sink: CollectingSubscriber[ItemDispatched] = CollectingSubscriber(bus, ItemDispatched)
do_the_thing(event_bus=bus)
assert len(sink.received) == 1
assert sink.received[0].action == "moved"
```

### Factories registry

`tests/fixtures/event_samples.py::EVENT_SAMPLE_FACTORIES` maps every
v1 event class to a zero-arg factory producing a realistic instance.
Tests that need to exercise every event type (round-trip,
`DebugLogSubscriber`, snapshot rendering) parametrize over this dict.
The `test_every_event_has_factory` gate prevents adding an event
without a factory.

### AST boundary test

`tests/architecture/test_app_context_boundary.py` walks every source
file and asserts that `_build_app_context` is only called from
allowlisted functions. Update the allowlist in the same commit that
introduces a new boundary — the test fails on every other
construction site. The walker also enforces that allowlisted
qualified names actually exist (no stale entries).

### Required-bus signature test

`tests/architecture/test_event_bus_required_signatures.py` parametrizes
over every required-bus site and asserts (a) `event_bus`
parameter exists, (b) it has no default value, (c) the annotation
excludes `None`. The same module also runs an exhaustive AST sweep
across `personalscraper/**/*.py` to catch any future regression
outside the hand-maintained list.

## Performance notes

The bus is engineered for tens-of-thousands of `ItemProgressed` emits
per pipeline run without becoming a bottleneck.

- **MRO cache.** Subscribe-time, each callback's target class is
  resolved once; emit-time, the bus walks the cached MRO list rather
  than recomputing `type(event).__mro__`.
- **Copy-on-write tuples.** Subscriptions live in
  `dict[type[Event], tuple[Callback, ...]]`. Adding a subscriber
  replaces the tuple; emits iterate a snapshot, so concurrent
  `subscribe` / `unsubscribe` mid-emit is safe and lock-free.
- **Zero-allocation fast path.** Events with no subscribers return
  immediately from `emit` — no list construction, no MRO walk.
- **Synchronous, in-process.** No threading, no asyncio. Subscribers
  run on the emit thread; the bus is a multicast call, not a queue.

The cost of an emit with one subscriber is dominated by the
subscriber's callback. The bus itself is a synchronous dispatch over
the cached MRO chain — at the scale used by `ItemProgressed` (a few
thousand emits per pipeline run) the overhead is irrelevant compared to
the per-item I/O of the step itself. Don't optimise emit count — write
the emit where the semantic transition happens, not "when convenient".

## Future evolution

Roadmap items that depend on the bus contract being stable but are
NOT in scope for the v1 catalog:

- **WebSocketSubscriber prototype.** Phase 1 of the future Web UI —
  subscribes to `Event`, relays envelopes over a WebSocket. Tracked
  as DESIGN §Open Questions #3; postponed to the P2 Web UI feature.
- **Outbox persistence.** The indexer already has a write-through
  outbox; extending it to a generic event-store would let the future
  Web UI replay events on reconnection. Not started.
- **Event versioning.** Partially realized in v0.17.0 (arch-cleanup-2): the
  `Event` base now carries a `schema_version: int = 1` field that threads
  through `event_to_envelope` / `event_from_envelope`. It is bumped on the
  first breaking event-shape change once a cross-process consumer exists;
  today every consumer is in-tree so version skew is impossible and all
  events stay at `1`.

For the rationale and decision log, see
[`docs/features/event-bus/DESIGN.md`](../features/event-bus/DESIGN.md)
§Roadmap Alignment.

The bus contract is intentionally additive: new event classes and new
subscribers can land without coordination across the codebase. The
two things that **do** require coordination are (a) renaming an
existing event class (envelope `_type` is part of the wire contract)
and (b) removing a field from an existing event (subscribers that
read the field will break). Both are PR-review-flagged regressions,
not silent migrations.
