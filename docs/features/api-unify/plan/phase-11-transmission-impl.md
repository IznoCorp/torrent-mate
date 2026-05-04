# Phase 11 — Transmission Implementation

**Type**: impl
**Goal**: Implement `api/torrent/transmission.py`, wire factory, tests.

## Gate (prereq)

Phase 10 complete. `docs/reference/transmission-api.md` exists. User chose Option A or B.

## Sub-phases

### 11.1 — Add `transmission-rpc` dependency

Update `pyproject.toml` `[project.dependencies]`. Run `pip install -e .[dev]`. Verify import.

**Commit**: `chore(api-unify): add transmission-rpc dependency`

### 11.2 — Build `api/torrent/transmission.py`

Per user-chosen option from Phase 10:

**Option A (recommended, only if confirmed by Phase 10 doc)** — pre-check via HttpTransport, ops via library:

```python
class TransmissionClient:
    REQUIRED_CREDS: ClassVar[list[str]] = ["TRANSMISSION_USERNAME", "TRANSMISSION_PASSWORD"]

    @classmethod
    def policy(cls, host: str, port: int, username: str, password: str) -> TransportPolicy:
        return TransportPolicy(
            provider_name="transmission-precheck",
            base_url=f"http://{host}:{port}",
            auth=LoginAuth(username, password),
            timeout_seconds=5,
            retry=RetryPolicy(max_attempts=2),
            circuit=CircuitPolicy(failure_threshold=3, cooldown_seconds=60),
        )

    def __init__(self, transport: HttpTransport, host: str, port: int,
                 username: str, password: str) -> None:
        self._transport = transport
        # Pre-check reachability.
        # Exact endpoint and acceptable status codes MUST come from Phase 10 doc.
        # Prefer /transmission/rpc if the doc confirms CSRF 409 behavior; do not
        # use /transmission/web/ unless the doc confirms it returns a JSON-compatible
        # response or response_format is set appropriately.
        try:
            self._transport.get("/transmission/rpc")
        except ApiError as e:
            if e.http_status == 401:
                raise  # creds wrong
            # 409 = CSRF, normal — library will handle it
            if e.http_status != 409:
                raise

        self._client = transmission_rpc.Client(
            host=host, port=port, username=username, password=password
        )
```

Implements `TorrentClient`:

- `get_completed()` — `self._client.get_torrents(...)` filtered by status in {5, 6}; map to `TorrentItem`.
- `get_all_hashes()` — set of hashStrings.
- `is_seeding(t)` — status == 6.
- `get_content_path(t)` — `Path(t.download_dir) / t.name`.
- `pause(hash)` → `stop_torrent`.
- `resume(hash)` → `start_torrent`.
- `delete(hash, delete_files)` → `remove_torrent(delete_data=delete_files)`.

### 11.3 — Wire factory

`build_active_torrent_client`: add `if cfg.active == "transmission"` branch.

### 11.4 — Tests

- `tests/unit/test_transmission_client.py` — mock `transmission_rpc.Client`, verify `TorrentItem` mapping (status enum, percentDone × 100, etc.).
- `tests/integration/test_transport_factory.py` — switch active=transmission via config, verify factory returns `TransmissionClient`.
- Pre-check test mirrors the endpoint/status-code decision captured in Phase 10 doc. If the chosen pre-check endpoint returns HTML/text, set `TransportPolicy.response_format` accordingly and add the parser branch before this phase gate.

### 11.5 — Phase 11 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.torrent.transmission import TransmissionClient"
python -c "from personalscraper.api.torrent._factory import build_active_torrent_client"
```

**Commit**: `chore(api-unify): phase 11 gate — transmission done`
