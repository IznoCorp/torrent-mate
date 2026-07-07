# Phase 4 — Run History Unification

## Gate

**Prerequisite — Phase 1, 2 & 3 delivered**:

- Migration 012 applied → `pipeline_run.kind`, `command`, `options_json`, `output_tail` exist.
- Panel routes (Phase 2) pass tests — `IndexHealthResponse.last_scan` queries the `scan_run` table correctly.
- Action runner (Phase 3) writes `kind='maintenance'` rows with correct `command` and `options_json`.

**Produces for Phase 5+6**: unified history endpoint that the frontend's `RunHistoryPanel` queries with `?kind=` filter chips. Phase 5's `RunOutput` component reads `output_tail` from `RunDetail`.

## Sub-phases

### 4.1 — Extend S2 response models (`feat(maint-dash): add kind, command, options_json, output_tail to RunSummary/RunDetail`)

**Files:**

- Modify: `personalscraper/web/models/pipeline.py` (add fields to `RunSummary`, `RunDetail`)
- Create: `tests/unit/web/models/test_pipeline_maintenance_models.py`

**Changes to `RunSummary`**: add three fields:

```python
kind: str = "pipeline"       # 'pipeline' | 'maintenance'
command: str | None = None   # e.g. "library-clean" (None for pipeline runs)
```

**Changes to `RunDetail`**: add four fields (inherits kind + command from RunSummary pattern, plus two more):

```python
kind: str = "pipeline"
command: str | None = None
options_json: str | None = None
output_tail: str | None = None
```

Backcompat: default values (`"pipeline"`, `None`) ensure existing S2 test fixtures (which don't set these fields when constructing model instances) still pass. The migration's `DEFAULT 'pipeline'` ensures existing DB rows also work.

**Test**: (1) `RunSummary` with default `kind='pipeline'`, `command=None` passes validation. (2) `RunDetail` with `kind='maintenance'`, `command='library-clean'`, `options_json='{"dry_run":true}'`, `output_tail='log...'` serializes correctly. (3) Existing S2 test fixtures still pass (regression check on `PipelineControls.test.tsx` and `RunHistoryTable.test.tsx` backends — these use mock data, not the real models, so no change expected).

### 4.2 — Add ?kind= filter to GET /api/pipeline/history (`feat(maint-dash): add kind filter to pipeline history endpoint`)

**Files:**

- Modify: `personalscraper/web/routes/pipeline.py` (`pipeline_history` function)
- Modify: `personalscraper/web/models/pipeline.py` (already done in 4.1)

**Change**: Add `kind: str = "all"` query parameter to `pipeline_history`:

```python
@router.get("/history")
def pipeline_history(
    ...,
    kind: str = "all",  # "pipeline" | "maintenance" | "all"
    ...
) -> HistoryResponse:
```

SQL change: replace `SELECT COUNT(*) FROM pipeline_run` with `SELECT COUNT(*) FROM pipeline_run WHERE (? = 'all' OR kind = ?)` and same filter on the data query. Select list adds `kind, command`.

**Row mapper** (`_row_to_run_summary`): extended to read `kind` and `command` from the row.

**Also extend** `GET /api/pipeline/history/{run_uid}`: select list adds `kind, command, options_json, output_tail`. The response model already has these fields (from 4.1), so no model change needed.

### 4.3 — History unification tests (`test(maint-dash): add tests for unified history with kind filter`)

**Files:**

- Create: `tests/unit/web/routes/test_pipeline_history_unified.py`

**Test cases** (FastAPI TestClient, seed pipeline_run with both kinds):

1. `test_history_default_returns_all` → `?kind=all` (default) returns both pipeline + maintenance rows.
2. `test_history_kind_pipeline` → `?kind=pipeline` returns only `kind='pipeline'` rows.
3. `test_history_kind_maintenance` → `?kind=maintenance` returns only `kind='maintenance'` rows, each has `command` set.
4. `test_history_invalid_kind` → `?kind=invalid` → 400.
5. `test_detail_maintenance_run` → `GET /api/pipeline/history/{uid}` returns `kind`, `command`, `options_json`, `output_tail` fields for a maintenance run.
6. `test_detail_pipeline_run` → same endpoint for a pipeline run returns `kind='pipeline'`, `command=None`.
7. `test_history_pagination_with_filter` → `?kind=maintenance&limit=10&offset=0` respects pagination.
