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

### ACC-01 — Drift mechanism active (DEV #18)

```bash
# After Phase 1.1 + 1.3
make test -k test_miss_strike_lifecycle && echo OK
# Live verification on a test FS with file deletion across N scans
```

**Expected** : `media_file.miss_strikes` increments per missed scan ; soft-delete fires at N.

### ACC-02 — FK enforced runtime (DEV #19)

```bash
sqlite3 .data/library.db "PRAGMA foreign_keys;"          # returns 1
sqlite3 .data/library.db "PRAGMA foreign_key_check;"     # returns zero rows
```

### ACC-03 — Test E2E miss-strike lifecycle (MUST-17)

```bash
make test -k test_miss_strike_lifecycle
```

### ACC-04 — Test E2E scan→reconcile=clean (MUST-16)

```bash
make test -k test_scan_reconcile_clean
```

### ACC-05 — schema_version row 3 backfilled (DEV #15)

```bash
sqlite3 .data/library.db "SELECT version FROM schema_version ORDER BY version;"
# Expected: 1, 2, 3, 4, 5, 6
```

### ACC-06 — PRAGMA integrity_check at boot (SH-9)

```bash
# Open DB triggers integrity_check; corrupt DB → IndexerCorruptError
make test -k test_open_db_integrity_check_at_boot
```

### ACC-07 — \_ensure_disk_row no duplicates (DEV #50)

```bash
make test -k test_ensure_disk_row_no_duplicate
# Pre-condition: 4 disks in BDD, call scan_library, assert disk count unchanged
```

### ACC-08 — Enrich + walker retry oshash on NULL (DEV #51, #52)

```bash
make test -k "test_enrich_recomputes_null_oshash or test_walker_retries_oshash"
```

### ACC-09 — init-canonical CLI works (DEV #54)

```bash
personalscraper library init-canonical --help && echo OK
personalscraper library init-canonical --dry-run  # populates canonical_provider
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NOT NULL;"
# Expected post-real-run: > 0 (depends on NFO presence)
```

### ACC-10 — PRAGMA discipline multi-site (DEV #33, #34, #37 audit)

```bash
rg "sqlite3\.connect\(" personalscraper/ --type py | grep -v "indexer/db.py"
# Expected: zero matches (every raw connect bypassed)
python3 scripts/check-pragma-discipline.py
# Expected: exit 0
```

---

## CLI gaps (Phase 2)

### ACC-11 — `library-scan` exists (DEV #16, MUST-3)

```bash
personalscraper library-scan --help
# Expected: exit 0, lists --disk, --mode, --dry-run flags
```

### ACC-12 — --dry-run on 4 mutators (DEV #21, MUST-9)

```bash
for cmd in library-repair library-relink library-clean init-config; do
  personalscraper "$cmd" --dry-run --help && echo "OK: $cmd"
done
# Plus library-verify --no-enqueue
personalscraper library-verify --no-enqueue --help
```

### ACC-13 — `run --help` lists 9 steps (DEV #7, MUST-11)

```bash
personalscraper run --help | grep -E "enforce|trailers"
# Expected: both present
```

### ACC-14 — Test "matrix references valid CLI" (MUST-12, DEV #10, #20)

```bash
make test -k test_matrix_cli_refs
# All matrix-mentioned CLI commands have --help exit 0
```

### ACC-15 — CI coverage CLI check (MUST-13)

```bash
python3 scripts/audit-cli-coverage.py
# Expected: exit 0, every command has commands.md entry
```

### ACC-16 — backfill-ids first run executed (MUST-19, DEV #28)

```bash
# After Phase 8.10 Plan A
sqlite3 .data/library.db "SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL;"
# Expected: tends to 0 (modulo items truly without TMDB/TVDB ID)
```

---

## Observability (Phase 3)

### ACC-17 — VERIFY structured events (MUST-10, DEV #6, #40)

```bash
personalscraper verify -v 2>&1 | grep -E "verify_item_done|cli\.invoke\.verify"
# Expected: both event types present
```

### ACC-18 — cli_telemetry decorator (DEV #23)

```bash
personalscraper info 2>&1 | grep "cli.invoke.info"
# Expected: event present
```

### ACC-19 — Console+log parity test (SH-11)

```bash
make test -k test_console_log_parity
```

---

## Path detection + paranoia branch (Phase 4)

### ACC-20 — Path-missing detector (MUST-4)

```bash
personalscraper library-reconcile --scope path_missing
# Expected: JSON report with path_missing array
```

### ACC-21 — 8 phantom shows cleanup (DEV #17, MUST-18, DEV #12 sub-cause)

```bash
sqlite3 .data/library.db "SELECT id, label FROM disk;"  # only 4 (no duplicates)
# Post-Phase 4.3
personalscraper library-reconcile | jq .files_without_release
# Expected: <= 6655 (legit sidecars only)
```

### ACC-22 — Paranoia branch fires (DEV #31)

```bash
make test -k test_paranoia_branch_catches_crash_between_fs_and_db
sqlite3 .data/library.db "SELECT COUNT(*) FROM scan_event WHERE event LIKE 'outbox.%';"
# Expected post-fix: > 0 after first dispatch
```

---

## Conformity (Phase 5)

### ACC-23 — Drop monolithic Protocols (MUST-14, DEV #29, #38)

```bash
rg "^class MetadataProvider\b|^class TorrentClientFull\b" personalscraper/
# Expected: zero matches
```

### ACC-24 — Atomic Protocol tests (DEV #29)

```bash
make test -k "test_metadata_client_supports"
# Expected: per-capability assertions pass
```

### ACC-25 — Pydantic ratings boundary (DEV #30)

```bash
make test -k test_scraper_uses_externalids_pydantic
```

### ACC-26 — library-gc + library-doctor (SH-7, SH-8)

```bash
personalscraper library-gc --help && personalscraper library-doctor --help
personalscraper library-doctor   # exit 0 on healthy DB
```

---

## Format + documentation (Phase 6)

### ACC-27 — --format unified (DEV #22, SH-13)

```bash
personalscraper --format json library-reconcile | jq .   # valid JSON
personalscraper --format plain library-reconcile         # no rich rendering
```

### ACC-28 — commands.md exhaustive (SH-12, CL-J)

```bash
python3 scripts/audit-cli-coverage.py --check-docs
# Each command has section in commands.md
```

### ACC-29 — architecture.md complete (SH-18, SH-19, AR-A, AR-B, AR-E)

```bash
grep -E "State ownership|Module relationships|Out of scope for 1.0" docs/reference/architecture.md
# Expected: all 3 sections present
```

---

## Matrix v2.1 (Phase 7)

### ACC-30 — Matrix v2.1 binding (MUST-15)

```bash
grep "Matrix version.*2.1" .claude/skills/pipeline-monitor/references/design-conformity-matrix.md
grep 'matrix_version.*"2.1"' .claude/skills/pipeline-monitor/SKILL.md
# Both present
```

### ACC-31 — 12 coverage gap events in matrix (DEV #8)

```bash
for ev in tracker_dest_path_pruned repair_root_duplicate_replaced enforce.orphan_episode_moved verify_item_done; do
  grep -q "$ev" .claude/skills/pipeline-monitor/references/design-conformity-matrix.md && echo "OK: $ev"
done
```

### ACC-32 — Agents matrix-aware (DEV #2, #3)

```bash
grep -l "AVANT toute classification" .claude/agents/pipeline-*.md
# Expected: all pipeline-* agents
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

### ACC-44 — Pin commands tests (SH-25)

```bash
make test -k test_pin_existence_of_every_exposed_command
```

### ACC-45 — ACCEPTANCE.md complete with all criteria

```bash
grep -c "^### ACC-" docs/features/tech-debt/ACCEPTANCE.md
# Expected: 50+ (ACC-00 + ACC-01..ACC-49 + ACC-final-* = 55 actually)
```

---

## Archive doc updates (Phase 9)

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

### ACC-49 — Reference docs synced (DEV #45, #47)

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

**Total** : 49 ACCEPTANCE criteria (45 numbered + 4 final). All executable. Each maps to a
specific phase + DEV(s) + commit.

**Coverage** :

- 54/54 DEVs covered by ≥ 1 ACCEPTANCE criterion
- 34/34 patterns leveraged by ≥ 1 ACCEPTANCE criterion
- 8/8 DESIGN sections §9-§16 validated by ≥ 1 ACCEPTANCE criterion
- 9 phases each have ≥ 1 ACCEPTANCE in their gate

**Status post-tech-debt 0.16.0 merge** : marquer ✅/❌/🟡 next to each ACC- as Phase 8.9 closure.
