# Phase 4 - Cablage des surfaces + S11 constitution + ACCEPTANCE

**Codename**: `media-sheet` . **Gate**: Phase 3 complete.

## Gate

> Phase 3 [x] - `MediaSheet` component autonomous (loading, error, degraded, loaded); `MediaSheetPage` thin host; route `/media/:provider/:providerId` mounted with mirror test; `mediaSheetHref` helper tested.

## ANCHOR CORRECTION

- **DESIGN says 4 surfaces**: `MediaSearchAdd`, `FollowedPanel`, `CandidateCard`, `StagingLibrary`.
- **Reality**: file names must be verified at dispatch time. Expected locations:
  - `frontend/src/components/acquisition/MediaSearchAdd.tsx`
  - `frontend/src/components/acquisition/FollowedPanel.tsx`
  - `frontend/src/components/decisions/CandidateCard.tsx` (or under `staging/`/`medias/`)
  - `frontend/src/pages/Medias.tsx` (renders the library grid)
- The dispatcher MUST verify these paths exist before editing. Adapt to real names.
- `product-intent.md` at `docs/reference/product-intent.md`.
- `MediaCard.onOpen` at `frontend/src/components/ds/MediaCard.tsx:25`.

## Sub-phases

### 4.1 Wire surface 1: Acquisition - MediaSearchAdd

**Files**:
- `frontend/src/components/acquisition/MediaSearchAdd.tsx` (modify - verify path first)

**Implementation**:
- Import `mediaSheetHref` from `@/lib/media-href`.
- On each search result item with `provider` + `provider_id`:
  - Pass `onOpen={() => navigate(mediaSheetHref({provider, providerId}))}` to `MediaCard`.
- Items without a provider ID -> no link (S11 exception).

**Tests**:
- Existing tests still pass. New assertion: identified card has clickable link to `/media/...`.

**Gate**:
```bash
cd frontend && npx tsc --noEmit
cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -5
```

### 4.2 Wire surface 2: Acquisition - FollowedPanel

**Files**:
- `frontend/src/components/acquisition/FollowedPanel.tsx` (modify - verify path)

**Implementation**:
- Import `mediaSheetHref`. Each followed item carries `media_ref` with provider + id.
- Pass `onOpen` to `MediaCard`. No provider id -> no link.

**Gate**:
```bash
cd frontend && npx tsc --noEmit
```

### 4.3 Wire surface 3: Medias - CandidateCard

**Files**:
- Find actual path at dispatch time.

**Implementation**:
- Import `mediaSheetHref`. Cards carry `provider` + `provider_id` from NFO/scrape-decision data.
- Pass `onOpen` to `MediaCard`.

**Gate**:
```bash
cd frontend && npx tsc --noEmit
```

### 4.4 Wire surface 4: Medias - StagingLibrary

**Files**:
- Likely `frontend/src/pages/Medias.tsx` or sub-component.

**Implementation**:
- Items carry `provider_ids` from NFO. Only link when at least one ID is present.
- Import `mediaSheetHref`, pass `onOpen` to `MediaCard` for identified items.

**Gate**:
```bash
cd frontend && npx tsc --noEmit && npx eslint . && npx vitest run --reporter=verbose 2>&1 | tail -5
```

### 4.5 Add S11 to `product-intent.md`

**Files**:
- `docs/reference/product-intent.md` (modify)

**Implementation**:
- After existing S10, add S11 block (exact text from DESIGN S4):
  - S11 heading + paragraph about every media being consultable.
  - Single exception: unidentified media (no provider ID) -> no link.
- Add DOIT-11 to the "DOIT" section.
- Add NE-DOIT-PAS-4 to the "NE-DOIT-PAS" section (verify slot is free).

**Gate**:
```bash
grep -n "S11" docs/reference/product-intent.md
grep -n "DOIT-11" docs/reference/product-intent.md
```

### 4.6 Anti-drift constitution test

**Files**:
- `frontend/src/components/media/__tests__/constitution.test.tsx` (create)

**Implementation**:
- Test enumerates wired surfaces, verifies each renders a link for identified media.
- SURFACES array is explicit - adding a surface requires updating this test (the enforcement mechanism).

**Gate**:
```bash
cd frontend && npx vitest run src/components/media/__tests__/constitution.test.tsx
```

### 4.7 ACCEPTANCE criteria

**Files**:
- `docs/features/media-sheet/ACCEPTANCE.md` (create)

**Implementation**:
- Executable ACCEPTANCE criteria per feature-lifecycle convention (shell commands + expected output):
  - ACC-01: MediaDetails extended - python smoke test
  - ACC-02: Endpoint movie (authenticated) - HTTP GET + verify shape
  - ACC-03: Endpoint TV (authenticated) - HTTP GET + verify series fields
  - ACC-04: Cache TTL - two successive calls, single provider call via logs
  - ACC-05: Degraded response - provider failure, verify 200 with degraded_reason
  - ACC-06: Frontend route renders - HTTP GET + grep for data-testid
  - ACC-07: product-intent S11 present - grep
  - ACC-08: Preuve mobile 390px - manual (documented as manual, not automated)

**Gate**:
```bash
grep -c "^ACC-" docs/features/media-sheet/ACCEPTANCE.md
```

### 4.8 Gate complet - Phase 4 + feature

```bash
make lint
make test
make check
cd frontend && npx tsc --noEmit && npx eslint . && npx vitest run
python -c "import personalscraper"
git diff --stat HEAD
grep -rn "old.import" --type py tests/  # must be zero
```

**Commit**: `feat(media-sheet): wire 4 surfaces, add S11 constitution, ACCEPTANCE (D8, S11)`

---

## Post-Phase 4: PR + review + merge

After Phase 4 gate passes:
1. `make openapi` -> commit regenerated files if any drift.
2. Push branch, create PR.
3. Poll CI to green.
4. Adversarial review (PR review toolkit).
5. Fix cycle (max 3).
6. Squash merge.
7. Re-exercise all ACC-NN criteria post-merge.
8. Bump version to 0.78.0 (already in IMPLEMENTATION.md).
