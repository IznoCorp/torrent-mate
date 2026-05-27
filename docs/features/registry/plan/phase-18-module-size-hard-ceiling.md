# Phase 18 — Module size hard ceiling fixes

Created in response to `make check` HARD failure detected post-Phase 17:

```
[REPORT] personalscraper/indexer/scanner/_modes/backfill_ids.py: 1043 non-blank lines
[REPORT] personalscraper/scraper/tv_service.py: 1152 non-blank lines
```

Project hard ceiling per `CLAUDE.md`: 1000 non-blank LOC. Both files exceed.

## Gate

- All previous phases (7–17) complete.
- `python3 scripts/check-module-size.py` reports REPORT-level findings (> 1000 LOC)
  on the two files above.

## Goal

Extract enough helpers from each oversized module to fall below the 1000 LOC hard
ceiling. Soft warning (800 LOC) acceptable; the priority is clearing the hard ceiling.

## Scope

- `personalscraper/scraper/tv_service.py` (1278 LOC raw, 1152 non-blank) — drift from
  Phase 7.2 (chain iteration added significant code).
- `personalscraper/indexer/scanner/_modes/backfill_ids.py` (1150 LOC raw, 1043
  non-blank) — drift from Phase 11 (registry migration added wiring).
- New extracted modules (sibling files in same directory).
- Tests that import the extracted helpers (verify imports still work).

## Sub-phases

### 18.1 — Audit tv_service.py structure

```bash
wc -l personalscraper/scraper/tv_service.py
grep -nE "^(class|def|    def) " personalscraper/scraper/tv_service.py | head -40
```

Identify natural extraction targets (likely the chain helpers added in Phase 7.2,
the episode flow helpers, or the xref helpers).

Commit (audit-only doc): `docs(scraper): audit tv_service.py for Phase 18 extraction`

### 18.2 — Extract tv_service.py helpers

Move a logical group (likely chain/match helpers OR episode flow helpers OR xref
helpers) to a new module like `tv_service_chain.py` or `tv_service_episodes.py`.

Add re-export imports in `tv_service.py` for backward compatibility.

Acceptance: `python3 scripts/check-module-size.py` on tv_service.py reports under
1000 non-blank LOC (ideally under 800 for soft warning).

Commit: `refactor(scraper): extract <group> helpers from tv_service to tv_service_<name>`

### 18.3 — Audit backfill_ids.py structure

Same as 18.1 for the indexer file.

Commit: `docs(indexer): audit backfill_ids.py for Phase 18 extraction`

### 18.4 — Extract backfill_ids.py helpers

Same as 18.2 for the indexer file. Likely candidates: the rating-fetch loop, the
cross-provider ID resolution helpers, or the persistence layer.

Commit: `refactor(indexer): extract <group> helpers from backfill_ids to backfill_ids_<name>`

### 18.5 — Verification

- `python3 scripts/check-module-size.py` → exit 0 (no REPORT-level findings).
- `make test` → 5634+ passed.
- `make lint` → clean.
- `make check` → exit 0.

Commit (optional): `chore: verify Phase 18 module-size compliance`

## Phase gate

- `make check` exit 0.
- `wc -l personalscraper/scraper/tv_service.py` < 1000 raw.
- `wc -l personalscraper/indexer/scanner/_modes/backfill_ids.py` < 1000 raw.
- No regression in test count.

## ACC criteria touched

- ACC-12 (module-size guardrail) — must clear.
- ACC-01 (`make check`) — depends on ACC-12.

## Cost estimate

- 18.1+18.3 audits: ~20 min combined.
- 18.2+18.4 extractions: ~30–40 min combined (mechanical refactor with re-exports
  per Phase 10 precedent).
- 18.5 verify: ~5 min.
- Total: ~60 min.

## Risk

Low. The pattern is identical to Phase 10's successful `existing_validator.py` split.
Re-exports preserve external import paths.
