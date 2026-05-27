# Phase 20 — Re-pin ACC criteria to reality

Created from the same audit as Phase 19. Seven of the 14 ACC criteria in
`docs/features/registry/ACCEPTANCE.md` are desynchronized:

| ACC     | Expected     | Actual                        | Reason                                                           |
| ------- | ------------ | ----------------------------- | ---------------------------------------------------------------- |
| ACC-03  | empty stdout | matches `self._tvdb_language` | regex too broad (no word boundary)                               |
| ACC-04a | exit 0       | exit 1                        | no default `config/providers.json5` on fresh clones              |
| ACC-04b | grep `1`     | grep `0`                      | output via Rich traceback — pattern doesn't match                |
| ACC-05b | grep `1`     | grep `0`                      | same Rich traceback issue                                        |
| ACC-06  | TBD          | grep `0`                      | N_PROVIDERS never set; grep pattern doesn't match command output |
| ACC-07  | `48`         | `55`                          | Phases 7+8+9 added registry tests                                |
| ACC-09  | `315`        | `338`                         | Phases 7+11+15 added e2e/integration tests                       |

## Gate

- Phase 19 complete (template boots).
- Current numbers measurable with `make test` baseline at 5636.

## Goal

Every ACC criterion in `ACCEPTANCE.md` re-executes cleanly against current code
state, with deterministic commands matching the real CLI output.

## Scope

- `docs/features/registry/ACCEPTANCE.md` (1 file).
- `IMPLEMENTATION.md` Pinned baseline values section (re-measure each integer).
- Optionally `Makefile` if a new gate target is needed for ACC re-exercise.

## Sub-phases

### 20.1 — Fix ACC-03 regex word boundary

Replace `rg -e "self\._tmdb" -e "self\._tvdb"` with
`rg -e "self\._tmdb\b" -e "self\._tvdb\b"` (word boundary excludes
`_tmdb_language` / `_tvdb_language` etc.) — OR add a `| grep -v _language` post-filter.

Re-run: expected empty stdout.

Commit: `docs(registry): tighten ACC-03 regex word boundary (avoid language vars)`

### 20.2 — Re-pin ACC-07 baseline

`pytest tests/unit/api/metadata/registry/ --collect-only -q | tail -1` →
record the actual integer (currently 55). Update `ACCEPTANCE.md` ACC-07
expected stdout AND `IMPLEMENTATION.md` `REGISTRY_UNIT_TEST_COUNT`.

Commit: `docs(registry): re-pin ACC-07 to 55 (post Phases 7+8+9 test additions)`

### 20.3 — Re-pin ACC-09 baseline

`pytest tests/e2e/ tests/integration/ -q | tail -1 | grep -oE "[0-9]+ passed"` →
record the actual integer (currently 338). Update `ACCEPTANCE.md` AND
`IMPLEMENTATION.md` `BASELINE_PASS_COUNT`.

Commit: `docs(registry): re-pin ACC-09 to 338 (post Phases 11+15 test additions)`

### 20.4 — Set N_PROVIDERS + rewrite ACC-06 grep

After Phase 19's template fix, count active providers in the template
(currently 5 with non-empty sections + 2 façades visible to `info providers`).
Re-read the actual CLI output of `personalscraper info providers` and pick a
grep pattern that matches exactly. Update `ACCEPTANCE.md` + `IMPLEMENTATION.md`.

Commit: `docs(registry): pin N_PROVIDERS + ACC-06 grep aligned with info providers output`

### 20.5 — Fix ACC-04a/04b/05b commands

Three options per criterion:

- (a) Require Phase 19's template path explicitly: `--config config.example/providers.json5`.
- (b) Add `personalscraper init-config` as a prerequisite step (documented in ACC body).
- (c) Rewrite the grep to extract the error from `2>&1` mixed stderr (Rich
  traceback writes to stderr; the structured log may appear separately).

Pick the cleanest path for each. Verify each command produces the expected
result deterministically.

Commit: `docs(registry): rewrite ACC-04a/04b/05b commands for current CLI output`

### 20.6 — Add `make acc` Makefile target (optional follow-up)

Wire every ACC criterion into a single `make acc` target so post-merge
re-exercise is a one-command audit. Each ACC has its own line; failures stop
the build.

Commit (optional): `build: add make acc target for one-shot ACCEPTANCE re-exercise`

## Phase gate

- Every ACC criterion in `ACCEPTANCE.md` produces its documented expected
  output when executed in a clean shell (no surrounding env contamination).
- `make acc` exits 0 (if 20.6 implemented).

## ACC criteria touched

- ACC-03, ACC-04a, ACC-04b, ACC-05b, ACC-06, ACC-07, ACC-09 (all re-pinned).

## Cost estimate

- 20.1–20.5: ~5–10 min each via DeepSeek (single-file edits + verification).
- 20.6 (optional): ~10 min.
- Total: ~35–60 min.

## Risk

Low. Doc-only changes verified by re-execution.
