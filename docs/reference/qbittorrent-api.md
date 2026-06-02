# qBittorrent API Reference

This document has two parts:

1. **WebUI HTTP API** — the raw `/api/v2/` HTTP surface qBittorrent exposes.
2. **`qbittorrentapi` Python client** — the library the pipeline uses to talk to that
   surface, including the `TorrentDictionary` / `TorrentState` typed objects and the
   patterns the ingest step relies on.

The pipeline integration lives in `personalscraper/api/torrent/qbittorrent.py`
(`QBitClient` + `build_client`).

## Table of contents

- [Part 1 — WebUI HTTP API](#part-1--webui-http-api)
  - [Auth (`/api/v2/auth/`)](#auth-apiv2auth)
  - [Torrent info (`/api/v2/torrents/`)](#torrent-info-apiv2torrents)
  - [Torrent actions (`/api/v2/torrents/`)](#torrent-actions-apiv2torrents)
  - [Sync (`/api/v2/sync/`)](#sync-apiv2sync)
  - [Transfer info (`/api/v2/transfer/`)](#transfer-info-apiv2transfer)
  - [Categories & Tags](#categories-apiv2torrentscategories)
  - [Auth lockout (qBit-specific)](#auth-lockout-qbit-specific)
  - [Version compatibility](#version-compatibility)
  - [Endpoints used by the pipeline](#endpoints-used-by-the-pipeline)
- [Part 2 — `qbittorrentapi` Python client](#part-2--qbittorrentapi-python-client)
  - [Overview & installation](#overview--installation)
  - [Connection & authentication](#connection--authentication)
  - [Client constructor — key parameters](#client-constructor--key-parameters)
  - [Listing torrents — `torrents_info()`](#listing-torrents--torrents_info)
  - [`TorrentDictionary` — torrent properties](#torrentdictionary--torrent-properties)
  - [`TorrentState` — enum and helpers](#torrentstate--enum-and-helpers)
  - [Error handling](#error-handling)
  - [CSRF and security](#csrf-and-security)
  - [qBittorrent v4.x vs v5.x compatibility](#qbittorrent-v4x-vs-v5x-compatibility)
  - [Timeout and retry](#timeout-and-retry)
  - [Pipeline-specific patterns](#pipeline-specific-patterns)
  - [Useful imports](#useful-imports)
  - [Sources](#sources)

---

# Part 1 — WebUI HTTP API

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
cron/launchd from accumulating attempts across scheduled runs. This is implemented in
`build_client` (raw `GET /` pre-check via `requests`) and `QBitClient.login`
(`_check_lockout` / `_set_lockout`) in `personalscraper/api/torrent/qbittorrent.py`.

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

---

# Part 2 — `qbittorrentapi` Python client

## Overview & installation

[`qbittorrent-api`](https://github.com/rmartin16/qbittorrent-api) is a Python client for the
qBittorrent WebUI API. It replaces a hand-rolled HTTP client by handling automatically:

- Authentication (login / re-login if the cookie expires)
- CSRF headers (`Referer` / `Origin`)
- qBittorrent v4.x and v5.0+ compatibility (`pausedUP` / `stoppedUP`)
- The `TorrentState` enum with helpers (`is_complete`, `is_uploading`, `is_stopped`)
- Built-in retry with exponential backoff

License: MIT. Python: `>= 3.9`. Dependencies: `requests >= 2.16.0`, `urllib3 >= 1.24.2`,
`packaging`.

```bash
pip install qbittorrent-api
```

> The pipeline pins this dependency in `pyproject.toml`. The reference behavior described
> below was validated against the `qbittorrent-api` release current at the time of writing
> (supporting qBittorrent up to v5.1.x, WebUI API up to v2.11.x).

## Connection & authentication

### Context manager (recommended)

```python
import qbittorrentapi

with qbittorrentapi.Client(
    host="localhost",
    port=8081,
    username="izno",
    password="secret",
) as qbt:
    # auth_log_in() is called automatically on entry
    torrents = qbt.torrents_info()
    # auth_log_out() is called automatically on exit
```

### Manual connection

```python
qbt = qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
)

try:
    qbt.auth_log_in()
except qbittorrentapi.LoginFailed:
    print("Invalid credentials")
except qbittorrentapi.APIConnectionError:
    print("qBittorrent unreachable")

# ... work ...

qbt.auth_log_out()
```

The pipeline does **not** use the context manager: `QBitClient` constructs an
un-authenticated `qbittorrentapi.Client` and `build_client` calls `client.login()`
explicitly so it can wrap the login in the anti-ban lockout logic (see
[Auth lockout](#auth-lockout-qbit-specific)).

### Auto-reconnect

If the session cookie expires mid-operation, the library intercepts the HTTP 403,
re-calls `auth_log_in()`, and replays the request automatically. Transparent to the caller.

### Environment variables (fallback)

| Variable                                         | Role               |
| ------------------------------------------------ | ------------------ |
| `QBITTORRENTAPI_HOST`                            | Host               |
| `QBITTORRENTAPI_USERNAME`                        | Username           |
| `QBITTORRENTAPI_PASSWORD`                        | Password           |
| `QBITTORRENTAPI_DO_NOT_VERIFY_WEBUI_CERTIFICATE` | Disable SSL verify |

The pipeline does not rely on these; it reads `QBIT_USERNAME` / `QBIT_PASSWORD` from the
process environment and passes them explicitly to the `Client` constructor.

## Client constructor — key parameters

```python
qbittorrentapi.Client(
    host="localhost",
    port=8081,
    username="izno",
    password="secret",
    VERIFY_WEBUI_CERTIFICATE=True,    # False for self-signed certificates
    REQUESTS_ARGS={"timeout": 30},    # Timeout in seconds (default: 15.1s)
    SIMPLE_RESPONSES=False,           # True = raw dicts instead of rich objects
)
```

The pipeline's `QBitClient.__init__` constructs the client with
`REQUESTS_ARGS={"timeout": 30}` and `VERIFY_WEBUI_CERTIFICATE=False` (self-signed-cert
tolerant), keeping `SIMPLE_RESPONSES` at its default so it gets rich `TorrentDictionary`
objects.

## Listing torrents — `torrents_info()`

```python
torrents = qbt.torrents_info(
    status_filter=None,     # Filter by state (see table below)
    category=None,          # Filter by category
    sort=None,              # Sort by field
    reverse=None,           # Reverse the sort
    limit=None,             # Max results
    offset=None,            # Offset (negative = from the end)
    torrent_hashes=None,    # Filter by hash(es)
    tag=None,               # Filter by tag ("" = untagged)
)
```

### Values of `status_filter`

| Filter                  | Description                                           |
| ----------------------- | ----------------------------------------------------- |
| `"all"`                 | All torrents                                          |
| `"downloading"`         | Currently downloading                                 |
| `"seeding"`             | Seeding (uploading after completion)                  |
| `"completed"`           | Download finished (100%), regardless of seeding state |
| `"paused"`              | Paused (qBit v4.x term)                               |
| `"stopped"`             | Stopped (qBit v5.x term, replaces "paused")           |
| `"active"`              | Data transfer in progress                             |
| `"inactive"`            | No transfer                                           |
| `"stalled"`             | Stalled (no peers)                                    |
| `"stalled_uploading"`   | Stalled while uploading                               |
| `"stalled_downloading"` | Stalled while downloading                             |
| `"errored"`             | In error                                              |
| `"checking"`            | Checking in progress                                  |
| `"moving"`              | Moving in progress                                    |

### Fluent API (alternative)

```python
# Equivalents:
qbt.torrents_info(status_filter="completed")
qbt.torrents.info.completed()

qbt.torrents_info(status_filter="seeding")
qbt.torrents.info.seeding()
```

The pipeline uses three call shapes:

- `torrents_info(status_filter="completed")` — `QBitClient.get_completed()`
- `torrents_info()` — `QBitClient.get_all_hashes()` (any state)
- `torrents_info(hashes=<hash>)` — `QBitClient.is_seeding()` / `get_content_path()` (single)

## `TorrentDictionary` — torrent properties

Each torrent returned by `torrents_info()` is a `TorrentDictionary`: both a dict and an object.

```python
torrent = qbt.torrents_info()[0]

# Both syntaxes work:
torrent.name            # "Shrinking.S03.MULTi.1080p..."
torrent["name"]         # same

torrent.hash            # "a1b2c3d4e5..."
torrent.content_path    # "/path/to/torrents/complete/Shrinking.S03..."
torrent.save_path       # "/path/to/torrents/complete/"
torrent.progress        # 1.0
torrent.size            # 5368709120 (bytes)
torrent.state           # "uploading"
torrent.state_enum      # TorrentState.UPLOADING
```

### Main properties

| Property        | Type         | Description                                    |
| --------------- | ------------ | ---------------------------------------------- |
| `hash`          | str          | Torrent SHA-1 info hash                        |
| `name`          | str          | Display name                                   |
| `state`         | str          | Raw state ("uploading", "stalledUP", etc.)     |
| `state_enum`    | TorrentState | Enum with helpers                              |
| `content_path`  | str          | Absolute path to the content (file or folder)  |
| `save_path`     | str          | Destination folder                             |
| `progress`      | float        | Progress (0.0 to 1.0)                          |
| `size`          | int          | Size in bytes (selected files)                 |
| `total_size`    | int          | Total size in bytes (all files)                |
| `completion_on` | int          | Unix completion timestamp (-1 if not finished) |
| `added_on`      | int          | Unix added timestamp                           |
| `ratio`         | float        | Share ratio                                    |
| `seeding_time`  | int          | Seeding time in seconds                        |
| `category`      | str          | Assigned category                              |
| `tags`          | str          | Tags (comma-separated)                         |
| `tracker`       | str          | URL of the first active tracker                |
| `dlspeed`       | int          | Download speed (bytes/s)                       |
| `upspeed`       | int          | Upload speed (bytes/s)                         |
| `amount_left`   | int          | Bytes remaining to download                    |
| `magnet_uri`    | str          | Magnet link                                    |

The pipeline maps a `TorrentDictionary` to its internal `TorrentItem` dataclass in
`_torrent_item()`, reading `hash`, `name`, `total_size` (→ `size_bytes`), `progress`,
`state`, `ratio`, `content_path`, `category`, and `added_on`. Note it uses **`total_size`**
(all files) rather than `size` (selected files only) for the reported size.

## `TorrentState` — enum and helpers

### All states

| State                      | API value              | Description                          |
| -------------------------- | ---------------------- | ------------------------------------ |
| `UPLOADING`                | `"uploading"`          | Active seed                          |
| `STALLED_UPLOAD`           | `"stalledUP"`          | Seeding with no peers                |
| `FORCED_UPLOAD`            | `"forcedUP"`           | Forced seed                          |
| `QUEUED_UPLOAD`            | `"queuedUP"`           | Queued for seeding                   |
| `CHECKING_UPLOAD`          | `"checkingUP"`         | Checking after completion            |
| `PAUSED_UPLOAD`            | `"pausedUP"`           | Paused after completion (qBit v4.x)  |
| `STOPPED_UPLOAD`           | `"stoppedUP"`          | Stopped after completion (qBit v5.x) |
| `DOWNLOADING`              | `"downloading"`        | Active download                      |
| `STALLED_DOWNLOAD`         | `"stalledDL"`          | Downloading with no peers            |
| `FORCED_DOWNLOAD`          | `"forcedDL"`           | Forced download                      |
| `QUEUED_DOWNLOAD`          | `"queuedDL"`           | Queued for download                  |
| `CHECKING_DOWNLOAD`        | `"checkingDL"`         | Checking during download             |
| `PAUSED_DOWNLOAD`          | `"pausedDL"`           | Paused during download (v4.x)        |
| `STOPPED_DOWNLOAD`         | `"stoppedDL"`          | Stopped during download (v5.x)       |
| `METADATA_DOWNLOAD`        | `"metaDL"`             | Fetching metadata                    |
| `FORCED_METADATA_DOWNLOAD` | `"forcedMetaDL"`       | Forced metadata (v5.0+)              |
| `ERROR`                    | `"error"`              | Error                                |
| `MISSING_FILES`            | `"missingFiles"`       | Missing files                        |
| `ALLOCATING`               | `"allocating"`         | Disk allocation                      |
| `CHECKING_RESUME_DATA`     | `"checkingResumeData"` | Checking on startup                  |
| `MOVING`                   | `"moving"`             | Moving in progress                   |
| `UNKNOWN`                  | `"unknown"`            | Unknown state                        |

### Boolean helpers

| Helper           | True for                                                           | Pipeline use                          |
| ---------------- | ------------------------------------------------------------------ | ------------------------------------- |
| `is_complete`    | All `*UP` states (uploading, stalledUP, pausedUP, stoppedUP, etc.) | Torrent finished (ready to copy/move) |
| `is_uploading`   | uploading, stalledUP, checkingUP, queuedUP, forcedUP               | Actively seeding (copy, don't move)   |
| `is_stopped`     | pausedUP, stoppedUP, pausedDL, stoppedDL                           | Stopped (safe to move)                |
| `is_downloading` | All `*DL` states                                                   | Currently downloading                 |
| `is_errored`     | error, missingFiles                                                | In error                              |
| `is_checking`    | checkingUP, checkingDL, checkingResumeData                         | Checking                              |
| `is_paused`      | Alias of `is_stopped`                                              | Compatibility                         |

### How the pipeline classifies "completed"

`QBitClient.get_completed()` lists `torrents_info(status_filter="completed")` — every torrent
at `progress == 1.0`, regardless of seeding state. The ingest step then uses
`state_enum.is_uploading` (via `QBitClient.is_seeding()`) to decide copy-vs-move:

```python
for torrent in qbt.torrents_info(status_filter="completed"):
    state = torrent.state_enum

    if state.is_uploading:
        # Still seeding → COPY (do not remove the source)
        action = "copy"
    elif state.is_complete and not state.is_uploading:
        # Finished, no longer seeding → MOVE
        action = "move"
    else:
        continue  # skip (checking, etc.)
```

## Error handling

### Exception hierarchy

```
APIError (base)
├── UnsupportedQbittorrentVersion
├── FileError (IOError)
│   └── TorrentFileError
│       ├── TorrentFileNotFoundError
│       └── TorrentFilePermissionError
└── APIConnectionError (requests.RequestException)
    ├── LoginFailed
    └── HTTPError (requests.HTTPError)
        ├── HTTP4XXError
        │   ├── HTTP400Error / InvalidRequest400Error
        │   ├── HTTP401Error / Unauthorized401Error
        │   ├── HTTP403Error / Forbidden403Error
        │   ├── HTTP404Error / NotFound404Error
        │   └── HTTP409Error / Conflict409Error
        └── HTTP5XXError
            └── HTTP500Error / InternalServerError500Error
```

### Pattern for the pipeline

```python
import qbittorrentapi

try:
    with qbittorrentapi.Client(
        host="localhost", port=8081,
        username="izno", password="secret",
    ) as qbt:
        completed = qbt.torrents_info(status_filter="completed")
        # ... processing ...

except qbittorrentapi.LoginFailed:
    # Invalid credentials or WebUI auth disabled
    log.error("qBittorrent: authentication failed")

except qbittorrentapi.APIConnectionError:
    # qBittorrent unreachable (not running, wrong host/port)
    log.error("qBittorrent: connection failed")

except qbittorrentapi.APIError as e:
    # Other API error
    log.error(f"qBittorrent: API error — {e}")
```

`QBitClient` translates these provider-specific exceptions into the project's uniform
`ApiError` (DESIGN §1.1): `LoginFailed` → `http_status=401`, `Forbidden403Error` →
`http_status=403` (IP ban), missing creds / unreachable host → `http_status=0`. It also
raises its own `QBitAuthLockoutError` when a recent failure lockout is still active. On
login failure it writes the lockout file (`_set_lockout`); `logout()` swallows
`APIConnectionError` / `OSError` at warning level so a dead daemon doesn't crash teardown.

## CSRF and security

The library handles automatically:

- **Session cookie**: `SID` (v4.x) or `QBT_SID_{port}` (v5.2+)
- **Transparent re-login** if the cookie expires
- **CSRF**: handled server-side by qBittorrent, no client-side token required

**IP ban**: after too many failed login attempts, qBittorrent bans the IP (HTTP 403).
Configurable via `web_ui_max_auth_fail_count` and `web_ui_ban_duration` in qBit settings.
See [Auth lockout](#auth-lockout-qbit-specific) for the pipeline's own short-circuit lockout
file that prevents scheduled runs from accumulating attempts toward this ban.

## qBittorrent v4.x vs v5.x compatibility

The library abstracts the differences:

| Concept             | v4.x                | v5.x               | Library             |
| ------------------- | ------------------- | ------------------ | ------------------- |
| Pause               | `torrents_pause()`  | `torrents_stop()`  | Both work (aliases) |
| Resume              | `torrents_resume()` | `torrents_start()` | Both work (aliases) |
| Paused-upload state | `pausedUP`          | `stoppedUP`        | Both in the enum    |
| Pause filter        | `"paused"`          | `"stopped"`        | Both accepted       |
| Resume filter       | `"resumed"`         | `"running"`        | Both accepted       |

The code does **not** need to check the qBittorrent version. The pipeline accordingly
calls the v4.x-named `torrents_pause()` / `torrents_resume()` (in `QBitClient.pause()` /
`resume()`), which the library aliases to the v5.x calls transparently.

## Timeout and retry

- **Default timeout**: 15.1 seconds
- **Built-in retry**: 2 layers
  - `HTTPAdapter`: 1 retry for connection/read errors and codes 500/502/504
  - Request manager: up to 2 retries with exponential backoff (max 10s)

```python
# Custom timeout:
qbt = qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
    REQUESTS_ARGS={"timeout": 30},  # 30 seconds
)
```

The pipeline sets `REQUESTS_ARGS={"timeout": 30}` (see
[constructor](#client-constructor--key-parameters)). The raw reachability pre-check in
`build_client` uses a separate, tighter `requests.get(..., timeout=5)`.

## Pipeline-specific patterns

### List completed torrents

```python
with qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
) as qbt:
    for torrent in qbt.torrents_info(status_filter="completed"):
        print(f"{torrent.name}")
        print(f"  Hash:    {torrent.hash}")
        print(f"  Path:    {torrent.content_path}")
        print(f"  Size:    {torrent.total_size / 1e9:.1f} GB")
        print(f"  State:   {torrent.state}")
        print(f"  Seeding: {torrent.state_enum.is_uploading}")
```

### Copy or move depending on seeding state

```python
from pathlib import Path
import shutil

STAGING = Path("/path/to/staging")

with qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
) as qbt:
    for torrent in qbt.torrents_info(status_filter="completed"):
        source = Path(torrent.content_path)
        dest = STAGING / source.name

        if dest.exists():
            continue  # already present

        if torrent.state_enum.is_uploading:
            # Still seeding → copy
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                shutil.copy2(source, dest)
        else:
            # No longer seeding → move
            shutil.move(str(source), str(dest))
```

### Collect all hashes (for the tracker)

```python
with qbittorrentapi.Client(
    host="localhost", port=8081,
    username="izno", password="secret",
) as qbt:
    all_hashes = {t.hash for t in qbt.torrents_info()}
    # Used to clean up the tracker (drop hashes that disappeared)
```

This is exactly what `QBitClient.get_all_hashes()` does.

### Robust connection with retry

```python
import time
import qbittorrentapi

def connect_qbit(host, port, username, password, max_retries=3, delay=5):
    """Connect with retry, suitable for cron."""
    for attempt in range(max_retries):
        try:
            qbt = qbittorrentapi.Client(
                host=host, port=port,
                username=username, password=password,
                REQUESTS_ARGS={"timeout": 30},
            )
            qbt.auth_log_in()
            return qbt
        except qbittorrentapi.LoginFailed:
            raise  # do not retry on bad credentials
        except qbittorrentapi.APIConnectionError:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
```

> The pipeline's actual anti-ban strategy is stricter than a blind retry: it pre-checks
> reachability with `GET /` and, on a credential failure, writes a 1-hour lockout file so
> scheduled runs stop retrying until the operator fixes the credentials. See
> [Auth lockout](#auth-lockout-qbit-specific).

## Useful imports

```python
# Client
from qbittorrentapi import Client

# State enum
from qbittorrentapi import TorrentState

# Exceptions
from qbittorrentapi import (
    APIError,
    APIConnectionError,
    LoginFailed,
    Forbidden403Error,
)
```

## QBitClient — Write Capabilities (torrent-write, v0.20.0)

`QBitClient` (`personalscraper/api/torrent/qbittorrent.py`) composes two new
atomic `@runtime_checkable` Protocols introduced in `torrent-write`:

- **`TorrentAdder`** (`api/torrent/_contracts.py:124`) — add a torrent from a
  `TorrentSource` (magnet URI or `.torrent` bytes).
- **`TorrentLimiter`** (`api/torrent/_contracts.py:158`) — apply transfer limits
  (ratio, seed time, bandwidth) to an existing torrent.

### `QBitClient.add(source, *, category, tags, paused, limits) → str`

Adds a torrent to qBittorrent via `torrents_add`, with category, tags, paused
state, and limits all applied inline in a single call (DESIGN D1/D2/D6/D7/D8).

| Parameter  | Type                    | Required | Description                                      |
| ---------- | ----------------------- | -------- | ------------------------------------------------ |
| `source`   | `TorrentSource`         | yes      | Magnet URI or `.torrent` bytes (exactly one set) |
| `category` | `str \| None`           | no       | Category label (qBit category feature)           |
| `tags`     | `Sequence[str]`         | no       | Tag strings applied via comma-separated format   |
| `paused`   | `bool`                  | no       | Add in paused state (default `False`)            |
| `limits`   | `TorrentLimits \| None` | no       | Optional transfer limits; qBit honors all fields |

**Source routing**: magnet → `urls=` kwarg; file bytes → `torrent_files=` kwarg.
The native `qbittorrentapi.torrents_add()` accepts either shape.

**Limits applied inline** via `_limit_kwargs()`: `ratio_limit` (float),
`seeding_time_limit` (minutes × 60, because qBit's API expects **seconds**),
`upload_limit` (bytes/s), `download_limit` (bytes/s). All four are set in the
same `torrents_add` call — qBit is the only client that supports this (D2).

**Return value**: `source.info_hash` (lowercase hex SHA-1, per D6). On
duplicate, qBit returns `"Fails."` → treated as idempotent success (D7); the
existing `info_hash` is returned unchanged. 401 (`LoginFailed`) and 403
(`Forbidden403Error`) are caught and re-raised as the project's uniform
`ApiError`.

### `QBitClient.apply_limits(info_hash, limits) → None`

Applies transfer limits to an **existing** torrent (D2).

| Parameter   | Type            | Required | Description             |
| ----------- | --------------- | -------- | ----------------------- |
| `info_hash` | `str`           | yes      | Lowercase hex info_hash |
| `limits`    | `TorrentLimits` | yes      | Limits to apply         |

**Dispatch logic:**

- `ratio` or `seed_time_minutes` → `torrents_set_share_limits` with sentinel
  `-2` for unchanged fields (qBit convention: `-2` = "leave as-is").
- `up_bytes_per_s` → `torrents_set_upload_limit`.
- `down_bytes_per_s` → `torrents_set_download_limit`.
- All-`None` `TorrentLimits` → no-op (no API calls made).

### Capability Composition

| Capability          | QBitClient | Notes                                                         |
| ------------------- | ---------- | ------------------------------------------------------------- |
| `TorrentLister`     | ✓          | (pre-existing) list torrents                                  |
| `TorrentInspector`  | ✓          | (pre-existing) inspect single torrent                         |
| `TorrentController` | ✓          | (pre-existing) pause/resume/delete                            |
| `TorrentAdder`      | ✓          | add via `torrents_add` (category + tags + limits inline)      |
| `TorrentLimiter`    | ✓          | apply limits via `torrents_set_share_limits` / `_set_*_limit` |

## Sources

- [PyPI](https://pypi.org/project/qbittorrent-api/)
- [GitHub](https://github.com/rmartin16/qbittorrent-api) — MIT
- [qBittorrent Web API wiki](<https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)>)
