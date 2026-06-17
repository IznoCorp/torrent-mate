# RP7 — Tracker Auth Lifecycle (observability) — Design

> **Status:** brainstorm-approved + adversarially design-reviewed (2026-06-16). Re-scoped after
> review (see §3 D4). Not yet committed; `implement:create-branch` moves this to
> `docs/features/{codename}/DESIGN.md` on the feature branch.
> **SemVer:** minor — `0.33.0 → 0.34.0` (new event + behaviour change).
> **Roadmap:** RP7 (P2 prerequisite). Unblocks Follow D3 (grab) and the torr9/digitalcore trackers.
> **Depends on:** RP1a (`torrent-fetch`, shipped) — provides the typed `TrackerAuthError` 401/403 signal.

---

## 1. Purpose

When the grab core downloads a `.torrent` from a tracker and the credential is broken (revoked
apikey, wrong passkey, rotated token), the fetch returns HTTP 401/403. Today that surfaces as
`TrackerAuthError` (RP1a) and is routed to a **silent, terminal abandon**
(`orchestrator.py:250-252 → _terminal('tracker_auth') → WantedAbandoned`). The circuit breaker
deliberately ignores 4xx, so **no one is alerted** — the item is dropped and the broken credential
goes unnoticed until an operator happens to look.

RP7 makes that auth failure **observable**: it emits a typed `TrackerAuthFailed` event that
SUPERVISE consumes (the muted Telegram subscriber now; Active Health, vague 7, later). The item is
still abandoned (a broken credential will not self-heal by retrying the same item) — but the
abandon is now a routable signal an operator can act on.

RP7 also fixes a **latent crash in the exact `add()` site it touches** (§4.2): the grab calls
`add(category=None, tags=(provider,))`, which a Transmission client rejects with `ValueError`.

## 2. Code-grounded reality (verified, not roadmap guesses)

- RP1a already provides the typed signal: `_fetch.py:167-179` maps `_AUTH_STATUSES=(401,403)` →
  `TrackerAuthError`; caught at `orchestrator.py:250`.
- The circuit breaker (`core/circuit.py:318 _is_circuit_error`) opens only on `http_status >= 500`
  - connection/timeout. 401/403 are **deliberately excluded** and **stay excluded** — RP7's auth
    signal is an **orthogonal side-channel event**, never folded into the breaker (a naive "treat 401
    as a circuit error" would trip on transient gateway 401s). Retry policy (tenacity) also excludes
    401, so a 401 surfaces on the first attempt.
- **Threat-model correction (design review).** An earlier draft proposed re-resolving the download
  URL just before use, to recover a _stale_ short-lived token. The code makes that futile:
  `grab()` runs a **fresh `search_candidates(query)` per item** (`orchestrator.py:210`) and spends
  the token a few in-memory steps later (`resolve_source` at `:245`) — only filter/dedup/rank in
  between, no network, no sleep. The token is therefore **milliseconds old when used**, never
  stale. The ">1h stale-requeue" path (`service.py _STALE_THRESHOLD_S=3600`) **re-runs `grab()`**
  (a fresh search), it does not replay an aged URL. And LaCale caches searches ~30 s, so a
  re-search inside that window returns the **same** token. A 401 here is therefore a genuinely
  broken credential, which re-resolution cannot fix. **Conclusion: the reactive re-resolve half is
  dropped** (D4); RP7 keeps only the observability event + the Transmission fix.
- The `query` passed to search is a plain **`str`** (`_build_query(media_ref) -> str`,
  `orchestrator.py:284`); `TorrentSearchable.search` and `TrackerRegistry.search_candidates` are
  both `str`-typed. (An earlier draft referenced a non-existent `TrackerQuery` VO — corrected.)
- The acquisition event catalog (RP4) ships the base `Event`, the `_EVENT_CLASS_REGISTRY`
  auto-registration (`Event.__init_subclass__`), the eager-import hub, the factory + round-trip
  gates, and the muted Telegram subscriber. Adding an event is **purely additive** but touches
  **six count surfaces** (§4.1) that are hard-pinned by tests.
- Layering: `acquire/` imports `api/`/`core/` downward only — never the reverse.

## 3. Decisions (resolved with operator, 2026-06-16)

| #   | Decision                                | Choice                                                                                                                                                                                                     |
| --- | --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Auth-fail observability                 | Emit a typed `TrackerAuthFailed` event in the orchestrator's `except TrackerAuthError` branch (today a silent abandon).                                                                                    |
| D2  | Disposition after a 401                 | **Terminal abandon, unchanged** — a broken credential will not self-heal by retrying the same item. The event is the operator signal; fixing the credential is an operator action.                         |
| D3  | Pre-existing Transmission `add()` crash | **Fix inside RP7** — the grab `add()` site is exactly what RP7 re-touches.                                                                                                                                 |
| D4  | Reactive re-resolve + retry             | **Dropped** — futile in the current per-grab-fresh-search + 30 s-cache architecture (§2). Re-introducible later, with a real threat model, if a token-using tracker (torr9/digitalcore) proves to need it. |

## 4. Architecture

Two units, each independently testable.

### 4.1 `TrackerAuthFailed` event + catalog plumbing

New frozen event in `acquire/events.py` (already eager-imported → auto-registers via
`Event.__init_subclass__`):

```python
@dataclass(frozen=True, kw_only=True)
class TrackerAuthFailed(Event):
    tracker: str        # provider wire name the grab targeted (top.provider, lowercase)
    http_status: int    # 401 or 403
    media_ref: MediaRef  # the desired item that could not be grabbed
```

Layering: `acquire/events.py` may import only `core.event_bus` + `core.identity` + stdlib.

**Mandatory plumbing — six pinned count surfaces, all in the same commit** (omitting any one
fails a test or silently drops the event cross-process):

1. `events/__init__.py` hub — add `TrackerAuthFailed` to the re-export block **and** `__all__`
   (the producer module `acquire/events.py` is already eager-imported, so registration fires; the
   re-export keeps the public surface complete).
2. `tests/event_bus/test_pipeline_events.py:130` — bump literal `== 33` → `== 34`.
3. `tests/event_bus/test_pipeline_events.py:131` — bump message `"23 existing + 10 acquire-events"`
   → `"... 11 acquire-events"`.
4. `tests/fixtures/event_samples.py` — add a `register_factory` entry with **real** field data
   (mirror the existing acquire factories). The parametrized round-trip
   (`tests/architecture/test_registry_events_contract.py`) and `test_every_event_has_factory` then
   cover it automatically — no separate round-trip test needed.
5. `subscribers/acquire.py` — import + add `bus.subscribe(TrackerAuthFailed,
self._on_tracker_auth_failed)` to the `_tokens` list + an `_on_tracker_auth_failed` formatter
   calling `self._dispatch`; bump the three docstrings (`:3`, `:43`, `:95`) `10`→`11`.
6. `tests/subscribers/test_acquire_subscriber.py:247` — bump token pin `== 10` → `== 11`.

Gated behind `acquire_notify_enabled` (default False), like the rest of the subscriber.

### 4.2 Grab `except TrackerAuthError` emit + Transmission `add()` fix

At `orchestrator.py:241-259`. Two changes inside the resolve/add `try` ladder.

**(a) Emit on the auth-error branch.** Bind the exception (`as exc`) to read `http_status`:

```python
except TrackerAuthError as exc:
    self._event_bus.emit(
        TrackerAuthFailed(tracker=top.provider, http_status=exc.http_status, media_ref=media_ref)
    )
    return self._terminal(media_ref, "tracker_auth", chosen=top)
```

(Follows the orchestrator's self-emit-on-failure convention — failures are emitted by the
orchestrator; `GrabSucceeded` stays the service's emit-after-persist. `correlation_id` propagates
via the `Event` base's ContextVar, like every other event.)

**(b) Transmission `add()` fix — add first, then tag.** The grab currently calls
`add(source, category=None, tags=(top.provider,))`; Transmission's `add()` deliberately rejects
`category=None` + non-empty `tags` (`transmission.py:227-235`, flat `labels=[category, *tags]`
cannot represent it). Move the provider tag to the tagger, which handles the category-less case via
the seed-pure empty-string sentinel (on both clients):

```python
source = resolve_source(top, self._transports)
info_hash = self._torrent_client.add(source, category=None)
if isinstance(self._torrent_client, TorrentTagger):
    try:
        self._torrent_client.add_tags(info_hash, [top.provider])
    except ApiError as exc:
        # Torrent is ADDED; the provider tag is provenance metadata. A tag
        # failure must NOT bubble to the outer `except ApiError` (that would
        # re-bucket an already-added torrent as add_failed → retryable → a
        # duplicate add next run). Swallow + log; end state 'added' stands.
        log.warning("acquire.grab.tag_failed", hash=info_hash, provider=top.provider,
                    error=str(exc), error_type=type(exc).__name__)
```

**Invariants preserved:**

- Both `resolve_source` and `add()` stay **inside the same outer `try`** whose ladder is, in order,
  `CircuitOpenError → TrackerAuthError → TorrentFetchError → ApiError` (`CircuitOpenError` is NOT an
  `ApiError` subclass and must precede it). RP7 does not move `add()` out of the ladder, so an
  `add()` transport failure is still bucketed `add_failed` (retryable) exactly as today.
- The inner `try` around `add_tags` is the **only** new swallow — scoped to the post-add tagging,
  not the add itself.
- `category` stays `None` (the media is not yet sorted; no category exists at grab time).

## 5. Data flow

```
grab(item):
  query = build_query(item)                 # str
  outcome = registry.search_candidates(query, ...)   # fresh search, per item
  top = rank(dedup(filter(outcome.results)))[0]
  try:
    source = resolve_source(top)            # spends the (ms-old) token
    info_hash = add(source, category=None)  # qBit + Transmission safe
    add_tags(info_hash, [top.provider])     # post-add; tag failure swallowed+logged
  except CircuitOpenError:  -> retryable 'circuit_open'
  except TrackerAuthError(exc):             # 401/403 = broken credential
        emit TrackerAuthFailed(tracker, http_status, media_ref)
        -> terminal 'tracker_auth'          # observable, then abandon
  except TorrentFetchError: -> retryable 'fetch_failed'
  except ApiError:          -> retryable 'add_failed'
  -> success (service emits GrabSucceeded after mark_grabbed)
```

## 6. Error handling

- The circuit breaker, retry policy, and `_is_circuit_error` predicate are **not modified** (401
  stays non-circuit, non-retryable).
- `add_tags` failure after a successful `add()` → swallowed + logged, item counts as grabbed
  (provenance tag is non-essential). Never re-buckets as a retryable add failure.
- Except-clause ordering is preserved exactly; no new exception type can escape `grab()`.

## 7. Non-goals

- **No URL re-resolution / retry** — dropped as futile in the current architecture (§2/§3 D4).
  Re-introducible later with a real threat model if a token-using tracker needs it.
- No change to the circuit breaker or retry policy.
- No credential-refresh automation — the event surfaces the failure; rotating the apikey/passkey is
  an operator action.
- No Active Health subscriber (vague 7) — only the muted Telegram subscriber is wired now.
- No magnet handling (magnets carry no auth, never reach the auth-error branch).

## 8. Testing (test-per-behaviour; non-vacuous, mutation-checked)

1. **`TrackerAuthFailed` event registration** — present in `_EVENT_CLASS_REGISTRY`; catalog count
   pin = 34 (`test_pipeline_events.py`); factory present with real data; JSON envelope round-trips
   equal (covered by the parametrized contract test); subscriber token pin = 11; Telegram formatter
   renders a non-empty message.
2. **Grab emits on 401 (the headline behaviour)** — `resolve_source` raises `TrackerAuthError(401)`
   → assert `grab()` returns terminal `'tracker_auth'` **and** emits exactly one `TrackerAuthFailed`
   with `tracker == top.provider`, `http_status == 401`, the right `media_ref`. Mutation-proof:
   removing the `emit` line drops the asserted event. (Use a real/captured event bus, not a bare
   MagicMock, so the emission is actually observed.)
3. **Non-auth failures emit NO auth event** — `TorrentFetchError` → retryable `'fetch_failed'` and
   **zero** `TrackerAuthFailed`; `ApiError` → retryable `'add_failed'` and zero `TrackerAuthFailed`.
4. **Transmission `add()` fix** — `grab()` against a Transmission client adds without raising **and**
   applies the `[provider]` tag (readable back via the sentinel: `category is None`, provider tag
   present). Mutation-proof: reverting to `add(category=None, tags=(provider,))` reproduces the
   `ValueError`.
5. **`add_tags` failure after add is non-fatal** — `add()` succeeds, `add_tags` raises `ApiError`
   → `grab()` returns success (item grabbed), the failure is logged, and it is **not** re-bucketed
   as retryable `'add_failed'` (no duplicate-add next run).

## 9. Acceptance criteria (executable; finalized in ACCEPTANCE.md at plan time)

Sketch (each becomes an `ACC-NN` shell command with documented expected output):

- `python -c "from personalscraper.events import TrackerAuthFailed"` → no error.
- `pytest tests/event_bus/test_pipeline_events.py -q` → count-pin 34 passes.
- `pytest tests/acquire/test_grab_auth_event.py -q` → emit-on-401 + non-auth-no-event pass.
- `pytest tests/acquire/test_grab_transmission_add.py -q` → no-crash + tag-applied + tag-failure-soft.
- `pytest tests/subscribers/test_acquire_subscriber.py -q` → token pin 11 passes.
- `make check` → green; `python -c "import personalscraper"` → smoke.

## 10. Open questions (resolve at plan time, none blocking)

- **Telegram formatter wording** — confirm the `_on_tracker_auth_failed` message format (include
  tracker + a redacted media identity; never log the auth-bearing URL or token).
- **`media_ref` rendering in the event factory** — reuse the existing acquire factories' `MediaRef`
  construction so the round-trip test passes unchanged.
