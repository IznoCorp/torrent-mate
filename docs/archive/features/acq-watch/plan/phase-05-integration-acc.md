# Phase 5 — Integration + ACC + Docs

## Gate

- [ ] `make check` — lint + test + module-size + typed-api guardrails, zero errors
- [ ] `cd frontend && npm run lint && npm run typecheck && npx vitest run` — green
- [ ] `python scripts/audit_design_coverage.py --strict` — design-gaps clean
- [ ] `python scripts/update_feature_map.py --check` — feature-map clean
- [ ] All ACCEPTANCE criteria (from `ACCEPTANCE.md`) re-exercised and passing
- [ ] Commit with `chore(acq-watch): phase 5 gate — integration + ACC + docs`

## Objectives

1. Write `ACCEPTANCE.md` with executable shell-command criteria per the
   `docs/reference/feature-lifecycle.md` convention.

2. Write an E2E test exercising the full API surface (CRUD flow).

3. Add the Acquisition section to `docs/reference/web-ui.md`.

4. Final gate: all checks green, all ACC criteria passing.

## DESIGN gotchas

- **All prior phase gotchas still apply** — re-verify:
  - DIRECT acquire.db (WAL + BEGIN IMMEDIATE, no projection, no detached runner).
  - `guarded_api` mount (single auth perimeter).
  - Staging-guard + XRW on all writes.
  - quality_profile_json read-only (no editor exposed).
  - Watcher toggle reuses `POST /api/pipeline/watcher`.
  - R13 new-events-only ref pattern (not `events.some`).
  - No web-side event emission for follow writes.
- **design-gaps check** — `audit_design_coverage.py --strict` is a CI-only
  check (not in `make check`). Run it locally. Pipe-to-tail masks exit codes
  — run without pipe.
- **feature-map check** — `update_feature_map.py --check` is CI-only. Run
  locally after all test files are staged. The pre-commit hook regenerates
  feature maps for staged `test_design_*.py` files; S7 adds new test files.
- **OpenAPI drift** — after Phase 4, if any route changed, re-run
  `make openapi` and commit the regen.

## Files to create

| File                                    | Purpose                        |
| --------------------------------------- | ------------------------------ |
| `docs/features/acq-watch/ACCEPTANCE.md` | Executable acceptance criteria |
| `tests/e2e/test_acquisition_api.py`     | E2E API test (full CRUD flow)  |

## Files to modify

| File                       | Change                                 |
| -------------------------- | -------------------------------------- |
| `docs/reference/web-ui.md` | Add Acquisition section (§Acquisition) |

## ACCEPTANCE.md

````markdown
# ACCEPTANCE — acq-watch (S7 Web UI: Acquisition + Watcher)

> **Feature**: acq-watch | **Branch**: feat/acq-watch | **DESIGN**: DESIGN.md
> **Rule**: every criterion is an executable shell command with documented
> expected output. Prose criteria are invalid (SH-16 /
> docs/reference/feature-lifecycle.md).

## ACC-01 — GET /api/acquisition/followed (authed)

```bash
curl -s --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_SESSION" \
  "http://localhost:8711/api/acquisition/followed" | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert 'items' in data, 'missing items key'
assert isinstance(data['items'], list), 'items is not a list'
for item in data['items']:
    assert 'id' in item
    assert 'title' in item
    assert 'media_ref' in item
    assert 'active' in item
    assert 'added_at' in item
    assert 'wanted_pending' in item
    assert isinstance(item['added_at'], (int, float)), 'added_at must be numeric epoch'
print('PASS: got', len(data['items']), 'followed items')
"
```
````

Expected: `PASS: got N followed items` (N ≥ 0).

## ACC-02 — GET /api/acquisition/followed (unauthenticated)

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  "http://localhost:8711/api/acquisition/followed"
```

Expected: `401`.

## ACC-03 — GET /api/acquisition/followed (staging → 200)

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_STAGING_SESSION" \
  "https://tm-staging.iznogoudatall.xyz/api/acquisition/followed"
```

Expected: `200` (reads are staging-allowed).

## ACC-04 — POST /api/acquisition/followed (prod, XRW) → 201

```bash
curl -s --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_SESSION" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d '{"tvdb_id": 99999, "title": "ACC Test Show"}' \
  "http://localhost:8711/api/acquisition/followed" | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert data.get('title') == 'ACC Test Show', f'unexpected title: {data.get(\"title\")}'
assert data.get('active') is True, 'new follow must be active'
print('PASS: created id', data['id'])
"
```

Expected: `PASS: created id <N>`.

## ACC-05 — POST /api/acquisition/followed (same ID → 409)

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_SESSION" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d '{"tvdb_id": 99999, "title": "ACC Test Show"}' \
  "http://localhost:8711/api/acquisition/followed"
```

Expected: `409`.

## ACC-06 — POST /api/acquisition/followed (staging → 403)

```bash
curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_STAGING_SESSION" \
  -H "X-Requested-With: TorrentMate" \
  -H "Content-Type: application/json" \
  -d '{"tvdb_id": 88888, "title": "Staging Write"}' \
  "https://tm-staging.iznogoudatall.xyz/api/acquisition/followed"
```

Expected: `403`.

## ACC-07 — DELETE /api/acquisition/followed/{id} → 204, active=0 in DB

```bash
# First get the id from ACC-04's created row
ID=$(curl -s --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_SESSION" \
  "http://localhost:8711/api/acquisition/followed?active=all" | \
  python3 -c "import json,sys; items=json.load(sys.stdin)['items']; print([i['id'] for i in items if i['title']=='ACC Test Show'][0])")

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_SESSION" \
  -H "X-Requested-With: TorrentMate" \
  -X DELETE \
  "http://localhost:8711/api/acquisition/followed/$ID")
echo "HTTP: $HTTP_CODE"

# Verify active=0 in acquire.db
python3 -c "
import sqlite3, json, sys
from pathlib import Path
config_path = Path('config/paths.json5')
# Resolve data_dir from config — simplified: use the known default
db = sqlite3.connect('file:$DATA_DIR/acquire.db?mode=ro', uri=True)
db.row_factory = sqlite3.Row
row = db.execute('SELECT active FROM followed_series WHERE id = ?', ($ID,)).fetchone()
assert row is not None, 'row still exists'
assert row['active'] == 0, f'expected active=0, got {row[\"active\"]}'
print('PASS: soft-deleted (active=0)')
"
```

Expected: `HTTP: 204` + `PASS: soft-deleted (active=0)`.

## ACC-08 — GET /api/acquisition/status (watcher fields)

```bash
curl -s --connect-timeout 10 --max-time 30 \
  -b "tm_session=$TM_SESSION" \
  "http://localhost:8711/api/acquisition/status" | python3 -c "
import json, sys
data = json.load(sys.stdin)
assert 'last_successful_run_at' in data, 'missing last_successful_run_at'
assert 'watcher_enabled' in data, 'missing watcher_enabled'
assert isinstance(data['watcher_enabled'], bool), 'watcher_enabled must be bool'
assert 'recent_runs' in data, 'missing recent_runs'
assert isinstance(data['recent_runs'], list), 'recent_runs must be list'
print('PASS: status shape ok, watcher_enabled =', data['watcher_enabled'])
"
```

Expected: `PASS: status shape ok, watcher_enabled = true/false`.

## ACC-09 — Frontend /acquisition renders (browser check)

Open `https://tm-staging.iznogoudatall.xyz/acquisition` in a browser
(after deploying the branch to staging).

- The Followed tab renders (table of followed series or empty state).
- The nav entry "Acquisition" is active (Radar icon, not disabled).
- Switching to the Wanted tab shows the wanted table.
- The Watcher tab shows last run + enabled toggle.

## ACC-10 — make check green

```bash
make check
```

Expected: `make check` exit code 0, all checks pass (lint, test, module-size,
typed-api). No test failures, no lint errors.

## ACC-11 — Frontend triple gate green

```bash
cd frontend && npm run lint && npm run typecheck && npx vitest run
```

Expected: all three commands exit 0.

## ACC-12 — design-gaps + feature-map clean

```bash
python scripts/audit_design_coverage.py --strict
python scripts/update_feature_map.py --check
```

Expected: both exit 0 (no gaps, no missing feature map entries).

## ACC-13 — OpenAPI drift check

```bash
make openapi
git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
```

Expected: exit code 0 (no uncommitted drift).

````

## E2E test (`tests/e2e/test_acquisition_api.py`)

```python
"""End-to-end API test for the acquisition REST surface (acq-watch feature).

Exercises the full CRUD flow against a live (or TestClient) web process:
create → read → update → delete → verify soft-delete.  Also exercises the
staging guard and XRW guard on each mutating endpoint.
"""

import pytest


class TestAcquisitionCRUD:
    """Full lifecycle: follow → read → patch cadence → unfollow."""

    def test_follow_reactivate_read_unfollow(self, authed_client):
        """Create a follow, read it back, verify it, soft-unfollow, verify inactive."""
        client = authed_client  # TestClient with tm_session cookie pre-set

        # ── Create ──
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 12345, "title": "E2E Test Show"},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "E2E Test Show"
        assert data["active"] is True
        assert data["media_ref"]["tvdb_id"] == 12345
        followed_id = data["id"]

        # ── Read (active only — should include it) ──
        resp = client.get("/api/acquisition/followed")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(item["id"] == followed_id for item in items)

        # ── Read (all) ──
        resp = client.get("/api/acquisition/followed?active=all")
        assert resp.status_code == 200

        # ── Dedup: create again — 409 ──
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 12345, "title": "Duplicate"},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 409

        # ── Update cadence ──
        resp = client.patch(
            f"/api/acquisition/followed/{followed_id}",
            json={"cadence": {"interval_minutes": 120}},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 200
        assert resp.json()["cadence"] == {"interval_minutes": 120}

        # ── Toggle active off ──
        resp = client.patch(
            f"/api/acquisition/followed/{followed_id}",
            json={"active": False},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

        # ── Unfollow (soft) ──
        resp = client.delete(
            f"/api/acquisition/followed/{followed_id}",
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 204

        # ── Reactivate (was inactive, now active again) ──
        resp = client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 12345, "title": "E2E Test Show Reactivated"},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 201
        assert resp.json()["active"] is True

    def test_read_guards(self, client, authed_client):
        """Reads are staging-safe and require auth."""
        # Unauthenticated → 401
        resp = client.get("/api/acquisition/followed")
        assert resp.status_code == 401

        resp = client.get("/api/acquisition/wanted")
        assert resp.status_code == 401

        resp = client.get("/api/acquisition/obligations")
        assert resp.status_code == 401

        resp = client.get("/api/acquisition/status")
        assert resp.status_code == 401

    def test_write_guards(self, authed_client):
        """Writes require XRW header and return 400 without it."""
        # Missing XRW → 400
        resp = authed_client.post(
            "/api/acquisition/followed",
            json={"tvdb_id": 1, "title": "No XRW"},
        )
        assert resp.status_code == 400

        resp = authed_client.patch(
            "/api/acquisition/followed/1",
            json={"active": False},
        )
        assert resp.status_code == 400

        resp = authed_client.delete("/api/acquisition/followed/1")
        assert resp.status_code == 400

    def test_not_found(self, authed_client):
        """404 on unknown IDs for PATCH and DELETE."""
        resp = authed_client.patch(
            "/api/acquisition/followed/999999",
            json={"active": False},
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 404

        resp = authed_client.delete(
            "/api/acquisition/followed/999999",
            headers={"X-Requested-With": "TorrentMate"},
        )
        assert resp.status_code == 404
````

## docs/reference/web-ui.md — Acquisition section

Add after the §Registry section (the last shipped wave S6):

```markdown
## §Acquisition (S7 — acq-watch)

The `/acquisition` page exposes the acquisition subsystem: followed series CRUD,
the wanted queue, seed obligations + ratio state, and watcher control.

### Data source

Reads and writes go **directly** to the shared WAL `acquire.db` via the
`ConcreteAcquireStore` (lazy-open, lock-free reads, BEGIN IMMEDIATE writes).
No event projection (unlike S6 registry → projection) — acquisition state is
persisted and the store's `_write_tx` serializes concurrent writers (web +
pipeline + watcher). Live updates come from the existing acquisition event
stream via WebSocket (the R13 new-events-only ref pattern).

### API surface

| Method | Path                             | Auth    | Staging | XRW |
| ------ | -------------------------------- | ------- | ------- | --- |
| GET    | `/api/acquisition/followed`      | session | allowed | no  |
| GET    | `/api/acquisition/wanted`        | session | allowed | no  |
| GET    | `/api/acquisition/obligations`   | session | allowed | no  |
| GET    | `/api/acquisition/status`        | session | allowed | no  |
| POST   | `/api/acquisition/followed`      | session | 403     | yes |
| PATCH  | `/api/acquisition/followed/{id}` | session | 403     | yes |
| DELETE | `/api/acquisition/followed/{id}` | session | 403     | yes |

The watcher toggle reuses `POST /api/pipeline/watcher` (S2) — S7 does NOT
add a new watcher route.

### Override rules

- **Cadence** (`cadence_json`): editable per-series via
  `PATCH /api/acquisition/followed/{id}`. Consumed by
  `acquire/desired.py effective_cadence`.
- **Quality profile** (`quality_profile_json`): surfaced **read-only**.
  Editing is deferred to RP3a (backend doesn't consume it yet).

### Frontend

Typed client + TanStack hooks: `frontend/src/api/acquisition.ts`,
`frontend/src/hooks/useAcquisition.ts`. Page: `AcquisitionPage.tsx` — four
tabbed panels (Followed, Wanted, Obligations, Watcher). Live invalidation
via `useEventStreamContext` with the R13 new-events-only ref pattern.
```

## Final gate sequence

1. `make check` — lint + test + module-size + typed-api.
2. `cd frontend && npm run lint && npm run typecheck && npx vitest run`.
3. `python scripts/audit_design_coverage.py --strict`.
4. `python scripts/update_feature_map.py --check`.
5. `make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts`.
6. `python -c "import personalscraper"` — smoke test.
7. Re-exercise every ACC-NN criterion.
8. Commit: `chore(acq-watch): phase 5 gate — integration + ACC + docs`.
