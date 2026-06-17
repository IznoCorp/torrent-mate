# Phase 3 — PR #202 review fixes (cycle 1)

> Findings from the adversarial review of PR #202 (4 confirmed, 2 refuted). The two
> `major` findings are one root cause: the orchestrator's `except ApiError` swallow
> around `add_tags()` (added in Phase 2) is defeated because the real tagger clients
> raise raw library exceptions, not `personalscraper.ApiError`. DESIGN §4.2/§5/§6/§8
> all assume `add_tags`/`remove_tags` raise `ApiError`; this phase makes that contract
> true at the client boundary (layering: translate in `api/torrent/*`, never import
> `transmission_rpc`/`qbittorrentapi` exception types into `acquire/`).

## Gate (what this phase starts from)

- `personalscraper/api/torrent/transmission.py` `add_tags` (~315-325) / `remove_tags` (~340-349) call `self._client.get_torrent(...)` / `change_torrent(...)` RAW — no translation. Sibling `add()` DOES translate `transmission_rpc.TransmissionError`.
- `personalscraper/api/torrent/qbittorrent.py` `add_tags` / `remove_tags` wrap `torrents_addTags`/`torrents_removeTags` RAW. Siblings `add()` (~230-281) and `login()` (~359-372) translate `qbittorrentapi` exceptions → `ApiError`.
- `tests/acquire/test_grab_transmission_add.py:228` injects `personalscraper.ApiError` as the `add_tags` side-effect — the type the real clients never raise (vacuous against reality).
- `tests/subscribers/test_acquire_subscriber.py:41-52` lists 10 acquire event classes, omitting `TrackerAuthFailed` → the new `_on_tracker_auth_failed` formatter is never exercised (DESIGN §8.1 item 1 unmet).
- `tests/acquire/test_orchestrator.py` exercises the non-`TorrentTagger` skip branch only implicitly (no `add_tags.assert_not_called()`).

## Phase gate (exit criteria)

`make check` green. Client-level translation is mutation-proof (raw library exception → `ApiError`). The orchestrator swallow is exercised end-to-end with the real exception type. Formatter for `TrackerAuthFailed` is exercised.

---

### Sub-phase 3.1 — Translate tagger-client library exceptions to `ApiError` (fixes major #1/#2)

**Files:**

- Modify: `personalscraper/api/torrent/transmission.py` (`add_tags`, `remove_tags`)
- Modify: `personalscraper/api/torrent/qbittorrent.py` (`add_tags`, `remove_tags`)
- Modify: `personalscraper/api/torrent/_contracts.py` (`TorrentTagger` docstrings: add `Raises: ApiError`)
- Test: `tests/api/torrent/test_tagger.py` (NEW regression tests, per test-per-bug)

- [ ] **Step 1: Write the failing regression tests FIRST** in `tests/api/torrent/test_tagger.py`. For BOTH clients, drive the real `add_tags` (and `remove_tags`) with the underlying `_client` method raising the REAL library exception, and assert it is re-raised as `personalscraper.ApiError`:
  - Transmission: `_client.get_torrent` (or `change_torrent`) raises `transmission_rpc.TransmissionError(...)` → `TransmissionClient.add_tags(...)` raises `ApiError`.
  - qBittorrent: `_client.torrents_addTags` raises `qbittorrentapi.exceptions.APIError(...)` → `QBitClient.add_tags(...)` raises `ApiError`.
  - Verify the exact library base-exception classes at runtime first (`command python -c "import transmission_rpc, qbittorrentapi; print(transmission_rpc.TransmissionError.__mro__)"` etc.) and catch the BASE class so subclasses are covered.
    Run → confirm FAIL (today the raw library exception propagates unchanged).
- [ ] **Step 2: Add translation** to all four methods, mirroring the existing `add()`/`login()` pattern (wrap the raw `_client.*` calls in `try/except <LibraryBaseError> as exc: raise ApiError(provider=..., http_status=..., message=...) from exc`). Use the provider name already used by the class. Keep the read-first / idempotence logic unchanged — only wrap the raw RPC/API calls.
- [ ] **Step 3: Document the contract.** In `_contracts.py`, add a `Raises:\n    ApiError: ...` clause to `TorrentTagger.add_tags` and `remove_tags` so the protocol states what the orchestrator swallow relies on.
- [ ] **Step 4: Run** `command python -m pytest tests/api/torrent/test_tagger.py -q` → confirm PASS.
- [ ] **Step 5: Mutation check.** Temporarily remove one client's translation `try/except`, re-run → confirm the new regression test FAILS (raw library exception leaks), then restore.
- [ ] **Step 6: Commit** `fix(tracker-auth): translate tagger-client library errors to ApiError so the grab tag-failure swallow works`

---

### Sub-phase 3.2 — De-vacuum the orchestrator tag-failure test (fixes major #2 test side)

**Files:**

- Modify: `tests/acquire/test_grab_transmission_add.py`

- [ ] **Step 1.** Keep the existing orchestrator-level swallow test (inject `ApiError` → success, not `add_failed`) — it is now CORRECT given 3.1 makes the client raise `ApiError`. Add a complementary assertion or comment documenting that 3.1 guarantees `add_tags` raises `ApiError` (the type the swallow catches), so the end-to-end chain (raw library error → `ApiError` → swallowed) is closed by 3.1's client test + this orchestrator test together.
- [ ] **Step 2: Run** the file → PASS. (No separate commit needed if trivial; fold into 3.1's commit OR commit `test(tracker-auth): document the tag-failure swallow chain` — executor's choice, one commit.)

---

### Sub-phase 3.3 — Exercise the `TrackerAuthFailed` formatter (fixes medium #3)

**Files:**

- Modify: `tests/subscribers/test_acquire_subscriber.py` (import + `_ALL_ACQUIRE_EVENT_CLASSES` list at ~41-52)

- [ ] **Step 1.** Import `TrackerAuthFailed` (alphabetical in the acquire-events import block) and add it to the `_ALL_ACQUIRE_EVENT_CLASSES` list so the parametrized formatter tests (disabled / enabled-sends-once / structlog-discriminator) drive `_on_tracker_auth_failed`. The factory `make_tracker_auth_failed` already exists in `event_samples.py` and `_camel_to_snake('TrackerAuthFailed') == 'tracker_auth_failed'` matches the discriminator.
- [ ] **Step 2: Run** `command python -m pytest tests/subscribers/test_acquire_subscriber.py -q` → PASS (the list now has 11 entries; this is consistent with the token-pin already at 11).
- [ ] **Step 3: Commit** `test(tracker-auth): exercise TrackerAuthFailed Telegram formatter`

---

### Sub-phase 3.4 — Pin the non-`TorrentTagger` skip branch (fixes minor #4)

**Files:**

- Modify: `tests/acquire/test_orchestrator.py` (the golden happy-path test ~189-196)

- [ ] **Step 1.** Add an explicit `client.add_tags.assert_not_called()` — or assert the `MagicMock(spec=TorrentAdder)` client never had `add_tags` invoked — so the skip branch (`isinstance(client, TorrentTagger)` False → no tag) is a first-class assertion, not implicit MagicMock-spec behavior. (Fold into 3.3's commit or commit separately — executor's choice.)
- [ ] **Step 2: Run** the file → PASS.

---

### Sub-phase 3.5 — Phase gate

- [ ] **Step 1: Full gate** `make check` → ruff + mypy clean, `NNNN passed` (0 failed/errors), guardrails green.
- [ ] **Step 2: Smoke** `command python -c "import personalscraper; print('ok')"`.
- [ ] **Step 3: Acceptance** — re-run the tagger + grab + subscriber suites:
  ```
  command python -m pytest tests/api/torrent/test_tagger.py tests/acquire/test_grab_transmission_add.py tests/acquire/test_grab_auth_event.py tests/subscribers/test_acquire_subscriber.py tests/acquire/test_orchestrator.py -q
  ```
