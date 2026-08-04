# Phase 4 — Extract the season-grab route (behaviour-constant)

**Why.** `personalscraper/web/routes/acquisition.py` is at **995 non-blank LOC** against a hard
ceiling of 1000. Phase 5 cannot fit in five lines. This phase makes room and nothing else: it is
a pure move, so the reviewer can verify by diff that no behaviour changed.

**Files:**
- Create: `personalscraper/web/routes/acquisition_seasons.py`
- Modify: `personalscraper/web/routes/acquisition.py` (remove the moved block)
- Modify: `personalscraper/web/app.py` (mount the new router on `guarded_api`)

**Interfaces:**
- Consumes: nothing from phases 1-3.
- Produces: `acquisition_seasons_router` exporting `POST
  /follows/{followed_id}/seasons/{season}/grab` with the **same** path, status codes, response
  model and dependencies as before.

## What moves

Three contiguous units, currently at `acquisition.py`:

| Symbol | Current line | Role |
| --- | --- | --- |
| `_count_absorbed_for_season` | ~985 | Truthful `absorbed_count` for the reused path |
| `_absorb_live_episodes_for_season` | ~1010 | R5 absorption on manual grab |
| `grab_season` | ~1040-1147 | The route itself |

Anything else stays. Do not "tidy" the remaining file — an unrelated reformat in this commit
destroys the behaviour-constant proof.

## Invariants that must survive verbatim

- Path, `status_code=201`, `response_model=SeasonGrabResponse`.
- `dependencies=[Depends(require_not_staging), Depends(require_x_requested_with)]`.
- **No** per-route `Depends(require_session)` — the auth perimeter is the single `guarded_api`
  dependency (web-ui.md §6). The new router is mounted there like its siblings.
- The reused-row path still answers **200** with `reused=True`, the fresh path **201**.

---

- [ ] **Step 1: Record the pre-move behaviour**

Run the existing season-grab tests and the OpenAPI snapshot, and keep the output:

```bash
command python -m pytest tests/web/ -k "season" -v
make openapi && git diff --stat frontend/openapi.json
```

Expected: tests pass; `git diff` on the generated OpenAPI is **empty** (nothing has changed yet).
This is the baseline the move must preserve.

- [ ] **Step 2: Create the new module**

Create `personalscraper/web/routes/acquisition_seasons.py` with a module docstring stating why
it exists, its own `router = APIRouter(...)` matching the prefix/tags `acquisition.py` uses for
this route, and the three moved symbols **copied byte-for-byte** (only the imports adapted).

```python
"""Season-scoped acquisition routes (manual whole-season grab).

Split out of :mod:`personalscraper.web.routes.acquisition` when that module reached the
1000-non-blank-LOC ceiling. Pure extraction — the path, status codes, response model and
dependencies are unchanged, and the auth perimeter stays the single ``guarded_api``
dependency mounted in :mod:`personalscraper.web.app` (web-ui.md §6).
"""
```

- [ ] **Step 3: Remove the moved block from `acquisition.py`**

Delete exactly the three symbols. Then remove any import that is now unused — but run ruff
rather than eyeballing it:

```bash
command python -m ruff check personalscraper/web/routes/acquisition.py
```

Expected: no `F401` unused-import findings.

- [ ] **Step 4: Mount the router**

In `personalscraper/web/app.py`, next to the sibling acquisition routers (line ~240-249):

```python
    guarded_api.include_router(acquisition_seasons_router)
```

with the matching import alongside the others. Mount it on `guarded_api`, never on `app`.

- [ ] **Step 5: Prove the behaviour is constant**

```bash
command python -m pytest tests/web/ -k "season" -v
```

Expected: the SAME tests pass, **with no test file modified**. If a test needed changing, the
move was not behaviour-constant — revert and redo.

```bash
make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts
```

Expected: exit 0. A pure move must not move the OpenAPI schema. If it drifts, the router prefix
or tags differ from the original — fix the new router, not the snapshot.

- [ ] **Step 6: Confirm the ceiling is cleared**

```bash
python3 scripts/check-module-size.py
```

Expected: `personalscraper/web/routes/acquisition.py` no longer appears (it drops from 995 to
roughly 830), and `acquisition_seasons.py` is well under the warn threshold.

- [ ] **Step 7: Phase gate**

```bash
make lint
make test
make check
```

Expected: 0 errors, 0 failed. Same test count as the baseline — an extraction adds no tests.

- [ ] **Step 8: Commit**

```bash
git add personalscraper/web/routes/acquisition_seasons.py \
        personalscraper/web/routes/acquisition.py \
        personalscraper/web/app.py
git commit -m "refactor(acq-escalade): extraction de la route season-grab, comportement constant"
```
