# Transmission RPC API Reference

Official reference: <https://github.com/transmission/transmission/blob/main/docs/rpc-spec.md>
Protocol: JSON-RPC 2.0 over HTTP POST
Endpoint: `http://host:9091/transmission/rpc`

## Architecture

Transmission RPC is **not REST**. It's a single POST endpoint accepting JSON-RPC 2.0 payloads
with `method` + `params.arguments`. All responses wrap results in `{"result": ..., "tag": ...}`.

```json
{
  "jsonrpc": "2.0",
  "method": "torrent-get",
  "params": { "fields": ["id", "name", "status"] },
  "id": 1
}
```

## Auth

HTTP Basic Access Authentication. `Authorization: Basic <base64(user:pass)>`.

The `transmission-rpc` Python library handles this transparently.

## CSRF / Session ID

Transmission uses `X-Transmission-Session-Id` header for CSRF protection:

1. Client sends request → server returns **HTTP 409** with `X-Transmission-Session-Id` in response headers
2. Client retries with that header → server processes normally

The `transmission-rpc` library handles this CSRF dance transparently.

## Torrent Status Codes

| Value | Meaning         | Seeding? |
| ----- | --------------- | -------- |
| 0     | Stopped         | No       |
| 1     | Queued to check | No       |
| 2     | Checking        | No       |
| 3     | Queued to DL    | No       |
| 4     | Downloading     | No       |
| 5     | Queued to seed  | Yes      |
| 6     | Seeding         | Yes      |

**"Completed" detection**: status **5** (queued/pending to seed) OR **6** (seeding) — and
**only** those two. The check is membership in `_COMPLETED_STATES`
(`personalscraper/api/torrent/transmission.py`), a `frozenset` of
`{transmission_rpc.Status.SEEDING, transmission_rpc.Status.SEED_PENDING}`. Status **4**
(downloading) and anything below it (0–3) are treated as in-progress **regardless of
`percent_done`** — `percent_done` is never consulted for completion. This differs from
qBittorrent where completion is `progress == 1.0` across multiple states.

## Methods used by the pipeline

### `torrent-get` (list torrents)

`POST /transmission/rpc` with `method: "torrent-get"`

| Parameter | Type   | Required | Description                        |
| --------- | ------ | -------- | ---------------------------------- | --------------------------------- |
| `ids`     | mixed  | no       | Omitted = all; int, [int           | str, ...], or `"recently_active"` |
| `fields`  | array  | yes      | Field keys to return               |
| `format`  | string | no       | `"objects"` (default) or `"table"` |

Returns `{"result": "success", "arguments": {"torrents": [...]}}`.

**Key fields for TorrentItem mapping:**

| Field             | Type   | Description                              |
| ----------------- | ------ | ---------------------------------------- |
| `id`              | int    | Torrent ID (not stable across restarts!) |
| `hash_string`     | string | SHA1 info hash (stable identifier)       |
| `name`            | string | Torrent display name                     |
| `total_size`      | int    | Total bytes of all files                 |
| `percent_done`    | double | 0.0–1.0 completion                       |
| `status`          | int    | 0–6 (see status table)                   |
| `download_dir`    | string | Download directory path                  |
| `added_date`      | int    | Unix epoch when added                    |
| `rate_download`   | int    | Current download speed (B/s)             |
| `rate_upload`     | int    | Current upload speed (B/s)               |
| `upload_ratio`    | double | Share ratio                              |
| `peers_connected` | int    | Connected peers                          |
| `eta`             | int    | Seconds until completion                 |
| `is_finished`     | bool   | True when download completed             |
| `is_stalled`      | bool   | True if no activity                      |
| `left_until_done` | int    | Bytes remaining                          |
| `size_when_done`  | int    | Bytes when download finishes             |
| `labels`          | array  | String labels                            |
| `files`           | array  | `[{name, length, bytes_completed}]`      |
| `file_stats`      | array  | `[{bytes_completed, wanted, priority}]`  |

> **Note**: `id` (integer) is **not stable across daemon restarts**. Use `hash_string` for persistent identification.

### `torrent-start` / `torrent-stop`

`method: "torrent-start"` / `method: "torrent-stop"`

| Parameter | Type  | Required | Description            |
| --------- | ----- | -------- | ---------------------- |
| `ids`     | mixed | no       | Omitted = all torrents |

Returns `{"result": "success"}` with no additional arguments.

### `torrent-remove`

`method: "torrent-remove"`

| Parameter           | Type    | Required | Description                   |
| ------------------- | ------- | -------- | ----------------------------- |
| `ids`               | array   | yes      | Torrent IDs/hashes            |
| `delete_local_data` | boolean | no       | Delete files (default: false) |

Returns `{"result": "success"}`.

### `torrent-add`

`method: "torrent-add"`

| Parameter      | Type    | Required | Description                     |
| -------------- | ------- | -------- | ------------------------------- |
| `filename`     | string  | \*       | URL or path to .torrent file    |
| `metainfo`     | string  | \*       | Base64-encoded .torrent content |
| `download_dir` | string  | no       | Custom download path            |
| `paused`       | boolean | no       | Don't start immediately         |
| `labels`       | array   | no       | String labels to apply          |
| `peer_limit`   | number  | no       | Max connected peers             |

\*Either `filename` or `metainfo` must be provided.

Returns `{"result": "success", "arguments": {"torrent_added": {"id": N, "name": "...", "hash_string": "..."}}}`.
On duplicate: `"torrent_duplicate"` key instead.

## Session methods

### `session_get`

Returns global Transmission configuration. Key fields: `version`, `rpc_version_semver`,
`download_dir`, `download_dir_free_space`, `seed_ratio_limit`, `session_id`.

### `session_stats`

Returns `torrent_count`, `active_torrent_count`, `download_speed`, `upload_speed`,
`cumulative_stats` and `current_stats` (each with `uploaded_bytes`, `downloaded_bytes`,
`files_added`, `seconds_active`, `session_count`).

### `free_space`

Queries free space at a given path: `{"path": "/data"}` → `{"path": "/data", "size_bytes": N, "total_size": N}`.

## Data mapping (Transmission → TorrentItem)

| Transmission field | TorrentItem field | Conversion                                      |
| ------------------ | ----------------- | ----------------------------------------------- |
| `hash_string`      | `hash`            | direct                                          |
| `name`             | `name`            | direct                                          |
| `total_size`       | `size_bytes`      | direct                                          |
| `percent_done`     | `progress`        | direct (already float 0.0–1.0)                  |
| `status`           | `state`           | `str(status)` — status codes 0–6                |
| `download_dir`     | `content_path`    | `Path(download_dir) / name`? Or field-dependent |
| `labels`           | `category`        | First label if any, else None                   |
| `added_date`       | `added_on`        | `datetime.fromtimestamp(added_date)`            |

**`content_path`**: Transmission does not provide a single `content_path` field.
The torrent data lives in `download_dir`. For single-file torrents: `Path(download_dir) / name`.
For multi-file torrents: `Path(download_dir)`. The `files` array provides per-file paths.

## Particularities

1. **CSRF session id**: handled by `transmission-rpc` library transparently.
2. **`percent_done` is float 0.0–1.0** (vs qBit's 0–1 int for completed). Already float — no cast needed.
3. **`total_size` is total bytes** — direct equivalent to `totalSize` (qBit 5.x), unlike `size` (selected).
4. **`download_dir` ≠ content_path**: Transmission stores files in `download_dir/<name>/` for multi-file
   torrents or `download_dir/<name>` for single-file. Content path resolution differs from qBit's `content_path`.
5. **Seed ratio modes**: `seed_ratio_mode` (0=global, 1=single, 2=unlimited) and `seed_ratio_limit`.
   Analogous to qBit's `ratio_limit` + `seeding_time_limit`.
6. **"Completed" detection differs from qBit**: only status 5 (seed-pending) or 6 (seeding)
   means completed (`_COMPLETED_STATES`). Status 4 (downloading) and below are in-progress
   regardless of `percent_done`. qBit instead uses `progress == 1.0` + state check.
7. **Integer torrent IDs are NOT stable across daemon restarts**. Must use `hashString` for persistence.
8. **JSON-RPC 2.0**: all responses wrapped in `{"jsonrpc": "2.0", "result": ..., "id": N}`.
   Error format: `{"jsonrpc": "2.0", "error": {"code": N, "message": "..."}, "id": N}`.
9. **DNS rebinding protection**: host whitelisting on by default. `localhost` always allowed.
10. **`ids` parameter** accepts int, [int|"hashString", ...], or `"recently_active"`.

## `transmission-rpc` library coverage

The `transmission-rpc` Python package handles:

- HTTP Basic Auth
- CSRF session-id dance (409 response → retry)
- JSON-RPC 2.0 request/response serialization
- All methods: `get_torrents`, `add_torrent`, `remove_torrent`, `start_torrent`, `stop_torrent`
- `get_session`, `set_session`, `free_space`

What we need beyond the library:

- **Pre-check**: Transmission does not have a "safe" root-page endpoint like qBit (`GET /`).
  The pre-check can be `session_get` with `fields=["version"]` — cheap, requires auth, exercises
  the full RPC stack including session-id dance. Using `HttpTransport(BasicAuth)` gives us
  observability and circuit-breaking parity with qBit.
- Content path resolution logic (mapping `download_dir` + `files` to a single path).

## HttpTransport decision (for Phase 11)

The plan proposes using `HttpTransport(BasicAuth)` for a pre-check on Transmission,
mirroring the qBittorrent pattern. Arguments:

- **Option A (recommended)**: `HttpTransport(LoginAuth)` for pre-check, `transmission-rpc` for ops.
  Pros: observability (logging), circuit breaker (don't hammer a dead daemon), parity with qBit.
  Cons: slightly more code, pre-check endpoint choice matters (recommend: `session_get` with version field).
- **Option B**: `transmission-rpc` only, no `HttpTransport`. Pros: simpler. Cons: less observability,
  no circuit breaker, harder to diagnose RPC errors at the infrastructure layer.

## TransmissionClient — Write Capabilities (torrent-write, v0.21.0)

`TransmissionClient` (`personalscraper/api/torrent/transmission.py`) composes
one new atomic `@runtime_checkable` Protocol introduced in `torrent-write`:

- **`TorrentAdder`** (`api/torrent/_contracts.py:124`) — add a torrent from a
  `TorrentSource` (magnet URI or `.torrent` bytes).
- `TorrentLimiter` is **not** composed — Transmission's RPC protocol has no
  equivalent of qBit's per-torrent ratio/seed-time/bandwidth limits (D2/D8).

### `TransmissionClient.add(source, *, category, tags, paused, limits) → str`

Adds a torrent to Transmission via `add_torrent`, with category and tags encoded
as labels (DESIGN D1/D5/D7/D8).

| Parameter  | Type                    | Required | Description                                       |
| ---------- | ----------------------- | -------- | ------------------------------------------------- |
| `source`   | `TorrentSource`         | yes      | Magnet URI or `.torrent` bytes (exactly one set)  |
| `category` | `str \| None`           | no       | Category (becomes `labels[0]`, per D5)            |
| `tags`     | `Sequence[str]`         | no       | Tag strings (appended after category in `labels`) |
| `paused`   | `bool`                  | no       | Add in paused state (default `False`)             |
| `limits`   | `TorrentLimits \| None` | no       | **Must be `None`**; raises if set (D8)            |

**Labels encoding (D5 round-trip).** Transmission has `labels` (array of
strings), no separate `category`/`tags` fields. The round-trip is:

- **Write**: `labels = [category, *deduped_tags]` where category is first and
  any duplicates are removed. The helper `_labels()` (`transmission.py:324`)
  implements this.
- **Read**: `category = labels[0] if labels else None`, `tags = labels[1:]`.
  This is applied in `_torrent_item()` when mapping a Transmission torrent to
  the internal `TorrentItem` dataclass.

**`limits` rejection (D8).** Passing a non-`None` `TorrentLimits` raises
`UnsupportedCapabilityError`. Callers gate via
`isinstance(client, TorrentLimiter)`. This follows the project's
no-silent-failure norm: capacity absence is a hard error, not a quiet ignore.

**Idempotence (D7).** A duplicate add returns the existing `info_hash`
successfully. Transmission returns a `transmission_rpc.TransmissionError` with
`"duplicate"` in its message string → caught and mapped to a success return
(the original lookup returns `source.info_hash`).

**Return value**: `source.info_hash` (per D6). Transmission echoes its own
`hashString` from the RPC response; it is logged as a cross-check at debug
level (`transmission_add_ok` event) but the caller always receives the
client-computed `info_hash`.

### Capability Composition

| Capability          | TransmissionClient | Notes                                              |
| ------------------- | ------------------ | -------------------------------------------------- |
| `TorrentLister`     | ✓                  | (pre-existing) list torrents via `torrent-get`     |
| `TorrentInspector`  | ✓                  | (pre-existing) inspect single torrent              |
| `TorrentController` | ✓                  | (pre-existing) start/stop/remove                   |
| `TorrentAdder`      | ✓                  | add via `add_torrent` (labels encoding, D5)        |
| `TorrentLimiter`    | ✗                  | **Not supported** (D2/D8); passing `limits` raises |
