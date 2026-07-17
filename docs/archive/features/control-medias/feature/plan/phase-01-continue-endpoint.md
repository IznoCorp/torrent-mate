# Phase 01 — Backend: `continue` endpoint

**Gate:** `POST /api/staging/media/{id}/continue` → 202 (spawned) or 202+deferred (lock held) or 404/422.

## Sub-phases

### 1.1 — Models: `ContinueResponse`

**Commit:** `feat(control-medias): add ContinueResponse model for staging continue endpoint`

**File:** `personalscraper/web/models/staging.py`

Add after `EnqueueDecisionResponse` (~line 269):

```python
class ContinueResponse(BaseModel):
    """Response body for ``POST /api/staging/media/{id}/continue`` (§5.2).

    Mirrors the resolve 202 pattern: the run is either spawned now (run_uid
    present) or deferred because another run holds the lock (run_uid is None —
    « En file »). The ``timeline_resumes`` flag lets the UI know to start
    polling for progress.
    """

    ok: bool
    media_id: str
    run_uid: str | None = None
    deferred: bool = False
    detail: str = ""
```

No imports needed — `BaseModel` already imported.

**Gate:** `make lint && make test` (no route yet, model-only — smoke via `python -c "from personalscraper.web.models.staging import ContinueResponse"`).

---

### 1.2 — Route: `POST /api/staging/media/{id}/continue`

**Commit:** `feat(control-medias): add POST /api/staging/media/{id}/continue endpoint`

**File:** `personalscraper/web/routes/staging.py`

1. Add import at top (~line 26):

```python
from personalscraper.web.pipeline_trigger import spawn_pipeline_run, RESOLVE_CONTINUATION_TRIGGER
```

2. Add `ContinueResponse` to the models import (~line 31):

```python
from personalscraper.web.models.staging import (
    ...,
    ContinueResponse,
)
```

3. Add route after the enqueue endpoint (~line 469). **Contract:**
   - Validate via `resolve_scrapable_item(config, media_id)` → 404 if None.
   - Read NFO from `media_dir` to check `match == "matched"` (the NFO exists with provider IDs).
   - If NOT matched → **422** with FR detail: `"Ce média n'est pas encore identifié — résolvez le matching d'abord."`
   - If matched: call `spawn_pipeline_run(data_dir, trigger_reason=RESOLVE_CONTINUATION_TRIGGER)`.
   - Return `ContinueResponse(ok=True, media_id=media_id, run_uid=uid, deferred=uid is None, detail=...)`
     with TRUTHFUL FR detail strings (guarantor-fixed, §6/§méthode): spawned →
     `"Reprise lancée — le média termine son pipeline (vérification → dispatch)."` ; deferred →
     `"En file — un run est en cours ; le média sera repris par le run en cours ou le suivant."`
     (No dedicated queue entry exists: runs sweep the whole staging — say exactly that, never promise
     a dedicated queued run.)
   - **Recorded deviation vs spec §5.2** (documented per §méthode rule 1): the "intent row in the
     activity read-model" is NOT implemented this wave — ScrapeActivityPanel is decision-scoped and a
     matched media has no decision row; visibility is served by the 202 body + the sheet's run polling +
     the media's persistent `blocked_reason`/timeline. If the operator wants standing queue rows for
     continuations, that is a follow-up to arbitrate.
   - Staging-guarded + typed (`response_model=ContinueResponse`).

**Key pattern** — reuses the same trigger authority as the resolve continuation (`runner.py:531-536`), same `RESOLVE_CONTINUATION_TRIGGER = "scrape-resolve"`, same defer-when-locked semantics.

**Gate:** `make lint && make test`

---

### 1.3 — Route tests

**Commit:** `test(control-medias): route tests for POST /api/staging/media/{id}/continue`

**File:** `tests/web/test_staging_media.py`

Add ~4 tests following the existing fixture pattern (`_make_client`, `_staging_dirs`, temp staging tree):

1. `test_continue_matched_spawns_run` — matched movie → 200+ok → verifies `run_uid` is present and looks like a hex UUID.
2. `test_continue_not_matched_returns_422` — absent item → 422 with FR detail.
3. `test_continue_unknown_media_returns_404` — bogus id → 404.
4. `test_continue_requires_staging_guard` — without `X-Requested-With` header → 403 (reuse the pattern from `test_enqueue_requires_x_requested_with` at line 676).
5. `test_continue_deferred_when_lock_held` — create a fake `pipeline.lock` → returns `deferred=True, run_uid=None`.

Mock `subprocess.Popen` via `unittest.mock.patch` to avoid actually launching a pipeline.

**Gate:** `make lint && make test`

---

### 1.4 — OpenAPI regeneration

**Commit:** `chore(control-medias): regenerate openapi.json + schema.d.ts for continue endpoint`

```bash
make openapi
git add frontend/src/api/schema.d.ts docs/api/openapi.json
```

**Gate:** `make lint && make test` (smoke: `python -c "import personalscraper"`).
