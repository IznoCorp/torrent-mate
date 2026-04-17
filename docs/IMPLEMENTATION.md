# Implementation Progress — PersonalScraper v14

> **For Claude:** Read this file at the start of each session. It indicates exactly where to resume.
> Update **after each completed task** (check the checkbox, update "Next action", commit).
> Never batch updates.

**Archive v13:** `docs/archive/v13/IMPLEMENTATION.md`
**Branch:** `feat/library-maintenance`
**PR merge:** auto-merge
**PR:** _(created after last phase)_
**Design spec:** `docs/superpowers/specs/2026-04-15-library-maintenance-design.md`
**Master plan:** `docs/superpowers/plans/2026-04-15-library-maintenance.md`

## Global Status

| Phase | Name                                                | Status      | Last Update |
| ----- | --------------------------------------------------- | ----------- | ----------- |
| 1     | Foundation (models, preferences, config, nfo_utils) | DONE        | 2026-04-17  |
| 2     | Scanner (library-scan)                              | DONE        | 2026-04-17  |
| 3     | Disk Cleaner (library-clean)                        | NOT STARTED |             |
| 4     | Validator (library-validate)                        | NOT STARTED |             |
| 5     | Analyzer (library-analyze)                          | NOT STARTED |             |
| 6     | Recommender (library-recommend)                     | NOT STARTED |             |
| 7     | Reporter (library-report)                           | NOT STARTED |             |
| 8     | Documentation (CLAUDE.md, MANUAL.md, --help)        | NOT STARTED |             |
| 9     | E2E Tests (integration)                             | NOT STARTED |             |

## Next Action

**Phase 3, Task 3.1** — Implement cleaner core logic (NTFS-safe)

## Detailed Tracking

### Phase 1: Foundation (DONE)

- [x] Task 1.1: Create library package + scan result models (@dataclass)
- [x] Task 1.2: Add analysis and recommendation models
- [x] Task 1.3: Create preferences models (pydantic)
- [x] Task 1.4: Extend Settings with library_preferences_file
- [x] Task 1.5: Refactor \_is_nfo_complete to shared nfo_utils module
- [x] Task 1.6: Add JSON serialization helpers
- [x] Task 1.7: Phase 1 gate — all model tests pass, full suite green, no regression

### Phase 2: Scanner (DONE)

- [x] Task 2.1: Implement scan_movie_dir and scan_tvshow_dir
- [x] Task 2.2: Implement scan_library with disk/category filters
- [x] Task 2.3: Add library-scan CLI command
- [x] Task 2.4: Phase 2 gate — scanner tests pass, full suite green, no regression

### Phase 3: Disk Cleaner (NOT STARTED)

- [ ] Task 3.1: Implement cleaner core logic (NTFS-safe)
- [ ] Task 3.2: Add library-clean CLI command (dry-run/apply/lock)
- [ ] Task 3.3: Phase 3 gate — cleaner tests pass, full suite green, no regression

### Phase 4: Validator (NOT STARTED)

- [ ] Task 4.1: Add ValidationItem and LibraryValidationResult models
- [ ] Task 4.2: Implement validator core logic (checker + genre_mapper integration)
- [ ] Task 4.3: Add library-validate CLI command (quick/full/fix/apply)
- [ ] Task 4.4: Phase 4 gate — validator tests pass, full suite green, no regression

### Phase 5: Analyzer (NOT STARTED)

- [ ] Task 5.1: Extend extract_stream_info (bitrate, is_atmos, forced, format, is_default)
- [ ] Task 5.2: Implement analyzer with audio profile detection and incremental skip
- [ ] Task 5.3: Add library-analyze CLI command
- [ ] Task 5.4: Phase 5 gate — analyzer + mediainfo tests pass, full suite green, no regression

### Phase 6: Recommender (NOT STARTED)

- [ ] Task 6.1: Implement recommendation engine (priority, savings, encoding rules, id_lookup)
- [ ] Task 6.2: Add \_reconstruct_analysis_items helper to analyzer.py
- [ ] Task 6.3: Add library-recommend CLI command with CSV export
- [ ] Task 6.4: Phase 6 gate — recommender tests pass, full suite green, no regression

### Phase 7: Reporter (NOT STARTED)

- [ ] Task 7.1: Implement reporter (scan/analysis/validation/recommendation aggregation + disk free space)
- [ ] Task 7.2: Add library-report CLI command (text/json, --disk/--category)
- [ ] Task 7.3: Phase 7 gate — reporter tests pass, full suite green, no regression

### Phase 8: Documentation (NOT STARTED)

- [ ] Task 8.1: Update CLAUDE.md (commands, config, version table, directory structure)
- [ ] Task 8.2: Update MANUAL.md (French "Maintenance médiathèque" section)
- [ ] Task 8.3: Polish ROADMAP.md (V14 → Implemented)
- [ ] Task 8.4: Add Rich help panels to CLI (Pipeline vs Library groups)
- [ ] Task 8.5: Update docs/IMPLEMENTATION.md with final status
- [ ] Task 8.6: Phase 8 gate — all docs consistent, --help renders correctly

### Phase 9: E2E Tests (NOT STARTED)

- [ ] Task 9.1: Create mini_library fixture and scan/clean/validate integration tests
- [ ] Task 9.2: Recommend + report integration tests + full workflow chain test
- [ ] Task 9.3: Phase 9 gate — all tests pass (~1130+), all 14 acceptance criteria verified
