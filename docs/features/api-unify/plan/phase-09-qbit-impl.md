# Phase 9 — qBittorrent Migration

**Type**: impl
**Goal**: Migrate `ingest/qbit_client.py` (212 LOC) → `api/torrent/qbittorrent.py`. Wire factory.

## Gate (prereq)

Phase 8 complete. `api/torrent/_base.py`, `_factory.py` exist. qBit doc + user checkpoint done.

## Sub-phases

### 9.1 — Build `api/torrent/qbittorrent.py`

Per DESIGN §5 + qBit doc:

```python
class QBitClient:
    REQUIRED_CREDS: ClassVar[list[str]] = ["QBIT_USERNAME", "QBIT_PASSWORD"]
    provider_name = "qbittorrent"

    @classmethod
    def policy(cls, host: str, port: int) -> TransportPolicy:
        return TransportPolicy(
            provider_name="qbittorrent-precheck",
            base_url=f"http://{host}:{port}",
            auth=NoAuth(),
            timeout_seconds=5,
            retry=RetryPolicy(max_attempts=2),  # pre-check is cheap
            circuit=CircuitPolicy(failure_threshold=3, cooldown_seconds=60),
        )

    def __init__(self, transport: HttpTransport, host: str, port: int,
                 username: str, password: str) -> None:
        self._transport = transport  # for pre-check
        self._client = qbittorrentapi.Client(host=host, port=port,
                                             username=username, password=password)
        # Pre-check + login + lockout handling preserved verbatim from old module
```

Implements `TorrentClient` Protocol with: `get_completed`, `get_all_hashes`, `is_seeding`, `get_content_path`, `pause`, `resume`, `delete`.

Legacy compatibility decisions for this migration commit:

- Rewrite `get_completed_torrents()` call sites to `get_completed()`.
- Rewrite `get_all_torrent_hashes()` call sites to `get_all_hashes()`.
- Keep provider-specific qBit exceptions where they carry actionable user
  guidance: `QBitAuthLockoutError`, `qbittorrentapi.LoginFailed`,
  `qbittorrentapi.Forbidden403Error`, and `qbittorrentapi.APIConnectionError`.
  The ingest step already turns these into specific report messages; preserve
  those messages during the factory migration.

Keep `QBitAuthLockoutError` as a qBit-specific exception (NOT folded into `ApiError`). Document in `_base.py` as the only allowed provider-specific exception escape hatch.

### 9.2 — Wire factory

`build_active_torrent_client` constructs `QBitClient` from config + env:

```python
if cfg.active == "qbittorrent":
    client_cfg = cfg.clients["qbittorrent"]
    if not client_cfg.enabled: raise ValueError(...)
    creds = check_creds(QBitClient.REQUIRED_CREDS, env)
    transport = HttpTransport(QBitClient.policy(client_cfg.host, client_cfg.port))
    return QBitClient(transport, client_cfg.host, client_cfg.port, **creds)
```

### 9.3 — Update consumers + delete old

```bash
rg "from personalscraper\.ingest\.qbit_client import" personalscraper/ tests/
```

Rewrite imports to `from personalscraper.api.torrent.qbittorrent import QBitClient`. Pipeline entry points (especially `personalscraper/ingest/ingest.py`) instead call `build_active_torrent_client(cfg.torrent, os.environ)`.

`ingest/ingest.py` must keep the same operator-facing error details for qBit
auth lockout, bad credentials, IP ban, and unreachable Web UI after switching
to the factory.

```bash
git rm personalscraper/ingest/qbit_client.py
```

**Commit**: `refactor(api-unify): migrate qBittorrent to api/torrent/qbittorrent.py`

### 9.4 — Phase 9 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.torrent.qbittorrent import QBitClient"
python -c "from personalscraper.api.torrent._factory import build_active_torrent_client"
! rg "ingest\.qbit_client" personalscraper/ tests/ --files-with-matches
```

**Commit**: `chore(api-unify): phase 9 gate — qbit migration done`
