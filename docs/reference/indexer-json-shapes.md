# Indexer JSON Column Shapes

Every JSON column in the indexer schema (DESIGN §6.5) is validated by a Pydantic
model in `personalscraper/indexer/schema.py`. This document provides the
canonical shape and a concrete example for each column.

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

**Pydantic model**: `OutboxPayload` (`personalscraper/indexer/schema.py`)

Shape varies by the `op` column value. The model uses `extra="allow"` to
accommodate per-op extensions. The common envelope fields are:

| Field         | Type         | Present for                                              |
| ------------- | ------------ | -------------------------------------------------------- |
| `op`          | string       | All ops (must match parent `op`)                         |
| `source_path` | string\|null | `move`, `nfo_write`, `artwork_write`, `trailer_download` |
| `dest_path`   | string\|null | `move`                                                   |
| `item_id`     | int\|null    | All ops that have an item context                        |

### `op: "move"`

```json
{
  "op": "move",
  "source_path": "/Volumes/Staging/001-MOVIES/Inception (2010)",
  "dest_path": "/Volumes/Disk1/medias/films/Inception (2010)",
  "item_id": 42
}
```

### `op: "nfo_write"`

```json
{
  "op": "nfo_write",
  "source_path": "/Volumes/Disk1/medias/films/Inception (2010)/Inception (2010).nfo",
  "dest_path": null,
  "item_id": 42
}
```

### `op: "artwork_write"`

```json
{
  "op": "artwork_write",
  "source_path": "/Volumes/Disk1/medias/films/Inception (2010)/poster.jpg",
  "dest_path": null,
  "item_id": 42,
  "artwork_type": "poster"
}
```

### `op: "trailer_download"`

```json
{
  "op": "trailer_download",
  "source_path": null,
  "dest_path": "/Volumes/Disk1/medias/films/Inception (2010)/Trailers/Inception (2010)-trailer.mp4",
  "item_id": 42,
  "youtube_url": "https://www.youtube.com/watch?v=..."
}
```

---

## `pending_op.payload_json`

**Pydantic model**: `OutboxPayload` (same model as `index_outbox.payload_json`)

`pending_op` rows are created when a write-through event targets an **unmounted
disk**. The payload is identical in shape to `index_outbox.payload_json` — it
is replayed into the outbox when the disk remounts.

```json
{
  "op": "move",
  "source_path": "/Volumes/Staging/001-MOVIES/Dune (2021)",
  "dest_path": "/Volumes/Disk2/medias/films/Dune (2021)",
  "item_id": 117
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

**Pydantic model**: `ScanStats` (`personalscraper/indexer/schema.py`)

Written at scan completion (or on budget-exhaustion checkpoint).

```json
{
  "items_added": 3,
  "items_updated": 12,
  "items_deleted": 0,
  "files_walked": 8421,
  "bytes_read": 536870912,
  "budget_exhausted": false
}
```

| Field              | Type    | Default | Meaning                                             |
| ------------------ | ------- | ------- | --------------------------------------------------- |
| `items_added`      | int     | 0       | New `media_item` rows created.                      |
| `items_updated`    | int     | 0       | Existing `media_item` rows updated.                 |
| `items_deleted`    | int     | 0       | Items soft-deleted (`deleted_at` set).              |
| `files_walked`     | int     | 0       | Total files visited by the walker.                  |
| `bytes_read`       | int     | 0       | Total bytes read for fingerprinting.                |
| `budget_exhausted` | boolean | false   | `true` when halted due to budget; resume on re-run. |

Schema: `extra="forbid"` — unknown keys are rejected.

---

## `scan_event.payload_json`

**Pydantic model**: `ScanEventPayload` (`personalscraper/indexer/schema.py`)

Each event type carries different keys; the model is permissive (`extra="allow"`)
to avoid tight coupling with the per-event documentation.

### Common events

**`indexer.scan.checkpoint`** — written every N files to enable crash-resume.

```json
{
  "last_path": "001-MOVIES/Inception (2010)",
  "files_walked": 3000,
  "generation": 17
}
```

**`indexer.drift.tier1`** — stat-only change detected.

```json
{
  "file_id": 305,
  "old_mtime_ns": 1714300000000000000,
  "new_mtime_ns": 1714399999000000000
}
```

**`indexer.drift.rename`** — file moved or renamed; OSHash match found.

```json
{
  "file_id": 305,
  "old_path": "001-MOVIES/Inception (2010)/Inception.mkv",
  "new_path": "001-MOVIES/Inception (2010)/Inception (2010).mkv",
  "oshash": "a3f2e1d0c9b8a7b6"
}
```

**`indexer.drift.oshash_collision`** — two distinct files share the same OSHash;
escalated to `xxh3_full`.

```json
{
  "oshash": "deadbeefdeadbeef",
  "file_id_a": 101,
  "file_id_b": 202,
  "resolved_by": "xxh3_full"
}
```

**`indexer.fs.invalid_mtime`** — mtime clamped to valid range.

```json
{
  "path": "/Volumes/Disk1/medias/films/Old Movie (1999)/Old Movie (1999).mkv",
  "raw_mtime_ns": -1,
  "clamped_to": 0
}
```

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
