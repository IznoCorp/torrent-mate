# Phase 29 — PR fixes cycle 5

Generated 2026-05-28 after cycle-5 review of PR #27 returned 1 Major + 2 Medium
retained findings (1 Critical + 2 Important + 1 Medium per pr-review-toolkit
raw output, then Opus-filtered against DESIGN.md + plan + user norms in memory
`feedback_regression_test_per_bug`).

## Gate

- Phases 0–28 complete (all `[x]` in IMPLEMENTATION.md).
- PR #27 `OPEN`, CI green on `5abb9102`, MERGEABLE.
- Cycle 5 review verdict: Case B (fixes needed) — see `## Review cycles` §"Cycle 5".

## Goal

Close the 3 retained cycle-5 findings, then exit the review loop and let the
operator squash-merge PR #27 (merge_mode = manual).

## Scope

### Sub-phase 29.1 — Pin the new regression test against production SQL

**Target finding** : F1 (Major) + F2 (Medium) consolidated.

**Evidence** :

- `tests/integration/api/metadata/registry/test_canonical_provider_tvdb_fallback.py`
  currently re-implements the rule in a Python loop. If
  `personalscraper/commands/library/fix_canonical_provider.py` `_SHOWS_COUNT_SQL`
  (lines 47–51) drifts (e.g. someone removes `IS NOT NULL`), the test will not
  catch it.
- The same file also exposes `_SHOWS_REPAIR_SQL` (lines 41–45) — the actual
  UPDATE statement applied by the `library-fix-canonical-provider` CLI.
- An edge case noted by `pr-test-analyzer` : `tvdb.series_id = ""` (empty
  string). The test's Python loop classifies this as "not a violation" (falsy
  truthiness), but the production SQL `IS NOT NULL` matches the empty string
  → divergence.

**Tasks** :

1. Edit `tests/integration/api/metadata/registry/test_canonical_provider_tvdb_fallback.py`:
   - Import `_SHOWS_COUNT_SQL` from
     `personalscraper.commands.library.fix_canonical_provider`.
   - Replace the in-test Python loop with a `conn.execute(_SHOWS_COUNT_SQL).fetchone()[0]`
     call.
   - Use `sqlite3.connect(...)` as a context manager so the connection closes.
   - Add edge-case rows to the fixture:
     - row 5 : `{"tvdb": {"series_id": null, ...}}` (explicit JSON null) — must
       NOT count as violation
     - row 6 : `{"tvdb": {}}` (tvdb key without series_id) — must NOT count
     - row 7 : `{"tvdb": {"series_id": ""}}` (empty string) — production SQL
       counts this as a match because `IS NOT NULL` is true. Document the
       behavior explicitly in an inline comment ; this row's expected count
       contribution is **1** under the production rule.
     - row 8 : a `kind='movie'` row with `canonical_provider='tmdb'` and a tvdb
       entry — must NOT be counted because the `WHERE kind='show'` clause
       scopes the rule.
   - Final assertion : `count == <expected>` where expected = number of rows
     that match the production rule (currently row 3 + row 7 = 2 rows ; verify
     by reading the production SQL and the fixture).
2. Update the test docstring : remove the "enforced by `pipeline-bdd-validator`
   agent v2.3" sentence (the agent enforcement is one of two enforcers — the
   other is the CLI tool tested here). Keep the date reference.
3. Run `python -m pytest tests/integration/api/metadata/registry/test_canonical_provider_tvdb_fallback.py -xvs` — must pass.

**Acceptance** :

- The test imports `_SHOWS_COUNT_SQL` from
  `personalscraper.commands.library.fix_canonical_provider`.
- The test fixture includes ≥ 4 edge-case rows beyond the original 4.
- The test passes locally + in CI.
- Mutating `_SHOWS_COUNT_SQL` (e.g. dropping `IS NOT NULL`) makes the test
  fail (manual verification — no need to commit a mutation, just confirm the
  pinning is real).

**Commit** : `test(registry): pin canonical_provider regression test against
production _SHOWS_COUNT_SQL`.

### Sub-phase 29.2 — Fix broken bullet in phase-28 plan

**Target finding** : F3 (Medium — comment-analyzer).

**Evidence** : `docs/features/registry/plan/phase-28-pipeline-monitor-deviations.md`
around L383-385 has a paragraph split by a blank line where a `+` was
auto-formatted into a list item, producing a phantom bullet that breaks
Markdown rendering.

**Tasks** :

1. Edit the file to collapse the split paragraph back into one sentence :
   `The agent's AI over-counting is fixed in the batch above (per-show timeout
   - coverage_partial reporting instead of inflating totals).`
2. Sanity : `grep -nB1 -A1 'coverage_partial' docs/features/registry/plan/phase-28-pipeline-monitor-deviations.md`
   shows one contiguous line per occurrence.

**Acceptance** :

- No phantom bullet at `phase-28-...md:383-385`.
- Markdown renders cleanly (visual check ; the bullet `).` is gone).

**Commit** : `docs(registry): phase-28 plan — fix broken bullet rendering`.

## Verification (phase gate)

After both sub-phases :

1. `make lint` → 0 errors.
2. `python -m pytest tests/integration/api/metadata/registry/test_canonical_provider_tvdb_fallback.py -xvs` → pass.
3. `make check` → exit 0.
4. `git diff phase-29-baseline..HEAD --stat` reflects only the 2 expected
   touched files (test + plan markdown).

## Out of scope

- The minor cycle-5 findings ignored at filter time (test name, directory
  placement, hand-rolled schema, conform-case assertion, IMPLEMENTATION.md
  duplicate Next-action, "iff" wording). Defer to post-merge cleanup if
  desired.

## Next action

After phase 29 closes : the loop exits at cycle-5 (no Case B re-entry because
cycle-5 fix doesn't trigger cycle-6 — max 5). The cycle-5 record is appended
to IMPLEMENTATION.md `## Review cycles` with the verdict `MERGE — fixes
applied`. PR #27 is squash-merged manually by the operator via GitHub UI per
`merge_mode = manual` set at `/implement:feature` time. After merge :
`/implement:archive` may be invoked manually.
