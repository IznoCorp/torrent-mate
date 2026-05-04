# Phase 20 — C411 Implementation

**Type**: impl
**Goal**: Implement `api/tracker/c411.py`. If Phase 19 chose Option A (XML in transport), retrofit `HttpTransport` first.

## Gate (prereq)

Phase 19 complete. User chose Option A or B.

## Sub-phases

### 20.1 (conditional) — XML support in HttpTransport (if Option A)

If user chose Option A:

- Add `xmltodict` dependency.
- Extend `TransportPolicy.response_format` type from `Literal["json"]` to `Literal["json", "xml"]` (the field already exists since Phase 1).
- In `HttpTransport._do_request`, add branch: `if self._policy.response_format == "xml": return xmltodict.parse(resp.text)`.
- Update Phase 1 reference test to also cover XML parsing path.

**Commit**: `feat(api-unify): add XML response support to HttpTransport`

If Option B chosen, skip this sub-phase.

### 20.2 — Build `api/tracker/c411.py`

```python
class C411Client:
    REQUIRED_CREDS: ClassVar[list[str]] = ["C411_API_KEY"]
    provider_name = "c411"

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy: ...

    def search(self, query, media_type="movie", year=None) -> list[TrackerResult]: ...
    def get_categories(self) -> dict[str, str]: ...
```

Reuse `_parse_title` helper. Consider extracting to `api/tracker/_title_parser.py` if both LaCale and C411 use it (DRY).

If extraction makes sense:

```bash
# Move helper from lacale.py to _title_parser.py, both clients import it.
```

This may amend Phase 18's `lacale.py` — do it in the same commit.

### 20.3 — Tests

`tests/unit/test_c411_client.py` — same shape as LaCale tests.

If `_title_parser.py` extracted, add `tests/unit/test_title_parser.py` covering edge cases.

### 20.4 — Phase 20 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.tracker.c411 import C411Client"
```

**Commit**: `chore(api-unify): phase 20 gate — c411 done`
