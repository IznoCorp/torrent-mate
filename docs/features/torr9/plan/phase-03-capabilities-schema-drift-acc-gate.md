# Phase 03 — FreeleechAware re-check, capabilities, schema-drift, ACC gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `FreeleechAware` capability on `Torr9Client` via the
**live-confirmed** per-torrent detail endpoint (`GET /api/v1/torrents/{id}`), pin the
capability `isinstance` contracts (now `TorrentSearchable + CategoryListable +
FreeleechAware`), extend the schema-drift test to torr9, then re-exercise every DESIGN
ACC criterion (ACC-1..8). Phase gate = `make check` green + all ACC pass.

**Architecture:** `FreeleechAware` requires `is_freeleech(self, torrent_id: str) -> bool`
— a pre-download re-check distinct from the search-time `is_freeleech` field on
`TrackerResult`. Unlike c411/lacale (which deliberately do NOT implement it — no detail
endpoint), torr9 **does** expose `GET /api/v1/torrents/{id}` returning a single-torrent
object whose `is_freeleech` reflects the current state. `is_freeleech()` mirrors
`search()`'s lazy-login + re-login-on-401 (RP7) and wraps the bool extraction in
`wrap_parser_drift`. `FreeleechAware` is `@runtime_checkable`, so adding the method (and
the base) makes `isinstance(torr9, FreeleechAware)` True. **User decision (2026-06-19):
implement FreeleechAware to match DESIGN §Approach §1** — and the live detail endpoint
makes it a genuine re-check, not a stub.

**Tech Stack:** `personalscraper/api/tracker/torr9.py`, `tests/unit/test_torr9_client.py`,
`tests/unit/test_tracker_capabilities_composition.py`,
`tests/unit/test_tracker_parser_schema_drift.py`, golden fixture
`docs/reference/_samples/torr9/torr9_detail.json` (already captured), `pytest`,
`unittest.mock`.

## Gate

**Prerequisites:** Phase 1 + Phase 2 complete. `make check` was green at end of phase 2.
The detail fixture `docs/reference/_samples/torr9/torr9_detail.json` exists (committed
with the design reconciliation).

**This phase gate passes when ALL of the following are true:**

- `python -m pytest tests/unit/test_torr9_client.py -q` passes (incl. new is_freeleech tests)
- `python -m pytest tests/unit/test_tracker_capabilities_composition.py -q` passes (incl. torr9)
- `python -m pytest tests/unit/test_tracker_parser_schema_drift.py -q` passes (incl. torr9)
- All ACC-1 through ACC-8 shell commands from the DESIGN produce their expected output
- `make check` is green (lint + test + module-size + typed-api guardrails)

---

## File Map

| Action | Path                                                  | Responsibility                                                          |
| ------ | ----------------------------------------------------- | ----------------------------------------------------------------------- |
| Modify | `personalscraper/api/tracker/torr9.py`                | Add `FreeleechAware` base + `is_freeleech(torrent_id)` re-check         |
| Modify | `tests/unit/test_torr9_client.py`                     | `is_freeleech` golden tests (detail fixture) + re-login-on-401          |
| Modify | `tests/unit/test_tracker_capabilities_composition.py` | torr9 `isinstance` tests (TorrentSearchable+CategoryListable+Freeleech) |
| Modify | `tests/unit/test_tracker_parser_schema_drift.py`      | torr9 schema-drift → ApiError test                                      |

---

## Task 1: Implement `FreeleechAware.is_freeleech()` on `Torr9Client`

**Files:**

- Modify: `personalscraper/api/tracker/torr9.py`

Add `FreeleechAware` to the `_contracts` import and to the class bases; replace the
class docstring's "does NOT implement FreeleechAware" paragraph; add the `is_freeleech`
method after `search()` (or after `_parse_item`/`get_categories`).

- [ ] **Step 1.1: Add `FreeleechAware` to the import**

In the `from personalscraper.api.tracker._contracts import (...)` block, add `FreeleechAware`:

```python
from personalscraper.api.tracker._contracts import (
    CategoryListable,
    FreeleechAware,
    TorrentSearchable,
)
```

- [ ] **Step 1.2: Add `FreeleechAware` to the class bases + fix the docstring**

Change the class declaration and its docstring:

```python
class Torr9Client(TorrentSearchable, CategoryListable, FreeleechAware):
    """torr9 tracker API client — authenticated JSON API with JWT login.

    Composes :class:`~personalscraper.api.tracker._contracts.TorrentSearchable`,
    :class:`~personalscraper.api.tracker._contracts.CategoryListable`, and
    :class:`~personalscraper.api.tracker._contracts.FreeleechAware`.
    Auth is lazy JWT login (POST /auth/login) with re-login on 401 (RP7).

    Unlike c411/lacale (no per-torrent detail endpoint), torr9 exposes
    ``GET /api/v1/torrents/{id}`` (live-confirmed), so ``is_freeleech`` is a
    genuine pre-download re-check, not a stub.
    """
```

- [ ] **Step 1.3: Add the `is_freeleech` method** (place it after `search()`)

```python
    def is_freeleech(self, torrent_id: str) -> bool:
        """Re-check whether a torrent is currently freeleech (FreeleechAware).

        Pre-download re-check via the per-torrent detail endpoint
        ``GET /api/v1/torrents/{id}`` (live-confirmed 2026-06-19). Distinct from
        the ``is_freeleech`` field captured at search time on ``TrackerResult`` —
        this surfaces a flag that flipped asynchronously. Logs in lazily and
        re-logins once on 401 (RP7 auth-lifecycle), mirroring ``search()``.

        Args:
            torrent_id: The torr9 numeric torrent id (as a string).

        Returns:
            True if the detail payload reports freeleech; False otherwise
            (including when the ``is_freeleech`` field is absent).

        Raises:
            ApiError: On a non-401 transport error, a 401 surviving one re-login
                (bad creds → fail-loud), or a malformed (non-dict) detail payload
                (surfaced via ``wrap_parser_drift``).
        """
        self._ensure_logged_in()
        path = f"/api/v1/torrents/{torrent_id}"

        try:
            raw = self._transport.get(path=path)
        except ApiError as exc:
            if exc.http_status == 401:
                # RP7: token expired — re-login once and retry the detail GET.
                log.info("torr9_relogin_on_401", provider=self.provider_name)
                self._token = None
                self._login()
                raw = self._transport.get(path=path)
            else:
                raise

        def _parse() -> bool:
            data = cast("dict[str, Any]", raw)
            return bool(data.get("is_freeleech", False))

        return wrap_parser_drift(self.provider_name, _parse)
```

- [ ] **Step 1.4: Lint + smoke**

```bash
make lint
python -c "from personalscraper.api.tracker.torr9 import Torr9Client; from personalscraper.api.tracker._contracts import FreeleechAware; import unittest.mock as m; print(isinstance(Torr9Client(m.MagicMock(), username='u', password='p'), FreeleechAware))"
# Expected: make lint 0 errors; print True
```

---

## Task 2: `is_freeleech` golden tests (detail fixture, anti-vacuity)

**Files:**

- Modify: `tests/unit/test_torr9_client.py`

Add a test class using the real captured `torr9_detail.json`. `_load` already exists in
the file (returns `object`); narrow with `assert isinstance(..., dict)` before mutating
so mypy stays happy.

- [ ] **Step 2.1: Add `TestTorr9FreeleechRecheck`** (after the existing test classes)

```python
class TestTorr9FreeleechRecheck:
    """is_freeleech(torrent_id) — pre-download re-check via GET /torrents/{id}.

    Anti-vacuity: asserts the re-check reads the real detail payload's
    is_freeleech field (golden fixture), the correct path, and the re-login path.
    """

    def test_is_freeleech_false_from_detail_fixture(self) -> None:
        """Re-check returns False from the real torr9_detail.json (id 305292)."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_detail.json")  # type: ignore[attr-defined]
        assert client.is_freeleech("305292") is False

    def test_is_freeleech_true_when_detail_flag_true(self) -> None:
        """Re-check returns True when the detail payload reports freeleech."""
        client = _make_client()
        client._token = "t"
        detail = _load("torr9_detail.json")
        assert isinstance(detail, dict)  # narrow for mypy before mutating
        detail["is_freeleech"] = True
        client._transport.get.return_value = detail  # type: ignore[attr-defined]
        assert client.is_freeleech("305292") is True

    def test_is_freeleech_hits_detail_path(self) -> None:
        """Re-check calls GET /api/v1/torrents/{id}."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = {"id": 999, "is_freeleech": False}  # type: ignore[attr-defined]
        client.is_freeleech("999")
        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/v1/torrents/999"

    def test_is_freeleech_missing_field_defaults_false(self) -> None:
        """A detail payload without is_freeleech defaults to False (graceful)."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = {"id": 1, "title": "x"}  # type: ignore[attr-defined]
        assert client.is_freeleech("1") is False

    def test_is_freeleech_relogin_on_401(self) -> None:
        """A 401 on the detail GET triggers re-login and a single retry."""
        client = _make_client()
        client._token = "stale"
        call_count = 0

        def _side_effect(**kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ApiError(provider="torr9", http_status=401, message="Missing authorization token")
            return {"id": 1, "is_freeleech": True}

        client._transport.get.side_effect = _side_effect  # type: ignore[attr-defined]
        client._transport.post.return_value = {"token": "new-jwt"}  # type: ignore[attr-defined]

        assert client.is_freeleech("305292") is True
        assert client._transport.post.call_count == 1  # type: ignore[attr-defined]

    def test_is_freeleech_non_dict_payload_raises_api_error(self) -> None:
        """A non-dict detail payload surfaces as ApiError via wrap_parser_drift."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = [1, 2, 3]  # type: ignore[attr-defined]
        with pytest.raises(ApiError) as exc:
            client.is_freeleech("1")
        assert exc.value.provider == "torr9"
        assert "shape drift" in exc.value.message
```

- [ ] **Step 2.2: Run**

```bash
python -m pytest tests/unit/test_torr9_client.py -q
# Expected: all pass (phase-1 tests + 6 new is_freeleech tests), 0 failed
```

- [ ] **Step 2.3: Sub-commit (Task 1 + Task 2 together — same unit)**

```bash
git add personalscraper/api/tracker/torr9.py tests/unit/test_torr9_client.py
git commit -m "$(cat <<'EOF'
feat(torr9): FreeleechAware via GET /torrents/{id} detail re-check + golden tests
EOF
)"
```

---

## Task 3: Capability `isinstance` contract tests for `Torr9Client`

**Files:**

- Modify: `tests/unit/test_tracker_capabilities_composition.py`

Pin: (a) `TorrentSearchable` ✓, (b) `CategoryListable` ✓, (c) `FreeleechAware` ✓ (now
implemented via the detail re-check). Ensure `FreeleechAware` is imported in the file
(it likely already is — used by the c411 "not freeleech aware" test).

- [ ] **Step 3.1: Add `_torr9()` factory and protocol tests**

```python
from personalscraper.api.tracker.torr9 import Torr9Client


def _torr9() -> Torr9Client:
    transport = MagicMock()
    return Torr9Client(transport=transport, username="u", password="p")


def test_torr9_client_is_torrent_searchable_isinstance() -> None:
    """``Torr9Client`` satisfies the ``TorrentSearchable`` capability."""
    assert isinstance(_torr9(), TorrentSearchable)


def test_torr9_client_is_category_listable_isinstance() -> None:
    """``Torr9Client`` satisfies the ``CategoryListable`` capability."""
    assert isinstance(_torr9(), CategoryListable)


def test_torr9_client_is_freeleech_aware_isinstance() -> None:
    """``Torr9Client`` satisfies ``FreeleechAware`` — torr9 exposes a real
    per-torrent detail endpoint (``GET /torrents/{id}``) so ``is_freeleech`` is a
    genuine pre-download re-check (DESIGN §Approach §1; user decision 2026-06-19).
    """
    assert isinstance(_torr9(), FreeleechAware)
    assert hasattr(_torr9(), "is_freeleech")
```

- [ ] **Step 3.2: Run + sub-commit**

```bash
python -m pytest tests/unit/test_tracker_capabilities_composition.py -q
# Expected: all pass + 3 new torr9 tests
git add tests/unit/test_tracker_capabilities_composition.py
git commit -m "$(cat <<'EOF'
test(torr9): pin TorrentSearchable + CategoryListable + FreeleechAware contracts
EOF
)"
```

---

## Task 4: Schema-drift test — torr9 parser drift surfaces as `ApiError`

**Files:**

- Modify: `tests/unit/test_tracker_parser_schema_drift.py`

Same as the original phase-3 plan. Verify two search drift scenarios: (a) response root
is a list (AttributeError on `.get`), (b) item `file_size_bytes` is a dict (TypeError on
`int`). Both re-raised as `ApiError` via `wrap_parser_drift`.

- [ ] **Step 4.1: Add torr9 schema-drift tests** (at end of file)

```python
# -- torr9 ----------------------------------------------------------------

from personalscraper.api.tracker.torr9 import Torr9Client


class TestTorr9SchemaDriftReRaisedAsApiError:
    """torr9.search() must re-raise parser exceptions as ApiError."""

    def test_response_envelope_not_dict_raises_api_error(self) -> None:
        """A response that is a list (not a dict) → AttributeError → ApiError."""
        transport = MagicMock()
        transport.get.return_value = [{"id": 1}]  # list, not dict
        client = Torr9Client(transport, username="u", password="p")
        client._token = "t"

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "torr9"
        assert exc.value.http_status == 0
        assert "shape drift" in exc.value.message

    def test_item_file_size_bytes_wrong_type_raises_api_error(self) -> None:
        """An item where file_size_bytes is a dict → TypeError → ApiError."""
        transport = MagicMock()
        transport.get.return_value = {
            "torrents": [
                {
                    "id": 1,
                    "title": "x",
                    "file_size_bytes": {"nested": "object"},
                    "magnet_link": "magnet:?xt=urn:btih:aaa",
                    "is_freeleech": False,
                    "upload_date": None,
                    "category_id": 5,
                    "info_hash": "aaa",
                }
            ],
            "page": 1,
            "limit": 20,
        }
        client = Torr9Client(transport, username="u", password="p")
        client._token = "t"

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "torr9"
        assert "shape drift" in exc.value.message


def test_torr9_schema_drift_does_not_abort_multi_tracker_search() -> None:
    """End-to-end: torr9 parser blowing up must not kill other trackers' results."""
    transport = MagicMock()
    transport.get.return_value = [{"id": 1}]  # list, not dict → ApiError
    bad_torr9 = Torr9Client(transport, username="u", password="p")
    bad_torr9._token = "t"
    good = _OkTracker("lacale")

    registry = TrackerRegistry(
        trackers={"torr9": bad_torr9, "lacale": good},  # type: ignore[dict-item]
        priority=["torr9", "lacale"],
        ranking=RankingConfig(min_seeders=0),
    )

    ranked = registry.search_all("Inception")

    assert len(ranked) == 1, f"Expected lacale's result to survive torr9 drift; got {ranked!r}"
    assert ranked[0][0].provider == "lacale"
```

> **Note:** If `_OkTracker`, `TrackerRegistry`, `RankingConfig`, `ApiError`, `MagicMock`,
> `pytest` are not already imported at module scope in this file, check the existing
> c411/lacale sections and reuse their imports. The `RankingConfig(min_seeders=0)`
> signature must match the existing usage — if `min_seeders` is not a field, copy the
> exact `RankingConfig(...)` the c411 multi-tracker test uses.

- [ ] **Step 4.2: Run + sub-commit**

```bash
python -m pytest tests/unit/test_tracker_parser_schema_drift.py -q
# Expected: all pass + 3 new torr9 tests
git add tests/unit/test_tracker_parser_schema_drift.py
git commit -m "$(cat <<'EOF'
test(torr9): schema-drift → ApiError + multi-tracker survival regression
EOF
)"
```

---

## Task 5: Re-exercise all DESIGN ACC criteria (SH-16 gate)

Run each criterion ACC-1 through ACC-8. Every command must produce its documented
expected output.

- [ ] **Step 5.1: ACC-1** — module exists + search + get_categories → `True`
- [ ] **Step 5.2: ACC-2** — `'torr9' in _TRACKER_CLASSES` → `True`
- [ ] **Step 5.3: ACC-3** — `PROVIDER_CREDS.get('torr9')` → `['TORR9_USERNAME', 'TORR9_PASSWORD']`
- [ ] **Step 5.4: ACC-4** — `grep -c 'torr9' config/tracker.json5 config.example/tracker.json5` → ≥1 each
- [ ] **Step 5.5: ACC-5** — `pytest tests/unit/test_torr9_client.py -q` → 0 failed
- [ ] **Step 5.6: ACC-6** — `make test 2>&1 | tail -1` → "NNNN passed", 0 failed
- [ ] **Step 5.7: ACC-7** — `pytest tests/integration/api/tracker/test_composition_root.py -q -k torr9` → passed
- [ ] **Step 5.8: ACC-8** — FreeleechAware:

```bash
python -c "from personalscraper.api.tracker.torr9 import Torr9Client; from personalscraper.api.tracker._contracts import FreeleechAware; t=Torr9Client(__import__('unittest.mock',fromlist=['MagicMock']).MagicMock(), username='u', password='p'); print(isinstance(t, FreeleechAware) and hasattr(Torr9Client,'is_freeleech'))"
# Expected: True
```

---

## Task 6: `make check` and phase gate commit

- [ ] **Step 6.1: Run `make check`** — lint + test + module-size + typed-api all green
- [ ] **Step 6.2: Residual import grep**

```bash
rg "from personalscraper.api.tracker.torr9" --type py personalscraper/ tests/
# Expected: torr9.py itself + the test files that import Torr9Client
```

- [ ] **Step 6.3: Smoke import** — `python -c "import personalscraper; print('smoke OK')"`
- [ ] **Step 6.4: Phase gate commit** — the orchestrator (main session) makes the
      milestone gate commit with the IMPLEMENTATION.md `[x]` update. Do NOT make an empty
      gate commit here.
