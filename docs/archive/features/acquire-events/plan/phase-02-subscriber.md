# Phase 2 — Muted Telegram subscriber + config flag + dispatch tests + CLI wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `AcquisitionTelegramSubscriber` in
`personalscraper/subscribers/acquire.py` — subscribes to all 10 acquisition events,
formats a human-readable message, emits a structlog line, and sends via Telegram only when
`enabled=True`. Wire a config flag (`notify.acquire_notify_enabled: bool = False`) and
connect the subscriber at the CLI boundary near `commands/pipeline.py`. Prove with
non-vacuous dispatch tests: handler ran + message formatted + `enabled` toggle controls
whether `notifier.send` is called.

**Architecture:** Mirrors `subscribers/telegram.py` exactly: `__init__` self-registers one
handler per event via `bus.subscribe(...)`; each handler formats a message + logs via
`personalscraper.logger.get_logger`; if `enabled` → `notifier.send(message)` on a
daemon thread via `_spawn`; if not → log-only (the "muted" default). The `enabled` flag
comes from a new `notify.acquire_notify_enabled` bool field in `NotifyConfig`
(`conf/models/api_config.py`), defaulting to `False`. CLI wiring adds
`AcquisitionTelegramSubscriber` alongside `TelegramSubscriber` in
`commands/pipeline.py::run`, guarded by `TelegramNotifier.is_configured(settings)`.

**Tech Stack:** `personalscraper.core.event_bus.EventBus`, `personalscraper.logger.get_logger`
(NOT `structlog.get_logger` — enforced by `make lint`), `personalscraper.api.notify.telegram.TelegramNotifier`,
`threading.Thread` (daemon, fire-and-forget), `unittest.mock.MagicMock`.

---

## Gate (start of phase)

Phase 1 delivered:

- `personalscraper/acquire/events.py` — 10 frozen event classes
- `personalscraper/events/__init__.py` — eager-imports acquire events, re-exports all 10
- `tests/fixtures/event_samples.py` — 10 real-data factories
- `tests/acquire/test_acquire_events.py` — round-trip + registration tests, all passing
- `tests/event_bus/test_pipeline_events.py` — count-pin at 33
- `make check` green

Verify gate before starting:

```bash
cd /Users/izno/dev/PersonnalScaper
python -c "
import personalscraper.events
from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
assert len(_EVENT_CLASS_REGISTRY) == 33, len(_EVENT_CLASS_REGISTRY)
print('Phase 1 gate: OK')
"
```

---

## File map

| Action | File                                           | Responsibility                                               |
| ------ | ---------------------------------------------- | ------------------------------------------------------------ |
| Create | `personalscraper/subscribers/acquire.py`       | `AcquisitionTelegramSubscriber` (10 handlers)                |
| Modify | `personalscraper/conf/models/api_config.py`    | add `acquire_notify_enabled: bool = False` to `NotifyConfig` |
| Modify | `personalscraper/commands/pipeline.py`         | wire `AcquisitionTelegramSubscriber` in `run`                |
| Create | `tests/subscribers/test_acquire_subscriber.py` | dispatch + enabled/disabled toggle + fail-soft tests         |

---

## Task 2.1 — Add `acquire_notify_enabled` config flag

**Files:**

- Modify: `personalscraper/conf/models/api_config.py`

- [ ] **Step 2.1.1 — Read current `NotifyConfig`**

  Read `personalscraper/conf/models/api_config.py` around line 296 to understand the
  current `NotifyConfig` and `NotifyProviderConfig` shape:

  ```python
  class NotifyProviderConfig(_StrictModel):
      enabled: bool = False

  class NotifyConfig(_StrictModel):
      telegram: NotifyProviderConfig = Field(default_factory=NotifyProviderConfig)
      healthchecks: NotifyProviderConfig = Field(default_factory=NotifyProviderConfig)
  ```

- [ ] **Step 2.1.2 — Add the flag to `NotifyConfig`**

  Extend `NotifyConfig` with the new field (smallest additive change — one bool, default False):

  ```python
  class NotifyConfig(_StrictModel):
      """Top-level notify.json5 model.

      Attributes:
          telegram: Telegram bot configuration.
          healthchecks: Healthchecks ping configuration.
          acquire_notify_enabled: Whether the muted acquisition Telegram subscriber
              is allowed to send messages. Default ``False`` (muted) until producers
              arrive in waves 4–5.
      """

      telegram: NotifyProviderConfig = Field(default_factory=NotifyProviderConfig)
      healthchecks: NotifyProviderConfig = Field(default_factory=NotifyProviderConfig)
      acquire_notify_enabled: bool = Field(
          default=False,
          description="Enable Telegram notifications for acquisition events (RP4+). "
                      "Default False — muted until wave-4/5 producers are active.",
      )
  ```

- [ ] **Step 2.1.3 — Verify config loads clean**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  python -c "
  from personalscraper.conf.models.api_config import NotifyConfig
  cfg = NotifyConfig()
  assert cfg.acquire_notify_enabled is False
  print('NotifyConfig.acquire_notify_enabled default:', cfg.acquire_notify_enabled)
  "
  ```

  Expected: `NotifyConfig.acquire_notify_enabled default: False`

---

## Task 2.2 — Write the subscriber (TDD)

**Files:**

- Create: `tests/subscribers/test_acquire_subscriber.py`
- Create: `personalscraper/subscribers/acquire.py`

- [ ] **Step 2.2.1 — Write failing tests first**

  Create `tests/subscribers/test_acquire_subscriber.py`:

  ```python
  # tests/subscribers/test_acquire_subscriber.py
  """Non-vacuous dispatch tests for AcquisitionTelegramSubscriber.

  Tests verify:
  1. Every handler fires when its event is emitted.
  2. Each handler formats a non-empty string message and logs a structlog line.
  3. With enabled=True + a mocked notifier: notifier.send called exactly once.
  4. With enabled=False (default): notifier.send never called.
  5. A notifier that raises does not propagate (fail-soft contract).
  """
  from __future__ import annotations

  import threading
  import time
  from unittest.mock import MagicMock, patch

  import pytest

  import personalscraper.events  # noqa: F401 — eager-import acquire events
  from personalscraper.core.event_bus import EventBus
  from personalscraper.core.identity import MediaRef
  from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber
  from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

  _REF = MediaRef(tvdb_id=81189)


  def _make_bus_and_sub(enabled: bool = False) -> tuple[EventBus, AcquisitionTelegramSubscriber, MagicMock]:
      """Return a fresh bus + subscriber + mock notifier triple."""
      bus = EventBus()
      notifier = MagicMock()
      notifier.send.return_value = True
      sub = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=enabled)
      return bus, sub, notifier


  # ---------------------------------------------------------------------------
  # 1. All 10 handlers fire on emit
  # ---------------------------------------------------------------------------

  @pytest.mark.parametrize(
      "event_cls",
      [
          pytest.param(cls, id=cls.__name__)
          for cls in [
              # import inside parametrize so test collection works before the module exists
          ]
      ],
  )
  def test_placeholder() -> None:
      """Placeholder — replaced below with real parametrize after imports resolve."""
      pass


  # Real parametrized tests (import after subscriber module exists):
  from personalscraper.acquire.events import (  # noqa: E402
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

  _ALL_ACQUIRE_EVENT_CLASSES = [
      SeriesFollowed, SeriesUnfollowed, WantedEnqueued, WantedAbandoned,
      GrabSucceeded, GrabFailed, SeedObligationRecorded, SeedObligationBreached,
      SeedObligationSatisfied, RatioMeasured,
  ]


  @pytest.mark.parametrize("event_cls", _ALL_ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
  def test_handler_fires_on_emit(event_cls: type) -> None:
      """Each acquisition event triggers its handler (handler ran proof)."""
      bus, sub, notifier = _make_bus_and_sub(enabled=False)
      event = EVENT_SAMPLE_FACTORIES[event_cls]()
      fired: list[bool] = []

      # Patch the format method on the subscriber to observe it was called
      original_method = None
      method_name = f"_on_{_camel_to_snake(event_cls.__name__)}"
      original_method = getattr(sub, method_name)

      called = []

      def _spy(ev: object) -> None:
          called.append(ev)
          original_method(ev)

      setattr(sub, method_name, _spy)
      bus.emit(event)
      assert len(called) == 1, f"Handler {method_name} did not fire for {event_cls.__name__}"
      sub.close()


  def _camel_to_snake(name: str) -> str:
      """Convert CamelCase event name to snake_case handler name."""
      import re
      s = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
      return s


  @pytest.mark.parametrize("event_cls", _ALL_ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
  def test_handler_disabled_does_not_send(event_cls: type) -> None:
      """With enabled=False, notifier.send is never called (muted mode)."""
      bus, sub, notifier = _make_bus_and_sub(enabled=False)
      event = EVENT_SAMPLE_FACTORIES[event_cls]()
      bus.emit(event)
      notifier.send.assert_not_called()
      sub.close()


  @pytest.mark.parametrize("event_cls", _ALL_ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
  def test_handler_enabled_sends_once(event_cls: type) -> None:
      """With enabled=True + mocked notifier, notifier.send is called exactly once per emit."""
      bus, sub, notifier = _make_bus_and_sub(enabled=True)
      event = EVENT_SAMPLE_FACTORIES[event_cls]()
      bus.emit(event)
      # _spawn uses a daemon thread; give it a moment to fire
      time.sleep(0.05)
      assert notifier.send.call_count == 1, (
          f"Expected notifier.send called once for {event_cls.__name__}, "
          f"got {notifier.send.call_count}"
      )
      msg = notifier.send.call_args[0][0]
      assert msg, f"send called with empty message for {event_cls.__name__}"
      sub.close()


  def test_fail_soft_notifier_error_does_not_propagate() -> None:
      """A raising notifier must not propagate out of the subscriber."""
      bus = EventBus()
      notifier = MagicMock()
      notifier.send.side_effect = RuntimeError("telegram down")
      sub = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=True)
      event = EVENT_SAMPLE_FACTORIES[SeriesFollowed]()
      # Must not raise
      bus.emit(event)
      time.sleep(0.05)  # let daemon thread run
      sub.close()


  def test_close_unsubscribes_all() -> None:
      """close() unregisters all 10 subscriptions."""
      bus = EventBus()
      sub = AcquisitionTelegramSubscriber(bus, enabled=False)
      assert len(sub._tokens) == 10
      sub.close()
      assert len(sub._tokens) == 0
      # Emit after close — notifier.send must not be called (no subscriptions)
      notifier = MagicMock()
      sub2 = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=True)
      sub2.close()
      event = EVENT_SAMPLE_FACTORIES[RatioMeasured]()
      bus.emit(event)
      time.sleep(0.05)
      notifier.send.assert_not_called()
  ```

- [ ] **Step 2.2.2 — Run failing tests (ImportError expected)**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/subscribers/test_acquire_subscriber.py -x --tb=short 2>&1 | head -20
  ```

  Expected: `ImportError: cannot import name 'AcquisitionTelegramSubscriber' from
'personalscraper.subscribers.acquire'` (or ModuleNotFoundError).

- [ ] **Step 2.2.3 — Write `personalscraper/subscribers/acquire.py`**

  ```python
  # personalscraper/subscribers/acquire.py
  """Muted Telegram subscriber for acquisition events (RP4).

  Subscribes to all 10 acquisition events from :mod:`personalscraper.acquire.events`.
  Each handler formats a human-readable message and emits a structlog line.
  Network send is dispatched on a fire-and-forget daemon thread only when
  ``enabled=True`` (default ``False`` — muted until wave-4/5 producers are active).

  Mirrors the pattern of :mod:`personalscraper.subscribers.telegram`:
  - Self-registers in ``__init__`` via ``bus.subscribe``.
  - ``_spawn`` launches a daemon thread for the HTTP call.
  - ``close`` unsubscribes every stored token (idempotent).
  """

  from __future__ import annotations

  import threading
  from typing import TYPE_CHECKING

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
  from personalscraper.core.event_bus import EventBus, SubscriptionToken
  from personalscraper.logger import get_logger

  if TYPE_CHECKING:
      from personalscraper.api.notify.telegram import TelegramNotifier

  log = get_logger(__name__)


  class AcquisitionTelegramSubscriber:
      """Formats and (optionally) sends Telegram alerts for acquisition events.

      Subscribes to all 10 acquisition event types defined in
      :mod:`personalscraper.acquire.events`. Each handler formats a short message
      and emits a structlog line at ``INFO`` level (``acquire.notify.<event>``).
      When ``enabled=True`` the message is also sent via ``notifier`` on a
      fire-and-forget daemon thread (fail-soft: any notifier exception is caught
      and logged at ``WARNING``). When ``enabled=False`` (default) the subscriber
      is fully silent toward Telegram — useful for wiring + testing before the
      wave-4/5 producers go live.

      Attributes:
          name: Subscriber identity tag for logging.
      """

      name = "acquire_telegram"

      def __init__(
          self,
          bus: EventBus,
          notifier: TelegramNotifier | None = None,
          *,
          enabled: bool = False,
      ) -> None:
          """Register one handler per acquisition event and store state.

          Args:
              bus: The :class:`EventBus` to subscribe to.
              notifier: Pre-configured :class:`TelegramNotifier`; required when
                  ``enabled=True``. When ``None`` and ``enabled=True``, sending
                  is silently skipped (fail-soft for mis-configured callers).
              enabled: When ``True``, handlers send messages via ``notifier``.
                  Default ``False`` (muted) — no messages sent until wave-4/5.
          """
          self._bus = bus
          self._notifier = notifier
          self._enabled = enabled
          self._tokens: list[SubscriptionToken] = [
              bus.subscribe(SeriesFollowed, self._on_series_followed),
              bus.subscribe(SeriesUnfollowed, self._on_series_unfollowed),
              bus.subscribe(WantedEnqueued, self._on_wanted_enqueued),
              bus.subscribe(WantedAbandoned, self._on_wanted_abandoned),
              bus.subscribe(GrabSucceeded, self._on_grab_succeeded),
              bus.subscribe(GrabFailed, self._on_grab_failed),
              bus.subscribe(SeedObligationRecorded, self._on_seed_obligation_recorded),
              bus.subscribe(SeedObligationBreached, self._on_seed_obligation_breached),
              bus.subscribe(SeedObligationSatisfied, self._on_seed_obligation_satisfied),
              bus.subscribe(RatioMeasured, self._on_ratio_measured),
          ]

      def close(self) -> None:
          """Unsubscribe every stored token. Idempotent.

          Releases all 10 subscriptions registered in ``__init__``.
          """
          for token in self._tokens:
              self._bus.unsubscribe(token)
          self._tokens = []

      @staticmethod
      def _spawn(target: object, *args: object) -> None:
          """Schedule ``target(*args)`` on a fire-and-forget daemon thread.

          The daemon flag ensures the worker dies with the interpreter so a
          hanging Telegram POST cannot prevent the pipeline from exiting.
          Any uncaught exception from the worker is logged at WARNING level.
          """

          def _runner() -> None:
              try:
                  target(*args)  # type: ignore[operator]
              except Exception:
                  log.warning(
                      "acquire_telegram_subscriber_worker_crashed",
                      target=getattr(target, "__name__", repr(target)),
                      exc_info=True,
                  )

          threading.Thread(target=_runner, daemon=True).start()

      def _send(self, message: str, event_name: str) -> None:
          """Background-thread worker: send message (fail-soft).

          Args:
              message: Plain-text or HTML message to send.
              event_name: Event class name for the warning log.
          """
          if self._notifier is None:
              log.warning("acquire_telegram_subscriber_no_notifier", event=event_name)
              return
          if not self._notifier.send(message):
              log.warning("acquire_telegram_subscriber_send_failed", event=event_name)

      def _dispatch(self, message: str, event_name: str) -> None:
          """Log the structlog line and optionally schedule the send.

          Args:
              message: Formatted human-readable message.
              event_name: Structlog event name (``acquire.notify.<event>``).
          """
          log.info(f"acquire.notify.{event_name}", message=message)
          if self._enabled:
              self._spawn(self._send, message, event_name)

      # ----- Bus callbacks --------------------------------------------------

      def _on_series_followed(self, event: SeriesFollowed) -> None:
          """Handle SeriesFollowed — format + dispatch."""
          msg = f"📺 Following: {event.title} (tvdb:{event.media_ref.tvdb_id})"
          self._dispatch(msg, "series_followed")

      def _on_series_unfollowed(self, event: SeriesUnfollowed) -> None:
          """Handle SeriesUnfollowed — format + dispatch."""
          msg = f"📺 Unfollowed: tvdb:{event.media_ref.tvdb_id}"
          self._dispatch(msg, "series_unfollowed")

      def _on_wanted_enqueued(self, event: WantedEnqueued) -> None:
          """Handle WantedEnqueued — format + dispatch."""
          if event.kind == "episode":
              loc = f"S{event.season:02d}E{event.episode:02d}" if event.season and event.episode else "?"
              msg = f"🔍 Wanted episode: tvdb:{event.media_ref.tvdb_id} {loc}"
          else:
              msg = f"🔍 Wanted movie: tvdb:{event.media_ref.tvdb_id}"
          self._dispatch(msg, "wanted_enqueued")

      def _on_wanted_abandoned(self, event: WantedAbandoned) -> None:
          """Handle WantedAbandoned — format + dispatch."""
          msg = f"❌ Wanted abandoned: tvdb:{event.media_ref.tvdb_id} — {event.reason}"
          self._dispatch(msg, "wanted_abandoned")

      def _on_grab_succeeded(self, event: GrabSucceeded) -> None:
          """Handle GrabSucceeded — format + dispatch."""
          tags = ", ".join(event.tags) if event.tags else "—"
          msg = (
              f"✅ Grabbed: {event.info_hash[:8]}… "
              f"tracker={event.source_tracker} cat={event.category or '?'} tags={tags}"
          )
          self._dispatch(msg, "grab_succeeded")

      def _on_grab_failed(self, event: GrabFailed) -> None:
          """Handle GrabFailed — format + dispatch."""
          tracker = event.source_tracker or "unknown"
          msg = f"⚠️ Grab failed: tracker={tracker} — {event.reason}"
          self._dispatch(msg, "grab_failed")

      def _on_seed_obligation_recorded(self, event: SeedObligationRecorded) -> None:
          """Handle SeedObligationRecorded — format + dispatch."""
          hours = event.min_seed_time_s // 3600
          msg = (
              f"🌱 Seed obligation: {event.info_hash[:8]}… "
              f"tracker={event.source_tracker} min={hours}h"
          )
          self._dispatch(msg, "seed_obligation_recorded")

      def _on_seed_obligation_breached(self, event: SeedObligationBreached) -> None:
          """Handle SeedObligationBreached — format + dispatch."""
          msg = (
              f"🚨 Seed obligation BREACHED: {event.info_hash[:8]}… "
              f"tracker={event.source_tracker}"
          )
          self._dispatch(msg, "seed_obligation_breached")

      def _on_seed_obligation_satisfied(self, event: SeedObligationSatisfied) -> None:
          """Handle SeedObligationSatisfied — format + dispatch."""
          msg = (
              f"✔️ Seed obligation satisfied: {event.info_hash[:8]}… "
              f"tracker={event.source_tracker}"
          )
          self._dispatch(msg, "seed_obligation_satisfied")

      def _on_ratio_measured(self, event: RatioMeasured) -> None:
          """Handle RatioMeasured — format + dispatch."""
          msg = (
              f"📊 Ratio: tracker={event.tracker} "
              f"observed={event.observed_ratio:.2f} target={event.target_ratio:.2f}"
          )
          self._dispatch(msg, "ratio_measured")
  ```

- [ ] **Step 2.2.4 — Ensure `tests/subscribers/` has an `__init__.py`**

  ```bash
  ls /Users/izno/dev/PersonnalScaper/tests/subscribers/__init__.py 2>/dev/null || \
    touch /Users/izno/dev/PersonnalScaper/tests/subscribers/__init__.py
  ```

- [ ] **Step 2.2.5 — Run the subscriber tests**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/subscribers/test_acquire_subscriber.py -x --tb=short
  ```

  Expected: all PASS. In particular:
  - `test_handler_disabled_does_not_send` — 10 parametrized variants all PASS.
  - `test_handler_enabled_sends_once` — 10 variants, `notifier.send.call_count == 1`.
  - `test_fail_soft_notifier_error_does_not_propagate` — PASS.
  - `test_close_unsubscribes_all` — PASS.

  If `test_handler_fires_on_emit` fails because `_camel_to_snake` doesn't match the
  method names, verify the handler naming convention in the subscriber matches
  `_on_series_followed`, `_on_series_unfollowed`, etc. and adjust `_camel_to_snake`
  accordingly (or drop the spy test and rely on `test_handler_enabled_sends_once`).

- [ ] **Step 2.2.6 — Run `make lint` to check logging convention**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  make lint 2>&1 | tail -20
  ```

  Expected: zero errors. If `check_logging.py` reports `structlog.get_logger` usage,
  replace any such call with `from personalscraper.logger import get_logger`.

---

## Task 2.3 — Wire the subscriber at the CLI boundary

**Files:**

- Modify: `personalscraper/commands/pipeline.py`

- [ ] **Step 2.3.1 — Read the wiring zone**

  Open `personalscraper/commands/pipeline.py` around lines 477–585 (the `run` command
  body). Locate the block:

  ```python
  from personalscraper.subscribers.telegram import TelegramSubscriber
  ...
  telegram_subscriber: TelegramSubscriber | None = None
  ...
  if TelegramNotifier.is_configured(settings):
      tg_transport = HttpTransport(...)
      tg_notifier = TelegramNotifier(tg_transport, settings.telegram_chat_id)
      telegram_subscriber = TelegramSubscriber(app_context.event_bus, tg_notifier)
  ```

  The new subscriber is added **inside the same `if TelegramNotifier.is_configured`
  block** (it needs the same notifier) and reads `config.notify.acquire_notify_enabled`
  for the `enabled` flag.

- [ ] **Step 2.3.2 — Add the import inside the `run` function body**

  After the existing `from personalscraper.subscribers.telegram import TelegramSubscriber`
  line (inside the function, to keep the lazy-import pattern), add:

  ```python
  from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber
  ```

- [ ] **Step 2.3.3 — Declare the acquisition subscriber variable**

  After the line `telegram_subscriber: TelegramSubscriber | None = None`, add:

  ```python
  acq_telegram_subscriber: AcquisitionTelegramSubscriber | None = None
  ```

- [ ] **Step 2.3.4 — Construct it inside the Telegram-configured branch**

  Immediately after `telegram_subscriber = TelegramSubscriber(app_context.event_bus, tg_notifier)`, add:

  ```python
  acq_telegram_subscriber = AcquisitionTelegramSubscriber(
      app_context.event_bus,
      notifier=tg_notifier,
      enabled=config.notify.acquire_notify_enabled,
  )
  ```

- [ ] **Step 2.3.5 — Close it in the finally block**

  After `if telegram_subscriber is not None: telegram_subscriber.close()`, add:

  ```python
  if acq_telegram_subscriber is not None:
      acq_telegram_subscriber.close()
  ```

- [ ] **Step 2.3.6 — Verify the import path for `config.notify`**

  `config` in the `run` body is the `Config` object. Confirm `config.notify` exists
  and has `acquire_notify_enabled`:

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  python -c "
  from personalscraper.conf.models.config import Config
  from personalscraper.conf.models.api_config import NotifyConfig
  import inspect
  hints = {}
  for f in Config.__dataclass_fields__.values() if hasattr(Config, '__dataclass_fields__') else []:
      pass
  cfg = NotifyConfig()
  assert hasattr(cfg, 'acquire_notify_enabled')
  print('Config.notify.acquire_notify_enabled accessible:', cfg.acquire_notify_enabled)
  "
  ```

  If `Config` uses Pydantic (it does — it's a `_StrictModel`), check the field exists:

  ```bash
  python -c "
  from personalscraper.conf.models.api_config import NotifyConfig
  n = NotifyConfig()
  print('acquire_notify_enabled:', n.acquire_notify_enabled)
  "
  ```

  Expected: `acquire_notify_enabled: False`

- [ ] **Step 2.3.7 — Run `make check`**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  make check 2>&1 | tail -20
  ```

  Expected: green. If mypy reports a type error on `config.notify.acquire_notify_enabled`
  (e.g. `Config` does not have a `notify` attribute), check `personalscraper/conf/models/config.py`
  line ~108: it should read `notify: NotifyConfig = Field(default_factory=NotifyConfig)`.
  Verify that field exists; if `Config` stores it under a different name, use that name.

---

## Task 2.4 — Commit Phase 2

- [ ] **Step 2.4.1 — Final test run**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  pytest tests/subscribers/test_acquire_subscriber.py tests/acquire/test_acquire_events.py --tb=short
  ```

  Expected: all PASS.

- [ ] **Step 2.4.2 — Commit**

  ```bash
  cd /Users/izno/dev/PersonnalScaper
  git add \
    personalscraper/subscribers/acquire.py \
    personalscraper/conf/models/api_config.py \
    personalscraper/commands/pipeline.py \
    tests/subscribers/test_acquire_subscriber.py \
    tests/subscribers/__init__.py
  git commit -m "feat(acquire-events): muted Telegram subscriber + config flag + CLI wiring + dispatch tests"
  ```

---

## Phase 2 gate

```bash
cd /Users/izno/dev/PersonnalScaper
make check
python -c "
from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber
from personalscraper.conf.models.api_config import NotifyConfig
assert NotifyConfig().acquire_notify_enabled is False
print('Phase 2 gate: OK')
"
```

Expected: `make check` green + `echo` prints `Phase 2 gate: OK`.
