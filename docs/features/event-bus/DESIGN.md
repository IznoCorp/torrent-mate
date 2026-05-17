# Event Bus — Design

**Feature**: Event Bus
**Codename**: event-bus
**Type**: minor (SemVer Y+1)
**Status**: spec (preparation — not yet implemented)
**Date**: 2026-05-11
**Replaces**: `PipelineObserver` Protocol (introduced in `pipeline-obs`, merged 2026-05-11)

## NO DEFERRAL — MANDATORY

**Every step is adapted. Every test is written. Nothing is skipped, nothing is
deferred, nothing is left for "later". This applies to every phase and every
sub-phase of the implementation plan. Each phase gate MUST verify that all
planned work for that phase is complete — no partial implementations, no
"foundation first, integration later".**

## Purpose

PersonalScraper has no event/signal system. The pipeline runs as a linear
sequence with zero hooks for external code to react to step transitions, item
completion, errors, circuit-breaker trips, disk-full conditions, dispatch
decisions. The `PipelineObserver` Protocol introduced by `pipeline-obs` solves
a sub-problem (pipeline lifecycle) but is not extensible to cross-cutting
events emitted outside pipeline runs (CircuitBreaker transitions from any HTTP
component, scheduled launchd indexer scans, standalone trailer CLI invocations).

This feature replaces `PipelineObserver` with a single application-wide
`EventBus` that serves as the only substrate for component-to-component
asynchronous communication. Every cross-cutting event in the system flows
through one bus, every subscriber speaks one API.

The design is **greenfield-first, no compromises**. Pipeline observer
infrastructure introduced two days earlier is fully removed and rewritten as
subscribers on the bus. This is a deliberate choice: the rest of the roadmap
(Web UI, Watcher Service, Auto-Download, Provider Registry, DI Container)
all depend on a single coherent event substrate, and carrying a dual
mechanism would tax every future feature.

## Goals

1. `EventBus` class with type-indexed subscribe and fire-and-forget emit,
   owned by an `AppContext`.
2. Typed frozen event dataclasses inheriting from a common `Event` base.
3. Event catalog covering v1 needs: pipeline lifecycle, item progress,
   dispatch outcomes, circuit-breaker transitions, disk pressure, indexer
   scan completion, trailer downloads.
4. Subscribe-to-base-class catches all subclasses via MRO resolution of
   the emitted event type — enables "everything" consumers (CLI
   `--verbose`, Web UI in P2).
5. Zero overhead when no subscribers are registered (early-return fast path).
6. Error isolation: a failing subscriber does not break dispatch.
7. Re-entrant emit: a subscriber may emit during its own handler.
8. JSON-serializable events: every event in the catalog round-trips
   through `event_to_envelope()` → JSON → `event_from_envelope()`,
   verified by test for every concrete event type via factory-built
   realistic instances. Pure-payload form available via `event_to_dict()`
   for consumers that already know the type out-of-band. Web UI and
   future cross-process variants can ship events over the wire without
   an adapter layer.
9. Clean removal of `PipelineObserver`, `RichConsoleObserver`,
   `TelegramObserver` — rewritten as subscribers.
10. `AppContext` bootstrap pattern reusable by CLI, launchd scan, and
    (later) Web UI / Watcher Service.

## Non-Goals (verrouillés)

- Persistent event log / event sourcing.
- Cross-process event propagation (deferred to Watcher Service v2 — out of
  v1 scope, but events are JSON-serializable so the bridge is non-traumatic
  later).
- Retry/replay semantics.
- Asynchronous (asyncio) dispatch — sync only. The name `aemit` is reserved
  for future addition without API change.
- Middleware / event interceptors.
- Predicate-based subscription filters (`bus.subscribe(T, fn, where=...)`).
  Type-indexed subscribe is the only filter.
- Subscription priorities / weights.

Each non-goal is intentionally absent. v1 MUST NOT add them speculatively.

## Architecture

### AppContext (new) — boundary-only rule

`AppContext` is the long-lived process-scoped bundle. Created **once per
process** (CLI entry, launchd scan entry, future Web UI / Watcher boot).

```python
@dataclass(frozen=True)
class AppContext:
    config: Config
    settings: Settings
    event_bus: EventBus
```

Future fields (designed-for but not in v1): `provider_registry` (P1),
`service_container` (P3 DI Container).

**Boundary-only rule** (architectural invariant): `AppContext` is constructed
and passed at process boundaries only. Internal components MUST receive
specifically what they need — typically `event_bus: EventBus`, sometimes
`config: Config`. They MUST NOT receive `AppContext` "for convenience".

Rationale: `AppContext` is a god-object risk. If low-level modules take
`AppContext` "in case they need other services later", tests become
constructor-heavy and unit boundaries blur. The bus is the only piece every
component will eventually need; pass it directly.

Construction sites (v1) — real paths in the current codebase:

- `personalscraper/cli.py` (interactive pipeline run) → builds AppContext, hands to Pipeline.
- `personalscraper/commands/library/scan.py::library_index` (launchd `library-index` Typer command) → builds AppContext, hands to the indexer scanner orchestrator (`personalscraper/indexer/commands/scan.py::library_index_command`).
- `personalscraper/trailers/cli.py::{scan, download, verify, purge}` (standalone trailers commands — single module, four Typer entrypoints) → builds AppContext, hands to the trailers orchestrator.
- Test fixtures → build minimal AppContext with collector subscribers.

Path note: `personalscraper/pipeline.py` is a single flat module today (NOT a `pipeline/` package). Events live in `personalscraper/pipeline_events.py` next to it. Converting `pipeline.py` to a package is OUT of scope for this feature (deferred to a future refactor) — the event-bus introduces events as a sibling module, never as a package conversion.

### EventBus

`personalscraper/core/event_bus.py` exports: `EventBus`, `Event` base,
`SubscriptionToken`, `event_to_dict`, `event_to_envelope`,
`event_from_envelope`, `current_correlation_id` (ContextVar), and the
event class registry helpers. Co-located with `core/circuit.py`. Module
target ≤ 400 LOC (uplift from 350 because the module carries MRO cache,
COW subscriber tuples, ContextVar handling, envelope encode/decode,
event class registry and the `__init_subclass__` hook; revisit if a
clean internal split emerges during Phase 1).

```python
class EventBus:
    """In-process pub/sub for typed events.

    Subscribe by event type; subscribing to a base class catches all
    subclasses via MRO walk of the emitted event type. Emit is
    synchronous, fire-and-forget,
    error-isolated.
    """

    def subscribe(
        self,
        event_type: type[E],
        callback: Callable[[E], None],
    ) -> SubscriptionToken: ...

    def unsubscribe(self, token: SubscriptionToken) -> None: ...

    def emit(self, event: Event) -> None: ...
```

`SubscriptionToken` is an opaque handle returned from `subscribe`. Use case:
a subscriber that registers itself in `__init__` and tears down in a
`close()` / `__exit__` method (Web UI WebSocket session lifecycle, test
fixtures, etc.).

### Dispatch semantics

1. **Type matching**: `emit(StepStarted(...))` notifies subscribers of
   `StepStarted`, `Event` (base), and any intermediate ancestors. The MRO
   walk is performed once per `emit`; the result is cached per concrete event
   type after the first emit (~5 LOC, real win on `ItemProgressed` which can
   fire 1000× per run).
2. **Fast path**: if `_subscribers` dict is empty, `emit` returns immediately
   after a single check. If subscribers exist for some types but not the
   emitted type's MRO, the cached resolution yields an empty tuple — still
   sub-microsecond.
3. **Error isolation**: each callback invocation is wrapped in `try/except`.
   Exceptions are logged via structlog at WARNING with `event_emit_failed`,
   `subscriber=<name>`, `event_type=<class>`, `event_id=<UUID>`,
   `exc_info=True`. Dispatch continues to the next subscriber.
4. **Re-entrancy**: a subscriber MAY emit during its own handler. Dispatch
   iterates over an immutable snapshot of the subscriber tuple per type to
   avoid mutation-during-iteration bugs. Snapshot is the same tuple object
   when no mutation has occurred (copy-on-write inside `subscribe` /
   `unsubscribe`), so no allocation per emit in the steady state.
   **Recursion policy**: the bus has NO recursion guard. A subscriber that
   emits an event whose dispatch eventually re-invokes the same subscriber
   (subscribing to its own type, or to `Event` base) is caller
   responsibility. `RecursionError` is a subclass of `Exception` and is
   therefore caught by the per-subscriber `try/except Exception` block —
   the bus logs `event_emit_failed` at WARNING and continues with the
   next subscriber. Dispatch is NOT halted, but the buggy subscriber
   stops contributing on its next attempt. Subscribers MUST NOT subscribe
   to a type they themselves emit unless the recursion is bounded by their
   own logic. Documented and tested (Phase 1 §1.4
   `test_recursive_subscriber_caught_as_error_isolation`).
5. **Ordering**: subscribers for a given type are invoked in subscription
   order across the union of (concrete-type subscribers, ancestor-type
   subscribers in MRO order). The MRO cache is built once per concrete event
   type as the **concatenation** of subscriber tuples walked along
   `type(event).__mro__` (excluding `object`), starting with the concrete
   type. Within each MRO step, subscribers retain their subscription-order
   index. The result: concrete-type subscribers fire first (in subscription
   order), then immediate-parent subscribers, then grand-parent, … then
   `Event`-base subscribers — so a `bus.subscribe(StepStarted, …)` sees the
   event before a generic `bus.subscribe(Event, debug_log)` does, regardless
   of which `subscribe` call happened first. **Cache invariant**: the cached
   tuple's order is determined entirely by current subscriber state, not by
   historical order of `subscribe` calls across types. Invalidated on every
   `subscribe` / `unsubscribe`.
6. **Thread safety** (v1): the bus itself (subscribe / unsubscribe / emit /
   the MRO cache) is single-threaded. Pipeline is single-threaded. Only
   `correlation_id` propagation is thread-safe by virtue of `ContextVar`
   per-thread isolation — that is, an event constructed in thread T picks up
   thread T's bound `correlation_id`. If a future Watcher Service introduces
   multi-threaded concurrent emit on the same bus instance, add a lock then
   (well-bounded change).

### Event base class

```python
@dataclass(frozen=True, kw_only=True)
class Event:
    """Base for all bus events.

    Carries metadata common to every event. Subclasses add their payload.
    All Event subclasses MUST also use `@dataclass(frozen=True, kw_only=True)`
    — the `kw_only=True` convention is inherited from the base and propagated
    explicitly because Python's dataclass machinery does not transitively
    enforce it. This avoids the "non-default argument follows default
    argument" error that would otherwise arise when a subclass adds a
    required field after the base's defaulted fields.
    """

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = field(default="")     # auto-derived in __post_init__
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: str | None = field(
        default_factory=lambda: current_correlation_id.get()
    )

    def __post_init__(self) -> None:
        # Frozen dataclass — use object.__setattr__ to populate auto-derived
        # default. Caller may override `source` via constructor.
        if not self.source:
            cls = type(self)
            object.__setattr__(
                self, "source", f"{cls.__module__}.{cls.__name__}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convenience method — delegates to module-level `event_to_dict(self)`.

        Returns the pure payload form (no `_type` tag). For the
        type-tagged envelope used by transport/reconstruction, use
        `event_to_envelope(self)`. Round-trip is verified by
        `tests/event_bus/test_serialization.py` for every concrete event.
        """
        return event_to_dict(self)
```

**Auto-derived `source`**: eliminates the "empty source default" failure
class. Emitters can still override (e.g. CircuitBreaker passes
`source=f"core.circuit.{breaker_name}"` so subscribers can distinguish TMDB
breaker from TVDB breaker without payload inspection).

**`source` field semantics**: `source` is a **debug hint**, not a stable
identity. Subscribers SHOULD NOT route or filter on `source` — they
discriminate by event type and by payload fields (`breaker:`, `step:`, etc.).
The string format is `"<module>.<ClassName>"` for auto-derived (e.g.
`"personalscraper.core.circuit.CircuitBreakerOpened"`), or an emitter-chosen
override (e.g. `"core.circuit.tmdb"`). The format MAY change in future
versions without bumping the major version — consumers needing stable
identity MUST use `type(event)` + payload, not `source`.

**`correlation_id` convention** (v1):

Long-lived emitters (CircuitBreaker singletons constructed at HTTP client
boot time, indexer DiskGuard) cannot receive a per-run `run_id` via
constructor — they outlive any single run. The chosen mechanism is a
module-level `ContextVar`:

```python
# core/event_bus.py
current_correlation_id: ContextVar[str | None] = ContextVar(
    "current_correlation_id", default=None
)
```

- `Pipeline.run()` generates `run_id: UUID` once per run and binds it via
  `token = current_correlation_id.set(str(run_id))` inside a try/finally
  that calls `current_correlation_id.reset(token)` on exit (success or
  failure). `StepContext.run_id` exposes the same value to step code
  that needs it explicitly.
- **Capture happens at event construction**, not at emit: the base
  `Event` dataclass declares
  `correlation_id: str | None = field(default_factory=lambda:
current_correlation_id.get())`. Constructing any event inside a
  bound region picks up the current `run_id` automatically; outside
  any bound region the factory returns `None`. Caller can still
  override explicitly: `StepStarted(step="ingest",
correlation_id="custom")`.
- `EventBus.emit()` does **not** read or modify `correlation_id`. The
  event is frozen and dispatched as-is. This avoids
  `dataclasses.replace`/`object.__setattr__` in the hot path
  (`ItemProgressed` can fire 1000× per run) and eliminates the
  "explicit None vs default None" ambiguity that a sentinel would
  otherwise require.
- Long-lived emitters (CircuitBreaker, DiskGuard) construct their
  events normally; the current run's `run_id` is picked up at event
  construction time via the ContextVar. **No `correlation_provider`
  callable on the CircuitBreaker constructor** — ContextVar removes
  the need.
- Emits originating outside a pipeline run (launchd indexer scan,
  standalone trailers command) bind their own `run_id` at AppContext
  bootstrap time using the same `current_correlation_id.set(...)` /
  try-finally pattern. Each AppContext build site owns one bind/reset
  cycle.
- Cross-thread/async safety: `ContextVar` is per-task in asyncio and
  per-thread in threading; a future Watcher Service multi-threaded
  emit Just Works without redesign.

### JSON serialization contract

`core/event_bus.py` exports:

```python
def event_to_dict(event: Event) -> dict[str, Any]:
    """Recursively serialize an event payload to a JSON-safe dict.

    Returns the **pure** payload form — no `_type` metadata wrapper.
    Suitable for consumers that already know the event type out-of-band
    (Web UI typed channels, structured logs with explicit type labels,
    typed RPC responses).

    Encoding rules:
      datetime  → ISO 8601 string (UTC, with timezone)
      UUID      → str
      Path      → str
      Enum      → enum.value
      dataclass → asdict (recursive)
      list/tuple → list
      dict      → dict (keys must be JSON-safe; otherwise TypeError)
      None/str/int/float/bool → unchanged
      anything else → TypeError (fail-loud, never silent)
    """

def event_to_envelope(event: Event) -> dict[str, Any]:
    """Wrap an event in a self-describing envelope for transport.

    Returns `{"_type": "<ClassName>", "data": event_to_dict(event)}`.
    Used by the cross-process bridge (P2 Watcher v2), the test
    round-trip, and any consumer that needs reconstruction without
    prior type knowledge.

    The split between `event_to_dict` (pure) and `event_to_envelope`
    (tagged) is deliberate: keeps the wire format clean for typed
    consumers, keeps reconstruction explicit for untyped consumers.
    """

def event_from_envelope(data: dict[str, Any]) -> Event:
    """Reconstruct an event from its envelope form.

    Looks up `data["_type"]` in a class registry populated at import
    time by the `events/__init__.py` re-exports. Raises `KeyError` if
    the type is unknown (fail-loud — never silently drop unknown
    events, the caller decides whether to skip or crash).

    Nested-dataclass reconstruction: for each field of the top-level
    event class (introspected via `dataclasses.fields`), the encoded
    value in `data["data"][field.name]` is decoded according to the
    field's declared annotation, recursively. Supported decode rules
    are the inverse of `event_to_dict` encoding:
      datetime annotation  → datetime.fromisoformat(value)
      UUID annotation      → UUID(value)
      Path annotation      → Path(value)
      Enum subclass        → EnumClass(value)
      dataclass annotation → recursive decode of each of its fields
      list[T] annotation   → [decode(v, T) for v in value]
      dict[K, V] annotation → {decode(k, K): decode(v, V) for ...}
      str/int/float/bool/None → value as-is
      anything else        → TypeError (symmetric with encoder)
    The decoder uses `typing.get_type_hints` (with the event module's
    globals) to resolve forward refs and string annotations. Nested
    dataclass payloads (`PipelineReport`, `StepReport`, …) reconstruct
    recursively via the same rules — no per-type registry needed for
    nested dataclasses because their class is known from the parent
    event's field annotation.
    """
```

`PipelineReport` and `StepReport` are plain dataclasses; `event_to_dict`
handles them via the recursive `dataclass` rule. They MUST keep all their
fields JSON-friendly (no `Console`, no `Callable`, no live file handle).
This is enforced in v1 by the round-trip test (`test_event_round_trip`)
which iterates over every concrete event in `personalscraper.events`.

### Event catalog (v1)

Located by domain producer; re-exported from
`personalscraper/events/__init__.py`. The `events/__init__.py` module MUST
eagerly import each producer module at import time so that
`Event.__init_subclass__` fires and populates `_EVENT_CLASS_REGISTRY`
before any consumer calls `event_from_envelope`. Layout rationale: events
sit next to their producer module, NOT under a `personalscraper/events/`
flat package — this keeps each producer self-contained and avoids
artificial coupling at the package level.

| Event                      | Module               | Payload (beyond Event base)                                                                    |
| -------------------------- | -------------------- | ---------------------------------------------------------------------------------------------- |
| `PipelineStarted`          | `pipeline_events.py` | `report: PipelineReport`                                                                       |
| `PipelineEnded`            | `pipeline_events.py` | `report: PipelineReport`                                                                       |
| `StepStarted`              | `pipeline_events.py` | `step: str`                                                                                    |
| `StepCompleted`            | `pipeline_events.py` | `step: str, report: StepReport, elapsed_s: float`                                              |
| `StepErrored`              | `pipeline_events.py` | `step: str, error_class: str, error_message: str`                                              |
| `ItemProgressed`           | `pipeline_events.py` | `step: str, item: str, status: str, details: dict[str, Any]`                                   |
| `ItemDispatched`           | `dispatch/events.py` | `item: str, target_disk: Path, category_id: str, action: Literal["moved","merged","replaced"]` |
| `CircuitBreakerOpened`     | `core/circuit.py`    | `breaker: str, failure_count: int, last_error_class: str, last_error_message: str`             |
| `CircuitBreakerClosed`     | `core/circuit.py`    | `breaker: str`                                                                                 |
| `CircuitBreakerHalfOpened` | `core/circuit.py`    | `breaker: str`                                                                                 |
| `DiskFullWarning`          | `indexer/events.py`  | `disk_path: Path, free_bytes: int, threshold_bytes: int`                                       |
| `TrailerDownloaded`        | `trailers/events.py` | `media_path: Path, trailer_path: Path, source_url: str`                                        |
| `LibraryScanCompleted`     | `indexer/events.py`  | `mode: str, scanned: int, errors: int, elapsed_s: float`                                       |

Producer-module paths above are real paths (flat `personalscraper/pipeline_events.py`
next to `pipeline.py`; sub-package events files under `dispatch/`, `indexer/`,
`trailers/` which ARE packages today; circuit events embedded in `core/circuit.py`).

Notes:

- `ItemProgressed` replaces `StepEvent` from pipeline-obs (renamed and lifted
  to the canonical hierarchy). `details: dict[str, Any]` payload values MUST
  be JSON-safe (the encoder fails loud otherwise — see Phase 1 test).
  **`details` keys are step-specific** (scrape uses `provider`, `confidence`;
  verify uses `check_category`; etc.). Convention: `lowercase_snake_case`.
  The full per-step keyset is documented in `docs/reference/event-bus.md`
  (Phase 5). New steps MUST follow the convention and add their keyset to
  that doc.
- `ItemDispatched` only fires for **completed transfers** (real moves).
  `dry_run=True` pipeline runs do NOT emit `ItemDispatched` — the `action`
  field is `Literal["moved","merged","replaced"]` with no `"skipped"`
  value, by design.
- `StepErrored.error_class` and `error_message` split is intentional:
  Telegram subscriber needs the human message; structlog still captures the
  traceback via `exc_info` at the emit site.
- All payload fields MUST be JSON-safe types. Adding an event with a
  non-serializable field is caught by the round-trip test.

## Migration

### Removed

- `personalscraper/pipeline_observer.py` — entire file (PipelineObserver,
  PipelineObserverBase, notify_progress, StepEvent, CollectorObserver).
- `personalscraper/pipeline_protocol.py::StepContext.observers` field.
- `personalscraper/observers/` package — renamed to
  `personalscraper/subscribers/`. Grep `from personalscraper.observers` is
  required (mechanical sweep in Phase 3 — tests/, docs/reference/, every
  importer).

### Refactored

- **`StepContext`** (final shape after Phase 3): gains `app: AppContext` and
  `run_id: UUID` fields; drops `config`, `settings`, `observers`. Steps
  access config via `ctx.app.config`, bus via `ctx.app.event_bus`.
  Run-scope flags (`dry_run`, `interactive`, `verbose`, `upstream`,
  `extras`) remain. **Phase-wise rollout**: Phase 2 adds `app` + `run_id`
  and removes `config` + `settings`, but KEEPS the `observers` field so
  legacy `notify_progress(ctx.observers, …)` still drives user-visible
  output during the migration window. Phase 3 removes `observers` once
  every step has bus emit and `RichConsoleSubscriber` + `TelegramSubscriber`
  replace the legacy observers. The "final shape" described in this bullet
  is post-Phase-3.
- **`Pipeline.__init__`** accepts `AppContext` (not `Console`, not observers
  tuple). Generates `run_id: UUID` per run. Builds `StepContext` from
  `AppContext` + per-run state.
- **`RichConsoleObserver` → `RichConsoleSubscriber`** in
  `subscribers/rich_console.py`: subscribes in `__init__` to
  `PipelineStarted`, `PipelineEnded`, `StepStarted`, `StepCompleted`,
  `StepErrored`, `ItemProgressed`. Same visual behavior; different wiring.
- **`TelegramObserver` → `TelegramSubscriber`** in `subscribers/telegram.py`:
  subscribes to `PipelineEnded`, `StepErrored`, `CircuitBreakerOpened`,
  `DiskFullWarning`. **Behavioral gain over pipeline-obs**: Telegram now
  alerts on circuit-breaker trips and disk-full warnings, previously
  invisible to operators.
- **`CollectorObserver` → `CollectingSubscriber[E]`** generic, exported from
  `tests/fixtures/event_bus.py` (test-only utility). Tests parametrize on
  event type or subscribe to `Event` to collect everything.
- **All `notify_progress(observers, StepEvent(...))` call sites** become
  `ctx.app.event_bus.emit(ItemProgressed(...))`. Mechanical migration.

### CircuitBreaker integration

`personalscraper/core/circuit.py` gains constructor parameters:

```python
def __init__(
    self,
    *,
    event_bus: EventBus | None = None,            # Phase 4: optional
    name: str = "anonymous",
    ...
):
```

- `event_bus` is **optional in Phase 4** (migration window): call sites that
  haven't been threaded yet pass nothing, breakers silently skip emit.
- `event_bus` is **required from Phase 5**: the `| None` is removed, all
  call sites must pass a bus. Audit at Phase 5 gate: `grep "CircuitBreaker("`
  shows zero call sites without `event_bus=...`.
- `name` identifies the breaker (e.g. `"tmdb"`, `"tvdb"`, `"qbit"`); used as
  the `breaker:` payload field on emitted events.
- **No `correlation_provider` parameter**: the `current_correlation_id`
  `ContextVar` (see "correlation_id convention" above) handles run_id
  lookup at event construction time. The base `Event` dataclass's
  `correlation_id` default_factory reads the ContextVar when the
  CircuitBreaker constructs a `CircuitBreakerOpened` / `Closed` /
  `HalfOpened` instance — so even though the breaker singleton was
  constructed long before any pipeline run started, the event it
  emits during a run carries the current `run_id`. `EventBus.emit`
  itself does not read or modify `correlation_id`.

### DiskGuard / indexer integration

The indexer's existing disk-free check (currently embedded in
`indexer/db.py::handle_disk_full`, slated for extraction to
`indexer/_disk_guard.py` per P3 roadmap) receives an `event_bus`
parameter from its AppContext-aware caller and emits `DiskFullWarning`
when free space crosses the threshold.

`indexer/scanner/_modes/*.py` orchestrator emits `LibraryScanCompleted` at
end of each mode, with `mode`, `scanned`, `errors`, `elapsed_s` extracted
from the scan summary.

### Dispatch integration

`dispatch/dispatcher.py` (and the per-type files `_movie.py`, `_tv.py`)
emit `ItemDispatched` after each successful move/merge/replace, with
`action` being one of the existing dispatch outcomes.

### Trailers integration

`personalscraper/trailers/orchestrator.py` emits `TrailerDownloaded` after
each successful trailer fetch (the orchestrator is the single coordination
point that wraps `personalscraper.scraper.ytdlp_downloader.YtdlpDownloader`),
with `source_url` derived from yt-dlp metadata. Standalone trailers
commands (`personalscraper/trailers/cli.py::{scan, download, verify, purge}`
— single module, four Typer entrypoints) thread the bus through the
orchestrator from their AppContext-aware bootstrap.

### CLI integration

- **`personalscraper run` (interactive)**: bootstrap creates `AppContext`,
  registers `RichConsoleSubscriber` (always) and `TelegramSubscriber` (if
  Telegram creds present). Same UX as today.
- **`--verbose` flag**: registers an additional `DebugLogSubscriber` that
  subscribes to `Event` (base) and logs every event via structlog at DEBUG
  with the full `event_to_dict` payload. Replaces ad-hoc verbose handling.
- **`personalscraper trailers download` (standalone)**: bootstrap creates
  AppContext; the trailers orchestrator emits `TrailerDownloaded` which subscribers
  (if registered) see.
- **Launchd `library-index` scan**: bootstrap creates AppContext with
  logging-only subscribers; emits `LibraryScanCompleted` at end. Future
  Watcher Service v2 subscribes to this event from its daemon AppContext.

### Logging convention (Phase 3 sweep)

**Emitters emit only — no structlog inside emit sites.** This eliminates
double-logging (event + log line for the same fact). `DebugLogSubscriber` is
the canonical path from emit → log.

Existing structlog calls at points that will become emit sites are
**removed** during Phase 3 migration (not left as duplicates). Calls that
log information NOT carried by any event (intermediate state, debug
breadcrumbs) stay as-is — they are not emit-equivalent.

Phase 3 gate audit: every emit site has at most one structlog call, and
only when it carries information distinct from the emitted event (e.g.
exception traceback via `exc_info=True` while the event carries the
class+message strings).

### Performance contract — subscribers MUST be fast

`EventBus.emit` is **synchronous, fire-and-forget**. Every subscriber for
the emitted type's MRO runs serially in the caller's thread, on the
caller's stack, before `emit` returns. There is NO queueing, NO async
offload, NO backpressure mechanism in v1.

**Subscriber contract**:

- A subscriber callback MUST complete in O(microseconds) for high-frequency
  events (`ItemProgressed` can fire 1000× per pipeline run — a 1 ms
  subscriber adds a full second of overhead to a run).
- If a subscriber needs to do non-trivial work (HTTP, disk, IPC), it MUST
  schedule that work asynchronously (`asyncio.create_task`, `threading.Thread`,
  `multiprocessing.Queue`, etc.) and return immediately. The bus does NOT
  provide such offload — it is the subscriber's responsibility.
- `TelegramSubscriber` is the canonical example: it MUST schedule the HTTP
  send off the calling thread (current implementation does — Phase 3
  carries this property forward).

**Backpressure**: none in v1. A slow subscriber will slow down the pipeline
linearly. Future async dispatch (`aemit`) is reserved but explicitly out of
v1 scope.

### Rollback policy — fix-forward only

The design is **greenfield, no compromises** (see Purpose). There is no
feature flag, no compatibility shim, no parallel-old-path opt-out. Once
Phase 3 merges, the `PipelineObserver` API is gone — re-introducing it
would be a new feature, not a rollback.

**Policy**:

- Phases 1, 2, 4, 5 are individually `git revert`-able (the per-phase
  Roll-back plan in each phase file describes the scope).
- Phase 3 is **the point of no return**. After Phase 3 merges to `main`
  and subsequent commits land on top, rolling back means cherry-picking
  fixes forward, not reverting.
- If a critical bug emerges after Phase 3 merge, the fix is **forward only**:
  a new commit that addresses the bug. Reverting Phase 3 wholesale is
  explicitly NOT in scope.
- This design choice is acceptable because the bus's behavior is locked by
  the Phase 1 unit suite, the visual regression test (Phase 3), and the
  acceptance criteria smoke tests (Phase 5). A bug that escapes all three
  is fixable by additive change.

## Roadmap Alignment (non-engaging vision)

**No code is written in v1 for any of the use cases listed below.** This
section explains why the v1 design choices (single bus, JSON-serializable
events, boundary AppContext) are not over-engineered — they are the
minimum that doesn't paint roadmap items into a corner. Reviewers should
NOT request features below to be implemented as part of this PR.

- **P2 Web Management UI**: `WebSocketSubscriber` will be implemented in
  the Web UI feature; it subscribes once with `bus.subscribe(Event, ws_fanout)`
  and forwards every event as JSON. v1 makes this trivial because events
  serialize natively.
- **P2 Watcher Service**: standalone process with its own AppContext.
  When the watcher triggers a pipeline run in-process, watcher and pipeline
  share the same `event_bus` instance → the watcher sees the pipeline's
  events. The cross-process bridge (for the daemon variant) consumes the
  JSON form of events.
- **P2 Auto-Download System**: adds `LibraryRecommendationListUpdated`,
  `TorrentSearchCompleted`, `DownloadCompleted` to the catalog when that
  feature lands. v1 adds no infrastructure for these; only the bus
  remains the same.
- **P1 Provider Registry**: `ProviderRegistered`, `ProviderSelected`,
  `ProviderFailedOver` join the catalog. Provider registry consumes
  `CircuitBreakerOpened` (already emitted in v1) to skip dead providers
  via one subscription, no new mechanism.
- **P3 DI Container**: `AppContext` is the seed. The DI feature formalizes
  its factory and a per-test variant. v1 introduces no DI framework.
- **P2 Verify Checker Plugin System**: each check plugin emits
  `CheckPassed` / `CheckFailed`. Web UI shows per-check progress in real
  time without a dedicated protocol.

## Testing strategy

- **`CollectingSubscriber[E]`** generic helper in `tests/fixtures/event_bus.py`.
  Subscribes to a given event type (or `Event` for all) and records every
  delivered event in a list ordered by arrival.
- **Per-step tests**: build a minimal `AppContext` with a collector, run the
  step against fixture inputs, assert on the collected events (count, order,
  payload fields).
- **Pipeline-level tests**: assert on the full event timeline (`PipelineStarted`
  → step starts/ends → `ItemProgressed × N` → `PipelineEnded`).
- **Error isolation test**: register a subscriber that always raises;
  emit; assert other subscribers received the event AND a WARNING
  `event_emit_failed` log was emitted with the right `subscriber=` /
  `event_type=` / `event_id=` fields.
- **Re-entrant emit test**: subscriber emits during its handler; assert the
  second event reaches its subscribers and no recursion bug occurs (depth
  bounded by the test's max emit chain).
- **Fast-path test**: emit without any subscribers; assert no allocation
  beyond the event itself (measured via a `tracemalloc` snapshot diff
  ≤ epsilon, or via instrumenting the dispatch path with a counter).
- **Event sample factories** (`tests/fixtures/event_samples.py`): for
  every concrete event in `personalscraper.events`, a factory function
  `make_<event_name>()` returns a realistic instance with all payload
  fields populated with canonical values. `PipelineReport`, `StepReport`,
  and other rich payloads are constructed with non-empty, type-correct
  data — **never `MagicMock`**, since the goal is to exercise the
  serialization path against real shapes. A registry
  `EVENT_SAMPLE_FACTORIES: dict[type[Event], Callable[[], Event]]` is
  populated by import-side decoration; adding a new event to the
  catalog without registering a factory triggers a unit test failure
  (`test_every_event_has_factory`).
- **JSON round-trip test**: parametrized over every concrete event via
  the sample factories. For each sample: `event_to_envelope(e)` →
  `json.dumps` → `json.loads` → `event_from_envelope(d)` → assert
  reconstructed event matches original. The assertion is **field-by-field**
  (not `==`): every field except `timestamp` MUST be exactly equal;
  `timestamp` MUST satisfy
  `abs((reconstructed.timestamp - original.timestamp).total_seconds()) <= 1e-6`
  (1 µs tolerance, accommodating ISO-8601 microsecond rounding). A helper
  `assert_event_round_trip(original, reconstructed)` lives in
  `tests/fixtures/event_bus.py` and implements this contract once for
  every test that needs it. `__eq__` on the dataclass is NOT used because
  it compares all fields including `timestamp` strictly. This is the gate
  that catches non-serializable payloads at PR time.
- **Snapshot determinism for `RichConsoleSubscriber`**: the visual
  regression test constructs Rich Console with forced parameters —
  `Console(width=120, color_system=None, force_terminal=False,
file=StringIO(), record=True)` — and compares the recorded text
  output. Without this setup terminal width/color detection makes the
  snapshot non-portable across dev/CI environments.
- **MRO resolution cache test**: emit the same event type twice; assert
  the second emit uses the cached subscriber tuple (verified via internal
  counter or by patching the MRO walk).
- **`AppContext` boundary test** (`tests/architecture/test_app_context_boundary.py`):
  **AST-based, NOT grep-based** — grep would false-positive on imports,
  type aliases, docstrings, and comments. The test parses every `.py`
  file under `personalscraper/`, walks `ast.FunctionDef` and
  `ast.AsyncFunctionDef` nodes, and inspects each parameter annotation
  via `ast.unparse`. If any parameter is annotated as `AppContext` (or
  `"AppContext"` forward-ref) in a module not on the allowlist, the
  test fails. Allowlist (each entry is a precise (module, qualified-name)
  pair, not the whole file — paths match the real codebase post arch-cleanup):
  - `personalscraper/cli.py` → `main` (Typer app entrypoint — minimal touch; the real Pipeline construction lives in `commands/pipeline.py` after the `arch-cleanup` refactor)
  - `personalscraper/cli_helpers.py` → `_build_app_context` (centralized AppContext factory shared by every CLI entry)
  - `personalscraper/commands/pipeline.py` → `run`
  - `personalscraper/commands/library/scan.py` → `library_index`
  - `personalscraper/trailers/cli.py` → `scan`, `download`, `verify`, `purge`
  - `personalscraper/pipeline.py` → `Pipeline.__init__`
  - `personalscraper/core/app_context.py` → factories (module-level allow)
  - `tests/fixtures/**` → fixtures may construct `AppContext` freely
    Any new boundary site MUST be added to the allowlist consciously
    (the diff review-gates the new authorization). ≤ 100 LOC (uplift
    from earlier 80 budget; see Module size budget table), robust,
    future-proof. The plan's Phase 2.6 implements this as two structures:
    `APP_CONTEXT_ALLOWED_MODULES` (module-level allow) +
    `APP_CONTEXT_ALLOWED_FUNCS` (per-(module, qualified-name) allow),
    with the AST walker computing class-method qualified names via
    `ast.NodeVisitor`.
- **Pipeline-obs test migration**: every test under `tests/` that
  references `PipelineObserver`, `CollectorObserver`, `notify_progress`,
  `StepEvent`, or `personalscraper.observers` is rewritten to use
  `EventBus` + `CollectingSubscriber`. Phase 3 gate: zero matches for
  `from personalscraper.observers` and `notify_progress(` across the
  entire repo.

## Module size budget

| Module                                               | LOC cible                                                                                                                          |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `core/event_bus.py`                                  | ≤ 400                                                                                                                              |
| `core/app_context.py`                                | ≤ 80                                                                                                                               |
| `pipeline_events.py`                                 | ≤ 150                                                                                                                              |
| `dispatch/events.py`                                 | ≤ 50                                                                                                                               |
| `core/circuit.py` (events embedded, existing module) | ≤ 350 total (vs. 216 today + ~50 for events + emit calls)                                                                          |
| `indexer/events.py`                                  | ≤ 60                                                                                                                               |
| `trailers/events.py`                                 | ≤ 30                                                                                                                               |
| `events/__init__.py` (re-exports + registry)         | ≤ 100                                                                                                                              |
| `subscribers/rich_console.py`                        | ≤ 200 (current `observers/rich_console.py` 174 LOC; rewrite targets ~180 LOC with bus-subscription scaffolding)                    |
| `subscribers/telegram.py`                            | ≤ 200 (today: 54 LOC; +pipeline handlers in Phase 3 ≈ 100; +circuit/disk in Phase 4 ≈ 150)                                         |
| `subscribers/debug_log.py`                           | ≤ 40                                                                                                                               |
| `tests/fixtures/event_bus.py`                        | ≤ 80                                                                                                                               |
| `tests/fixtures/event_samples.py`                    | ≤ 150                                                                                                                              |
| `tests/architecture/test_app_context_boundary.py`    | ≤ 100 (uplift from 80 — accommodates the qualified-name walker that builds class-method names via `ast.NodeVisitor` per Phase 2.6) |

These budgets are TIGHTER than the project-wide soft warning (800 LOC) /
hard ceiling (1000 LOC) from `scripts/check-module-size.py` — they are
self-imposed feature-local discipline. The project rule still applies on
top and is enforced by `make check`. New code budget: ~1000 LOC. Removed:
180 LOC (`pipeline_observer.py`) + mechanical adjustments across ~10 step
files. Net delta: ~+820 LOC.

## Performance notes

- **MRO resolution cache**: dict `type → tuple[SubscriptionToken, ...]`
  invalidated on `subscribe`/`unsubscribe`. First emit per type walks MRO;
  subsequent emits reuse the cache. Cache size bounded by the number of
  distinct concrete event types ever emitted (~13 in v1 catalog).
- **Subscriber tuple copy-on-write**: `_subscribers[type]` stored as
  `tuple[(token, callback), ...]`. `subscribe` rebuilds the tuple
  (O(n) but rare); `emit` iterates over the immutable tuple directly
  without allocation per emit.
- **`ItemProgressed` hot path**: with the cache + immutable tuple, emit
  without subscribers is a single dict lookup (`O(1)`) returning empty
  tuple. With subscribers, it's the cached tuple iteration + try/except
  per subscriber. Negligible vs. the actual step work.

## Phase outline (informational — actual phase plan lives in plan/INDEX.md)

1. **Phase 1 — Foundation (standalone)**: `EventBus` + `Event` base +
   `SubscriptionToken` + `event_to_dict` + `event_to_envelope` +
   `event_from_envelope` + `current_correlation_id` ContextVar + MRO
   cache + COW subscriber tuples + event sample factories registry.
   Full unit test suite: dispatch, error isolation, re-entrant emit,
   fast path, MRO cache, ContextVar capture at event construction
   (in-bound region → run_id captured; out-of-bound → `None`; explicit
   `correlation_id=` arg overrides default_factory; `emit` is verified
   to NOT mutate `correlation_id`), envelope round-trip via factory
   registry. Zero pipeline integration. Gate: `make check` green, all
   bus tests green, module ≤ 400 LOC.
2. **Phase 2 — AppContext + StepContext slim**: introduce `AppContext`;
   refactor CLI entry to build it; refactor `StepContext` to gain
   `app: AppContext` + `run_id: UUID` and drop `config`/`settings`
   (accessed via `ctx.app.config`/`ctx.app.settings`).
   **`observers` field is KEPT on `StepContext` in Phase 2** — it is
   removed in Phase 3 along with the `PipelineObserver` API; Phase 2
   keeps `notify_progress(ctx.observers, ...)` wiring intact so the
   pipeline still emits user-visible output through the legacy path
   while the new context shape lands. No event emit on the bus yet —
   pipeline visual behavior unchanged. Gate: full test suite passes
   against new context shape; `RichConsoleObserver` and
   `TelegramObserver` still wired through `ctx.observers`.
3. **Phase 3 — Pipeline event migration + subscribers rewrite**: define
   `pipeline_events.py`; pipeline steps emit (`PipelineStarted/Ended`,
   `Step*`, `ItemProgressed`); remove `PipelineObserver`, `notify_progress`,
   `StepContext.observers`, `observers/` package; rewrite
   `RichConsoleSubscriber` + `TelegramSubscriber`; migrate every test
   in `tests/` that references the old observer API. **Sweep grep**:
   `from personalscraper.observers`, `PipelineObserver`,
   `notify_progress(`, `StepEvent(` → zero matches at gate.
   **Structlog dedup audit**: every emit site has at most one
   structlog call carrying info distinct from the event.
4. **Phase 4 — Cross-cutting events (one commit per integration)**:
   CircuitBreaker (`event_bus: EventBus | None`), DiskGuard, Dispatch,
   Trailers, Indexer scan. Each integration is one focused commit with
   focused tests. **Phase 4 stays additive only** — each commit makes
   one component start emitting without touching contracts elsewhere.
   The `| None` on CircuitBreaker (and any other temporarily-optional
   `event_bus` parameter introduced here) is the price of that
   additive property and is paid off in Phase 5.
5. **Phase 5 — Required-bus tightening + CLI polish**: separated from
   Phase 4 deliberately to keep each Phase 4 commit reviewable as a
   pure additive integration. Phase 5 tightens contracts and lands
   the cross-cutting consumer in one pass. Tasks: remove `| None`
   from `CircuitBreaker.__init__(event_bus=...)` and any other Phase 4
   call site; audit
   `rg --type py 'CircuitBreaker\(' personalscraper/ tests/`
   shows zero call sites without `event_bus`. Implement
   `DebugLogSubscriber`, wire `--verbose` to register it. Final
   documentation pass (`docs/reference/event-bus.md`).

## pipeline-obs → event-bus mapping

The Pipeline Observer Protocol (`pipeline-obs`, commit `a890d70`) shipped
two days before this design. To prevent regressions during the rewrite,
every behavioral property of pipeline-obs maps explicitly to its event-bus
equivalent:

| pipeline-obs behavior                                                | event-bus equivalent                                                                    |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `PipelineObserver` Protocol (subclass and override callbacks)        | Subscribe a callable to one or more `Event` types via `bus.subscribe(EventType, cb)`    |
| `notify_progress(observers, StepEvent(...))` fan-out                 | `bus.emit(ItemProgressed(...))`                                                         |
| `StepEvent(step, item, status, details)`                             | `ItemProgressed(step, item, status, details)` (renamed; payload identical)              |
| `CollectorObserver` test helper                                      | `CollectingSubscriber[E]` generic, exported from `tests/fixtures/event_bus.py`          |
| `RichConsoleObserver` console rendering                              | `RichConsoleSubscriber` — bytes-identical output, verified by Phase 3 snapshot test     |
| `TelegramObserver` PipelineEnded + StepErrored alerts                | `TelegramSubscriber` — same alerts plus `CircuitBreakerOpened` + `DiskFullWarning`      |
| Observer error isolation (one observer failing did not break others) | Bus-level `try/except` per subscriber + WARNING log `event_emit_failed` (same behavior) |
| Headless mode (no observers registered = silent run)                 | Fast path: empty `_subscribers` dict → `emit` returns immediately (same behavior)       |
| Snapshot tests of Rich Console output                                | Same snapshot tests, retargeted at `RichConsoleSubscriber`; baseline file untouched     |
| Per-observer lifecycle (`__init__`, optional teardown)               | Subscriber's `__init__` calls `bus.subscribe(...)` storing tokens; optional `close()`   |

If any pipeline-obs behavior not listed above surfaces during Phase 3 as a
regression, that is a Phase 3 bug — land a regression test + fix in the
same sub-phase per Invariant 5.

## Open Questions (to resolve in plan or implementation)

1. **Location of the `_disk_guard.py` extraction**: P3 roadmap proposes
   moving disk-full check out of `indexer/db.py` (today at
   `indexer/db.py::handle_disk_full`). event-bus does the move if not
   already done (depends on phasing of P3 god-module-split). If P3 hasn't
   landed, event-bus extracts it as a sub-task of Phase 4.2a — the
   `DiskFullWarning` emit needs a clean call site.
2. **`run_id` propagation across launchd / standalone commands**: how does
   the launchd scan correlate its events? Decision: each AppContext build
   site generates its own `run_id` (CLI run, launchd scan, trailers
   command) — there is no cross-process correlation in v1. Cross-process
   correlation is a Watcher Service v2 concern.
3. **WebSocketSubscriber prototype**: out of scope, but worth a 10-minute
   spike at end of Phase 5 to confirm the v1 design suffices. NOT in the
   committed plan.

## Acceptance criteria

A PR for this feature is mergeable when:

- All five phases gate-green (`make check`, full test suite, module-size
  budget).
- `rg --type py 'PipelineObserver|notify_progress|StepEvent|from personalscraper\.observers' personalscraper/ tests/`
  returns zero matches (the old API is fully gone). Use `rg --type py`,
  NEVER bare `grep -r` — the latter would scan `tests/e2e/perf/.fixture/`
  (14 GB) and crash the machine per CLAUDE.md "Search Safety".
- Every concrete event in `personalscraper.events` has a factory in
  `tests/fixtures/event_samples.py` (enforced by
  `test_every_event_has_factory`) and passes the envelope round-trip
  test (`event_to_envelope` → JSON → `event_from_envelope` →
  equality).
- The `AppContext` boundary AST test
  (`tests/architecture/test_app_context_boundary.py`) passes — no
  internal module takes `AppContext` in its signature outside the
  documented allowlist.
- `RichConsoleSubscriber` produces visually identical output to the
  removed `RichConsoleObserver` on the canonical pipeline-run snapshot
  test. **Determinism setup mandatory**: the test constructs
  `Console(width=120, color_system=None, force_terminal=False,
file=StringIO(), record=True)` and compares the recorded text
  output; without this setup terminal width/color detection makes the
  snapshot non-portable across dev/CI.
- `TelegramSubscriber` alerts on `PipelineEnded`, `StepErrored`,
  `CircuitBreakerOpened`, `DiskFullWarning` (manual smoke test with a
  staging Telegram channel — documented in PR description).
- `personalscraper run --verbose` produces a structured event log of the
  whole run via `DebugLogSubscriber`.
- `docs/reference/event-bus.md` documents the API, the event catalog,
  the boundary-only AppContext rule, the `current_correlation_id`
  ContextVar convention, and the JSON serialization contract
  (`event_to_dict` vs `event_to_envelope`).
