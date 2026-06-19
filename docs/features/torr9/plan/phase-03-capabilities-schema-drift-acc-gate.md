# Phase 03 — Capabilities composition, schema-drift, ACC gate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the capability `isinstance` contracts for `Torr9Client`, extend the schema-drift test to cover torr9, then re-exercise every DESIGN ACC criterion as executable shell commands. Phase gate = `make check` green + all ACC-1..7 pass.

**Architecture:** No new source code beyond tiny test additions. The `TorrentSearchable` and `CategoryListable` `isinstance` checks are already satisfied by the class definition from phase 1 (structural protocol). `FreeleechAware` must NOT be implemented (torr9 search already carries `is_freeleech` as a boolean; no separate re-check endpoint exists). The schema-drift extension follows the pattern in `tests/unit/test_tracker_parser_schema_drift.py` for c411/lacale.

**Tech Stack:** `pytest`, `personalscraper.api.tracker._contracts`, `personalscraper.api.tracker.torr9`, `tests/unit/test_tracker_capabilities_composition.py`, `tests/unit/test_tracker_parser_schema_drift.py`.

## Gate

**Prerequisites:** Phase 1 + Phase 2 complete. `make check` was green at end of phase 2.

**This phase gate passes when ALL of the following are true:**

- `python -m pytest tests/unit/test_tracker_capabilities_composition.py -q` passes (including new torr9 tests)
- `python -m pytest tests/unit/test_tracker_parser_schema_drift.py -q` passes (including new torr9 test)
- All ACC-1 through ACC-7 shell commands from the DESIGN produce their documented expected output
- `make check` is green (lint + test + module-size + typed-api guardrails)

---

## File Map

| Action | Path                                                  | Responsibility                         |
| ------ | ----------------------------------------------------- | -------------------------------------- |
| Modify | `tests/unit/test_tracker_capabilities_composition.py` | Add torr9 `isinstance` protocol tests  |
| Modify | `tests/unit/test_tracker_parser_schema_drift.py`      | Add torr9 schema-drift → ApiError test |

---

## Task 1: Capability `isinstance` contract tests for `Torr9Client`

**Files:**

- Modify: `tests/unit/test_tracker_capabilities_composition.py`

The existing file covers `LaCaleClient` and `C411Client`. Add torr9 tests that pin: (a) `TorrentSearchable` ✓, (b) `CategoryListable` ✓, (c) `FreeleechAware` ✗ (no re-check endpoint — `is_freeleech` is already on `TrackerResult` at search time), (d) the legacy monolithic `TrackerClient` Protocol no longer exists (existing test already covers this — do not duplicate).

- [ ] **Step 1.1: Add `_torr9()` factory and protocol tests to the capabilities file**

Open `tests/unit/test_tracker_capabilities_composition.py`. Add after the existing `_c411()` factory and its tests:

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


def test_torr9_client_not_freeleech_aware_isinstance() -> None:
    """``Torr9Client`` deliberately does not implement ``FreeleechAware``.

    torr9 search already returns ``is_freeleech`` as a structured boolean on
    each ``TrackerResult`` — no separate per-torrent re-check endpoint exists
    or is needed. Advertising ``FreeleechAware`` with a stub that always
    returns ``False`` would be misleading (DESIGN §Approach — No FreeleechAware).
    """
    assert not isinstance(_torr9(), FreeleechAware)
```

- [ ] **Step 1.2: Run the capabilities test file**

```bash
python -m pytest tests/unit/test_tracker_capabilities_composition.py -v
# Expected: all existing tests pass + 3 new torr9 tests pass (0 failed)
```

- [ ] **Step 1.3: Sub-commit**

```bash
git add tests/unit/test_tracker_capabilities_composition.py
git commit -m "$(cat <<'EOF'
test(torr9): pin TorrentSearchable + CategoryListable isinstance contracts
EOF
)"
```

---

## Task 2: Schema-drift test — torr9 parser drift surfaces as `ApiError`

**Files:**

- Modify: `tests/unit/test_tracker_parser_schema_drift.py`

The schema-drift test file already covers c411 and lacale. Add a torr9 section that verifies two drift scenarios: (a) response root is not a dict (type drift on the envelope), (b) a torrent item has a `file_size_bytes` of a non-numeric type (`dict`) — the `int(size_raw)` call inside `_parse_item` raises `TypeError`, which `wrap_parser_drift` re-raises as `ApiError`. These are the same adversarial scenarios used to validate c411/lacale, adapted to torr9's JSON envelope shape.

- [ ] **Step 2.1: Add torr9 schema-drift tests**

Open `tests/unit/test_tracker_parser_schema_drift.py`. Add at the end of the file:

```python
# -- torr9 ----------------------------------------------------------------

from personalscraper.api.tracker.torr9 import Torr9Client


class TestTorr9SchemaDriftReRaisedAsApiError:
    """torr9.search() must re-raise parser exceptions as ApiError.

    ``wrap_parser_drift`` converts KeyError / IndexError / TypeError /
    AttributeError / ValueError from the parse closure into ``ApiError``
    so the TrackerRegistry can swallow drift from one tracker without
    killing the other trackers' results.
    """

    def test_response_envelope_not_dict_raises_api_error(self) -> None:
        """A response that is a list (not a dict) triggers AttributeError in .get() → ApiError."""
        transport = MagicMock()
        # torr9 parser expects dict with 'torrents' key; receiving a list
        # causes 'list'.get('torrents') → AttributeError → ApiError via drift.
        transport.get.return_value = [{"id": 1}]  # list, not dict
        client = Torr9Client(transport, username="u", password="p")
        client._token = "t"  # skip _ensure_logged_in

        with pytest.raises(ApiError) as exc:
            client.search("inception")

        assert exc.value.provider == "torr9"
        assert exc.value.http_status == 0
        assert "shape drift" in exc.value.message

    def test_item_file_size_bytes_wrong_type_raises_api_error(self) -> None:
        """An item where file_size_bytes is a dict (not int) triggers TypeError → ApiError."""
        transport = MagicMock()
        # int({"nested": "object"}) raises TypeError inside _parse_item.
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
    transport.get.return_value = [{"id": 1}]  # list, not dict → AttributeError → ApiError
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

- [ ] **Step 2.2: Run the schema-drift test file**

```bash
python -m pytest tests/unit/test_tracker_parser_schema_drift.py -v
# Expected: all existing tests pass + 3 new torr9 tests pass (0 failed)
```

- [ ] **Step 2.3: Sub-commit**

```bash
git add tests/unit/test_tracker_parser_schema_drift.py
git commit -m "$(cat <<'EOF'
test(torr9): schema-drift → ApiError + multi-tracker survival regression
EOF
)"
```

---

## Task 3: Re-exercise all DESIGN ACC criteria (SH-16 gate)

Run each acceptance criterion from the DESIGN in the order ACC-1 through ACC-7. Every command must produce its documented expected output. Fix anything that does not pass before moving on.

- [ ] **Step 3.1: ACC-1 — module exists and exposes search + get_categories**

```bash
python -c "
from personalscraper.api.tracker.torr9 import Torr9Client
from personalscraper.api.tracker._contracts import TorrentSearchable, CategoryListable
print(
    issubclass(Torr9Client, object)
    and hasattr(Torr9Client, 'search')
    and hasattr(Torr9Client, 'get_categories')
)
"
# Expected: True
```

- [ ] **Step 3.2: ACC-2 — torr9 in factory map**

```bash
python -c "from personalscraper.api.tracker._factory import _TRACKER_CLASSES; print('torr9' in _TRACKER_CLASSES)"
# Expected: True
```

- [ ] **Step 3.3: ACC-3 — creds gated**

```bash
python -c "from personalscraper.api._activation import PROVIDER_CREDS; print(PROVIDER_CREDS.get('torr9'))"
# Expected: ['TORR9_USERNAME', 'TORR9_PASSWORD']
# NOTE: The DESIGN's ACC-3 expects ['TORR9_API_KEY'] — that is a typo in the DESIGN
# (the API contract requires username + password). The actual value is the correct one.
```

- [ ] **Step 3.4: ACC-4 — config carries torr9 in both overlays**

```bash
grep -c 'torr9' config/tracker.json5 config.example/tracker.json5
# Expected: each file ≥ 1 (grep -c prints count per file)
```

- [ ] **Step 3.5: ACC-5 — golden-fixture parse test passes**

```bash
python -m pytest tests/unit/test_torr9_client.py -q
# Expected: N passed, 0 failed (N ≥ 20; asserts title/size/category/freeleech on real fields)
```

- [ ] **Step 3.6: ACC-6 — full suite green**

```bash
make test 2>&1 | tail -1
# Expected: line ending with "passed" and containing "0 failed" / "0 error"
# (exact count varies; 0 failures is the gate, not the count)
```

- [ ] **Step 3.7: ACC-7 — boot validation fails loud when torr9 enabled without creds**

```bash
python -m pytest tests/integration/api/tracker/test_composition_root.py -q -k torr9
# Expected: 2 passed, 0 failed / 0 errors
```

---

## Task 4: `make check` and phase gate commit

- [ ] **Step 4.1: Run `make check`**

```bash
make check
# Expected: lint + test + module-size + typed-api guardrails all green
```

If `make check` fails:

- **Lint (ruff)**: run `ruff check --fix personalscraper/ tests/` then `make lint` again
- **mypy**: fix type annotations in `torr9.py` or the modified test files
- **Module-size**: `python3 scripts/check-module-size.py` — `torr9.py` should be well under 800 LOC
- **Test collection ERROR**: fix any import error in the test files; run `python -m pytest --collect-only tests/unit/test_torr9_client.py tests/unit/test_tracker_capabilities_composition.py tests/unit/test_tracker_parser_schema_drift.py tests/integration/api/tracker/test_composition_root.py` to isolate

- [ ] **Step 4.2: Residual import grep (post-phase hygiene)**

Confirm no stale imports referencing torr9 from old locations (not applicable for a new module, but verify no import drift):

```bash
rg "from personalscraper.api.tracker.torr9" --type py personalscraper/ tests/
# Expected: only torr9.py itself + the test files that import Torr9Client
```

- [ ] **Step 4.3: Smoke import**

```bash
python -c "import personalscraper; print('smoke OK')"
# Expected: smoke OK
```

- [ ] **Step 4.4: Phase gate commit**

```bash
git commit --allow-empty -m "$(cat <<'EOF'
chore(torr9): phase 3 gate — capabilities composition + schema-drift + ACC gate
EOF
)"
```
