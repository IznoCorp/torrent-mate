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
the listing). GROUND TRUTH corrected 2026-07-17 by the orchestrator against the real
schemas: `library.db` has NO `info_hash` column anywhere (indexer lookup is impossible);
the clean title lives in **acquire.db itself** — the same DB the listing already reads.

1. **acquire.db join** (primary — clean title): `wanted.grabbed_hash = seed_obligation.info_hash`
   → `wanted.followed_id` → `followed_series.title`, composed with the wanted row's
   scope: episode row (`season` + `episode` non-NULL) → `"{title} S{ss:02d}E{ee:02d}"`;
   season pack (`season` only) → `"{title} S{ss:02d}"`; else bare `title`.
   Verified live: 4/5 current obligations joinable. One SQL join added to the existing
   obligations query (or a second query over the collected hashes) — same connection.

2. `dispatched_path` basename when the join misses and `dispatched_path is not None`:
   `Path(item.dispatched_path).name` — this is a RAW RELEASE NAME
   (e.g. `Murder.Mindfully.S01.MULTi.1080p.WEB.H265-TyHD`), still far better than a hash.
   No extension-stripping heuristics needed for directories; strip a video extension
   (`.mkv/.mp4/.avi`) only if present.

3. Fallback: `None` — the frontend renders the truncated info_hash with copy affordance
   (Phase 2).

**Fail-soft contract**: wrap each resolution path in `try/except`, log at `warning` on
failure, never let a resolver error propagate to the endpoint. A broken indexer DB must
not take down the obligations listing.

### 1.2 — Tests

**Commit**: `test(acquisition-queue): cover ObligationItem.title resolver paths`

Test cases (new file `tests/unit/web/routes/test_acquisition_obligations.py` or extend
existing):

- Join hit, episode row (season+episode) → `title` = `"Titre S01E02"`
- Join hit, season pack (season only, episode NULL) → `title` = `"Titre S01"`
- Join hit, bare wanted row (no season) → `title` = followed_series title verbatim
- Join miss, `dispatched_path` set → `title` = raw basename of the path
- Join miss, `dispatched_path` `None` → `title` is `None`
- Resolver exception (e.g. corrupted row) → logged, `title` is `None`, listing still returns

Use the existing temp acquire.db test fixture pattern (see current obligations route tests)
seeded with followed_series + wanted + seed_obligation rows.

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
