# Phase 13 — OMDB Implementation

**Type**: impl
**Goal**: Implement `api/metadata/omdb.py` with query-param auth.

## Gate (prereq)

Phase 12 complete. User confirmed Response/Ratings handling.

## Sub-phases

### 13.1 — Build `api/metadata/omdb.py`

```python
class OMDBClient(MetadataClient):
    REQUIRED_CREDS: ClassVar[list[str]] = ["OMDB_API_KEY"]

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        return TransportPolicy(
            provider_name="omdb",
            base_url="https://www.omdbapi.com",
            auth=ApiKeyAuth(api_key, param="apikey", location="query"),
            timeout_seconds=10,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
        )

    def search(self, title, year=None, media_type="movie") -> list[SearchResult]: ...
    def get_details(self, media_id, media_type="movie") -> MediaDetails: ...
    def get_notations(self, media_id, media_type="movie") -> Notations | None: ...
    def get_recommendations(self, media_id, media_type="movie") -> list[Recommendation]:
        return []  # OMDB has no recommendations endpoint
```

Key implementation rules:

- **Response:False handling** per Phase 12 user decision (default: raise `ApiError(http_status=200, message=Error)`).
- `Ratings[]` parsing: dedicated `_parse_ratings(raw) -> list[Notations]` private helper, one entry per source.
- `Year` parsing: extract first 4-digit int, ignore range suffix.
- `Runtime` parsing: extract int from `"148 min"`.
- `"N/A"` sentinel: convert to `None`.

Target ≤ 200 LOC. Extract `_omdb_parsers.py` if it grows.

### 13.2 — Tests

`tests/unit/test_omdb_client.py`:

- `search()` with mocked HTTP returns typed `SearchResult` list.
- `get_details()` mocked → `MediaDetails` with parsed runtime/year.
- `get_notations()` returns IMDB + RT + Metacritic from `Ratings[]`.
- `Response:False` raises `ApiError`.
- `apikey` query param appears on every request (use `responses` library to assert URL).

### 13.3 — Phase 13 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata.omdb import OMDBClient"
```

**Commit**: `chore(api-unify): phase 13 gate — omdb done`
