# Phase 20 — C411 Implementation

**Type**: impl
**Goal**: Implement `api/tracker/c411.py` using the response-format decision captured in Phase 19.

## Gate (prereq)

Phase 19 complete. User chose Option A or B. `HttpTransport` already supports
`response_format="xml"` from Phase 1.

## Sub-phases

### 20.1 — Build `api/tracker/c411.py`

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

**Commit**: `feat(api-unify): add C411 tracker client` (or `refactor(api-unify): extract _title_parser shared between LaCale and C411` if extraction is taken)

### 20.2 — Tests

`tests/unit/test_c411_client.py` — same shape as LaCale tests.

If `_title_parser.py` extracted, add `tests/unit/test_title_parser.py` covering edge cases.

**Commit**: `test(api-unify): add C411 client tests`

### 20.3 — Phase 20 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.tracker.c411 import C411Client"
```

**Commit**: `chore(api-unify): phase 20 gate — c411 done`
