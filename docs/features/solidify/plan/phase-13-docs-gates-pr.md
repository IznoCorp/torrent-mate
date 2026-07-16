# Phase 13 — Docs, gates, module-size zero, reintegration + PR (T10)

## Gate

This is the terminal phase: it runs the **complete** executable acceptance suite
ACC-01..15 (DESIGN §10) after reintegrating `origin/main`. All must pass before the PR
opens.

```bash
# Reintegration first (operator directive): merge, not rebase (squash PR)
git fetch origin && git merge origin/main    # resolve conflicts, then re-run everything below

make lint && make test && make check

# Frontend full gate (CI parity)
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run && npm run build && cd ..

python -c "import personalscraper" && echo IMPORT-OK

# ---- Executable acceptance criteria (DESIGN §10) ----
make check && echo ACC-01-OK
python3 scripts/check-module-size.py && echo ACC-02-OK
test "$(rg -c 'def _?resolve_external_ids' -t py personalscraper/ | wc -l)" = "1" \
 && test "$(rg -c 'def _?family_to_client' -t py personalscraper/ | wc -l)" = "1" && echo ACC-03-OK
test "$(rg -l 'poster\.(jpg|png)' -t py personalscraper/ -g '!core/*' | wc -l)" -le 2 && echo ACC-04-OK
command python3 - <<'EOF' && echo ACC-05-OK
import subprocess
out = subprocess.run(["rg", r"Details\(", "-t", "py", "personalscraper/",
                      "-g", "!api/**", "--count-matches"], capture_output=True, text=True).stdout
assert sum(int(l.rsplit(":",1)[1]) for l in out.strip().splitlines() if l) >= 9, out
EOF
command python -m pytest tests -k "journal and (merge or tv)" -q --no-header | grep -E "passed" && echo ACC-06-OK
command python -m pytest tests -k "dry_run and rank" -q --no-header | grep -E "passed" && echo ACC-07-OK
test "$(rg -l 'scandir' -t py personalscraper/indexer/scanner/ | wc -l)" = "1" && echo ACC-08-OK
test "$(rg -l 'os\.replace' -t py personalscraper/ -g '!io_utils.py' -g '!core/**' | wc -l)" = "0" && echo ACC-09-OK
test "$(rg -c 'function relativeTime|const relativeTime' -g '*.ts*' frontend/src/ | wc -l)" = "1" \
 && test "$(rg -l 'useRunToCompletion' -g '*.ts*' frontend/src/hooks/ | wc -l)" -ge 1 && echo ACC-10-OK
cd frontend && npm run lint && npm run typecheck && npx vitest run --reporter=dot && cd .. && echo ACC-11-OK
rg -q "web/" -g 'architecture.md' docs/reference/ && ! rg -q "No network server / web UI" docs/reference/architecture.md && echo ACC-12-OK
make openapi && git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts && echo ACC-13-OK
test "$(rg -c 'from personalscraper.scraper.(youtube_search|trailer_finder|ytdlp_downloader)' -t py personalscraper/ tests/ | wc -l)" = "0" && echo ACC-14-OK
command python3 scripts/check_version_bump.py --base origin/main && echo ACC-15-OK
```

## Objective

Realign the docs and gates to the consolidated architecture and close the module-size
budget to zero findings (DESIGN §5 T10): `architecture.md` gains the `web/` + `acquire/`
chapters and drops the "no web UI in-tree" claim; the module map, event-catalog count and
package-data (22 `.sql` migrations + `web/static`) are corrected; the CI-only gates folded
into `make check` in P0 are re-verified as the durable parity. Then perform the final
`origin/main` reintegration merge, run the full gate + ACC-01..15, and open the single PR.

## Findings addressed

DOCS-ARCH-DRIFT-01..09 (architecture.md web/acquire chapters, "no web UI" critical drift,
module map, event-catalog count, package-data), MEMTRACE-GRAPH-05 (graph/doc parity), and
the residual module-size relief owed by earlier phases (the 8 near-ceiling modules →
zero findings).

## Code anchors (verified)

- `docs/reference/architecture.md:612` — `- **No network server / web UI _in 1.0_.** The CLI is the only interface for …` This is the critical drift line ACC-12 requires removed/rewritten (and a `web/` chapter added).
- `scripts/check-module-size.py` — `WARN_LOC = 800`, `BLOCK_LOC = 1000`; current 8 WARN findings to drive to zero: `acquire/cross_seed.py` 836 (→ P9), `acquire/store.py` 811 (→ P9), `commands/pipeline.py` 826 (→ P3), `scraper/confidence.py` 979 (→ P4), `scraper/movie_service.py` 983 (→ P4), `scraper/tv_service.py` 812 (→ P4), `web/routes/acquisition.py` 909 (→ P9), `web/routes/maintenance.py` 974 (→ P9). This phase asserts `check-module-size` returns 0 findings and mops up any residual.
- `scripts/check_version_bump.py` — ACC-15 (`--base origin/main`). `personalscraper/__init__.py:17` `__version__ = "0.50.0"` (already bumped by create-branch: commit `chore(solidify): archive webui-overhaul and bump version to 0.50.0`). Re-verify vs `origin/main` after reintegration.
- Package-data (DOCS-ARCH-DRIFT): 22 `.sql` migrations under the indexer + `personalscraper/web/static/` must be declared in `pyproject.toml` package-data.
- CI-only gates now in `make check` (from P0): `scripts/update_feature_map.py --check`, `scripts/audit_design_coverage.py --strict`, openapi-drift, version-bump-vs-main, `make check-frontend`.
- Docs to update: `docs/reference/architecture.md` (web/ + acquire/ chapters, module map, event-catalog count), and the reference-index row set in `CLAUDE.md` if a module path moved (trailers stack, scanner walker, scraper seams).

## Tasks

1. **P13.1 — architecture.md web/ + acquire/ chapters (ACC-12).** Add a `web/` chapter (FastAPI single server, runner engine, `guarded_api`, WS relay, staging role) and an `acquire/` chapter; remove/rewrite the `docs/reference/architecture.md:612` "No network server / web UI" line. Verify: `rg -q "web/" -g 'architecture.md' docs/reference/` true AND `! rg -q "No network server / web UI" docs/reference/architecture.md` (ACC-12 line green).
2. **P13.2 — Module map + event-catalog count + package-data.** Refresh the architecture module map to the consolidated seams (scraper `_match`/`_ids`/`_writeback`, `trailers/discovery`, `core/completeness`, `web/_runner_engine`, scanner `_walker`); correct the event-catalog count against the actual event set; declare the 22 `.sql` migrations + `web/static` in `pyproject.toml` package-data. Verify: `rg -c '\.sql' pyproject.toml` covers the migrations; a `pip wheel`/`python -m build`-style check (or `check-manifest` if available) shows migrations + static packaged; event count matches `rg` of the event classes.
3. **P13.3 — Reference-index + CLAUDE.md touch-ups.** Update any `docs/reference/*` and the `CLAUDE.md` reference-index rows whose module paths moved this feature (trailers stack, scanner walker, scraper seams). Verify: `rg -n "scraper/(youtube_search|trailer_finder|ytdlp_downloader)" -g '*.md' docs/` == 0 (docs point at the new `trailers/discovery` paths). Note the `docs/` global-gitignore rule (`git add -f`).
4. **P13.4 — Module-size zero-findings mop-up (ACC-02).** Run `python3 scripts/check-module-size.py`; if any of the 8 modules still exceeds 800 non-blank LOC (a prior phase left relief owed), finish the split within that module's seam conventions. Verify: `scripts/check-module-size.py` exits 0 with 0 findings.
5. **P13.5 — Reintegration merge (operator directive).** `git fetch origin && git merge origin/main` (merge, NOT rebase — squash PR); resolve conflicts favoring the consolidated seams while preserving anything main added (PR #300+). Re-run the full gate. Verify: clean merge commit; `make lint && make test && make check` green post-merge; `check-media-complete.py`/pipeline invariants unaffected.
6. **P13.6 — Full ACC-01..15 run.** Execute the entire Gate block above; every `ACC-NN-OK` must print. Any failure is fixed in its owning seam (not patched around). Verify: 15/15 OK lines; `git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts` clean (ACC-13).
7. **P13.7 — Open the PR.** Push the branch; open ONE PR whose body cites the constitution §2/§6/§7/§8/§9 (conformity fixes F1–F8), the audit report as evidence, and the findings-traceability matrix (audit §2 T1–T10). Note any finding dropped at re-confirmation (with its IMPLEMENTATION.md note). Merge is a manual squash by the operator. Verify: PR created; CI green; the ACC-01..15 evidence pasted in the PR body.

## Non-goals

- No new behaviour, endpoints, or screens (docs + gates + reintegration only).
- Do not weaken any gate to hit zero findings — resolve by finishing the split, not by
  raising `WARN_LOC`/`BLOCK_LOC` or excluding a module.
- Do not rebase the branch (squash PR — merge main in). Do not force-push over the operator's
  reintegration.
- Do not auto-merge — the final squash is the operator's manual call.

## Commit

```
docs(solidify): architecture.md web/ + acquire/ chapters; drop "no web UI in-tree"; module map + counts
build(solidify): declare .sql migrations + web/static package-data
```

Reintegration + phase-gate commit:

```
chore(solidify): phase 13 gate — docs sweep, module-size zero, origin/main reintegration, full ACC-01..15
```
