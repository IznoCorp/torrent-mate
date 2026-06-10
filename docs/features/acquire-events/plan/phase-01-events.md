# Phase 1 — Event catalog, hub registration, factories, round-trip tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define 10 acquisition event classes in `personalscraper/acquire/events.py`,
register them via eager-import in `personalscraper/events/__init__.py`, add one real-data
factory per event in `tests/fixtures/event_samples.py`, prove nested-`MediaRef`
serialization works (DESIGN §3.1), and pass a TRUE envelope round-trip equality test for
each event.

**Architecture:** Each event is a `@dataclass(frozen=True, kw_only=True)` subclass of
`personalscraper.core.event_bus.Event`. The hub `events/__init__.py` eager-imports
`acquire.events` and re-exports all 10 names so `event_from_envelope` resolves them
cross-process. The existing `_decode_field_value` in `core/event_bus.py` already handles
nested dataclasses (the `issubclass(annotation, …dataclass)` branch at line 105) — the
round-trip test proves this for `MediaRef` without any code change. If it does NOT
round-trip (e.g. `MediaRef` arrives as a plain `dict`), Task 3 adds the minimal hook.

**Tech Stack:** Python 3.10+ frozen dataclasses, `personalscraper.core.event_bus.Event`,
`personalscraper.core.identity.MediaRef`, `personalscraper.acquire.domain` VOs,
`tests/fixtures/event_samples.py::register_factory`.

---

## Gate (start of phase)

Previous phase: none (this is Phase 1).
Precondition: `feat/acquire-events` branch checked out; `make check` is green at HEAD.

---

## File map

| Action | File                                      | Responsibility                             |
| ------ | ----------------------------------------- | ------------------------------------------ |
| Create | `personalscraper/acquire/events.py`       | 10 frozen Event subclasses                 |
| Modify | `personalscraper/events/__init__.py`      | eager-import + re-export acquire events    |
| Modify | `tests/event_bus/test_pipeline_events.py` | count-pin 23 → 33 + prose bump             |
| Modify | `tests/fixtures/event_samples.py`         | 10 `@register_factory` real-data factories |
| Create | `tests/acquire/test_acquire_events.py`    | round-trip + registration tests per event  |

---

## Task 1.1 — Probe serialization for nested MediaRef (no commit)

Before writing any event, verify the serializer can already handle `MediaRef` as a
nested frozen dataclass in a round-trip.

**Files:** `personalscraper/core/event_bus.py` (read-only), `personalscraper/core/identity.py` (read-only)

- [ ] **Step 1.1.1 — Read the decode path**

  Open `personalscraper/core/event_bus.py` lines 99–108. Confirm the
  `_decode_field_value` function has the branch:

  ```python
  if isinstance(annotation, type):
      ...
      if dataclasses.is_dataclass(annotation):
          sub_hints = typing.get_type_hints(annotation)
          kw = {f.name: _decode_field_value(value[f.name], sub_hints[f.name]) for f in fields(annotation)}
          return annotation(**kw)
  ```

  If it does: `MediaRef` (a plain frozen dataclass with only `int | None` and `str | None`
  fields) will round-trip without modification. Record decision: **serializer sufficient**.

  If it does NOT: add the branch in Task 1.3 before writing the event classes.

- [ ] **Step 1.1.2 — Run a quick smoke proof**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  python -c "
  import json, dataclasses, typing
  from personalscraper.core.event_bus import event_to_envelope, event_from_envelope, Event
  from personalscraper.core.identity import MediaRef
  from dataclasses import dataclass

  @dataclass(frozen=True, kw_only=True)
  class _Probe(Event):
      media_ref: MediaRef

  r = MediaRef(tvdb_id=12345)
  e1 = _Probe(media_ref=r)
  env = event_to_envelope(e1)
  # _Probe is test-local; patch registry for this probe
  from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
  _EVENT_CLASS_REGISTRY['_Probe'] = _Probe
  e2 = event_from_envelope(json.loads(json.dumps(env)))
  assert e2.media_ref == r, f'FAIL: {e2.media_ref!r} != {r!r}'
  print('MediaRef round-trip: OK')
  "
  ```

  Expected output: `MediaRef round-trip: OK`

  If the probe fails (e.g. `AssertionError` — `e2.media_ref` is a `dict`), the
  decode branch is missing. Proceed to Task 1.3 to add it before continuing.

---

## Task 1.2 — Create `personalscraper/acquire/events.py`

**Files:**

- Create: `personalscraper/acquire/events.py`

- [ ] **Step 1.2.1 — Write the failing test first**

  Create `tests/acquire/test_acquire_events.py` with a skeleton import test that
  fails because `acquire/events.py` does not exist yet:

  ```python
  # tests/acquire/test_acquire_events.py
  """Smoke tests for the acquire event catalog (Phase 1 gate)."""
  from __future__ import annotations

  import dataclasses
  import json

  import pytest

  import personalscraper.events  # noqa: F401 — eager-import side effect
  from personalscraper.acquire.events import (
      GrabFailed,
      GrabSucceeded,
      RatioMeasured,
      SeedObligationBreached,
      SeedObligationRecorded,
      SeedObligationSatisfied,
      SeriesFollowed,
      SeriesUnfollowed,
      WantedAbandoned,
      WantedEnqueued,
  )
  from personalscraper.core.event_bus import (
      Event,
      _EVENT_CLASS_REGISTRY,
      event_from_envelope,
      event_to_envelope,
  )
  from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

  ACQUIRE_EVENT_CLASSES: tuple[type[Event], ...] = (
      SeriesFollowed,
      SeriesUnfollowed,
      WantedEnqueued,
      WantedAbandoned,
      GrabSucceeded,
      GrabFailed,
      SeedObligationRecorded,
      SeedObligationBreached,
      SeedObligationSatisfied,
      RatioMeasured,
  )


  @pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
  def test_acquire_events_inherit_event_base(cls: type[Event]) -> None:
      """Every acquire event inherits from Event."""
      assert issubclass(cls, Event)


  @pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
  def test_acquire_events_are_frozen(cls: type[Event]) -> None:
      """Every acquire event is a frozen dataclass."""
      assert dataclasses.is_dataclass(cls)
      instance = EVENT_SAMPLE_FACTORIES[cls]()
      with pytest.raises(dataclasses.FrozenInstanceError):
          instance.source = "mutated"  # type: ignore[misc]


  @pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
  def test_acquire_events_auto_registered(cls: type[Event]) -> None:
      """Each acquire event class name appears in _EVENT_CLASS_REGISTRY."""
      assert _EVENT_CLASS_REGISTRY.get(cls.__name__) is cls


  @pytest.mark.parametrize("cls", ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
  def test_acquire_events_envelope_roundtrip(cls: type[Event]) -> None:
      """Envelope round-trip preserves equality for every acquire event (incl. MediaRef)."""
      e1 = EVENT_SAMPLE_FACTORIES[cls]()
      envelope = event_to_envelope(e1)
      e2 = event_from_envelope(json.loads(json.dumps(envelope)))
      assert e2 == e1, f"Round-trip failed for {cls.__name__}: {e2!r} != {e1!r}"
  ```

- [ ] **Step 1.2.2 — Run to confirm ImportError**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/acquire/test_acquire_events.py -x --tb=short 2>&1 | head -30
  ```

  Expected: `ImportError: cannot import name 'SeriesFollowed' from 'personalscraper.acquire.events'`
  (or ModuleNotFoundError if the file does not exist yet).

- [ ] **Step 1.2.3 — Write `personalscraper/acquire/events.py`**

  ```python
  # personalscraper/acquire/events.py
  """Acquisition event catalog (RP4).

  Defines the 10 typed events emitted by the acquisition lobe. All classes are
  frozen kw_only dataclasses over :class:`~personalscraper.core.event_bus.Event`.
  Payload fields mirror the already-persisted
  :mod:`personalscraper.acquire.domain` value objects so shapes are determined
  by shipped data, not speculation (DESIGN §3).

  Import direction: imports ``core.event_bus``, ``core.identity``, and stdlib
  only — no ``indexer``, ``scraper``, or triage imports (acquire/ layering rule).

  Producers arrive in waves 4–5 (Follow D1–D3, Ratio C1, Seed-Safety O2,
  Watcher). RP4 defines the shapes; events stay unused until then.
  """

  from __future__ import annotations

  from dataclasses import dataclass
  from typing import Literal

  from personalscraper.core.event_bus import Event
  from personalscraper.core.identity import MediaRef


  @dataclass(frozen=True, kw_only=True)
  class SeriesFollowed(Event):
      """A TV series or movie was added to the follow list.

      Emitted by Follow D1 when the user subscribes to a series.

      Attributes:
          media_ref: Provider-ID key (tvdb_id primary).
          title: Human-readable title for logging/display.
      """

      media_ref: MediaRef
      title: str


  @dataclass(frozen=True, kw_only=True)
  class SeriesUnfollowed(Event):
      """A TV series or movie was removed from the follow list.

      Emitted by Follow D1 when the user unsubscribes from a series.

      Attributes:
          media_ref: Provider-ID key (tvdb_id primary).
      """

      media_ref: MediaRef


  @dataclass(frozen=True, kw_only=True)
  class WantedEnqueued(Event):
      """A specific episode or movie was added to the wanted queue.

      Emitted by Follow D2 when a new episode/movie is queued for acquisition.

      Attributes:
          media_ref: Provider-ID key (tvdb_id primary).
          kind: ``"movie"`` or ``"episode"``.
          season: Season number (episodes only; ``None`` for movies).
          episode: Episode number (episodes only; ``None`` for movies).
      """

      media_ref: MediaRef
      kind: Literal["movie", "episode"]
      season: int | None
      episode: int | None


  @dataclass(frozen=True, kw_only=True)
  class WantedAbandoned(Event):
      """A wanted item was abandoned (e.g. cutoff reached, no source found).

      Emitted by Follow D2 when an item leaves the queue without being grabbed.

      Attributes:
          media_ref: Provider-ID key (tvdb_id primary).
          reason: Human-readable abandonment reason.
      """

      media_ref: MediaRef
      reason: str


  @dataclass(frozen=True, kw_only=True)
  class GrabSucceeded(Event):
      """A torrent was successfully grabbed from a tracker.

      Emitted by RP5b (Follow D3 + Ratio C1) after a successful grab POST.

      Attributes:
          media_ref: Provider-ID key; ``None`` when the grab is unbound to a
              specific media item (e.g. manual grab or freeleech sweep).
          info_hash: Torrent info-hash (hex string).
          source_tracker: Tracker name (e.g. ``"lacale"``).
          category: Category ID string (``None`` if unknown at grab time).
          tags: Ordered tuple of tracker-assigned tags.
      """

      media_ref: MediaRef | None
      info_hash: str
      source_tracker: str
      category: str | None
      tags: tuple[str, ...]


  @dataclass(frozen=True, kw_only=True)
  class GrabFailed(Event):
      """A torrent grab attempt failed.

      Emitted by RP5b on any grab failure (network, parse, no results, etc.).

      Attributes:
          media_ref: Provider-ID key; ``None`` when unbound to a specific item.
          source_tracker: Tracker name; ``None`` when failure is pre-selection.
          reason: Human-readable failure reason.
      """

      media_ref: MediaRef | None
      source_tracker: str | None
      reason: str


  @dataclass(frozen=True, kw_only=True)
  class SeedObligationRecorded(Event):
      """A seed obligation was created when a dispatched payload is registered.

      Emitted by the dispatch step / O2 when a new ``SeedObligation`` row is
      inserted (e.g. after a successful real dispatch with ``action != "dry_run"``).

      Attributes:
          info_hash: Torrent info-hash (hex string).
          source_tracker: Tracker name (e.g. ``"lacale"``).
          min_seed_time_s: Minimum seed time in seconds (snapshot from economy config).
          dispatched_path: Absolute path of the dispatched media; ``None`` until move.
      """

      info_hash: str
      source_tracker: str
      min_seed_time_s: int
      dispatched_path: str | None


  @dataclass(frozen=True, kw_only=True)
  class SeedObligationBreached(Event):
      """A seed obligation was breached (seeding stopped before min_seed_time).

      Emitted by O2 when ``acquire.hnr_risk`` structlog warning would fire
      today (this event is the typed equivalent that supervisors subscribe to).

      Attributes:
          info_hash: Torrent info-hash (hex string).
          source_tracker: Tracker name (e.g. ``"lacale"``).
          dispatched_path: Absolute path of the dispatched media; ``None`` if unset.
      """

      info_hash: str
      source_tracker: str
      dispatched_path: str | None


  @dataclass(frozen=True, kw_only=True)
  class SeedObligationSatisfied(Event):
      """A seed obligation was satisfied (seeding completed successfully).

      Emitted by O2 when the obligation's min_seed_time_s has elapsed.

      Attributes:
          info_hash: Torrent info-hash (hex string).
          source_tracker: Tracker name (e.g. ``"lacale"``).
      """

      info_hash: str
      source_tracker: str


  @dataclass(frozen=True, kw_only=True)
  class RatioMeasured(Event):
      """A tracker ratio measurement was recorded.

      Emitted by Ratio C1 after each ratio poll cycle.

      Attributes:
          tracker: Tracker identifier string (e.g. ``"lacale"``).
          observed_ratio: Latest measured upload/download ratio.
          target_ratio: Configured minimum ratio threshold.
      """

      tracker: str
      observed_ratio: float
      target_ratio: float


  __all__ = [
      "GrabFailed",
      "GrabSucceeded",
      "RatioMeasured",
      "SeedObligationBreached",
      "SeedObligationRecorded",
      "SeedObligationSatisfied",
      "SeriesFollowed",
      "SeriesUnfollowed",
      "WantedAbandoned",
      "WantedEnqueued",
  ]
  ```

- [ ] **Step 1.2.4 — Run the import test to confirm the module loads**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/acquire/test_acquire_events.py::test_acquire_events_inherit_event_base -x --tb=short
  ```

  Expected: tests PASS (or SKIP if `EVENT_SAMPLE_FACTORIES` doesn't have the keys yet —
  that is expected; factories come in Task 1.4).

---

## Task 1.3 — (Conditional) Fix nested-dataclass decode if probe failed

**Only execute if Step 1.1.2 produced an AssertionError.**

**Files:**

- Modify: `personalscraper/core/event_bus.py` — `_decode_field_value` function

- [ ] **Step 1.3.1 — Confirm the missing branch**

  The probe will fail if `_decode_field_value` does NOT have the nested-dataclass
  branch. Check around line 99 of `personalscraper/core/event_bus.py`:

  ```python
  # Missing branch would mean this block does NOT exist:
  if isinstance(annotation, type):
      if dataclasses.is_dataclass(annotation):
          sub_hints = typing.get_type_hints(annotation)
          kw = {f.name: _decode_field_value(value[f.name], sub_hints[f.name])
                for f in fields(annotation)}
          return annotation(**kw)
  ```

- [ ] **Step 1.3.2 — Write a failing test**

  Add to `tests/event_bus/test_serialization_envelope.py`:

  ```python
  def test_nested_dataclass_roundtrip() -> None:
      """Nested frozen dataclass field survives event_to_envelope / event_from_envelope."""
      import json, dataclasses, typing
      from personalscraper.core.event_bus import (
          event_to_envelope, event_from_envelope, Event, _EVENT_CLASS_REGISTRY
      )
      from personalscraper.core.identity import MediaRef
      from dataclasses import dataclass

      @dataclass(frozen=True, kw_only=True)
      class _NestedProbe(Event):
          ref: MediaRef

      _EVENT_CLASS_REGISTRY["_NestedProbe"] = _NestedProbe
      try:
          r = MediaRef(tvdb_id=99)
          e1 = _NestedProbe(ref=r)
          env = event_to_envelope(e1)
          e2 = event_from_envelope(json.loads(json.dumps(env)))
          assert e2.ref == r
      finally:
          _EVENT_CLASS_REGISTRY.pop("_NestedProbe", None)
  ```

  Run it: `pytest tests/event_bus/test_serialization_envelope.py::test_nested_dataclass_roundtrip -x --tb=short`

  Expected if branch is missing: `AssertionError` (e2.ref is a dict, not MediaRef).

- [ ] **Step 1.3.3 — The decode branch likely already exists (verified in 1.1)**

  If the branch already exists at `core/event_bus.py` lines 99–108, skip this task
  entirely. No code change needed.

  If truly missing: add the branch inside `_decode_field_value` after the `Enum` check:

  ```python
  if isinstance(annotation, type):
      if issubclass(annotation, PurePath):
          return Path(value)
      if issubclass(annotation, Enum):
          return annotation(value)
      if dataclasses.is_dataclass(annotation):
          sub_hints = typing.get_type_hints(annotation)
          kw = {f.name: _decode_field_value(value[f.name], sub_hints[f.name])
                for f in fields(annotation)}
          return annotation(**kw)
  ```

- [ ] **Step 1.3.4 — Rerun the probe test**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/event_bus/test_serialization_envelope.py::test_nested_dataclass_roundtrip -x --tb=short
  ```

  Expected: PASS.

---

## Task 1.4 — Add 10 real-data factories to `tests/fixtures/event_samples.py`

**Files:**

- Modify: `tests/fixtures/event_samples.py` — append 10 `@register_factory` blocks

- [ ] **Step 1.4.1 — Write failing test for missing factories**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/event_bus/test_pipeline_events.py::test_every_event_has_factory -x --tb=short 2>&1 | tail -15
  ```

  Expected: FAIL — after Task 1.2, 10 new events are in the registry but have no
  factories yet. The error message lists the missing class names.

- [ ] **Step 1.4.2 — Append factories to `tests/fixtures/event_samples.py`**

  Add the following block at the end of the file, after the existing registry-events section:

  ```python
  # ---------------------------------------------------------------------------
  # acquire-events feature (RP4) — 10 acquisition event factories
  # ---------------------------------------------------------------------------

  from personalscraper.acquire.events import (  # noqa: E402, PLC0415
      GrabFailed,
      GrabSucceeded,
      RatioMeasured,
      SeedObligationBreached,
      SeedObligationRecorded,
      SeedObligationSatisfied,
      SeriesFollowed,
      SeriesUnfollowed,
      WantedAbandoned,
      WantedEnqueued,
  )
  from personalscraper.core.identity import MediaRef  # noqa: E402, PLC0415

  _BREAKING_BAD_REF = MediaRef(tvdb_id=81189, tmdb_id=1396, imdb_id="tt0903747")
  _INCEPTION_REF = MediaRef(tvdb_id=None, tmdb_id=27205, imdb_id="tt1375666")


  @register_factory(SeriesFollowed)
  def make_series_followed() -> SeriesFollowed:
      """Realistic SeriesFollowed factory — Breaking Bad."""
      return SeriesFollowed(media_ref=_BREAKING_BAD_REF, title="Breaking Bad")


  @register_factory(SeriesUnfollowed)
  def make_series_unfollowed() -> SeriesUnfollowed:
      """Realistic SeriesUnfollowed factory — Breaking Bad."""
      return SeriesUnfollowed(media_ref=_BREAKING_BAD_REF)


  @register_factory(WantedEnqueued)
  def make_wanted_enqueued() -> WantedEnqueued:
      """Realistic WantedEnqueued factory — Breaking Bad S05E01."""
      return WantedEnqueued(
          media_ref=_BREAKING_BAD_REF,
          kind="episode",
          season=5,
          episode=1,
      )


  @register_factory(WantedAbandoned)
  def make_wanted_abandoned() -> WantedAbandoned:
      """Realistic WantedAbandoned factory — Inception movie."""
      return WantedAbandoned(
          media_ref=_INCEPTION_REF,
          reason="cutoff_reached",
      )


  @register_factory(GrabSucceeded)
  def make_grab_succeeded() -> GrabSucceeded:
      """Realistic GrabSucceeded factory — lacale grab with tags."""
      return GrabSucceeded(
          media_ref=_BREAKING_BAD_REF,
          info_hash="a" * 40,
          source_tracker="lacale",
          category="tv_shows",
          tags=("freeleech", "hd"),
      )


  @register_factory(GrabFailed)
  def make_grab_failed() -> GrabFailed:
      """Realistic GrabFailed factory — network failure, no tracker resolved."""
      return GrabFailed(
          media_ref=None,
          source_tracker="lacale",
          reason="ConnectionError: Max retries exceeded",
      )


  @register_factory(SeedObligationRecorded)
  def make_seed_obligation_recorded() -> SeedObligationRecorded:
      """Realistic SeedObligationRecorded factory."""
      return SeedObligationRecorded(
          info_hash="b" * 40,
          source_tracker="lacale",
          min_seed_time_s=86400,
          dispatched_path="/Volumes/Disk1/TV Shows/Breaking Bad (2008)",
      )


  @register_factory(SeedObligationBreached)
  def make_seed_obligation_breached() -> SeedObligationBreached:
      """Realistic SeedObligationBreached factory."""
      return SeedObligationBreached(
          info_hash="b" * 40,
          source_tracker="lacale",
          dispatched_path="/Volumes/Disk1/TV Shows/Breaking Bad (2008)",
      )


  @register_factory(SeedObligationSatisfied)
  def make_seed_obligation_satisfied() -> SeedObligationSatisfied:
      """Realistic SeedObligationSatisfied factory."""
      return SeedObligationSatisfied(
          info_hash="b" * 40,
          source_tracker="lacale",
      )


  @register_factory(RatioMeasured)
  def make_ratio_measured() -> RatioMeasured:
      """Realistic RatioMeasured factory — lacale ratio below target."""
      return RatioMeasured(
          tracker="lacale",
          observed_ratio=0.87,
          target_ratio=1.0,
      )
  ```

- [ ] **Step 1.4.3 — Run the factory coverage test**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/event_bus/test_pipeline_events.py::test_every_event_has_factory -x --tb=short
  ```

  Expected: PASS (all 33 registered events now have factories).

---

## Task 1.5 — Update hub registration + count-pin

**Files:**

- Modify: `personalscraper/events/__init__.py`
- Modify: `tests/event_bus/test_pipeline_events.py` lines 109–130

- [ ] **Step 1.5.1 — Write the failing count test**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/event_bus/test_pipeline_events.py::test_event_registry_has_eighteen_v1_events -x --tb=short
  ```

  Expected at this point: PASS (still 23) — the acquire events registered, but
  without the eager-import in `events/__init__.py`, they only register if
  `acquire.events` is imported by some other path first.

  Now trigger the real failure by checking what happens with a cold import:

  ```bash
  python -c "
  import importlib, sys
  # Remove any cached module
  for k in list(sys.modules):
      if 'acquire' in k or 'personalscraper.events' in k:
          del sys.modules[k]
  import personalscraper.events
  from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
  print(len(_EVENT_CLASS_REGISTRY))
  "
  ```

  Expected if hub not yet updated: `23` — acquire events not loaded.
  This confirms the hub update is necessary.

- [ ] **Step 1.5.2 — Update `personalscraper/events/__init__.py`**

  Add the following import block after the existing `from personalscraper.verify …` line
  (keep alphabetical order within the eager-import section):

  ```python
  from personalscraper.acquire import events as _acquire_events  # noqa: F401
  from personalscraper.acquire.events import (
      GrabFailed,
      GrabSucceeded,
      RatioMeasured,
      SeedObligationBreached,
      SeedObligationRecorded,
      SeedObligationSatisfied,
      SeriesFollowed,
      SeriesUnfollowed,
      WantedAbandoned,
      WantedEnqueued,
  )
  ```

  Also extend `__all__` with the 10 new names (alphabetical insertion):

  ```python
  "GrabFailed",
  "GrabSucceeded",
  "RatioMeasured",
  "SeedObligationBreached",
  "SeedObligationRecorded",
  "SeedObligationSatisfied",
  "SeriesFollowed",
  "SeriesUnfollowed",
  "WantedAbandoned",
  "WantedEnqueued",
  ```

- [ ] **Step 1.5.3 — Update the count-pin in `tests/event_bus/test_pipeline_events.py`**

  In the function `test_event_registry_has_eighteen_v1_events` (line 109):

  Change:

  ```python
  assert len(_EVENT_CLASS_REGISTRY) == 23, (
      f"Expected 23 events (18 original + 5 registry), "
      f"found {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}"
  )
  ```

  To:

  ```python
  assert len(_EVENT_CLASS_REGISTRY) == 33, (
      f"Expected 33 events (23 existing + 10 acquire-events), "
      f"found {len(_EVENT_CLASS_REGISTRY)}: {sorted(_EVENT_CLASS_REGISTRY)}"
  )
  ```

  Also update the docstring of `test_event_registry_has_eighteen_v1_events` to document
  the RP4 bump:

  ```python
  def test_event_registry_has_eighteen_v1_events() -> None:
      """The catalog is pinned at 33 events.

      Previous history: Phase 5 → 13; provider-ids sub-phase 8.4 → 17;
      tech-debt 0.16.0 sub-phase 3.1 → 18; arch-cleanup-2 Phase 1.2 → 23
      (5 provider-registry events). RP4 acquire-events adds 10 acquisition
      events (SeriesFollowed, SeriesUnfollowed, WantedEnqueued, WantedAbandoned,
      GrabSucceeded, GrabFailed, SeedObligationRecorded, SeedObligationBreached,
      SeedObligationSatisfied, RatioMeasured) → 33.
      """
  ```

- [ ] **Step 1.5.4 — Run count-pin and round-trip tests**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/event_bus/test_pipeline_events.py tests/acquire/test_acquire_events.py -x --tb=short
  ```

  Expected: all PASS. In particular `test_acquire_events_envelope_roundtrip[SeriesFollowed]`
  and all 9 siblings must pass — this is the nested-`MediaRef` proof.

- [ ] **Step 1.5.5 — Run make check**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  make check 2>&1 | tail -20
  ```

  Expected: green (0 errors, 0 failures). If `make check` shows ruff/mypy issues,
  fix them before the commit.

- [ ] **Step 1.5.6 — Commit**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  git add \
    personalscraper/acquire/events.py \
    personalscraper/events/__init__.py \
    tests/acquire/test_acquire_events.py \
    tests/event_bus/test_pipeline_events.py \
    tests/fixtures/event_samples.py
  git commit -m "feat(acquire-events): add 10 acquisition events + hub registration + factories + round-trip tests"
  ```

  If the conditional Task 1.3 was executed, also stage `personalscraper/core/event_bus.py`
  and `tests/event_bus/test_serialization_envelope.py`.

---

## Phase 1 gate

Run the full suite to confirm the phase is complete:

```bash
cd /Users/izno/dev/PersonnalScaper
make check
python -c "import personalscraper.events; from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY; assert len(_EVENT_CLASS_REGISTRY)==33, len(_EVENT_CLASS_REGISTRY)"
echo "Phase 1 gate: OK"
```

Expected: `make check` green + `echo` prints `Phase 1 gate: OK`.
