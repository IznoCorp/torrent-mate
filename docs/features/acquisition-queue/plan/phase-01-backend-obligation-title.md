# Phase 01 — Backend: ObligationItem.title

**Goal**: Enrich `ObligationItem` with a server-side `title` field so obligations rows
lead with the media title rather than a bare info_hash (E4).

**Constitution served**: §5, DOIT-2, E4.

## Surface

| File                                                    | Action                                              |
| ------------------------------------------------------- | --------------------------------------------------- |
| `personalscraper/web/models/acquisition.py`             | Add `title: str \| None = None` to `ObligationItem` |
| `personalscraper/web/routes/acquisition.py`             | Resolve title in `get_obligations` (L463-479)       |
| `tests/unit/web/routes/test_acquisition_obligations.py` | New or existing: test title resolver paths          |
| `openapi.json`                                          | Regenerated via `make openapi`                      |
| `frontend/src/api/schema.d.ts`                          | Regenerated via `make openapi`                      |

## Sub-phases

### 1.1 — Add `title` field to ObligationItem + resolver

**Commit**: `feat(acquisition-queue): resolve ObligationItem.title from dispatched_path and indexer`

In `personalscraper/web/models/acquisition.py`, add to `ObligationItem`:

```python
title: str | None = None
```

In `personalscraper/web/routes/acquisition.py`, in `get_obligations` just before the
return statement (~L479), add a resolver loop over `items`:

**Resolution order** (fail-soft — every resolver error is caught and logged, never breaks
the listing):

1. `dispatched_path` basename when `dispatched_path is not None`:
   `Path(item.dispatched_path).name` → strip common extensions (`.mkv`, `.mp4`, `.avi`)
   if the result is just a bare filename with nothing meaningful.

2. Indexer lookup by `info_hash` when `dispatched_path is None` or basename is empty:
   Query the library database — `SELECT title FROM media_file WHERE info_hash = ?` on the
   indexer DB (fail-soft: if the indexer DB is unreachable or the hash is unknown, title
   stays `None`).

3. Fallback: `None` — the frontend renders the truncated info_hash with copy affordance
   (Phase 2).

**Fail-soft contract**: wrap each resolution path in `try/except`, log at `warning` on
failure, never let a resolver error propagate to the endpoint. A broken indexer DB must
not take down the obligations listing.

### 1.2 — Tests

**Commit**: `test(acquisition-queue): cover ObligationItem.title resolver paths`

Test cases (new file `tests/unit/web/routes/test_acquisition_obligations.py` or extend
existing):

- `dispatched_path` set with a real basename → `title` = basename (stripped)
- `dispatched_path` set but basename is empty/invalid → falls through to indexer
- `dispatched_path` is `None`, indexer lookup succeeds → `title` from indexer
- `dispatched_path` is `None`, indexer lookup fails → `title` is `None`
- Indexer DB unreachable → `title` is `None`, listing still returns (fail-soft)
- Resolver exception → logged, `title` is `None`, listing still returns

Use a temporary SQLite database for the indexer lookup test (inject path via config or
monkeypatch).

### 1.3 — OpenAPI regen + commit

**Commit**: `chore(acquisition-queue): regenerate OpenAPI after ObligationItem.title addition`

```bash
make openapi
git add openapi.json frontend/src/api/schema.d.ts
```

Verify the regenerated `schema.d.ts` includes the `title` field on `ObligationItem`.

## Gate

- [ ] All commits have Conventional Commits format with `(acquisition-queue)` scope
- [ ] `make lint` → 0 errors
- [ ] `make test` → all passing, 0 errors
- [ ] `make openapi` regenerated files committed
- [ ] `python -c "import personalscraper"` → success
- [ ] `rg "ObligationItem" --type py tests/` — all references consistent with new field
- [ ] Open `openapi.json` — `ObligationItem` schema includes `title` property with `nullable: true`
