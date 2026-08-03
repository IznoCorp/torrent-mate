# Phase 1 — Config foundations + migration 014 + download_marks store

**Gate**: None (first phase). Requires: branch `feat/seed-caps` exists, DESIGN.md reviewed.

## Scope

`BandwidthConfig` nested model on `AcquireConfig`, `config.example/acquire.json5` update, migration 014 for `download_marks` table, plus the marks store CRUD + prune operations.

---

## Sub-phase 1.1: BandwidthConfig model + unit tests

**Commit**: `feat(seed-caps): add BandwidthConfig model with ByteSize coercion`

### Files

- **Modify**: `personalscraper/conf/models/acquire.py` — add `BandwidthConfig` class + field on `AcquireConfig`
- **Create**: `tests/conf/test_bandwidth_config.py` (NOTE: conf tests live FLAT in
  `tests/conf/` — there is no `tests/conf/models/` directory; verified 2026-08-03)

### Implementation

In `personalscraper/conf/models/acquire.py`, add import and class after `CadenceConfig`. Import `ByteSize` from `personalscraper.api._units`. The class uses `_StrictModel` base, 4 optional `int | None` fields (`per_torrent_down`, `per_torrent_up`, `global_down`, `global_up`), a `@field_validator(mode="before")` `_coerce_bytesize` that delegates `ByteSize.parse(v).bytes` for strings (D10), and a `@field_validator` `_reject_zero` that raises on `<= 0` (D2: zero is NOT unlimited). On `AcquireConfig`, add field `bandwidth: BandwidthConfig = Field(default_factory=BandwidthConfig)`. Add to `__all__`.

### Tests

In `tests/conf/test_bandwidth_config.py`, write unit tests covering:

1. **Defaults**: `BandwidthConfig()` → all four fields are `None`.
2. **ByteSize coercion**: Parametrized test — `"5MB"` → `5_000_000`, `"1GB"` → `1_000_000_000`, `"10MiB"` → `10_485_760`, etc. Int passthrough. None passthrough.
3. **Validation**: Zero rejected (`ValueError`). Negative rejected. Garbage string rejected.

### Gate

```bash
pytest tests/conf/test_bandwidth_config.py -v   # all pass
```

---

## Sub-phase 1.2: config.example update

**Commit**: `chore(seed-caps): add bandwidth block to config.example/acquire.json5`

### Files

- **Modify**: `config.example/acquire.json5`

### Implementation

In `config.example/acquire.json5`, add a commented block after the `cadence` section:

```json5
  // ── Bandwidth caps (O4 seed safety) ──────────────────────────────
  // Per-torrent AND global limits, in bytes/s. Humanized strings
  // accepted ("5MB", "1GB"). Omit a key (or set null) to leave the
  // current qBittorrent setting untouched.
  // "bandwidth": {
  //   "per_torrent_down": null,
  //   "per_torrent_up": null,
  //   "global_down": null,
  //   "global_up": null,
  // },
```

All values commented out and `null`.

### Gate

```bash
python -c "from personalscraper.conf.loader import load_config; c=load_config(); assert c.acquire.bandwidth.per_torrent_down is None; print('OK')"
```

---

## Sub-phase 1.3: Migration 014 + download_marks store

**Commit**: `feat(seed-caps): add migration 014 download_marks table + store`

### Files

- **Create**: `personalscraper/acquire/migrations/014_download_marks.sql`
- **Create**: `personalscraper/acquire/_download_marks.py`
- **Create**: `tests/acquire/test_download_marks.py`

### Migration 014

Create `personalscraper/acquire/migrations/014_download_marks.sql`:

```sql
-- Migration 014: download_marks table for exactly-once download event emission (O4/D7).

CREATE TABLE IF NOT EXISTS download_marks (
    info_hash           TEXT PRIMARY KEY,
    started_emitted     INTEGER NOT NULL DEFAULT 0,
    last_threshold      INTEGER NOT NULL DEFAULT 0,   -- 0 | 25 | 50 | 75
    completed_emitted   INTEGER NOT NULL DEFAULT 0,
    updated_at          REAL NOT NULL DEFAULT (CAST(strftime('%s', 'now') AS REAL))
);

PRAGMA user_version = 14;
```

(Repo convention — verified against `012_provenance_run_linkage.sql:33` and
`013_season_kind.sql:83`: the script itself bumps `PRAGMA user_version` so the DDL
and the version commit land in the same `executescript` transaction. There is NO
`schema_version` table in this schema; the runner `core/sqlite/_migrate.py` only
READS `PRAGMA user_version` to pick pending scripts.)

### Marks store (`_download_marks.py`)

Module `personalscraper.acquire._download_marks` with two classes:

**`DownloadMark`** dataclass: `info_hash: str`, `started_emitted: bool`, `last_threshold: int` (0/25/50/75), `completed_emitted: bool`.

**`DownloadMarksStore`** with `__init__(self, conn: sqlite3.Connection)`, `get(info_hash) -> DownloadMark | None`, `upsert(info_hash, *, started=None, threshold=None, completed=None) -> None` (partial update — only non-None kwargs are written), and `prune_stale(active_hashes: Iterable[str]) -> int` (deletes marks whose info_hash is not in active_hashes, returns count).

### Tests (`test_download_marks.py`)

In-memory SQLite with the migration DDL. Test cases:

- `get` on nonexistent returns `None`
- `upsert` insert then `get` returns correct mark
- `upsert` partial update (bump threshold only, started unchanged)
- `upsert` completed flag
- `prune_stale` removes closed hashes, keeps active
- `prune_stale` with empty active set deletes all

### Gate

```bash
pytest tests/acquire/test_download_marks.py -v      # all pass
make lint                                             # zero errors
python -c "import personalscraper"                    # smoke test
```

---

## Phase 1 Gate (before proceeding to Phase 2)

```bash
make lint
pytest tests/conf/test_bandwidth_config.py tests/acquire/test_download_marks.py -v
python -c "import personalscraper"
```

**Produces for Phase 2**: `BandwidthConfig` on `AcquireConfig` (importable), `DownloadMarksStore` (importable), `download_marks` table schema.
