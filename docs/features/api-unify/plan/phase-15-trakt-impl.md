# Phase 15 — Trakt Implementation

**Type**: impl
**Goal**: Implement `api/metadata/trakt.py` (header auth + extra header).

## Gate (prereq)

Phase 14 complete.

## Sub-phases

### 15.1 — Build `api/metadata/trakt.py`

```python
class TraktClient(MetadataClient):
    # App-only auth (search/details/ratings/related/trending) requires only
    # CLIENT_ID. CLIENT_SECRET belongs to the OAuth user-flow which is out
    # of scope per DESIGN §1.2 + Phase 14 doc decision; do NOT add it.
    # `_activation.py` PROVIDER_CREDS["trakt"] mirrors this single-entry list.
    REQUIRED_CREDS: ClassVar[list[str]] = ["TRAKT_CLIENT_ID"]

    @classmethod
    def policy(cls, client_id: str) -> TransportPolicy:
        return TransportPolicy(
            provider_name="trakt",
            base_url="https://api.trakt.tv",
            auth=ApiKeyAuth(client_id, param="trakt-api-key", location="header"),
            timeout_seconds=10,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
            rate_limit=RateLimitPolicy(requests_per_second=5),
            extra_headers={"trakt-api-version": "2", "Content-Type": "application/json"},
        )

    def search(self, title, year=None, media_type="movie") -> list[SearchResult]: ...
    def get_details(self, media_id, media_type="movie") -> MediaDetails: ...
    def get_notations(self, media_id, media_type="movie") -> Notations | None: ...
    def get_recommendations(self, media_id, media_type="movie") -> list[Recommendation]: ...
    def get_trending(self, media_type="movie", limit=20) -> list[SearchResult]: ...
```

Implementation notes:

- ID resolution per Phase 14 decision (accept slug | imdb | trakt_id).
- Trending response wrapper unwrapping: `result["movie"]` or `result["show"]`.
- `Notations.source = "trakt"`, `score` is 0–10 float, `votes_count` from `votes` field.

Target ≤ 250 LOC. Extract `_trakt_parsers.py` if it grows.

**Commit**: `feat(api-unify): add Trakt metadata client`

### 15.2 — Tests

`tests/unit/test_trakt_client.py`:

- Both `trakt-api-key` and `trakt-api-version: 2` headers present (verify via `responses`).
- `search()` mock → typed list.
- `get_notations()` mock → `Notations(source="trakt", score=8.5, votes_count=12345)`.
- `get_recommendations()` mock → list of `Recommendation`.
- `get_trending()` unwraps `{"watchers": N, "movie": {...}}`.

**Commit**: `test(api-unify): add Trakt client tests`

### 15.3 — Phase 15 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata.trakt import TraktClient"
```

**Commit**: `chore(api-unify): phase 15 gate — trakt done`
