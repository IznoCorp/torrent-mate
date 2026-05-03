# Indexer JSON Column Shapes

Every JSON column in the indexer schema (DESIGN §6.5) has a Pydantic
shape model in `personalscraper/indexer/schema.py`. This document provides
the canonical shape and a concrete example for each column.

> **Validation status (2026-05):** `ArtworkInventory` is the only model
> that is genuinely instantiated at write time (by `library/scanner.py`
> and `indexer/scanner/_modes/verify.py`). The other models — `OutboxPayload`,
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
`personalscraper/indexer/outbox/_apply.py` parse the dict directly — they do
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
producer-only metadata — `_apply_nfo_write` never reads it. `tmdb_id` /
`imdb_id` are merged with `COALESCE`.

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
`personalscraper/indexer/outbox/_apply.py` (DESIGN §9.6 defensive depth);
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

**Shape model (documentation only)**: `RepairPayload`
(`personalscraper/indexer/schema.py`). Not instantiated by the
runtime; each producer dumps its own dict (or `NULL`) into the
column.

The `RepairPayload` Pydantic model defines a `{context, discovered_at,
evidence}` envelope, but it is **documentation-only** — the runtime
never instantiates it. Each producer dumps its own dict (or `NULL`)
directly. The trigger reason is in the sibling `reason` text column on
the same `repair_queue` row; the discovery time is in the `enqueued_at`
column. `payload_json` carries detector-specific evidence only.

### Producer: `library-verify` (scanner `verify` mode)

```python
# personalscraper/indexer/scanner/_modes/verify.py — file missing on disk
payload_json=None
```

```json
// personalscraper/indexer/scanner/_modes/verify.py — size or mtime drift detected
{
  "expected_size": 4294967296,
  "actual_size": 4294967100,
  "expected_mtime_ns": 1714300000000000000,
  "actual_mtime_ns": 1714399999000000000
}
```

### Producer: `library-reconcile`

```json
// indexer/reconcile.py ~L423 — typical detector payload
{
  "detector": "merkle"
}
```

The `DivergenceItem.payload` field accepts `dict[str, object]`;
each detector chooses its own keys and is expected to keep them
forward-compatible.

---

## `scan_run.stats_json`

**Shape model (documentation only)**: `ScanStats`
(`personalscraper/indexer/schema.py`). The runtime serialises a raw
`dict[str, int]` directly via `json.dumps` in
`personalscraper/indexer/scanner/__init__.py` (around the
`UPDATE scan_run SET stats_json` writes); the `ScanStats` Pydantic
class is documentation, not enforcement.

**Runtime keys differ from model fields.** The `ScanStats` Pydantic
class declares `files_walked`, `items_added`, `items_updated`,
`items_deleted`, `bytes_read`, `budget_exhausted` — but the runtime
writes different keys (`files_visited`, `dirs_visited`,
`disks_skipped`). The JSON and table below document the **runtime
shape**; the model fields are listed in the Notes section.

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

- The `ScanStats` Pydantic class declares fields
  (`files_walked`, `items_added`, `items_updated`, `items_deleted`,
  `bytes_read`, `budget_exhausted`). Those are reserved for future
  runtime bookkeeping; today's writers do not populate them. Reader
  code treats missing keys as `0`/`False`.
- The budget-exhausted path writes `files_visited` + `dirs_visited`
  only (no `disks_skipped`); the post-mortem viewer should default
  the missing key.

---

## `scan_event.payload_json`

**Shape model (documentation only)**: `ScanEventPayload`
(`personalscraper/indexer/schema.py`). Permissive (`extra="allow"`),
not instantiated by the runtime.

**Current writers:** the only `insert_scan_event` call site today is
`personalscraper/indexer/scanner/__init__.py` (~L189), which writes one
row per scanned disk with `event = "indexer.scan.disk_done"`.

```json
{
  "disk_id": 1,
  "label": "Disk1",
  "files_visited": 3140,
  "dirs_visited": 122,
  "merkle_root": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
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

**Shape model (documentation only)**: `DeletedSnapshot`
(`personalscraper/indexer/schema.py`). **WARNING**: the Pydantic model
declares `kind: str` and `snapshot: dict` fields that do NOT match the
runtime payload (which is a flat dict). `model_validate_json()` on a
real row WILL fail. The model should be reconciled with the actual
writer in `indexer/drift.py`. The runtime writer builds a flat dict
with `json.dumps` directly.

**Current writer:** the only `insert_deleted_item` call site today
is the n-strikes file-level soft-delete in `indexer/drift.py:530`.
`deleted_item` rows always have `kind = 'file'`; `kind = 'item'`
and `kind = 'release'` are reserved for future tombstone writers
(item-level soft delete is not implemented yet — see DESIGN §8.3).

### `kind: "file"` — only kind currently written

The payload is a **flat snapshot** (no `kind` wrapper, no `snapshot`
sub-key — the columns of the deleted `media_file` row inlined):

```json
{
  "id": 305,
  "path_id": 47,
  "filename": "Inception (2010).mkv",
  "oshash": "a3f2e1d0c9b8a7b6",
  "size_bytes": 4294967296,
  "mtime_ns": 1714300000000000000
}
```

The deletion `reason` and `deleted_at` epoch are stored on the
`deleted_item` row itself (separate columns), not in `payload_json`.

### `kind: "item"`, `kind: "release"` — reserved

Not currently written by any code path. When the item-level / release-
level soft-delete worker lands the payload shape will be defined in a
follow-up; do not rely on speculative shapes from earlier drafts of
this document.
