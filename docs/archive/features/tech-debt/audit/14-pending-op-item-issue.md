# Audit — `pending_op` + `item_issue` tables (SH-6 / BD-U + BD-V)

> **Sub-phase**: 8.2 (phase-08-polish.md)
> **Acceptance criterion**: ACC-41
> **Date**: 2026-05-23
> **Baseline SHA**: 54268267178dba6b0df92b74261b1dfab154caac

## TL;DR

| Table        | Rows at audit (`05-bdd-audit.md`) | Real callers in `personalscraper/` | Real callers in `tests/` | Classification           | Decision                         |
| ------------ | --------------------------------- | ---------------------------------- | ------------------------ | ------------------------ | -------------------------------- |
| `pending_op` | 0                                 | **Yes — production wiring**        | Yes                      | Live (empty by accident) | **KEEP** — no DROP, no follow-up |
| `item_issue` | 0                                 | **Yes — production wiring**        | Yes                      | Live (empty by accident) | **KEEP** — no DROP, no follow-up |

The plan §8.2 assumption ("0 callers → DROP" / "0 callers or doc-only → design intent, not yet wired")
was based on the audit table content (0 rows) but did not cross-check the code wiring.
Both tables have full production wiring shipped before the tech-debt 0.16.0 audit.
The "0 rows" snapshot reflects pristine library state, not dead code.

No migration 007 entry is needed for these tables. No 0.17+ follow-up issue is needed.

---

## 1. Methodology

Cross-caller grep across `personalscraper/` and `tests/`, restricted to Python and SQL files
per the search-safety rule (CLAUDE.md). Then call-graph spot-check on each writer/reader to
confirm wiring is reachable from CLI entry points.

Plan §8.2 reserved the report path `15-pending-op-item-issue.md`, but `12-dead-infrastructure.md`
(reserved for sub-phase 8.4) is the path ACC-41 references. The next free index after
`13-ntfs-cache-pressure.md` is `14`, so this file lands at
`docs/features/tech-debt/audit/14-pending-op-item-issue.md` and ACC-41 is patched to match
(plan-drift handling).

---

## 2. `pending_op` — findings

### 2.1 Schema

Defined in `personalscraper/indexer/migrations/001_init.sql`:

```sql
CREATE TABLE pending_op (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  disk_id INTEGER NOT NULL REFERENCES disk(id),
  op TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  replayed_at TEXT
);
CREATE INDEX idx_pending_disk ON pending_op(disk_id);
```

Type: hinted-handoff queue for outbox operations whose target disk was unreachable at drain
time (DESIGN §9.2).

### 2.2 Production callers

Repository (`personalscraper/indexer/repos/outbox_repo.py`) — full CRUD:

- `insert_pending_op(conn, row) -> int`
- `insert_pending_op_row(conn, disk_id, op, payload_json) -> int`
- `get_pending_op_by_id(conn, id) -> PendingOpRow | None`
- `fetch_for_disk(conn, disk_id) -> list[PendingOpRow]`
- `mark_replayed(conn, row_id) -> None`
- `purge_expired(conn, ttl_days=30) -> int`
- `claim_pending_op(conn, id)` + `complete_pending_op(conn, id, status, now)` — outbox-row state
  machine helpers (these operate on `index_outbox`, not `pending_op`; named per the lifecycle
  step "pending op claim/complete").

Drain (`personalscraper/indexer/outbox/_drain.py`):

- `_replay_pending_ops(conn, disk_id, stats)` — called at the start of every drain run for any
  disk that has unreplayed rows. Reads via `fetch_for_disk`, dispatches per `op` type, marks
  via `mark_replayed`.
- `drain()` main loop — calls `insert_pending_op_row(...)` whenever an outbox row targets a disk
  whose mount is unreachable, then continues processing.
- TTL purge of stale `pending_op` rows older than 30 days runs at end of every drain.

Schema metadata (`personalscraper/indexer/schema.py`):

- `OutboxSource = Literal["dispatch", "scraper", "trailers", "scanner", "pending_op"]` — replay
  source tagging.
- `PendingOpRow` dataclass row type for the table.

### 2.3 Test coverage

- `tests/indexer/test_schema.py` — round-trip insert/get/claim/complete.
- `tests/indexer/test_outbox.py` — round-trip insert + fetch, drain deferral + replay, TTL purge,
  FK violation on missing disk row.
- `tests/indexer/test_migrations.py` — table present after migrations.
- `tests/e2e/test_pipeline_indexer.py` — E2E drain defers to `pending_op` when no disk mounted.

### 2.4 Why was the table empty at audit time?

The hinted-handoff path is only exercised when a target disk is unmounted at drain time.
On the operator's live BDD (`05-bdd-audit.md`), all 4 disks were mounted during recent
drains, so no deferral happened. The wiring is correct and tested; "0 rows" is a normal
operating state, not evidence of dead code.

### 2.5 Decision — `pending_op`

**KEEP. No DROP, no migration 007 entry, no 0.17+ follow-up.**

The table is live production infrastructure. The plan's "0 callers → DROP" trigger does not
apply: production callers exist in `outbox_repo.py` + `outbox/_drain.py` and are exercised by
both unit and E2E tests.

---

## 3. `item_issue` — findings

### 3.1 Schema

Defined in `personalscraper/indexer/migrations/001_init.sql`:

```sql
CREATE TABLE item_issue (
  item_id INTEGER NOT NULL REFERENCES media_item(id),
  type TEXT NOT NULL,
  detail TEXT,
  detected_at TEXT NOT NULL,
  PRIMARY KEY (item_id, type)
);
```

Type: directory-hygiene issue tags persisted per `media_item` so reporting layer can surface
them without rescanning the FS.

### 3.2 Production callers

Writer (`personalscraper/library/scanner.py`):

```python
conn.execute("DELETE FROM item_issue WHERE item_id = ?", (item_id,))
# then for each detected hygiene issue:
conn.execute(
    "INSERT OR IGNORE INTO item_issue (item_id, type, detail, detected_at) VALUES (?, ?, NULL, ?)",
    ...
)
```

Reader (`personalscraper/library/analyzer.py:~285`):

```python
rows = conn.execute("SELECT type, COUNT(*) FROM item_issue GROUP BY type").fetchall()
```

Aggregated counts surface in `LibraryReport.scan_issues` (see `analyzer.py:109-112` docstring
and `library/reporter.py` rendering).

Reference in `release_linker.py:322` is **doc-only** in the docstring ("caller can decide to
surface this via item_issue / log") — that line does not insert into `item_issue`. Matches
the plan's note.

### 3.3 Test coverage

- `tests/library/test_scanner.py` — `test_item_issue_rows_persisted_for_dirty_dir` +
  `test_item_issue_drops_resolved_issues_on_rescan` (insert + idempotent delete-and-reinsert).
- `tests/library/test_integration.py` — E2E `scan_library` persists `item_issue` rows for
  `.actors/` + junk files; cleanup rescan drops them.
- `tests/library/test_analyzer.py` — `test_scan_issues_aggregated_from_item_issue` +
  empty-table baseline.
- `tests/indexer/test_migrations.py` — table present after migrations.

### 3.4 Why was the table empty at audit time?

`item_issue` rows are written during `library scan_library()` runs. If the audited BDD
snapshot was taken after a recent `library-init-canonical` or a scan against a clean
fixture (no `.actors/`, no junk files, no `[GROUP]` artefacts), the table is legitimately
empty. The current production library may also simply have no hygiene issues to flag.

### 3.5 Decision — `item_issue`

**KEEP. No DROP, no migration 007 entry, no 0.17+ follow-up.**

The table is live production infrastructure exercised by scanner writes + analyzer reads,
with both unit and integration tests. The plan's "0 callers or doc-only → design intent,
not yet wired" trigger does not apply: real INSERT happens in `library/scanner.py` and real
SELECT in `library/analyzer.py`. The `release_linker.py:322` mention is doc-only as the
plan correctly noted, but it is not the only mention.

---

## 4. Grep commands and output (traceability)

### 4.1 `pending_op` callers

```bash
rg --type py "pending_op" personalscraper/ tests/
```

Output summary:

- `personalscraper/indexer/schema.py` — `OutboxSource` literal + `PendingOpRow` dataclass docstring
- `personalscraper/indexer/repos/outbox_repo.py` — full CRUD (insert / get / fetch / mark / purge / claim / complete)
- `personalscraper/indexer/outbox/_drain.py` — `_replay_pending_ops`, deferral on unmount, TTL purge,
  log events `indexer.pending_op.*`
- `personalscraper/indexer/outbox/_types.py` — `DrainStats.deferred` field docstring
- `tests/indexer/test_schema.py` — round-trip insert/get/claim/complete
- `tests/indexer/test_outbox.py` — drain defer + replay + TTL + FK
- `tests/indexer/test_migrations.py` — schema migration coverage
- `tests/e2e/test_pipeline_indexer.py` — E2E drain deferral

```bash
rg --type py "INSERT INTO pending_op" personalscraper/ tests/
```

Output:

- `personalscraper/indexer/repos/outbox_repo.py` — two INSERTs (one in `insert_pending_op`,
  one in `insert_pending_op_row`)
- `tests/indexer/test_outbox.py` — two raw-SQL INSERTs used by test fixtures to seed rows
  for replay scenarios

### 4.2 `item_issue` callers

```bash
rg --type py "item_issue" personalscraper/ tests/
```

Output summary:

- `personalscraper/indexer/schema.py` — `ItemIssueRow` dataclass docstring
- `personalscraper/library/scanner.py` — DELETE-then-INSERT-OR-IGNORE pair
- `personalscraper/library/analyzer.py` — SELECT type, COUNT(\*) aggregation
- `personalscraper/library/reporter.py` — narrative docstrings on rendering
- `personalscraper/indexer/release_linker.py:322` — doc-only mention in docstring (no insert)
- `tests/library/test_scanner.py` — persistence + rescan drop tests
- `tests/library/test_integration.py` — E2E persistence + cleanup
- `tests/library/test_analyzer.py` — aggregation + empty-table tests
- `tests/indexer/test_migrations.py` — schema migration coverage

```bash
rg --type py "INSERT INTO item_issue" personalscraper/ tests/
```

Output:

- `tests/library/test_analyzer.py` — one raw-SQL INSERT used by test fixture to seed rows
- (the scanner production INSERT uses `INSERT OR IGNORE` so doesn't match this literal)

### 4.3 Production INSERT — `item_issue` (production form)

```bash
rg --type py "INSERT OR IGNORE INTO item_issue" personalscraper/
```

Output:

- `personalscraper/library/scanner.py` — the real writer.

### 4.4 SQL files

```bash
rg -g '*.sql' "pending_op|item_issue" personalscraper/
```

Output:

- `personalscraper/indexer/migrations/001_init.sql` — both tables defined here
- `personalscraper/indexer/migrations/001_init.sql` — `idx_pending_disk` index on `pending_op(disk_id)`

No subsequent migration touches either table.

---

## 5. Cross-references

- Plan §8.2 in `docs/features/tech-debt/plan/phase-08-polish.md` lines 58-67 — sub-phase spec.
- Audit `docs/features/tech-debt/audit/05-bdd-audit.md` lines 38, 40 — original "0 rows" snapshot.
- Audit `docs/features/tech-debt/audit/05-bdd-audit.md` line 260 (item 7 area, P12 CLI surface) —
  the doc that flagged `pending_op` as "mécanisme zombie ?" question, which this audit answers.
- `docs/reference/event-bus.md` and `docs/reference/indexer.md` for outbox/drain context.
- `ACCEPTANCE.md` ACC-41 — patched in the same commit to point at this file
  (`14-pending-op-item-issue.md`) instead of the previously-cited `12-dead-infrastructure.md`
  (which is reserved for sub-phase 8.4).

---

## 6. Operator instructions (none required)

No code change, no migration, no follow-up issue. Sub-phase 8.2 deliverable is this audit
document plus the ACC-41 patch.

If `pending_op` or `item_issue` rows are observed in production later, the wiring is ready
to handle them (drain replays `pending_op`, analyzer aggregates `item_issue`). Re-running
`personalscraper library-analyze` against a library with junk files would populate
`item_issue`; running `personalscraper indexer drain` while a disk is unmounted would
populate `pending_op`.
