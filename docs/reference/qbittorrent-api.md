# qBittorrent WebUI API Reference

Official reference: <https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)>
Base path: `/api/v2/`
Auth: cookie-based (SID). All endpoints require auth except `POST /api/v2/auth/login`.
Convention: `GET` for reads, `POST` for mutations. Since v4.4.4, wrong method → `405`.

## Auth (`/api/v2/auth/`)

### Login

`POST /api/v2/auth/login`

| Parameter  | Type   | Required |
| ---------- | ------ | -------- |
| `username` | string | yes      |
| `password` | string | yes      |

Returns `200` + `SID` cookie on success. Returns `403` on bad credentials (counts toward IP ban).
**Header requirement**: set `Referer` or `Origin` to the same domain+port as the request `Host`.

### Logout

`POST /api/v2/auth/logout` — no parameters. Returns `200`.

## Torrent info (`/api/v2/torrents/`)

### List torrents

`GET /api/v2/torrents/info`

| Parameter  | Type   | Required | Description                                                                                                                                                       |
| ---------- | ------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `filter`   | string | no       | One of: `all`, `downloading`, `seeding`, `completed`, `paused`, `active`, `inactive`, `resumed`, `stalled`, `stalled_uploading`, `stalled_downloading`, `errored` |
| `category` | string | no       | Empty string = no category; absent = any                                                                                                                          |
| `tag`      | string | no       | Filter by tag (since API 2.8.3)                                                                                                                                   |
| `sort`     | string | no       | Field name to sort by                                                                                                                                             |
| `reverse`  | bool   | no       | Reverse sort order                                                                                                                                                |
| `limit`    | int    | no       | Max results                                                                                                                                                       |
| `offset`   | int    | no       | Pagination offset                                                                                                                                                 |
| `hashes`   | string | no       | Pipe-separated hashes to filter by                                                                                                                                |

Returns `200` — JSON array of torrent objects. Field reference:

| Field                | Type   | Description                                |
| -------------------- | ------ | ------------------------------------------ |
| `hash`               | string | Torrent info hash (v1)                     |
| `name`               | string | Torrent display name                       |
| `size`               | int    | Bytes **selected** for download            |
| `total_size`         | int    | Total bytes of all files in the torrent    |
| `progress`           | float  | 0.0–1.0                                    |
| `state`              | string | Current state (see table below)            |
| `content_path`       | string | Absolute path (empty until move completes) |
| `save_path`          | string | Data storage directory                     |
| `category`           | string | Category label (empty string if none)      |
| `tags`               | string | Comma-concatenated tag list                |
| `added_on`           | int    | Unix epoch when added                      |
| `completion_on`      | int    | Unix epoch when completed (0 if not)       |
| `amount_left`        | int    | Bytes remaining to download                |
| `completed`          | int    | Bytes completed so far                     |
| `dlspeed`            | int    | Current download speed (bytes/s)           |
| `upspeed`            | int    | Current upload speed (bytes/s)             |
| `eta`                | int    | Seconds until completion                   |
| `ratio`              | float  | Share ratio (capped at 9999)               |
| `num_seeds`          | int    | Connected seeds                            |
| `num_leechs`         | int    | Connected leechers                         |
| `num_complete`       | int    | Seeds in swarm                             |
| `num_incomplete`     | int    | Leechers in swarm                          |
| `tracker`            | string | First working tracker URL                  |
| `dl_limit`           | int    | Download limit (bytes/s, -1 = unlimited)   |
| `up_limit`           | int    | Upload limit (bytes/s, -1 = unlimited)     |
| `downloaded`         | int    | Total bytes downloaded                     |
| `uploaded`           | int    | Total bytes uploaded                       |
| `downloaded_session` | int    | Bytes downloaded this session              |
| `uploaded_session`   | int    | Bytes uploaded this session                |
| `availability`       | float  | Fraction of pieces available (0.0–1.0)     |
| `auto_tmm`           | bool   | Managed by Automatic Torrent Management    |
| `force_start`        | bool   | Force start enabled                        |
| `isPrivate`          | bool   | Private tracker (since API 5.0.0)          |
| `last_activity`      | int    | Unix epoch of last chunk activity          |
| `magnet_uri`         | string | Magnet URI                                 |
| `max_ratio`          | float  | Maximum share ratio                        |
| `max_seeding_time`   | int    | Max seeding time (seconds)                 |
| `priority`           | int    | Queue position (-1 = disabled)             |
| `ratio_limit`        | float  | Per-torrent ratio limit                    |
| `seeding_time`       | int    | Seconds spent as seed                      |
| `seeding_time_limit` | int    | Per-torrent seeding time limit (seconds)   |
| `seen_complete`      | int    | Unix epoch last seen complete              |
| `seq_dl`             | bool   | Sequential download enabled                |
| `super_seeding`      | bool   | Super seeding enabled                      |
| `time_active`        | int    | Total seconds active                       |
| `f_l_piece_prio`     | bool   | First/last piece prioritized               |

**`state` values** (all possible):

| Category    | States                                                                                 |
| ----------- | -------------------------------------------------------------------------------------- |
| Error       | `error`, `missingFiles`, `unknown`                                                     |
| Uploading   | `uploading`, `pausedUP`, `queuedUP`, `stalledUP`, `checkingUP`, `forcedUP`             |
| Downloading | `downloading`, `metaDL`, `pausedDL`, `queuedDL`, `stalledDL`, `checkingDL`, `forcedDL` |
| Other       | `allocating`, `checkingResumeData`, `moving`                                           |

The `qbittorrentapi` library exposes `state_enum.is_uploading` (covers all 6 uploading states).
The pipeline uses this to decide copy-vs-move: seeding torrents → copy, completed+paused/stopped → move.

**Important**: the `completed` filter returns torrents with `progress == 1.0`, which includes
`pausedUP` and `stalledUP` (both are "complete but not actively transferring"). We want both
— paused completed torrents are safe to move; stalled ones are seeding.

### Torrent properties

`GET /api/v2/torrents/properties?hash=<hash>`

Returns `200` — single torrent details including `save_path`, `creation_date`, `comment`,
`total_uploaded`, `total_downloaded`, `share_ratio`, `seeding_time`, `time_elapsed`,
`nb_connections`, `total_size`, `peers`, `seeds`, `isPrivate`, etc.
Returns `404` if hash not found.

### Torrent contents (files)

`GET /api/v2/torrents/files?hash=<hash>`

Returns `200` — JSON array with `index`, `name`, `size`, `progress`, `priority`, `is_seed`, `piece_range`, `availability`.

## Torrent actions (`/api/v2/torrents/`)

All actions accept `hashes` parameter as pipe-separated hash list or literal `all`.
Return `200` on success (even if no torrents matched).

| Action       | Method | Parameters                         | Notes                                   |
| ------------ | ------ | ---------------------------------- | --------------------------------------- |
| Pause        | POST   | `hashes`                           |                                         |
| Resume       | POST   | `hashes`                           |                                         |
| Delete       | POST   | `hashes`, `deleteFiles` (bool)     | `deleteFiles` also removes data on disk |
| Recheck      | POST   | `hashes`                           |                                         |
| Reannounce   | POST   | `hashes`                           |                                         |
| Set category | POST   | `hashes`, `category` (string)      | 409 if category not created             |
| Add tags     | POST   | `hashes`, `tags` (comma-separated) |                                         |
| Remove tags  | POST   | `hashes`, `tags` (comma-separated) | Empty `tags` = clear all                |

### Add torrent

`POST /api/v2/torrents/add` (multipart/form-data)

Key parameters: `urls` (newline-separated), `torrents` (file data, repeatable), `savepath`,
`category`, `tags`, `paused`, `skip_checking`, `root_folder`, `rename`,
`upLimit`/`dlLimit` (bytes/s), `ratioLimit` (float), `seedingTimeLimit` (int minutes).

Supports `http://`, `https://`, `magnet:`, `bc://bt/` links. Returns `415` on invalid torrent file.

## Sync (`/api/v2/sync/`)

### Main data (incremental)

`GET /api/v2/sync/maindata?rid=<int>`

Returns `200` — JSON with `rid` (int), `full_update` (bool), `torrents` (object keyed by hash),
`torrents_removed` (array), `categories`, `tags`, `server_state`.

If the `rid` differs from the server's last reply, `full_update` is `true`.
Useful for incremental polling (feed `rid` from the last response to get only changes).

## Transfer info (`/api/v2/transfer/`)

`GET /api/v2/transfer/info` — global transfer stats: `dl_info_speed`, `up_info_speed`,
`dl_rate_limit`, `up_rate_limit`, `connection_status` (`connected`/`firewalled`/`disconnected`).

## Categories (`/api/v2/torrents/categories`)

`GET /api/v2/torrents/categories` → `200` — JSON object: `"name": {name, savePath}`.
`POST /api/v2/torrents/createCategory` → `category` (string), `savePath` (optional).

## Tags (`/api/v2/torrents/tags`)

`GET /api/v2/torrents/tags` → `200` — JSON array of strings.
`POST /api/v2/torrents/createTags` → `tags` (comma-separated).
`POST /api/v2/torrents/deleteTags` → `tags` (comma-separated).

## Auth lockout (qBit-specific)

After **3 failed login attempts per IP**, qBittorrent blocks that IP for **~30 minutes**.
This is the WebUI server's brute-force protection — not configurable.

Even hitting API endpoints that return `403` when unauthenticated (e.g. `GET /api/v2/app/version`)
**counts as a failed login attempt**. Our pre-check therefore hits the qBit WebUI root page
(`GET /`) which always returns `200` regardless of auth state — a safe reachability check
that does NOT increment the ban counter.

Our client wrapper maintains a lockout file (`~/.cache/personalscraper/qbit_auth_lockout`,
1-hour TTL) to short-circuit further attempts after a credential failure, preventing
cron/launchd from accumulating attempts across scheduled runs.

## `qbittorrentapi` library coverage

The `qbittorrentapi` Python package wraps all endpoints listed above. It handles:

- CSRF token extraction (qBit v4.x `X-QBITTORRENT-CSRF` header; dropped in v5.0+)
- SID cookie management and automatic re-login
- `host:port` → URL construction
- Response JSON → typed Python objects (`TorrentDictionary`, `TorrentProperties`, etc.)

What we still need raw HTTP for:

- **Pre-check**: `GET /` on the qBit host — must bypass `qbittorrentapi` to avoid the
  auth layer triggering the ban counter before we're ready to log in.
- Batch operations not covered by `qbittorrentapi` convenience methods (if any).

## Version compatibility

- **qBit 4.x**: CSRF token required in `X-QBITTORRENT-CSRF` header for state-changing requests.
- **qBit 5.x**: CSRF requirement removed. `content_path` and `isPrivate` added to torrent info.
- **API version**: Separate from qBit version (e.g. qBit 4.6 ships API 2.8.3).
  Check via `GET /api/v2/app/webapiVersion`.
- `qbittorrentapi` detects version on first call and adapts transparently.

## Endpoints used by the pipeline

| Method | Endpoint                                 | Purpose                      | Via            |
| ------ | ---------------------------------------- | ---------------------------- | -------------- |
| GET    | `/`                                      | Pre-check (no auth)          | `requests`     |
| POST   | `/api/v2/auth/login`                     | Session login                | qbittorrentapi |
| POST   | `/api/v2/auth/logout`                    | Session logout               | qbittorrentapi |
| GET    | `/api/v2/torrents/info`                  | List all torrents (hash set) | qbittorrentapi |
| GET    | `/api/v2/torrents/info?filter=completed` | List completed               | qbittorrentapi |
| POST   | `/api/v2/torrents/pause`                 | Pause by hash                | qbittorrentapi |
| POST   | `/api/v2/torrents/resume`                | Resume by hash               | qbittorrentapi |
| POST   | `/api/v2/torrents/delete`                | Delete by hash               | qbittorrentapi |
