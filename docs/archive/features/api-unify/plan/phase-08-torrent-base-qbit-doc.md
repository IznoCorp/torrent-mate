# Phase 8 — Torrent Family Base + qBittorrent API Doc

**Type**: mixed (infra + doc)
**Goal**: Ship `api/torrent/_base.py` + `_factory.py` skeleton. Write qBittorrent API reference. Interactive checkpoint.

## Gate (prereq)

Phase 7 complete. Metadata family fully migrated.

## Sub-phases

### 8.1 — `api/torrent/__init__.py` + `_base.py`

`api/torrent/_base.py` contains:

- `TorrentItem` dataclass (per DESIGN §5.1) — hash, name, size_bytes, progress, state, content_path, category, added_on.
- `TorrentClient` Protocol (per DESIGN §5.1) — runtime_checkable.

**Commit**: `feat(api-unify): add torrent family base — Protocol + TorrentItem`

### 8.2 — `api/torrent/_factory.py` skeleton

```python
def build_active_torrent_client(cfg: TorrentConfig,
                                env: Mapping[str, str] | None = None) -> TorrentClient:
    """Read cfg.active, validate creds, return single TorrentClient instance.

    Raises:
        ValueError: cfg.active not in cfg.clients, or chosen client not enabled.
        ApiError: chosen client missing required credentials.
    """
```

For now, factory only knows `qbittorrent` (Phase 9 wires it). `transmission` branch raises `NotImplementedError("Transmission client not yet implemented (Phase 11)")` — a temporary stub resolved in Phase 11. No code path can trigger it before Transmission exists.

Unit tests: `cfg.active="qbittorrent"` + creds → returns instance (mocked); missing cred → raises; `cfg.active="unknown"` → ValueError.

**Commit**: `feat(api-unify): add torrent factory skeleton`

### 8.3 — Audit existing qBit usage

```bash
rg "qbittorrentapi\.|qbit_client|self\._client\." personalscraper/ingest/qbit_client.py
```

Identify which qBit endpoints `qbittorrentapi.Client` calls under the hood, plus the **pre-check HTTP** that `qbit_client.py` does directly via `requests` (the `/api/v2/auth/login` ping).

### 8.4 — Real test calls (qBit local instance)

Call the qBit WebUI directly:

- `POST /api/v2/auth/login` (form: username, password) → cookie session.
- `GET /api/v2/torrents/info` (filter=completed, sort=added_on).
- `POST /api/v2/torrents/pause` / `resume` / `delete`.
- `GET /api/v2/torrents/properties?hash=X`.

Capture sample responses to `docs/reference/_samples/qbittorrent/`.

### 8.5 — Write `docs/reference/qbittorrent-api.md`

Sections:

- Auth: cookie-based login (`POST /api/v2/auth/login`). qBit auth-lockout: after 3 failed logins per IP, account locks for ~30min.
- Endpoints used.
- Response formats (raw `qbittorrentapi.TorrentDictionary` shapes).
- The `qbittorrentapi` library handles most plumbing — what we still need raw HTTP for (the pre-check).
- Anti-ban mechanism rationale.

### 8.6 — Particularities checklist

- Auth lockout (qBit-specific) — preserved as `QBitAuthLockoutError` (kept since not generic).
- `state` field has 16+ possible values (`uploading`, `pausedUP`, `stalledUP`, …).
- `content_path` may be empty until torrent has finished moving.
- "Completed" filter includes `pausedUP` and `stalledUP` (we want both).
- WebUI version differences (qBit 4.x vs 5.x payload shape).

### 8.7 — Interactive user checkpoint

> Phase 8 base + qBittorrent doc complete.
> Particularities found: <list>
>
> Proposed implementation scope (Phase 9):
>
> - Pre-check HTTP via HttpTransport(NoAuth).
> - Main client uses qbittorrentapi.Client for ops.
> - Keep QBitAuthLockoutError (qBit-specific).
> - Add pause/resume/delete methods.
>
> Confirm or adjust before next phase?

### 8.8 — Phase 8 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.torrent._base import TorrentClient, TorrentItem"
python -c "from personalscraper.api.torrent._factory import build_active_torrent_client"
ls docs/reference/qbittorrent-api.md
```

**Commit**: `chore(api-unify): phase 8 gate — torrent base + qbit doc done

User checkpoint captured: <decisions>`
