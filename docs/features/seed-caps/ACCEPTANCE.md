# Seed Caps — Acceptance Criteria

> **Feature**: seed-caps (#177 — [O4] Seed Safety)
> **Version**: 0.76.0
> **Date**: 2026-08-03
> **DESIGN**: docs/features/seed-caps/DESIGN.md
> **Plan**: docs/features/seed-caps/plan/phase-04-subscribers-frontend-acceptance.md
>
> Every criterion is an executable shell command with documented expected output.
> Prose-only criteria are invalid per SH-16 / tech-debt 0.16.0.
> Status is updated at each phase gate and at the final PR gate.

---

## ACC-01 — BandwidthConfig loads with defaults (all None)

**What**: A bare `BandwidthConfig()` yields `None` on all four caps — "touch
nothing" is the default, never a surprise reset of the operator's client settings.
**Scope**: DESIGN §3.1 / D1 (config at `acquire.bandwidth`) + D2 (`None` = no-op per field).

```bash
command python3 -c "
from personalscraper.conf.models.acquire import BandwidthConfig
cfg = BandwidthConfig()
assert cfg.per_torrent_down is None and cfg.per_torrent_up is None
assert cfg.global_down is None and cfg.global_up is None
print('OK: all four caps default to None')
"
# Expected: OK: all four caps default to None (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: all four caps default to None`)

---

## ACC-02 — ByteSize coercion ("5MB" → 5_000_000)

**What**: Humanized byte-size strings are coerced to integer bytes/s via the
canonical `ByteSize` parser.
**Scope**: DESIGN §3.1 / D10 (reuse the `conf/models/_ranking.py` ByteSize pattern).

```bash
command python3 -c "
from personalscraper.conf.models.acquire import BandwidthConfig
cfg = BandwidthConfig(per_torrent_down='5MB')
assert cfg.per_torrent_down == 5_000_000, cfg.per_torrent_down
print('OK: 5MB ->', cfg.per_torrent_down)
"
# Expected: OK: 5MB -> 5000000 (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: 5MB -> 5000000`)

---

## ACC-03 — Zero values rejected

**What**: `0` is NOT the unlimited sentinel — it is rejected with a validation
error. Unlimited is expressed by omitting the key (`None`).
**Scope**: DESIGN §3.1 / D2 (zero rejected; the qBittorrent wire value 0 is
produced only by the mapper, never written by the operator).

```bash
command python3 -c "
from pydantic import ValidationError
from personalscraper.conf.models.acquire import BandwidthConfig
try:
    BandwidthConfig(per_torrent_down=0)
except ValidationError as e:
    assert 'must be > 0' in str(e), str(e)
    print('OK: zero rejected with ValidationError (must be > 0)')
else:
    raise SystemExit('FAIL: zero accepted')
"
# Expected: OK: zero rejected with ValidationError (must be > 0) (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: zero rejected with ValidationError (must be > 0)`)

---

## ACC-04 — Migration 014 schema valid

**What**: `014_download_marks.sql` executes cleanly on a fresh database, creates
the `download_marks` table with the exact 5-column shape, and bumps
`user_version` to 14 in the same script.
**Scope**: DESIGN §3.5 / D7 (exactly-once marks table, migration 014).

```bash
command python3 -c "
import sqlite3
sql = open('personalscraper/acquire/migrations/014_download_marks.sql').read()
conn = sqlite3.connect(':memory:')
conn.executescript(sql)
cols = [r[1] for r in conn.execute('PRAGMA table_info(download_marks)')]
assert cols == ['info_hash', 'started_emitted', 'last_threshold', 'completed_emitted', 'updated_at'], cols
ver = conn.execute('PRAGMA user_version').fetchone()[0]
assert ver == 14, ver
print('OK: download_marks schema valid, user_version=14')
"
# Expected: OK: download_marks schema valid, user_version=14 (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: download_marks schema valid, user_version=14`)

---

## ACC-05 — DownloadMarksStore CRUD + prune

**What**: `upsert` (partial update, case-insensitive key), `get`, and
`prune_stale` round-trip against a fresh in-memory database.
**Scope**: DESIGN §3.5 / D7 (advisory marks store, pruned when the hash leaves
the open set).

```bash
command python3 -c "
import sqlite3
from personalscraper.acquire._download_marks import DownloadMarksStore
conn = sqlite3.connect(':memory:')
conn.executescript(open('personalscraper/acquire/migrations/014_download_marks.sql').read())
store = DownloadMarksStore(conn)
store.upsert('ABCDEF', started=True)
store.upsert('abcdef', threshold=50)
m = store.get('ABCDEF')
assert m is not None and m.started_emitted is True and m.last_threshold == 50 and m.completed_emitted is False, m
pruned = store.prune_stale([])
assert pruned == 1 and store.get('abcdef') is None, pruned
print('OK: upsert/get/prune roundtrip (case-insensitive key, partial update)')
"
# Expected: OK: upsert/get/prune roundtrip (case-insensitive key, partial update) (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: upsert/get/prune roundtrip (case-insensitive key, partial update)`)

---

## ACC-06 — Download events importable + constructable

**What**: `DownloadStarted`, `DownloadProgressed`, `DownloadCompleted` are
importable from `personalscraper.acquire.events` and constructable with their
documented kw-only fields.
**Scope**: DESIGN §3.4 (RP4 catalogue additions).

```bash
command python3 -c "
from personalscraper.acquire.events import DownloadStarted, DownloadProgressed, DownloadCompleted
e = DownloadStarted(info_hash='abc123', title='Breaking Bad S05E01', provider='c411', kind='episode')
p = DownloadProgressed(info_hash='abc123', title='Breaking Bad S05E01', progress=0.5, threshold_pct=50)
c = DownloadCompleted(info_hash='abc123', title='Breaking Bad S05E01', provider='c411', kind='episode')
print('OK: all three events constructable:', e.title, '/', p.threshold_pct, '/', c.kind)
"
# Expected: OK: all three events constructable: Breaking Bad S05E01 / 50 / episode (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: all three events constructable: Breaking Bad S05E01 / 50 / episode`)

---

## ACC-07 — reconcile_wanted new signature

**What**: `reconcile_wanted` takes `client_items` (positional) and a REQUIRED
keyword-only `event_bus`; the old `client_hashes` parameter is gone.
**Scope**: DESIGN §3.6 / D9 (signature change, event_bus required at every
emission site).

```bash
command python3 -c "
import inspect
from personalscraper.acquire.reconcile import reconcile_wanted
sig = inspect.signature(reconcile_wanted)
params = list(sig.parameters)
assert 'client_items' in params and 'event_bus' in params, params
assert 'client_hashes' not in params, params
assert sig.parameters['event_bus'].kind is inspect.Parameter.KEYWORD_ONLY
assert sig.parameters['event_bus'].default is inspect.Parameter.empty
print('OK: params =', params)
"
# Expected: OK: params = ['store', 'ownership', 'client_items', 'event_bus', 'record_obligation'] (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK: params = ['store', 'ownership', 'client_items', 'event_bus', 'record_obligation']`)

---

## ACC-08 — No stale reconcile_wanted callers

**What**: Every call site passes `client_items` — the only line NOT mentioning
`client_items` is the `def` line itself.
**Scope**: DESIGN §3.6 / D9 (all callers updated).

```bash
rg "reconcile_wanted\(" --type py personalscraper/ tests/ | grep -v client_items
# Expected: exactly ONE line — personalscraper/acquire/reconcile.py:def reconcile_wanted(
# (any other line = a stale caller not passing client_items)
```

**Status**: PASS (exercised 2026-08-03 — observed exactly one line:
`personalscraper/acquire/reconcile.py:def reconcile_wanted(`)

---

## ACC-09 — Frontend French labels present

**What**: The three download event types have French labels in
`EVENT_TYPE_LABEL` (web feed shows all three — Telegram only gets Completed).
**Scope**: DESIGN §3.7 / D8 (web feed labels).

```bash
grep -cE '(DownloadStarted|DownloadProgressed|DownloadCompleted): "Téléchargement' frontend/src/components/dashboard/eventRow.utils.ts
# Expected: 3 (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `3`)

---

## ACC-10 — make lint zero errors

**What**: ruff check + ruff format + mypy + logging-convention audit all clean.
**Scope**: Phase 4 full gate.

```bash
make lint
# Expected: exit 0 — "All checks passed!", "NNNN files already formatted",
# "Success: no issues found in NNN source files", "0 finding(s): 0 error(s), 0 warning(s)"
```

**Status**: PASS (exercised 2026-08-03 — observed `All checks passed!` /
`1254 files already formatted` / `Success: no issues found in 476 source files` /
`0 finding(s): 0 error(s), 0 warning(s)`)

---

## ACC-11 — make test zero failures

**What**: The full backend suite passes with 0 failed / 0 errors.
**Scope**: Phase 4 full gate.

```bash
make test
# Expected: exit 0 — summary line "NNNNN passed, N skipped, N xfailed" with 0 failed.
```

**Status**: PASS (exercised 2026-08-03 — observed
`10161 passed, 3 skipped, 2 xfailed, 796 warnings in 80.10s (0:01:20)`)

---

## ACC-12 — Import smoke test

**What**: The package imports cleanly.
**Scope**: Phase 4 full gate.

```bash
command python3 -c "import personalscraper; print('OK')"
# Expected: OK (exit 0)
```

**Status**: PASS (exercised 2026-08-03 — observed `OK`)

---

## Re-exercise Log

| Date       | Phase | ACC-01 | ACC-02 | ACC-03 | ACC-04 | ACC-05 | ACC-06 | ACC-07 | ACC-08 | ACC-09 | ACC-10 | ACC-11 | ACC-12 |
| ---------- | ----- | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| 2026-08-03 | 4     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     | ✅     |

Run notes (2026-08-03, sub-phase 4.3 full gate):

- ACC-01..09 + ACC-12: each command ran individually from the project root —
  observed outputs recorded verbatim in the per-criterion Status lines above.
- Full gate: the FIRST `make test` run failed 2 architecture tests
  (`test_conf_does_not_import_upward`, `test_real_layering_markers_carry_justifications`):
  the seed-caps `ByteSize` import at `conf/models/acquire.py:15` carried a bare
  `# layering: allow` marker with no justification. Fixed in this sub-phase by
  adding the preceding justification comment (same documented boundary as
  `conf/models/_ranking.py`, per D10). Second run fully green:
  `10161 passed, 3 skipped, 2 xfailed` — 0 failed, 0 errors.
- `make check` exit 0 same day: backend under coverage `10024 passed, 3 skipped,
2 xfailed` (coverage deselects ~137 tests vs `make test` — known gap, 0-failures
  is the gate), module-size 4 advisory findings (soft warnings, 0.9.0 policy),
  PRAGMA discipline OK (471 files, 0 violations), typed-api OK,
  version bump OK 0.75.2 → 0.76.0, frontend vitest `1136 passed (116 files)`,
  frontend build + PWA precache OK.
- Stale-signature sweep: `rg "client_hashes" --type py personalscraper/acquire/reconcile.py`
  → 3 matches, ALL the internal derived local inside the function body
  (line 354 `client_hashes = set(client_items) if client_items is not None else None`
  - two consumers at 423/440). No parameter, no stale docstring — conformant to D9.
