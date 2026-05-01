# Indexer JSON Column Shapes

Every JSON column in the indexer schema (DESIGN §6.5) has a Pydantic
shape model in `personalscraper/indexer/schema.py`. This document provides
the canonical shape and a concrete example for each column.

> **Validation status (2026-05):** `ArtworkInventory` is the only model
> that is genuinely instantiated at write time (by `library/scanner.py`
> and `indexer/scanner/_modes.py`). The other models — `OutboxPayload`,
> `RepairPayload`, `ScanStats`, `ScanEventPayload`, `DeletedSnapshot`
> — currently serve as **documentation only**: production writers do
> `json.dumps` directly from a raw `dict` and readers parse with
> `json.loads` + `payload.get(key)`. The shapes below remain the
> contract; they are simply not enforced by the runtime today.

---

## `media_item.artwork_json`

**Pydantic model**: `ArtworkInventory` (`personalscraper/indexer/schema.py`)

Tracks which artwork types are present on disk for a media item. All fields
default to `false` so a freshly-indexed item can be written without probing the
filesystem.

```json
{
  "poster": true,
  "fanart": true,
  "landscape": false,
  "banner": false,
  "clearlogo": false,
  "clearart": false,
  "discart": false,
  "characterart": false
}
```

| Field          | Type    | Meaning                     |
| -------------- | ------- | --------------------------- |
| `poster`       | boolean | `poster.jpg` present.       |
| `fanart`       | boolean | `fanart.jpg` present.       |
| `landscape`    | boolean | `landscape.jpg` present.    |
| `banner`       | boolean | `banner.jpg` present.       |
| `clearlogo`    | boolean | `clearlogo.png` present.    |
| `clearart`     | boolean | `clearart.png` present.     |
| `discart`      | boolean | `discart.png` present.      |
| `characterart` | boolean | `characterart.png` present. |

Schema: `extra="forbid"` — unknown keys are rejected.

Generated virtual columns `has_poster` and `has_fanart` are computed directly
from this JSON via `json_extract()` and indexed for fast WHERE queries.

---

## `index_outbox.payload_json`

**Pydantic shape model (documentation only)**: `OutboxPayload`
(`personalscraper/indexer/schema.py`). The runtime apply functions in
`personalscraper/indexer/outbox.py` parse the dict directly — they do
not instantiate `OutboxPayload` — so the _real_ payload contract is
the set of `payload[...]` accesses inside each `_apply_*` function, not
the envelope fields on the Pydantic class. The shapes below mirror
those accesses verbatim.

### `op: "move"`

Apply function: `_apply_move` — UPSERTs a `media_file` row.

```json
{
  "disk_id": 1,
  "dst_rel_path": "films/Inception (2010)",
  "filename": "Inception (2010).mkv",
  "size_bytes": 8589934592,
  "mtime_ns": 1700000000000000000
}
```

`size_bytes` and `mtime_ns` may be omitted/null; in that case the row
is left to be reconciled by the next dir-mtime walk (DESIGN §17.1) and
the outbox row is still marked `'done'`.

### `op: "nfo_write"`

Apply function: `_apply_nfo_write` — UPDATEs `media_item.nfo_status`,
`tmdb_id`, `imdb_id`.

```json
{
  "disk_id": 1,
  "rel_path": "films/Inception (2010)/Inception (2010).nfo",
  "item_kind": "movie",
  "tmdb_id": 27205,
  "imdb_id": "tt1375666"
}
```

`rel_path` points at the `.nfo` file; the apply function resolves the
owning directory via `Path(rel_path).parent`. `item_kind` is
informational; `tmdb_id` / `imdb_id` are merged with `COALESCE`.

### `op: "artwork_write"`

Apply function: `_apply_artwork_write` — flips a boolean in
`media_item.artwork_json` via SQLite `json_set`.

```json
{
  "disk_id": 1,
  "rel_path": "films/Inception (2010)/poster.jpg",
  "kind": "poster"
}
```

The `kind` field is whitelisted by `_ALLOWED_ARTWORK_KINDS` in
`personalscraper/indexer/outbox.py` (DESIGN §9.6 defensive depth);
unknown values raise `OutboxPayloadError` before any DB UPDATE.

### `op: "trailer_download"`

Apply function: `_apply_trailer_download` — UPSERTs
`item_attribute(key='trailer_found')`.

```json
{
  "disk_id": 1,
  "rel_path": "films/Inception (2010)/Trailers/Inception (2010)-trailer.mp4",
  "trailer_path": "/Volumes/Disk1/medias/films/Inception (2010)/Trailers/Inception (2010)-trailer.mp4"
}
```

`rel_path` is the trailer FILE path; the apply function resolves the
owning directory via `Path(rel_path).parent` because the `path` table
stores directories, not individual files.

---

## `pending_op.payload_json`

**Shape model (documentation only)**: `OutboxPayload` — same shape model
as `index_outbox.payload_json`, same caveat that the runtime parses the
dict directly without instantiating the model.

`pending_op` rows are created when a write-through event targets an
**unmounted disk**. The payload is identical in shape to
`index_outbox.payload_json` (matching the apply-function dict accessors
listed above) — it is replayed into the outbox when the disk remounts.

```json
{
  "disk_id": 2,
  "dst_rel_path": "films/Dune (2021)",
  "filename": "Dune (2021).mkv",
  "size_bytes": 8589934592,
  "mtime_ns": 1700000000000000000
}
```

---

## `repair_queue.payload_json`

**Pydantic model**: `RepairPayload` (`personalscraper/indexer/schema.py`)

```json
{
  "context": "tier2 drift: size_bytes mismatch on Disk1 media_file id=305",
  "discovered_at": 1714300000,
  "evidence": {
    "expected_size": 4294967296,
    "actual_size": 4294967100,
    "file_path": "/Volumes/Disk1/medias/films/Inception (2010)/Inception (2010).mkv"
  }
}
```

| Field           | Type   | Required | Meaning                                        |
| --------------- | ------ | -------- | ---------------------------------------------- |
| `context`       | string | yes      | Human-readable description of the trigger.     |
| `discovered_at` | int    | yes      | Unix epoch seconds when drift was detected.    |
| `evidence`      | dict   | no       | Free-form key-value evidence from the scanner. |

Schema: `extra="forbid"` — unknown keys are rejected.

---

## `scan_run.stats_json`

**Shape model (documentation only)**: `ScanStats`
(`personalscraper/indexer/schema.py`). The runtime serialises a raw
`dict[str, int]` directly via `json.dumps` in
`personalscraper/indexer/scanner/__init__.py` (around the
`UPDATE scan_run SET stats_json` writes); the `ScanStats` Pydantic
class is documentation, not enforcement.

Written at scan completion (or on budget-exhaustion checkpoint). The
two write sites differ slightly in which counters are populated:

```json
{
  "files_visited": 8421,
  "dirs_visited": 312,
  "disks_skipped": 0
}
```

| Field           | Type | Written by                                                   | Meaning                                                                                      |
| --------------- | ---- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `files_visited` | int  | both branches (success + budget-exhausted)                   | Total files visited by the walker across all disks.                                          |
| `dirs_visited`  | int  | both branches                                                | Total directories visited.                                                                   |
| `disks_skipped` | int  | success branch only (omitted by the budget-exhausted branch) | Disks short-circuited by the Merkle root check (mode=quick) or unreachable-strikes guarding. |

Notes:

- The `ScanStats` Pydantic class declares richer fields
  (`items_added`, `items_updated`, `items_deleted`, `bytes_read`,
  `budget_exhausted`). Those are reserved for future runtime
  bookkeeping; today's writers do not populate them. Reader code
  treats missing keys as `0`/`False`.
- The budget-exhausted path writes `files_visited` + `dirs_visited`
  only (no `disks_skipped`); the post-mortem viewer should default
  the missing key.

---

## `scan_event.payload_json`

**Shape model (documentation only)**: `ScanEventPayload`
(`personalscraper/indexer/schema.py`). Permissive (`extra="allow"`),
not instantiated by the runtime.

**Current writers:** the only `insert_scan_event` call site today is
`personalscraper/indexer/scanner/__init__.py:187`, which writes one
row per scanned disk with `event = "indexer.scan.disk_done"`.

```json
{
  "disk_id": 1,
  "label": "Disk1",
  "files_visited": 3140,
  "dirs_visited": 122,
  "disks_skipped": 0
}
```

**Reserved events** — the original DESIGN listed several other event
types (`indexer.scan.checkpoint`, `indexer.drift.tier1`,
`indexer.drift.rename`, `indexer.drift.oshash_collision`,
`indexer.fs.invalid_mtime`) which are emitted to the **structured
log** (structlog) but are _not_ persisted to the `scan_event` table.
Future work may move them into `scan_event` for queryable audit; for
now grep the log file for those event names if you need them
post-mortem.

---

## `deleted_item.payload_json`

**Pydantic model**: `DeletedSnapshot` (`personalscraper/indexer/schema.py`)

A snapshot of the deleted row's columns at deletion time. The exact keys depend
on `kind`.

### `kind: "item"`

```json
{
  "kind": "item",
  "snapshot": {
    "id": 42,
    "title": "Inception",
    "year": 2010,
    "category_id": "movies",
    "tmdb_id": 27205,
    "nfo_status": "valid"
  }
}
```

### `kind: "file"`

```json
{
  "kind": "file",
  "snapshot": {
    "id": 305,
    "filename": "Inception (2010).mkv",
    "size_bytes": 4294967296,
    "mtime_ns": 1714300000000000000,
    "oshash": "a3f2e1d0c9b8a7b6",
    "miss_strikes": 3
  }
}
```

### `kind: "release"`

```json
{
  "kind": "release",
  "snapshot": {
    "id": 88,
    "item_id": 42,
    "quality": "1080p",
    "edition": null,
    "primary_lang": "fr"
  }
}
```

Schema: `extra="allow"` — additional snapshot fields are permitted to future-proof
the tombstone format.
