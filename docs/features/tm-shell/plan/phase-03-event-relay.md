# Phase 3 — Event relay (Redis Streams → WebSocket)

## Gate

- Phase 2 complete: auth routes respond, guard works, `web set-password` functional.
- Redis running locally (`redis-cli ping` → `PONG`).
- `config/web.json5` has `redis_url`, `stream_key`, `stream_maxlen` set.

## Sub-phases

### 3.1 — RedisEventPublisher (producer side)

**Commit**: `feat(tm-shell): add RedisEventPublisher subscriber`

**Files**:

| Action | Path                                          |
| ------ | --------------------------------------------- |
| Create | `personalscraper/subscribers/redis_stream.py` |
| Modify | `personalscraper/subscribers/__init__.py`     |

**Work**:

1. `subscribers/redis_stream.py` — `RedisEventPublisher` class:
   - `__init__(event_bus, web_config)` — subscribes to base `Event`, stores
     `redis.Redis` connection (sync, from `redis_url`).
   - `__call__(event)` — `event_to_envelope` → JSON → `XADD` to `stream_key`
     with `MAXLEN ~ stream_maxlen`, field `{"envelope": json, "type":
event_class_name}`.
   - **Fail-soft**: Redis unreachable → `log.warning("redis_publish_failed")`
     once (suppressed after first), drop events, never raise.
   - **Fast-subscriber contract**: enqueue to `queue.Queue`, daemon thread drains
     to Redis — subscriber callback returns immediately.
   - `close()` → stop thread, unsubscribe from bus, close Redis connection.
2. Re-export in `subscribers/__init__.py`.

**Verification**: `python -c "from personalscraper.subscribers.redis_stream
import RedisEventPublisher"` imports cleanly; unit test with fakeredis
(see 3.4).

### 3.2 — WebSocket relay + routes (web side)

**Commit**: `feat(tm-shell): add WebSocket event relay with replay`

**Files**:

| Action | Path                                 |
| ------ | ------------------------------------ |
| Create | `personalscraper/web/ws/__init__.py` |
| Create | `personalscraper/web/ws/relay.py`    |
| Create | `personalscraper/web/ws/routes.py`   |
| Modify | `personalscraper/web/app.py`         |

**Work**:

1. `ws/relay.py` — async-only module (only async code in `web/` per DESIGN §4.5):
   - `ConnectionRegistry` — set of active WebSocket connections, add/remove/discard.
   - `init_redis_pool(config)` → `redis.asyncio.Redis`.
   - `read_stream_loop(redis_pool, registry, stream_key)` — `XREAD BLOCK 5000`
     from `$`, fan-out each entry to all connected WS; runs as asyncio task
     per process.
   - `replay_events(redis_pool, stream_key, last_id)` — `XRANGE (last_id, +]`
     → list of entries; called on WS connect with `?last_id=`.
   - WS message shape: `{"id", "type", "data"}` + `{"type": "ws.hello", ...}`
     on connect + `{"type": "ws.ping"}` every 30 s.
2. `ws/routes.py` — `GET /ws/events`: FastAPI WebSocket endpoint:
   - Reads `tm_session` cookie → JWT verify (same `require_session` logic,
     adapted for WS; invalid → close 4401).
   - Registers connection, sends hello with `build_commit`, replays if
     `?last_id=<stream-id>`, then enters live fan-out.
   - On disconnect → remove from registry.
3. `app.py` — mount WS router (`app.include_router(ws_router)`), call
   `init_redis_pool` on startup, close on shutdown.

**Verification**: `python -c "from personalscraper.web.ws.relay import
ConnectionRegistry; print('ok')"` imports cleanly.

### 3.3 — Producer wiring (gate on `web.enabled`)

**Commit**: `feat(tm-shell): wire RedisEventPublisher into pipeline and watch daemon`

**Files**:

| Action | Path                                   |
| ------ | -------------------------------------- |
| Modify | `personalscraper/commands/pipeline.py` |
| Modify | `personalscraper/commands/watch.py`    |

**Work**:

1. In `commands/pipeline.py` and `commands/watch.py` (the two boundary sites that
   build subscribers): after existing subscriber wiring (RichConsole, Telegram),
   add `if config.web.enabled: RedisEventPublisher(bus, config.web)` with a
   `try/except` so Redis-down never blocks boot. Store token for `close()`.
2. In `watch.py`'s `finally` block, close the publisher before context teardown.

**Verification**: grep both files for `RedisEventPublisher`; imports pass.

### 3.4 — Relay tests

**Commit**: `test(tm-shell): add event relay tests with fakeredis`

**Files**:

| Action | Path                                |
| ------ | ----------------------------------- |
| Create | `tests/web/test_relay.py`           |
| Create | `tests/web/test_redis_publisher.py` |
| Create | `tests/web/conftest.py` (amend)     |

**Work**:

1. `conftest.py` — add `fakeredis` fixture (`fakeredis.FakeAsyncRedis` for WS
   side, `fakeredis.FakeRedis` for producer side).
2. `test_redis_publisher.py` — unit: `RedisEventPublisher` XADDs envelope on
   emit, names it correctly, fail-soft on Redis-down (no raise), daemon thread
   drain, `MAXLEN` trimming.
3. `test_relay.py` — integration: connect WS (patch `require_session` to
   bypass auth for test), XADD an event → received on WS, disconnect + reconnect
   with `last_id` → replays missed events, hello message on connect, ping/pong,
   invalid token → close 4401, envelope round-trip
   (`event_from_envelope(event_to_envelope(e))`).

## Verification

```bash
make lint                     # zero errors — check_logging on new subscribers/redis_stream.py
make test                     # all pass, ≥ 90% coverage on web/ws/ + subscribers/redis_stream.py
python scripts/check-module-size.py
```

**Manual checks**:

- Start web, `redis-cli XADD personalscraper:events '*' type Test data '{}'`,
  connect with `websocat ws://127.0.0.1:8710/ws/events` (with valid cookie) →
  receive the event.
- Disconnect, reconnect with `?last_id=<that-id>` → replay.
