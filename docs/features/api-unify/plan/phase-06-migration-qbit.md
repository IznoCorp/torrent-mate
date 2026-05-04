# Phase 6 — Migration qBittorrent

## Gate

**Prerequisites**: Phase 5 complete. `api/transport/` exists, `api/_contracts.py` exists.

## Goal

Migrate `ingest/qbit_client.py` (212 LOC) → `api/torrent/qbittorrent.py`. Implement `TorrentClient` Protocol. Preserve auth lockout (qBit-specific).

## Sub-phases

### 6.1 — Create `api/torrent/` package + `_base.py`

**Files**:

- `personalscraper/api/torrent/__init__.py`
- `personalscraper/api/torrent/_base.py`

`_base.py` contains:

- `TorrentClient` Protocol (from DESIGN §5.1)
- `TorrentItem` dataclass

**Commit**: `feat(api-unify): add torrent package with base types`

### 6.2 — Create `api/torrent/qbittorrent.py`

Copy `ingest/qbit_client.py` → `api/torrent/qbittorrent.py`. Rewrite:

1. Pre-check HTTP → `HttpTransport` with `NoAuth`
2. Keep `qbittorrentapi.Client` for qBit operations (that's the qBit library, not raw requests)
3. Implement `TorrentClient` Protocol (add type annotations)
4. Add `pause()`, `resume()`, `delete()` methods
5. Keep auth lockout logic (qBit-specific anti-ban mechanism)
6. `QBitAuthLockoutError` → kept (qBit-specific)
7. `REQUIRED_CREDS = ["QBIT_USERNAME", "QBIT_PASSWORD"]`

**Commit**: `refactor(api-unify): migrate qBittorrent to api/torrent/qbittorrent.py`

### 6.3 — Update consumers + delete old

```bash
rg "from personalscraper.ingest.qbit_client import" personalscraper/ --files-with-matches
```

Update imports. Delete `ingest/qbit_client.py`.

**Commit**: `refactor(api-unify): delete ingest/qbit_client.py`

### 6.4 — Phase 6 gate

```bash
make check && python3 scripts/check-module-size.py
! rg "from personalscraper.ingest.qbit_client" personalscraper/ --files-with-matches
```

**Commit**: `chore(api-unify): phase 6 gate — qbit migration done`
