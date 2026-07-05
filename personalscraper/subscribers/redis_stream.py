"""Redis Stream publisher for the in-process EventBus.

Subscribes to the base :class:`Event` class (catch-all) and publishes every
event to a Redis Stream so cross-process consumers (notably the web process
WebSocket relay) can receive them.

Self-subscribes on construction. The subscriber callback enqueues to an
in-memory :class:`queue.Queue` and returns immediately — a daemon worker
thread drains the queue and performs the blocking Redis I/O. This keeps
the bus fast-subscriber contract (DESIGN §Performance contract — subscribers
MUST be fast or schedule work off-thread).

Fail-soft contract (same as Telegram): Redis unreachable → warn once
(``redis_publish_failed``), drop events, never raise, never block the
pipeline. Queue overrun → warn once (``redis_publish_queue_full``).
"""

from __future__ import annotations

import json
import queue
import threading
from typing import TYPE_CHECKING

from personalscraper.core.event_bus import Event, EventBus, SubscriptionToken, event_to_envelope
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    import redis

    from personalscraper.conf.models.web import WebConfig

log = get_logger(__name__)

# Sentinel value for the worker thread shutdown signalling.
_SENTINEL = object()


def build_redis_publisher(
    event_bus: EventBus,
    web_config: "WebConfig",
) -> "RedisEventPublisher | None":
    """Construct a :class:`RedisEventPublisher` when ``web.enabled``, else ``None``.

    The ``web.enabled`` gate is checked here so every caller (pipeline, watch
    daemon, acquisition commands) uses the same guarded pattern.  When
    ``web.enabled`` is ``False`` or construction raises, ``None`` is returned
    and a warning is logged — Redis down must never block the caller's boot
    sequence (fail-soft contract, same as Telegram).

    Args:
        event_bus: The in-process :class:`EventBus` to subscribe to.
        web_config: Web server configuration carrying the ``enabled`` flag and
            Redis connection parameters (``redis_url``, ``stream_key``,
            ``stream_maxlen``).

    Returns:
        A new :class:`RedisEventPublisher` already subscribed and draining, or
        ``None`` when ``web.enabled`` is ``False`` or construction failed.
    """
    if not web_config.enabled:
        return None
    try:
        return RedisEventPublisher(event_bus, web_config)
    except Exception:
        log.warning("redis_publisher_init_failed", exc_info=True)
        return None


class RedisEventPublisher:
    """Publishes every bus event to a Redis Stream for cross-process consumers.

    Subscribes to the base :class:`Event` class (catch-all) so every
    typed event flows through. The callback enqueues to a bounded in-memory
    queue and returns immediately; a daemon worker thread drains the queue
    and performs the ``XADD`` calls. This keeps the bus dispatch latency
    low even when Redis is slow or unreachable.

    Designed as a fire-and-forget relay: dropped events (queue full or Redis
    down) are logged at WARNING level but never escalated — the pipeline
    must never be blocked by a broken Redis connection.
    """

    name = "redis_stream"

    def __init__(self, event_bus: EventBus, web_config: WebConfig) -> None:
        """Subscribe to the base Event class and start the daemon worker thread.

        Args:
            event_bus: The :class:`EventBus` to subscribe to.
            web_config: Web server configuration carrying ``redis_url``,
                ``stream_key``, and ``stream_maxlen``.
        """
        self._bus = event_bus
        self._web_config = web_config
        self._queue: queue.Queue[object] = queue.Queue(maxsize=1000)
        self._token: SubscriptionToken = event_bus.subscribe(Event, self._on_event)
        self._redis: redis.Redis | None = None
        self._redis_failed_warned: bool = False
        self._queue_full_warned: bool = False
        self._lock = threading.Lock()

        # Daemon thread — dies with the interpreter so a hanging Redis
        # connection cannot prevent the pipeline from exiting.
        self._worker = threading.Thread(target=self._drain, daemon=True, name="redis-publisher")
        self._worker.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Unsubscribe from the bus, signal and join the worker thread, close Redis.

        Idempotent — safe to call multiple times. The worker thread is
        joined with a 5-second timeout; if the thread is stuck in a
        blocking ``XADD`` to an unresponsive Redis, the daemon flag ensures
        the interpreter can still exit.
        """
        # Unsubscribe so no new events arrive while we drain.
        self._bus.unsubscribe(self._token)
        # Signal the worker to exit.
        try:
            self._queue.put_nowait(_SENTINEL)
        except queue.Full:
            # Queue is full — drain it.  The sentinel *must* reach the
            # worker or it will block forever on ``.get()``.  Drop the
            # oldest item to make room; close() is the shutdown path, so
            # losing one queued event is acceptable.
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(_SENTINEL)
        self._worker.join(timeout=5)
        # Close the Redis connection quietly.
        with self._lock:
            if self._redis is not None:
                try:
                    self._redis.close()
                except Exception:
                    pass
                self._redis = None

    # ------------------------------------------------------------------
    # Bus callback (fast — no I/O)
    # ------------------------------------------------------------------

    def _on_event(self, event: Event) -> None:
        """Enqueue *event* for the daemon thread; return immediately.

        When the queue is full the event is dropped and a warning is
        logged once (suppressed until the queue drains below half capacity,
        signalling the worker is catching up).
        """
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            if not self._queue_full_warned:
                log.warning("redis_publish_queue_full", maxsize=self._queue.maxsize)
                self._queue_full_warned = True

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _get_redis(self) -> redis.Redis:
        """Return (or lazily create) the sync Redis connection.

        The connection is created on first use inside the worker thread
        so a missing Redis at boot never blocks construction.
        """
        if self._redis is not None:
            return self._redis
        with self._lock:
            if self._redis is not None:
                return self._redis
            import redis as _redis

            self._redis = _redis.Redis.from_url(
                self._web_config.redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            return self._redis

    def _drain(self) -> None:
        """Daemon thread target: drain the in-memory queue into Redis.

        Blocks on ``queue.get()``.  Exits when the sentinel value is
        received.  Every Redis error is caught and logged once
        (suppressed until the next successful ``XADD``).
        """
        while True:
            item = self._queue.get()
            if item is _SENTINEL:
                return
            assert isinstance(item, Event)
            self._publish(item)

    def _publish(self, event: Event) -> None:
        """Serialize and ``XADD`` a single event to the Redis Stream.

        Args:
            event: The bus event to publish.

        Fail-soft: any Redis exception is caught, logged once (suppressed
        after the first failure until a successful ``XADD`` resets the
        guard), and the event is dropped.
        """
        try:
            envelope = event_to_envelope(event)
            self._get_redis().xadd(
                self._web_config.stream_key,
                {
                    "envelope": json.dumps(envelope),
                    "type": type(event).__name__,
                },
                maxlen=self._web_config.stream_maxlen,
                approximate=True,
            )
        except Exception:
            if not self._redis_failed_warned:
                log.warning(
                    "redis_publish_failed",
                    event_type=type(event).__name__,
                    exc_info=True,
                )
                self._redis_failed_warned = True
        else:
            # Success — reset both suppression guards so a future
            # failure is warned about again.
            if self._redis_failed_warned:
                self._redis_failed_warned = False
            if self._queue_full_warned:
                # Only reset the queue-full warning when the queue is
                # below half capacity — the worker has caught up.
                if self._queue.qsize() < self._queue.maxsize // 2:
                    self._queue_full_warned = False
