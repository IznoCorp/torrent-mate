# qBittorrent Web API Reference

Third-party torrent client API used by the ingest pipeline.
Home: <https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.x)>

## Auth

- **Method**: Cookie-based session via `POST /api/v2/auth/login`.
- **Parameters**: `username` (form field), `password` (form field).
- **Response**: Sets `SID` cookie on success (200). Returns 403 on bad credentials.
- **Logout**: `POST /api/v2/auth/logout` (ends session, clears SID).

### Auth lockout (qBit-specific)

After **3 failed login attempts per IP**, qBittorrent blocks that IP for **~30 minutes**.
This is a brute-force protection in the WebUI server — not configurable.

**Pre-check mechanism** (anti-ban):

The qBit WebUI root page (`GET /`) always returns 200 regardless of auth state.
API endpoints like `GET /api/v2/app/version` return **403** when unauthenticated,
and those 403s **count as failed login attempts** toward the ban threshold.

Our client therefore hits `/` (not an API endpoint) as a reachability pre-check
before attempting `auth_log_in`.

**Lockout file**: `~/.cache/personalscraper/qbit_auth_lockout`

On auth failure, a lockout file is written with a 1-hour TTL. All subsequent
attempts during that window raise `QBitAuthLockoutError` immediately — no
HTTP call is made. This prevents cron/launchd from accumulating failed attempts
and triggering the IP ban.

Fix procedure: correct `.env` credentials, then delete the lockout file.

## Endpoints used

| Method | Endpoint                             | Purpose                          | Via                         |
| ------ | ------------------------------------ | -------------------------------- | --------------------------- |
| GET    | `/`                                  | Reachability pre-check (no auth) | `requests.get()`            |
| POST   | `/api/v2/auth/login`                 | Session login                    | `qbittorrentapi`            |
| POST   | `/api/v2/auth/logout`                | Session logout                   | `qbittorrentapi`            |
| GET    | `/api/v2/torrents/info`              | List all torrents (hash set)     | `qbittorrentapi`            |
| GET    | `/api/v2/torrents/info?filter=...`   | List completed torrents          | `qbittorrentapi`            |
| GET    | `/api/v2/torrents/properties?hash=X` | Per-torrent properties           | `qbittorrentapi` (indirect) |
| POST   | `/api/v2/torrents/pause`             | Pause torrent                    | Not yet used (Phase 9)      |
| POST   | `/api/v2/torrents/resume`            | Resume torrent                   | Not yet used (Phase 9)      |
| POST   | `/api/v2/torrents/delete`            | Delete torrent                   | Not yet used (Phase 9)      |

## Response formats

### `GET /api/v2/torrents/info`

Returns `list[TorrentDictionary]`. Each dict has at minimum:

| Field          | Type  | Description                                         |
| -------------- | ----- | --------------------------------------------------- |
| `hash`         | str   | Torrent info hash (v1)                              |
| `name`         | str   | Torrent display name                                |
| `size`         | int   | Total size in bytes                                 |
| `progress`     | float | 0.0–1.0                                             |
| `state`        | str   | Current state (see State field below)               |
| `content_path` | str   | Filesystem path (may be empty until move completes) |
| `category`     | str   | Category label (empty string if none)               |
| `added_on`     | int   | Unix timestamp when added                           |

The `qbittorrentapi` library also exposes `state_enum` (`TorrentState` enum)
and convenience methods like `state_enum.is_uploading`.

### `GET /api/v2/torrents/properties?hash=X`

Returns a single `TorrentProperties` dict with additional fields:
`save_path`, `creation_date`, `comment`, `total_uploaded`, `total_downloaded`,
`share_ratio`, etc.

## State field

The `state` field has 16+ possible values. The ones relevant to the pipeline:

| State       | Meaning                | `is_uploading` |
| ----------- | ---------------------- | -------------- |
| `uploading` | Actively seeding       | True           |
| `stalledUP` | Seeding, no peers      | True           |
| `forcedUP`  | Force-started, seeding | True           |
| `queuedUP`  | Queued for seeding     | True           |
| `pausedUP`  | Completed but paused   | **False**      |
| `stoppedUP` | Completed but stopped  | **False**      |

The pipeline uses `is_uploading` to decide move vs copy: seeding torrents
are copied (leave the original in place), non-seeding completed torrents
are moved.

"Completed" filter (`status_filter="completed"`) returns torrents with
`progress == 1.0`, which includes `pausedUP` and `stalledUP` — we want both.

## qbittorrentapi library

The `qbittorrentapi` Python package handles:

- CSRF token extraction (qBit v4.x used custom header; v5.0+ dropped it)
- SID cookie management
- Automatic `host:port` URL construction
- Response JSON → typed objects (`TorrentDictionary`, `TorrentProperties`)

What we still need raw HTTP for:

- The pre-check (`GET /`) — must NOT go through the API client because
  `qbittorrentapi` automatically adds auth, which can trigger the ban counter.
- Future: pause/resume/delete hashes in batch operations not covered by
  `qbittorrentapi` convenience methods (if any).

## Version differences

- **qBit 4.x**: CSRF token required in `X-QBITTORRENT-CSRF` header for
  state-changing requests (pause/resume/delete). The `qbittorrentapi`
  library handles this transparently.
- **qBit 5.x**: CSRF requirement removed. Payload shapes are identical.

The library detects the version on first API call and adapts automatically.
No version-specific code is needed in our wrapper.
