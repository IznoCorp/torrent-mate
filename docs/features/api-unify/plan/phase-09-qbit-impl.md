# Phase 9 — qBittorrent Migration

**Type**: impl
**Goal**: Migrate `ingest/qbit_client.py` (212 LOC) → `api/torrent/qbittorrent.py`. Wire factory.

## Gate (prereq)

Phase 8 complete. Real API tested against qBit 5.0.4 (API 2.11.2). Samples in `docs/reference/_samples/qbittorrent/`.

## Sub-phases

### 9.1 — Build `api/torrent/qbittorrent.py`

Implements `TorrentClient` Protocol via a wrapper around `qbittorrentapi.Client`.

**Module exports**:

- `QBitClient` class (implements `TorrentClient` Protocol)
- `build_client(name, entry, env) -> TorrentClient` — factory entry point called by `_factory.py`

**`build_client()` logic**:

1. Read `QBIT_USERNAME` / `QBIT_PASSWORD` from `env`.
2. Pre-check: `requests.get(f"http://{entry.host}:{entry.port}/", timeout=5)` — hits qBit root `/`, not an API endpoint, safe against ban counter.
3. On failure: raise `APIConnectionError` wrapping the original exception.
4. On success: instantiate `QBitClient(host, port, username, password)`, call `login()`.
5. Return the logged-in client.

No `HttpTransport` for the pre-check — a bare `requests.get` with 5s timeout is simpler and the pre-check has no auth/retry/policy requirements.

**`QBitClient` class**:

```python
class QBitClient:
    REQUIRED_CREDS: ClassVar[list[str]] = ["QBIT_USERNAME", "QBIT_PASSWORD"]
    provider_name = "qbittorrent"

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self._client = qbittorrentapi.Client(
            host=host, port=port, username=username, password=password,
            REQUESTS_ARGS={"timeout": 30},
            VERIFY_WEBUI_CERTIFICATE=False,
        )

    def login(self) -> None:
        # Anti-ban lockout check (preserved verbatim from ingest/qbit_client.py)
        # Pre-check already done in build_client()
        # auth_log_in() with lockout handling
        ...

    def logout(self) -> None: ...
    def get_completed(self) -> list[TorrentItem]: ...
    def get_all_hashes(self) -> set[str]: ...
    def is_seeding(self, torrent: TorrentItem) -> bool: ...
    def get_content_path(self, torrent: TorrentItem) -> Path: ...
    def pause(self, hash: str) -> None: ...
    def resume(self, hash: str) -> None: ...
    def delete(self, hash: str, *, delete_files: bool = False) -> None: ...
```

**Data mapping (qBit → TorrentItem) — real-field observations from qBit 5.0.4**:

| qBit field     | TorrentItem field | Conversion                                                    |
| -------------- | ----------------- | ------------------------------------------------------------- |
| `hash`         | `hash`            | direct                                                        |
| `name`         | `name`            | direct                                                        |
| `total_size`   | `size_bytes`      | direct (use `total_size`, not `size` which is bytes selected) |
| `progress`     | `progress`        | `float(progress)` — qBit 5.x returns `int` `1` for completed  |
| `state`        | `state`           | direct string                                                 |
| `content_path` | `content_path`    | `Path(content_path) if content_path else None`                |
| `category`     | `category`        | `category if category else None` (empty string → None)        |
| `added_on`     | `added_on`        | `datetime.fromtimestamp(added_on)`                            |

**`state` values** (19 values per official spec): `error`, `missingFiles`, `uploading`, `pausedUP`, `queuedUP`, `stalledUP`, `checkingUP`, `forcedUP`, `allocating`, `downloading`, `metaDL`, `pausedDL`, `queuedDL`, `stalledDL`, `checkingDL`, `forcedDL`, `checkingResumeData`, `moving`, `unknown`.

`is_seeding()` uses `qbittorrentapi.TorrentDictionary.state_enum.is_uploading` which covers all 6 uploading states (`uploading`, `pausedUP`, `queuedUP`, `stalledUP`, `checkingUP`, `forcedUP`).

**`pause` / `resume` / `delete`**: the Protocol takes a single `hash: str`, the qBit API takes `hashes` (pipe-separated or `all`). The wrapper passes a single hash — `qbittorrentapi` handles the translation.

**`delete` parameter**: Protocol uses `delete_files` (snake_case), qBit API uses `deleteFiles` (camelCase). The wrapper translates.

**qBit 5.x specifics**:

- No CSRF header required (dropped in 5.x). `qbittorrentapi` detects version and adapts.
- `isPrivate` field available in torrent info (since 5.0.0). Not needed by the pipeline.

**Legacy exceptions preserved** (qBit-specific, not folded into `ApiError`):

- `QBitAuthLockoutError` — raised when `~/.cache/personalscraper/qbit_auth_lockout` is active (< 1h old).
- `qbittorrentapi.LoginFailed` — bad credentials.
- `qbittorrentapi.Forbidden403Error` — IP banned.
- `qbittorrentapi.APIConnectionError` — unreachable.

These carry actionable user guidance in the ingest step. Document in `_base.py` module docstring as the allowed provider-specific escape hatch.

**Commit**: `feat(api-unify): add qBittorrent client implementing TorrentClient Protocol`

### 9.2 — Wire factory

Update `build_active_torrent_client()` in `_factory.py`:

- Remove the `NotImplementedError("qBittorrent client not yet implemented (Phase 9)")` guard.
- The `importlib.import_module` + `mod.build_client()` call now actually works for `qbittorrent`.
- `transmission` branch still raises `NotImplementedError` (Phase 11).

No structural change — the factory was designed for this. Just remove the guard.

**Commit**: `feat(api-unify): wire qBittorrent into torrent factory`

### 9.3 — Update consumers + delete old

```bash
rg "from personalscraper\.ingest\.qbit_client import" personalscraper/ tests/
```

Rewrite imports to `from personalscraper.api.torrent.qbittorrent import QBitClient`. Pipeline entry points (especially `personalscraper/ingest/ingest.py`) instead call `build_active_torrent_client(cfg.torrent, os.environ)`.

`ingest/ingest.py` must keep the same operator-facing error details for qBit auth lockout, bad credentials, IP ban, and unreachable Web UI after switching to the factory.

```bash
git rm personalscraper/ingest/qbit_client.py
```

**Commit**: `refactor(api-unify): migrate qBittorrent consumers to api/torrent`

### 9.4 — Phase 9 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.torrent.qbittorrent import QBitClient, build_client"
python -c "from personalscraper.api.torrent._factory import build_active_torrent_client"
! rg "ingest\.qbit_client" personalscraper/ tests/ --files-with-matches
```

**Commit**: `chore(api-unify): phase 9 gate — qbit migration done`
