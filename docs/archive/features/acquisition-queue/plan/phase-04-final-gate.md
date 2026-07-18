# Phase 04 — Final gate

**Goal**: Full quality gate — all linters, test suites, coherence check, and IMPLEMENTATION.md update. No code changes.

**Constitution served**: §méthode (proof-or-non-conforme, dated executed run).

## Surface

| File                                     | Action                     |
| ---------------------------------------- | -------------------------- |
| `scripts/check-acquisition-coherence.py` | Create if absent           |
| `IMPLEMENTATION.md`                      | Update phases table to [x] |
| All Phase 1–3 files                      | Verified, no stale imports |

## Sub-phases

### 4.1 — Full quality gate

**Commit**: _(no commit — verification only until 4.2)_

Run all gates:

```bash
# Backend
make lint
make test
make check

# Frontend
cd frontend && npm run lint
cd frontend && npm run lint:ds
cd frontend && npm run typecheck
npx vitest run

# Import drift check
rg "wanted" --type py -g '!*.md' tests/    # only test files reference "wanted" route params
rg "downloads" --type py -g '!*.md' tests/ # only test files reference downloads
rg "ObligationItem" --type py tests/       # all references consistent

# Module size
python3 scripts/check-module-size.py

# Import smoke test
python -c "import personalscraper"
```

If any gate fails: fix in a follow-up commit with `fix(acquisition-queue): <description>`.
Re-run the full gate after each fix.

### 4.2 — Acquisition coherence check

**Commit**: `chore(acquisition-queue): add acquisition coherence checker script`

Create `scripts/check-acquisition-coherence.py` if it does not already exist. The script
validates:

1. **Tabs coherence**: `meta.ts` `TABS` has exactly 4 entries: `followed`, `file`,
   `obligations`, `watcher`. No `wanted` or `downloads` residue.
2. **Frontend import coherence**: `AcquisitionPage.tsx` does NOT import `WantedPanel` or
   `DownloadsPanel` directly (the merged panel imports them, not the page).
3. **Backend ObligationItem coherence**: the model has `title: str | None` field.
4. **OpenAPI drift**: `openapi.json` and `schema.d.ts` are in sync with the backend models
   (compare `make openapi` output with committed files — no drift).
5. **Redirect coverage**: `AcquisitionPage.tsx` handles `?tab=wanted|downloads` → `?tab=file`
   redirect logic (grep for the redirect pattern).
6. **Product intent invariants**: watcher numbered results referenced (DOIT-6),
   `client_available` fail-soft still present (NE-DOIT-PAS-5), per-episode badges + FR
   reasons survive (DOIT-2).

The script must be executable: `python3 scripts/check-acquisition-coherence.py` returns 0 on
clean, non-zero with a human-readable message on anomaly. Run it dated as the §méthode proof.

### 4.3 — Update IMPLEMENTATION.md

**Commit**: `docs(acquisition-queue): final gate — mark all phases done, update IMPLEMENTATION.md`

Update `IMPLEMENTATION.md`:

- **Status line**: `## Status: all phases complete — awaiting PR`
- **Master plan**: `docs/features/acquisition-queue/plan/INDEX.md`
- **Phases table**: mark all phases `[x]`:
  ```markdown
  | #   | Phase                             | File                                                                         | Status |
  | --- | --------------------------------- | ---------------------------------------------------------------------------- | ------ |
  | 1   | Backend: ObligationItem.title     | [phase-01-backend-obligation-title.md](phase-01-backend-obligation-title.md) | [x]    |
  | 2   | Suivis compact + Obligations rows | [phase-02-compact-rows.md](phase-02-compact-rows.md)                         | [x]    |
  | 3   | File d'acquisition (merge + tabs) | [phase-03-file-dacquisition.md](phase-03-file-dacquisition.md)               | [x]    |
  | 4   | Final gate                        | [phase-04-final-gate.md](phase-04-final-gate.md)                             | [x]    |
  ```

## Gate

- [ ] `make lint` → 0 errors
- [ ] `make test` → all passing (0 failed, 0 errors)
- [ ] `make check` → 0 errors
- [ ] `cd frontend && npm run lint && npm run lint:ds && npm run typecheck` → 0 errors
- [ ] `npx vitest run` → all passing
- [ ] `python3 scripts/check-acquisition-coherence.py` → 0, dated output
- [ ] `python3 scripts/check-module-size.py` → no new warnings or blocks
- [ ] No stale imports: `rg "from.*WantedPanel" frontend/src/pages/` → 0 matches
- [ ] No stale imports: `rg "from.*DownloadsPanel" frontend/src/pages/` → 0 matches
- [ ] `make openapi` → no diff vs committed `openapi.json` + `schema.d.ts`
- [ ] Product intent: every § served by this feature is cited in the DESIGN + plan
