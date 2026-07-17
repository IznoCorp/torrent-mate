# Phase 02 — Backend: `discard` endpoint

**Gate:** `POST /api/staging/media/{id}/discard` → 200+journal-entry or 404/422.

## Sub-phases

### 2.1 — Models: `DiscardResponse`

**Commit:** `feat(control-medias): add DiscardResponse model for staging discard endpoint`

**File:** `personalscraper/web/models/staging.py`

Add after `ContinueResponse` (from phase 01):

```python
class DiscardResponse(BaseModel):
    """Response body for ``POST /api/staging/media/{id}/discard`` (§7).

    The ``journaled`` flag confirms the append-only destructive-op row was
    written. ``quarantine_path`` is the destination (None when the folder was
    just emptied in-place).
    """

    ok: bool
    media_id: str
    journaled: bool
    quarantine_path: str | None = None
    detail: str = ""
```

---

### 2.2 — Route: `POST /api/staging/media/{id}/discard`

**Commit:** `feat(control-medias): add POST /api/staging/media/{id}/discard endpoint`

**File:** `personalscraper/web/routes/staging.py`

1. Add imports (~line 26 area):

```python
import shutil
from personalscraper.indexer.destructive_journal import record_destruction, OP_DELETE
```

2. Add `DiscardResponse` to models import.

3. New route after the continue endpoint. **Contract:**
   - Staging-guarded (`require_not_staging` + `require_x_requested_with`).
   - Typed: `response_model=DiscardResponse`.
   - Resolve media via `resolve_other_item(config, media_id)` — **only `media_kind == "other"` items qualify**.
   - If `resolve_other_item` returns None, also try `resolve_scrapable_item` → if found, it's a movie/tvshow → **422**: `"Cet élément est un média identifiable — utilisez 'Rechercher / résoudre' ou 'Relancer le pipeline', pas 'Ignorer'."`
   - If item found and is `other`:
     a. Build quarantine path: `<staging_dir>/_quarantine/<media_id>/`
     b. `shutil.move(str(media_dir), quarantine_path)`
     c. `record_destruction(db_path, op=OP_DELETE, path=str(media_dir), actor="web", detail=f"Discard non-media artifact: {media_dir.name}", run_uid=None)`
     d. Return `DiscardResponse(ok=True, media_id=media_id, journaled=True, quarantine_path=quarantine_path, detail=...)`
   - 404: no item matches.
   - The journal write is best-effort (fail-soft per `destructive_journal.py` contract) but should succeed in normal operation.

**Key constraint (§7):** Routes through `record_destruction` (the SAME journal as #300 dispatch deletes) — never a new deletion mechanism. The journal is the append-only audit trail; a test asserts the row.

**Gate:** `make lint && make test`

---

### 2.3 — Route tests

**Commit:** `test(control-medias): route tests for POST /api/staging/media/{id}/discard`

**File:** `tests/web/test_staging_media.py`

Add ~5 tests:

1. `test_discard_other_artifact_moves_to_quarantine_and_journals` — seed an `other` item in 098-AUTRES → 200, folder moved, `journaled=True`.
2. `test_discard_journal_row_written` — AFTER discard, `SELECT * FROM destructive_op WHERE actor='web' AND op='delete'` → exactly one row with the correct path.
3. `test_discard_movie_or_tvshow_returns_422` — matched movie → 422 with FR detail about using resolve/continue instead.
4. `test_discard_unknown_media_returns_404` — bogus id → 404.
5. `test_discard_requires_staging_guard` — no `X-Requested-With` → 403.

Journal assertion pattern:

```python
rows = db.execute("SELECT op, path, actor, detail FROM destructive_op WHERE actor = 'web'").fetchall()
assert len(rows) == 1
assert rows[0]["op"] == "delete"
```

**Gate:** `make lint && make test`

---

### 2.4 — OpenAPI regeneration

**Commit:** `chore(control-medias): regenerate openapi.json + schema.d.ts for discard endpoint`

```bash
make openapi
git add frontend/src/api/schema.d.ts docs/api/openapi.json
```

**Gate:** `make lint && make test`
