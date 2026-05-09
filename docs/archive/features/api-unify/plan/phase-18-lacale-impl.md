# Phase 18 — LaCale Implementation

**Type**: impl
**Goal**: Implement `api/tracker/lacale.py`.

## Gate (prereq)

Phase 17 complete.

## Sub-phases

### 18.1 — Build `api/tracker/lacale.py`

```python
class LaCaleClient:
    REQUIRED_CREDS: ClassVar[list[str]] = ["LACALE_API_KEY"]
    provider_name = "lacale"

    @classmethod
    def policy(cls, api_key: str) -> TransportPolicy:
        return TransportPolicy(
            provider_name="lacale",
            base_url="<from doc>",
            auth=ApiKeyAuth(api_key, param="<from doc>", location="<from doc>"),
            timeout_seconds=15,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
            rate_limit=RateLimitPolicy(requests_per_second=2),  # defensive default
        )

    def __init__(self, transport: HttpTransport) -> None:
        self._transport = transport

    def search(self, query, media_type="movie", year=None) -> list[TrackerResult]: ...
    def get_categories(self) -> dict[str, str]: ...

    @staticmethod
    def _parse_title(title: str) -> dict[str, str | None]:
        """Extract resolution / codec / source / audio / format from torrent title."""
```

Map response fields → `TrackerResult`:

- `size` → `ByteSize.parse(raw_size)`.
- `freeleech / silverleech` flags.
- Title regex extraction for codec/resolution/source/audio when API doesn't surface them.

Target ≤ 250 LOC.

**Commit**: `feat(api-unify): add LaCale tracker client`

### 18.2 — Tests

`tests/unit/test_lacale_client.py`:

- `search()` returns typed `TrackerResult` list with `ByteSize` size field.
- `_parse_title("Inception.2010.2160p.UHD.BluRay.x265.HDR.TrueHD-NCmt.mkv")` extracts all fields.
- `_parse_title("Random.title.no.metadata.mkv")` returns mostly Nones.
- API key is sent in correct location (header or query) per Phase 17 decision.

Golden response files from Phase 17 samples used in mocks.

**Commit**: `test(api-unify): add LaCale client tests`

### 18.3 — Phase 18 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.tracker.lacale import LaCaleClient"
```

**Commit**: `chore(api-unify): phase 18 gate — lacale done`
