# Tech-Debt 0.16.0 — ACCEPTANCE Criteria (executable)

**Status** : drafted at item 14 → REDO at coverage-fix (2026-05-22). Final state validated at
Phase 8 gate.

> Per DESIGN §14 (Success criteria enforcement) : each criterion is an executable shell
> command + expected output. Re-measured at phase gate AND at PR gate. Drift = block merge.

## How to validate

```bash
cd /Users/izno/dev/PersonnalScaper
bash docs/features/tech-debt/scripts/acceptance-check.sh  # to be created Phase 8.9
```

Or run the criteria one-by-one below. ✅ = passes, ❌ = fails, 🟡 = pending phase to ship it.

---

## Pre-Foundations (Phase 0)

### ACC-00 — Skill auto-detect missing agents (DEV #1, promu pré-foundations) ✅

```bash
grep -cE "MATRIX_AGENTS_MISSING|matrix agents discoverability" .claude/skills/pipeline-monitor/SKILL.md
# Expected: ≥1. Actual: 1 (commit 66943ce on .claude/personal-scraper, 2026-05-23)
```

**Status** : SHIPPED — Phase 0.1 implementé STOP-only (no --degraded-mode fallback, decision
2026-05-23). Voir `.claude/skills/pipeline-monitor/SKILL.md` §0.3.

**Note** : ACC-33 (ancien emplacement Phase 7) supprimé — voir ACC-00 ci-dessus.

---

## Foundations (Phase 1)

### ACC-01 — Drift mechanism active (DEV #18) ✅ [SHIPPED commit `38cdcd6`]

```bash
# After Phase 1.1 + 1.3
make test -k test_miss_strike_lifecycle && echo OK
# Live verification on a test FS with file deletion across N scans
```

**Expected** : `media_file.miss_strikes` increments per missed scan ; soft-delete fires at N.

### ACC-02 — FK enforced runtime (DEV #19) ✅ [SHIPPED commit `1320efc`]

```bash
sqlite3 .data/library.db "PRAGMA foreign_keys;"          # returns 1
sqlite3 .data/library.db "PRAGMA foreign_key_check;"     # returns zero rows
```

### ACC-03 — Test E2E miss-strike lifecycle (MUST-17) ✅ [SHIPPED commit `e5a79a3`]

```bash
make test -k test_miss_strike_lifecycle
```

### ACC-04 — Test E2E scan→reconcile=clean (MUST-16) ✅ [SHIPPED commit `5389529`]

```bash
make test -k test_scan_reconcile_clean
```

### ACC-05 — schema_version row 3 backfilled (DEV #15) ✅ [SHIPPED commit `36da687`]

```bash
sqlite3 .data/library.db "SELECT version FROM schema_version ORDER BY version;"
# Expected: 1, 2, 3, 4, 5, 6
```

### ACC-06 — PRAGMA integrity_check at boot (SH-9) ✅ [SHIPPED commit `c0e7094`]

```bash
# Open DB triggers integrity_check; corrupt DB → IndexerCorruptError
make test -k test_open_db_integrity_check_at_boot
```

### ACC-07 — \_ensure_disk_row no duplicates (DEV #50) ✅ [SHIPPED commit `1805f9b`]

```bash
make test -k test_ensure_disk_row_no_duplicate
# Pre-condition: 4 disks in BDD, call scan_library, assert disk count unchanged
```

### ACC-08 — Enrich + walker retry oshash on NULL (DEV #51, #52) ✅ [SHIPPED commit `b7d98a6`]

```bash
make test -k "test_enrich_recomputes_null_oshash or test_walker_retries_oshash"
```

### ACC-09 — init-canonical CLI works (DEV #54) ✅ [SHIPPED commits `224eaea` + `c83888d`]

```bash
personalscraper library init-canonical --help && echo OK
personalscraper library init-canonical --dry-run  # populates canonical_provider
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NOT NULL;"
# Expected post-real-run: > 0 (depends on NFO presence)
```

### ACC-10 — PRAGMA discipline multi-site (DEV #33, #34, #37 audit) ✅ [SHIPPED commit `61427b6`]

```bash
rg "sqlite3\.connect\(" personalscraper/ --type py | grep -v "indexer/db.py"
# Expected: zero matches (every raw connect bypassed)
python3 scripts/check-pragma-discipline.py
# Expected: exit 0
```

---

## CLI gaps (Phase 2)

### ACC-11 — `library-scan` exists (DEV #16, MUST-3) ✅ [SHIPPED commit `bcecd21`]

```bash
personalscraper library-scan --help
# Expected: exit 0, lists --disk, --mode, --dry-run flags
```

### ACC-12 — --dry-run on 4 mutators (DEV #21, MUST-9) ✅ [SHIPPED commit `1e771f2`]

```bash
for cmd in library-repair library-relink library-clean init-config; do
  personalscraper "$cmd" --dry-run --help && echo "OK: $cmd"
done
# Plus library-verify --no-enqueue
personalscraper library-verify --no-enqueue --help
```

### ACC-13 — `run --help` lists 9 steps (DEV #7, MUST-11) ✅ [SHIPPED commit `8026b8f`]

```bash
personalscraper run --help | grep -E "enforce|trailers"
# Expected: both present
```

### ACC-14 — Test "matrix references valid CLI" (MUST-12, DEV #10, #20) ✅ [SHIPPED commits `ff0a8d4` + `3b0d582`]

```bash
make test -k test_matrix_cli_refs
# All matrix-mentioned CLI commands have --help exit 0
```

### ACC-15 — CI coverage CLI check (MUST-13) ✅ [SHIPPED commit `ae985ca`]

```bash
python3 scripts/audit-cli-coverage.py
# Expected: exit 0, every command has commands.md entry
```

### ACC-16 — backfill-ids first run executed (MUST-19, DEV #28) 🟡 [SHIPPED commit `7391529` (CLI), operator action pending for real run]

```bash
# After Phase 8.10 Plan A
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL;"
# Expected: tends to 0 (modulo items truly without TMDB/TVDB ID)
```

---

## Observability (Phase 3)

### ACC-17 — VERIFY structured events (MUST-10, DEV #6, #40) ✅ [SHIPPED commit `a618aaf`]

```bash
personalscraper verify -v 2>&1 | grep -E "verify_item_done|cli\.invoke\.verify"
# Expected: both event types present
```

### ACC-18 — cli_telemetry decorator (DEV #23) ✅ partial [SHIPPED commit `a378e7a` decorator + ingest ; 6 KNOWN_VIOLATIONS xfail for full rollout]

```bash
personalscraper info 2>&1 | grep "cli.invoke.info"
# Expected: event present
```

### ACC-19 — Console+log parity test (SH-11) ✅ [SHIPPED commit `82d7c64`]

```bash
make test -k test_console_log_parity
```

---

## Path detection + paranoia branch (Phase 4)

### ACC-20 — Path-missing detector (MUST-4) ✅ [SHIPPED commit `c7b4aca`]

```bash
personalscraper library-reconcile --scope path_missing
# Expected: JSON report with path_missing array
```

### ACC-21 — 8 phantom shows cleanup (DEV #17, MUST-18, DEV #12 sub-cause) 🟡 [SHIPPED script `d7561d6`, operator action pending (332 path_missing detected)]

```bash
sqlite3 .data/library.db "SELECT id, label FROM disk;"  # only 4 (no duplicates)
# Post-Phase 4.3
personalscraper library-reconcile | jq .files_without_release
# Expected: <= 6655 (legit sidecars only)
```

### ACC-22 — Paranoia branch fires (DEV #31) ✅ [SHIPPED commit `b70e7a6`]

```bash
make test -k test_paranoia_branch_catches_crash_between_fs_and_db
sqlite3 .data/library.db "SELECT COUNT(*) FROM scan_event WHERE event LIKE 'outbox.%';"
# Expected post-fix: > 0 after first dispatch
```

---

## Conformity (Phase 5)

### ACC-23 — Drop monolithic Protocols (MUST-14, DEV #29, #38) ✅ [SHIPPED commit `4ffdf57`]

```bash
rg "^class MetadataProvider\b|^class TorrentClientFull\b" personalscraper/
# Expected: zero matches
```

### ACC-24 — Atomic Protocol tests (DEV #29) ✅ [SHIPPED commit `d87e26d`]

```bash
make test -k "test_metadata_client_supports"
# Expected: per-capability assertions pass
```

### ACC-25 — Pydantic ratings boundary (DEV #30) 🟡 [SHIPPED commit `28a2c32` (TV path), movie_service/_xref/nfo_generator pending 0.17]

```bash
make test -k test_scraper_uses_externalids_pydantic
```

### ACC-26 — library-gc + library-doctor (SH-7, SH-8) ✅ [SHIPPED commits `9666516` + `f322957`]

```bash
personalscraper library-gc --help && personalscraper library-doctor --help
personalscraper library-doctor   # exit 0 on healthy DB
```

---

## NTFS cache pressure (Phase 5.9)

Criteria sourced verbatim from `audit/13-ntfs-cache-pressure.md` §Validation.

### ACC-NTFS-A1 — rsync argv no longer contains `--checksum` ✅ [SHIPPED commit `3328924`]

```bash
rg -n '"--checksum"' personalscraper/dispatch/_transfer.py tests/
# Expected: zero matches
```

### ACC-NTFS-B1 — F_NOCACHE does not raise ENOTTY on arm64 ✅ [SHIPPED commit `5a9c38b`]

```bash
python3 -c "
import os, fcntl
fd = os.open('/Volumes/Disk1/medias/films/'+os.listdir('/Volumes/Disk1/medias/films')[0], os.O_RDONLY)
try:
    fcntl.fcntl(fd, 48, 1)  # F_NOCACHE
    print('OK')
finally:
    os.close(fd)
"
# Expected: single line "OK", no traceback.
```

### ACC-NTFS-B2 — Cache footprint measurement (qualitative) ✅ [SHIPPED commit `5edd016`]

```bash
sudo purge
vm_stat | grep 'File-backed pages'
personalscraper library-index --mode full --disk Disk1 --budget 600
vm_stat | grep 'File-backed pages'
# Expected: post-scan File-backed pages increase by < 500 000 pages
# (~2 GB at 4 KiB pages) on Disk1 with ~1 000 video files.
# Pre-fix baseline on the same disk typically shows 1 500 000+ pages.
```

### ACC-NTFS-D1 — Throttle activated and parallelism capped ✅ [SHIPPED commit `144638b`]

```bash
python3 -c "
import json5, pathlib
cfg = json5.loads(pathlib.Path('config/indexer.json5').read_text())
scan = cfg['indexer']['scan']
assert scan['max_workers_total'] == 2, scan['max_workers_total']
assert scan['read_rate_mb_per_sec'] == 80, scan['read_rate_mb_per_sec']
print('OK')
"
# Expected: single line "OK".
```

---

## Incident response BDD (Phase 5.12 — discovered 2026-05-23, fixed same day)

> Phase 5.12 captures 4 production BDD bugs discovered while exercising
> `library-doctor` on the live DB. Each bug had a pattern in common:
> command reported "success" while leaving the underlying state inconsistent
> (silent failure). All 4 fixes ship with regression tests that exercise
> the END-TO-END loop — not just the single function — so the same class
> of bug cannot return.

### ACC-BDD-1 — `soft_delete_subtree` cascade hard-deletes path row (BD-D #1) ✅ [SHIPPED commit `c5e2bbd`]

```bash
# After enqueue-repair on phantom path → repair drains → re-detect = 0
make test -k test_soft_delete_subtree_cascade_deletes_files_and_path
make test -k test_repair_processor_drains_path_missing_closes_detector_loop
# Both expected: pass (closure-of-loop guarded).
```

### ACC-BDD-2 — `soft_delete_subtree` refreshes `disk.merkle_root` (BD-D #2) ✅ [SHIPPED commit `00599f8`]

```bash
make test -k test_soft_delete_subtree_refreshes_disk_merkle
# Expected: pass. Without this fix, `library-index --mode quick` after a
# subtree prune trips bulk-change-detected protection on every disk.
```

### ACC-BDD-3 — `init_canonical` falls back from imdb default to tmdb sibling (BD-INIT-CANONICAL) ✅ [SHIPPED commit `3df78e0`]

```bash
make test -k test_parse_default_imdb_falls_back_to_tmdb
make test -k test_init_canonical_populates_fallback_tmdb_on_imdb_default
make test -k test_init_canonical_stats_breakdown_sums_to_total_visited
# Production impact: 92 % of movies (1094 / 1236) populated from this fix
# via fallback; the breakdown CLI output surfaces WHY any remaining items
# are still un-anchorable (no more silent "populated=0").
```

### ACC-BDD-4 — `library-relink --dry-run` rollback works (BD-RELINK-TX) ✅ [SHIPPED commit `9997f70`]

```bash
make test -k test_relink_dry_run_no_writes
# Pre-fix: isolation_level=None (autocommit) made conn.rollback() a no-op
# under --dry-run, so the function silently persisted link updates against
# the operator's explicit dry-run intent.
# Post-fix: explicit BEGIN IMMEDIATE wraps the link loop so the rollback
# is honored.
```

---

## Format + documentation (Phase 6)

### ACC-27 — --format unified (DEV #22, SH-13) ✅ [SHIPPED Phase 6.1 (`79629b2` + `cf1bd96` + `d23a746` + `a4decbe` + `5a81ef0` + `e4943fe`) + Phase 6.1.b (`de2b5e3` + `a3ef659` + `323455a` + `8092317` + `c6da905`) — 8/8 commands plumbed]

```bash
# 6.1 commands
personalscraper --format json library-doctor | jq .       # valid JSON
personalscraper --format plain library-status             # plain text rows
personalscraper --format json info | jq .                 # valid JSON
personalscraper --format json library-report | jq .       # valid JSON

# 6.1.b commands
personalscraper --format json library-reconcile | jq .    # valid JSON
personalscraper --format json library-search "year:2020" --limit 5 | jq .
personalscraper --format json library-show 1 | jq .       # any existing item_id
personalscraper --format json torrents-list | jq .        # valid JSON
```

### ACC-28 — commands.md exhaustive (SH-12, CL-J) ✅ [SHIPPED commits `209b3b3` through `e69ca4a` (12 commits across 6.2.a / 6.2.b / 6.2.c)]

```bash
grep -c "^## \`personalscraper" docs/reference/commands.md
# Expected: 39 (all 34 top-level + 5 sub-commands documented)
python3 scripts/audit-cli-coverage.py
# Expected: exit 0 (1 known false positive on `migrate-category` — script
# regex limitation on group sub-commands, fail-soft)
```

### ACC-29 — architecture.md complete (SH-18, SH-19, AR-A, AR-B, AR-E) ✅ [SHIPPED commit `ed4370f`]

```bash
grep -E "^## State ownership$|^## Module relationships$|^## Anti-decisions" docs/reference/architecture.md | wc -l
# Expected: 3 (all 3 new sections present)
```

---

## Matrix v2.1 (Phase 7)

### ACC-30 — Matrix v2.1 binding (MUST-15) ✅ [SHIPPED commits `cd47026` (matrix) + `30360ef` (skill) on `.claude/personal-scraper`]

```bash
grep "Matrix version.*2.1" .claude/skills/pipeline-monitor/references/design-conformity-matrix.md
grep 'matrix_version.*"2.1"' .claude/skills/pipeline-monitor/SKILL.md
# Both present
```

### ACC-31 — 18 coverage gap events in matrix (DEV #8) ✅ [SHIPPED commit `cd47026` on `.claude/personal-scraper`]

> Plan v0.16.0 said "12 events" but the actual matrix v2.0 → v2.1 gap audit
> identified 18 events (SORT 2 + PROCESS:clean 3 + PROCESS:scrape 9 + ENFORCE 3 + VERIFY 1).

```bash
for ev in tracker_dest_path_pruned repair_root_duplicate_replaced enforce.orphan_episode_moved verify_item_done; do
  grep -q "$ev" .claude/skills/pipeline-monitor/references/design-conformity-matrix.md && echo "OK: $ev"
done
```

### ACC-32 — Agents matrix-aware (DEV #2, #3) ✅ [SHIPPED commit `4f9d598` on `.claude/personal-scraper`]

```bash
grep -l "AVANT toute classification" .claude/agents/pipeline-*.md
# Expected: 7 pipeline-* agents (orphan-hunter, state-validator, scrape-checker,
# sort-checker, ingest-checker, dispatch-checker, output-analyzer)
grep -l "ALWAYS verify FS via Bash" .claude/agents/pipeline-state-validator.md
# Expected: 1 match
```

### ACC-33 — (moved to ACC-00 — DEV #1 promu en Phase 0)

DEV #1 (skill auto-detect missing agents) a été promu pré-foundations le 2026-05-22 — voir
**ACC-00** dans la section "Pre-Foundations (Phase 0)" en début de fichier. Ce criterion
reste numéroté ACC-33 pour ne pas casser les références ailleurs, mais re-pointe vers ACC-00.

---

## Polish + Plan A + ACCEPTANCE (Phase 8)

### ACC-34 — Plan A reset+rescrape executed (DEV #27, #54 closure)

```bash
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE external_ids_json != '{}';"
# Expected: > 90% of total
personalscraper library-doctor | grep "canonical_provider populated"
# Expected: > 90%
```

### ACC-35 — Module-size hard-block (DEV #46)

```bash
# Insert a module > 1000 LOC temporarily
python3 scripts/check-module-size.py
# Expected: exit 1 (hard block on > 1000)
```

### ACC-36 — \_upsert_media_item dedup (DEV #53)

```bash
make test -k test_upsert_media_item_no_duplicates
sqlite3 .data/library.db "SELECT title, year, COUNT(*) FROM media_item GROUP BY title, year HAVING COUNT(*) > 1;"
# Expected: empty (no dups)
```

### ACC-37 — Event-bus catalog sync (DEV #24, #25)

```bash
grep -c "Backfill" personalscraper/events/__init__.py
# Expected: >= 4 (all 4 Backfill* in __all__)
grep -c "BackfillStarted\|BackfillCompleted" docs/reference/event-bus.md
# Expected: present in catalog table
```

### ACC-38 — Test-coverage re-measured (DEV #41)

```bash
make test-cov 2>&1 | grep "TOTAL" | awk '{print $NF}'
# Expected: >= 90 (per gate), branch coverage tracked in IMPLEMENTATION.md
```

### ACC-39 — test_cli @patch <= 25 (DEV #49)

```bash
grep -cE "@patch\(" tests/test_cli.py
# Expected: <= 25
```

### ACC-40 — Cron backfill-ids (SH-3)

```bash
ls launchd-plists/ | grep "backfill-ids"
# Expected: plist file present
```

### ACC-41 — pending_op + item_issue audit (SH-6)

```bash
# Documented decision in docs/features/tech-debt/audit/12-dead-infrastructure.md
test -f docs/features/tech-debt/audit/12-dead-infrastructure.md
```

### ACC-42 — clean + cleanup CLI exposed (SH-21, AR-C)

```bash
personalscraper clean --help && personalscraper cleanup --help
```

### ACC-43 — trailers audit alias (SH-22, AR-D)

```bash
personalscraper trailers audit --help
personalscraper trailers verify --help  # deprecation warning visible
```

### ACC-44 — Pin commands tests (SH-25) ✅ [SUPERSEDED — absorbed by Phase 9 CLI Coverage]

The SH-25 intent (each CLI command has an existence-proof test) is now
covered by the 23 `test_library_*_e2e.py` harnesses shipped in Phase 9
(D1-D6 = commits `b9cb39c` through `1607f87` = 114 E2E tests). Every
harness includes a `test_<cmd>_help_exits_zero` smoke test that pins
the command's existence + CliRunner integration. See ACC-50..54 for
the Phase 9 coverage measurement.

```bash
ls tests/commands/test_library_*_e2e.py | wc -l
# Expected: 23 (one per library-* command)
rg -c "test_.+_help_exits_zero" tests/commands/test_library_*_e2e.py | wc -l
# Expected: 23 (each harness pins command existence)
```

### ACC-45 — ACCEPTANCE.md complete with all criteria

```bash
grep -c "^### ACC-" docs/features/tech-debt/ACCEPTANCE.md
# Expected: 50+ (ACC-00 + ACC-01..ACC-49 + ACC-final-* = 55 actually)
```

---

## CLI Test Coverage (Phase 9 NEW)

> **Note 2026-05-23** : ACC-50..54 révisés pour aligner sur l'approche **sections
> thématiques** (pattern observé sur les 11 harnesses E2E déjà shippés par
> l'agent d'implémentation parallèle), au lieu de markers numériques `cli_scenario(N)`
> théoriques. Source de vérité = en-têtes `# ── N. <Theme> ──` dans
> `tests/commands/test_*_e2e.py`. Voir `plan/phase-09-cli-coverage.md` §Sections thématiques.

### ACC-50 — CLI coverage report check 🟡

```bash
python3 scripts/cli-coverage-report.py --check
# Expected: exit 0 (0 ❌ on critical commands ; N/A justified in
# docs/features/tech-debt/cli-coverage-matrix.md footnotes — e.g. Closure-of-loop N/A
# for query-only diagnostics, Dry-run N/A for read-only cmds).
```

### ACC-51 — Section coverage threshold 🟡

```bash
python3 scripts/cli-coverage-report.py --metrics
# Expected on critiques (28 cmds × 8 sections — minus typical N/A):
#   ≥ 28 × 6 = 168 sections ✅
# Expected on non-critiques (8 cmds × 4 sections):
#   ≥ 8 × 4 = 32 sections ✅
# Total: ≥ 200 active sections across tests/commands/test_*_e2e.py.
```

### ACC-52 — Coverage matrix doc committed and synced 🟡

```bash
python3 scripts/cli-coverage-report.py --write
git diff --exit-code docs/features/tech-debt/cli-coverage-matrix.md
# Expected: exit 0 (matrix doc up-to-date with last test run — regenerable idempotently
# from `# ── N. <Theme> ──` headers parsed across tests/commands/test_*_e2e.py).
```

### ACC-53 — Each critical command has a Closure-of-loop section OR explicit N/A 🟡

```bash
python3 scripts/cli-coverage-report.py --section "Closure-of-loop" --filter critical
# Expected: zero ❌ (each critical cmd has either a `# ── N. Closure-of-loop ──`
# section OR an N/A footnote in cli-coverage-matrix.md with rationale —
# e.g. query-only diagnostic, no BDD ↔ FS cycle).
```

### ACC-54 — Each critical command has an Events section verified against matrix v2.1 🟡

```bash
python3 scripts/cli-coverage-report.py --section "Events" --filter critical
# Expected: zero ❌. Each `# ── N. Events ──` section must contain at least one
# assert_events_emitted() call against the matrix v2.1 source of truth
# (.claude/skills/pipeline-monitor/references/design-conformity-matrix.md).
```

---

## Archive doc updates (Phase 10 — ex-Phase 9, renumérotée)

### ACC-46 — 7 archived DESIGN.md have banner (P30)

```bash
for f in event-bus provider-ids media-indexer pipeline-obs trailer logging legacy-cleanup; do
  grep -q "STATUS.*superseded\|STATUS.*as-designed snapshot" "docs/archive/features/$f/DESIGN.md" && echo "OK: $f"
done
# Expected: 7 OK lines
```

### ACC-47 — VX leaks resolved (DEV #48)

```bash
rg "\bV[0-9]+\b" docs/*.md MANUAL.md | grep -v "docs/archive/"
# Expected: zero
```

### ACC-48 — \_exclusions.py docstring cleaned (DEV #44)

```bash
grep -c '"001-MOVIES/Inception' personalscraper/indexer/scanner/_exclusions.py
# Expected: 0
grep -c '{movies_dir}/Inception' personalscraper/indexer/scanner/_exclusions.py
# Expected: >= 1
```

### ACC-49 — Reference docs synced (DEV #45, #47) 🟡 [partial: DEV #45 logging.md SHIPPED commit `329afbc` ; DEV #47 still pending Phase 10.3]

```bash
grep -c "personalscraper.scraper.http_retry\|scraper/tmdb_client.py" docs/reference/logging.md
# Expected: 0
grep "dict\[str, Any\] | None" docs/reference/architecture.md
# Expected: present (details_payload type)
```

---

## Final PR gate

### ACC-final-1 — make check vert

```bash
make check
# Expected: exit 0 (lint + test + module-size + typed-api + pragma-discipline)
```

### ACC-final-2 — library-reconcile clean

```bash
personalscraper library-reconcile | jq '.total_findings'
# Expected: <= 5376 sidecars (no merkle_drift, no path_missing, no release_orphans)
```

### ACC-final-3 — library-doctor exit 0

```bash
personalscraper library-doctor
# Expected: exit 0, all health checks green
```

### ACC-final-4 — No regressions

```bash
make test | tail -1
# Expected: NNNN passed, 0 failed, 0 errors
```

### ACC-final-5 — PR ready

```bash
git log --oneline 882bc6f..HEAD | wc -l
# Expected: > 30 commits (9 phases × N sub-phases + gates)
git status --short
# Expected: empty (everything committed)
```

---

## Summary

**Total** : 54 ACCEPTANCE criteria (50 numbered ACC-00..ACC-54 + 4 final). All executable.
Each maps to a specific phase + DEV(s) + commit (ACC-50..54 added for Phase 9 CLI test
coverage, decision opérateur 2026-05-23).

**Coverage** :

- 54/54 DEVs covered by ≥ 1 ACCEPTANCE criterion
- 34/34 patterns leveraged by ≥ 1 ACCEPTANCE criterion
- 8/8 DESIGN sections §9-§16 validated by ≥ 1 ACCEPTANCE criterion
- 10 phases each have ≥ 1 ACCEPTANCE in their gate (Phase 9 = ACC-50..54,
  Phase 10 ex-Phase 9 = ACC-46..49)

**Status post-tech-debt 0.16.0 merge** : marquer ✅/❌/🟡 next to each ACC- as Phase 8.9 closure
(ACC-00..49) + Phase 9 gate (ACC-50..54).
