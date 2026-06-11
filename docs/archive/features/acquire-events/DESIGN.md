# DESIGN — RP4: acquisition event catalog + muted Telegram subscriber

| Field                   | Value                                                                                                                                                       |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Codename (proposed)** | `acquire-events`                                                                                                                                            |
| **Roadmap item**        | RP4 (P1, Vague 2, parallèle)                                                                                                                                |
| **Type**                | minor                                                                                                                                                       |
| **Version bump**        | 0.26.0 → 0.27.0                                                                                                                                             |
| **Date**                | 2026-06-10                                                                                                                                                  |
| **Depends on**          | EventBus (shipped), Telegram notifier + subscriber template (shipped), `acquire/domain.py` VOs + `core/identity.MediaRef` (shipped via RP3 `acquire-store`) |
| **Builds toward**       | Follow D1–D3, Ratio C1, Seed-Safety O2, Watcher, Web UI S7, Telegram supervision                                                                            |

> The acquisition lobe is **EventBus-silent today** (RP3 `acquire-store` deliberately left
> the catalog to RP4 — see acquire-store DESIGN §7 non-goals + §9). RP4 defines the
> acquisition event catalog **once** (the "define-once foundations" discipline the ROADMAP
> applies from RP1), grounded in the domain value objects already shipped, so the producers
> arriving in waves 4–5 (Follow / Ratio / Seed-Safety / Watcher) emit a stable, pre-agreed
> set instead of re-scattering ad-hoc events (the "events épars" anti-pattern, ROADMAP line 473).

---

## 1. Problem & context

There are **zero acquisition events** today: the live event registry holds exactly 23 classes
(pipeline / dispatch / circuit / indexer / trailers / registry / verify), none for
Follow / Wanted / Grab / SeedObligation / Ratio (verified:
`len(personalscraper.core.event_bus._EVENT_CLASS_REGISTRY) == 23`). The acquisition store is
event-silent by design. Supervision surfaces — Telegram and the future Web UI S7
acquisition/watcher pages — have nothing to subscribe to.

RP4 closes this by defining the acquisition event catalog and a **muted** Telegram subscriber.
"Muted" = the subscriber is wired and tested but does **not** send Telegram messages until a
config flag is flipped in waves 4–5 (the producers that emit these events do not exist yet).

## 2. Goals / Non-goals

**Goals**

1. A single acquisition event catalog (`acquire/events.py`) of frozen `Event` subclasses,
   payloads **grounded in the shipped `acquire/domain.py` value objects** (low churn risk).
2. Eager-import registration in `personalscraper/events/__init__.py` (so
   `event_from_envelope` resolves them cross-process) + the catalog count-pin bump.
3. A muted Telegram subscriber (`subscribers/acquire.py`) — subscribes, formats, logs;
   sends only when a config flag is enabled (default off).
4. Non-vacuous verification: a real-data factory + a true envelope round-trip per event
   (the "dispatched code ships vacuous tests" memory applies — events with no emit sites must
   still be proven to register + serialize + reconstruct equal).

**Non-goals**

- ❌ Emitting the events. The producers (Follow D1–D3, Ratio C1, Seed-Safety O2, Watcher)
  ship in waves 4–5. RP4 defines the **shapes**; they emit muted until then.
- ❌ Activating Telegram notifications. The send path is built + gated; flipping it on is a
  wave-4/5 decision.
- ❌ Web UI S7 read-models (Vague 6). RP4 only provides the events S7 will consume.
- ❌ Freeleech-window (R1) and tracker-auth-failure (RP7) events — those carry
  feature-specific payloads best designed with their own features; out of scope here.
- ❌ New emit-site `event_bus`-required signatures — RP4 defines events, does not emit them,
  so no new required-bus call sites (the `test_event_bus_required_signatures` AST sweep is
  untouched).

## 3. The event catalog (10 events)

All in `personalscraper/acquire/events.py`, each `@dataclass(frozen=True, kw_only=True)` over
`personalscraper.core.event_bus.Event`, with a Google-style catalog docstring. Payload fields
mirror the **already-persisted** `acquire/domain.py` VOs + `core.identity.MediaRef`, so the
shapes are determined by shipped data, not speculation.

| Event                     | Payload                                                                                                                  | Models on                  | Future producer                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------ | -------------------------- | ------------------------------------------------------------------ |
| `SeriesFollowed`          | `media_ref: MediaRef`, `title: str`                                                                                      | `FollowedSeries`           | Follow D1                                                          |
| `SeriesUnfollowed`        | `media_ref: MediaRef`                                                                                                    | `FollowedSeries`           | Follow D1                                                          |
| `WantedEnqueued`          | `media_ref: MediaRef`, `kind: Literal["movie","episode"]`, `season: int \| None`, `episode: int \| None`                 | `WantedItem`               | Follow D2                                                          |
| `WantedAbandoned`         | `media_ref: MediaRef`, `reason: str`                                                                                     | `WantedItem`               | Follow D2 (cutoff)                                                 |
| `GrabSucceeded`           | `media_ref: MediaRef \| None`, `info_hash: str`, `source_tracker: str`, `category: str \| None`, `tags: tuple[str, ...]` | `TrackerResult` + RP1 add  | RP5b (Follow D3 + Ratio C1)                                        |
| `GrabFailed`              | `media_ref: MediaRef \| None`, `source_tracker: str \| None`, `reason: str`                                              | grab outcome               | RP5b                                                               |
| `SeedObligationRecorded`  | `info_hash: str`, `source_tracker: str`, `min_seed_time_s: int`, `dispatched_path: str \| None`                          | `SeedObligation`           | RP3 dispatch / O2                                                  |
| `SeedObligationBreached`  | `info_hash: str`, `source_tracker: str`, `dispatched_path: str \| None`                                                  | `SeedObligation`           | O2 (the event behind today's `acquire.hnr_risk` structlog warning) |
| `SeedObligationSatisfied` | `info_hash: str`, `source_tracker: str`                                                                                  | `SeedObligation`           | O2                                                                 |
| `RatioMeasured`           | `tracker: str`, `observed_ratio: float`, `target_ratio: float`                                                           | `RatioState` + RP2 economy | Ratio C1                                                           |

Catalog count: **23 → 33**.

### 3.1 Serialization risk (load-bearing — surfaced by the round-trip gate)

Existing events carry only simple types (`str`/`Path`/`int`/`Literal`). Several RP4 events
carry a **nested `MediaRef` dataclass**. The envelope round-trip
(`event_to_envelope` → `event_from_envelope` → equal instance) **must** survive a nested
frozen dataclass. Phase 1 verifies this; if the envelope serializer does not already handle a
nested dataclass, Phase 1 adds the minimal support (a `MediaRef` (de)serialization hook, OR —
fallback — events carry `media_ref` as the same `media_ref_json` string shape the store
persists, with a typed accessor). The non-vacuous round-trip test is what forces this to be
real, not assumed. **Decision recorded at implementation time, in the DESIGN, once the
serializer behavior is verified.**

## 4. Module placement & layering

- `personalscraper/acquire/events.py` imports `core.event_bus.Event` + `core.identity.MediaRef`
  (downward) — obeys the acquire/ layering guard (acquire/ → api/core/conf/events, never triage).
- `personalscraper/events/__init__.py` eager-imports `acquire.events` + re-exports the classes +
  `__all__`. This mirrors how the hub already imports `dispatch.events`, `indexer.events`,
  `trailers.events`, `verify.events` (the hub is the catalog aggregator; importing a lobe's
  events module is the established convention, not a layering violation — `events/` is not a
  guarded source layer for the acquire rule).
- The subscriber lives in `personalscraper/subscribers/acquire.py` (consumer layer, like
  `subscribers/telegram.py`).

## 5. Muted Telegram subscriber

`personalscraper/subscribers/acquire.py::AcquisitionTelegramSubscriber`:

- `__init__(self, bus: EventBus, notifier: TelegramNotifier | None = None, *, enabled: bool = False)`
  — self-registers one handler per acquisition event (mirrors `subscribers/telegram.py`).
- Each handler **formats a human-readable message** from the event + emits a structlog line
  (`acquire.notify.<event>`). If `enabled` → `notifier.send(message)` via the shipped
  fire-and-forget `_spawn` daemon-thread + fail-soft pattern; if not (the default, "muet") →
  no send. So the subscriber does real work (formats + logs) and is fully testable, but stays
  silent until activated.
- `enabled` is driven by a config flag (a new `acquire.notify_enabled: bool = False` or a
  reuse of an existing notifier-enable toggle — settled in Phase 2, smallest additive change;
  default **False**).
- Wired at the CLI boundary near `commands/pipeline.py` (where `subscribers/telegram.py` is
  wired today), guarded so it is a no-op when no notifier is configured.

## 6. Verification (anti-vacuous)

Per the recipe (`event-bus.md §Writing a new event`) and the memory rule:

1. **Factory per event** in `tests/fixtures/event_samples.py` via `@register_factory` with
   **real data** (no `MagicMock`) — `test_every_event_has_factory` enforces 100% coverage.
2. **Round-trip per event**: `event_to_envelope` then `event_from_envelope` reconstructs an
   **equal** instance — proves hub registration + serialization (incl. the nested `MediaRef`).
3. **Count-pin bump**: `tests/event_bus/test_pipeline_events.py` `== 23` → `== 33` in the same
   commit, + the prose/docstring (`test_event_registry_has_eighteen_v1_events` name + message).
4. **Subscriber dispatch test**: emit each event → assert the handler ran (message formatted +
   structlog line); with `enabled=True` + a mocked notifier → `notifier.send` called once;
   with `enabled=False` → never called. Fail-soft: a notifier error never propagates.
5. **Catalog docs**: append 10 rows to `docs/reference/event-bus.md §Event catalog` + the
   DESIGN; update `docs/reference/architecture.md` if it enumerates event domains.

## 7. Phase decomposition (for `/implement:plan`)

1. **`acquire/events.py` (10 events) + hub registration + count-pin bump + factories +
   round-trip tests** — including the nested-`MediaRef` serialization verification/fix (§3.1).
2. **`subscribers/acquire.py` muted subscriber + config flag + dispatch tests + CLI wiring.**
3. **Docs (`event-bus.md` catalog + architecture) + `ACCEPTANCE.md` + `make check` gate.**

## 8. ACCEPTANCE preview (executable criteria — finalized in ACCEPTANCE.md)

- `python -c "import personalscraper.events; from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY; assert len(_EVENT_CLASS_REGISTRY)==33"` → exit 0.
- A pytest selector proving every acquisition event round-trips through the envelope to an equal instance.
- A pytest selector proving the muted subscriber formats + logs but does NOT send when disabled, and sends once when enabled (mocked notifier).
- `make check` → green.

## 9. Open items explicitly deferred (not gaps)

- Emitting the events → the producers (Follow D1–D3, Ratio C1, Seed-Safety O2, Watcher).
- Activating Telegram acquisition notifications → wave-4/5 flag flip.
- Web UI S7 acquisition/watcher read-models → Vague 6.
- Freeleech-window (R1) + tracker-auth-failure (RP7) events → their own features.
