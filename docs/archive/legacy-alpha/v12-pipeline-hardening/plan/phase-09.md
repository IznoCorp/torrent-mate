# Phase 9: Test audit final (bug #11 — transversal)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Verify all 22 bugs have reproducer tests. Fill gaps. Create traceability table.

**Architecture:** Audit phases 1-8 test coverage against the 22 bugs. Write missing tests. Build bug→test mapping.

**Tech Stack:** Python, pytest

---

## Task 1: Build traceability table

**Files:**

- Modify: `docs/IMPLEMENTATION.md`

- [ ] **Step 1: Create the bug→test mapping**

Verify each bug has a test by checking the test files. Build this table:

```markdown
### V12 Bug Traceability

| Bug # | Description                     | Test file                                       | Test name                                                       | Phase |
| ----- | ------------------------------- | ----------------------------------------------- | --------------------------------------------------------------- | ----- |
| 1     | qBit auth lockout               | test_qbit_client.py                             | test_403_pre_check_skips_login                                  | 4     |
| 2     | Torrents non ingérés            | (consequence of #1 — fixed by pre-check)        | —                                                               | 4     |
| 3     | Artwork doublons avec `:`       | test_scraper.py                                 | test_old_artwork_with_colon_removed_after_rename                | 1     |
| 4     | Spirale dossier garde `:`       | test_scraper.py                                 | test_old_artwork_with_colon_removed_after_rename                | 1     |
| 5     | Spirale mkv non renommé         | (consequence of TMDB no-match — not a code bug) | —                                                               | —     |
| 6     | Jury Duty épisodes nested       | test_scraper.py                                 | test_finds_mkv_in_subdirectory                                  | 2     |
| 7     | The Boys épisodes nested        | (same root cause as #6)                         | —                                                               | 2     |
| 8     | Pluribus épisodes nested        | (same root cause as #6)                         | —                                                               | 2     |
| 9     | rsync `:` Invalid argument      | test_dispatcher.py                              | test_item_with_colon_skipped                                    | 5     |
| 10    | sanitize pas appliqué           | test_scraper.py                                 | test_old_artwork_with_colon_removed_after_rename                | 1     |
| 11    | Tests manquants                 | (this audit — Phase 9)                          | —                                                               | 9     |
| 12    | qBit ban IP                     | test_qbit_client.py                             | test_403_pre_check_skips_login                                  | 4     |
| 13    | Anciens artwork non nettoyés    | test_scraper.py                                 | test_old_artwork_with_colon_removed_after_rename                | 1     |
| 14    | pipeline-monitor trop permissif | (skill file, no code test)                      | —                                                               | 8     |
| 15    | Pas de crash recovery           | test_pipeline.py                                | test_expired_lockout_cleaned + test_orphan_tmp_dispatch_cleaned | 6     |
| 16    | reclean sans sanitize           | test_reclean.py                                 | test_reclean_removes_colon_from_folder_name                     | 1     |
| 17    | result.media_path stale         | test_scraper.py                                 | test_media_path_updated_after_rename                            | 3     |
| 18    | Verify pas de check NTFS        | test_checker.py                                 | test_colon_in_artwork_fails_check                               | 5     |
| 19    | Dispatch pas de pre-scan        | test_dispatcher.py                              | test_item_with_colon_skipped                                    | 5     |
| 20    | Pre-check qBit accessible       | test_qbit_client.py                             | test_connection_refused_raises_api_error                        | 4     |
| 21    | Regex Saison trop strict        | test_scraper.py                                 | test_single_digit_saison_excluded_from_rglob                    | 7     |
| 22    | desktop.ini manquant            | test_cleanup.py                                 | test_desktop_ini_treated_as_junk                                | 7     |
```

- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.9.1: Add V12 bug traceability table — 22 bugs mapped to tests"
```

## Task 2: Identify and fill test gaps

- [ ] **Step 1: Verify each test exists**

Run these commands to confirm each test referenced in the table exists:

```bash
python -m pytest tests/scraper/test_scraper.py::TestCleanupStaleFiles -v --collect-only
python -m pytest tests/scraper/test_scraper.py::TestFindVideoFileNested -v --collect-only
python -m pytest tests/scraper/test_scraper.py::TestCleanupEmptyReleaseDirs -v --collect-only
python -m pytest tests/scraper/test_scraper.py::TestScrapeTvshowMediaPath -v --collect-only
python -m pytest tests/scraper/test_scraper.py::TestSaisonRegex -v --collect-only
python -m pytest tests/ingest/test_qbit_client.py::TestPreCheckBan -v --collect-only
python -m pytest tests/verify/test_checker.py::TestNtfsSafeNames -v --collect-only
python -m pytest tests/dispatch/test_dispatcher.py::TestNtfsPreScan -v --collect-only
python -m pytest tests/test_pipeline.py::TestCrashRecovery -v --collect-only
python -m pytest tests/process/test_reclean.py::test_reclean_removes_colon_from_folder_name -v --collect-only
python -m pytest tests/process/test_cleanup.py::test_desktop_ini_treated_as_junk -v --collect-only
```

Expected: ALL collected successfully. If any missing → write the test.

- [ ] **Step 2: Write any missing gap tests**

For bugs that are "consequence of" another bug (bugs #2, #5, #7, #8), verify
the root cause test is sufficient. If not, add a dedicated test.

Specific gaps to check:

**Bug #5 (Spirale mkv non renommé)**: This is because TMDB returned 0 results
for the search query. Not a code bug per se — the scraper correctly skips
when no match is found. However, verify there IS a test for the "no TMDB match"
path in `test_scraper.py`. If not, add one:

```python
def test_no_tmdb_match_skips_gracefully(self, tmp_path: Path) -> None:
    """When TMDB returns no results, folder should be left unchanged."""
    # ...mock TMDBClient.search_movie returning []
    # Verify result.action == "skipped_low_confidence"
```

**Bugs #7, #8 (The Boys, Pluribus)**: Same root cause as #6 (Jury Duty).
The test for `_find_video_file` with nested dirs covers this. However, add
a test specifically for `_cleanup_empty_release_dirs` being called after
episode processing to ensure the full flow works.

- [ ] **Step 3: Commit any new tests**

```bash
git add tests/
git commit -m "v12.9.2: Fill test coverage gaps for bugs #5, #7, #8"
```

## Task 3: Run full test suite and verify count

- [ ] **Step 1: Run full suite**

```bash
python -m pytest tests/ -x -q
```

Expected: All pass, count should be ~1030+ (1006 baseline + ~25 new tests from phases 1-8).

- [ ] **Step 2: Verify no regressions**

Compare test count with pre-V12 baseline (1006 tests). The increase should
correspond to the number of new tests written across all phases.

- [ ] **Step 3: Final commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.9.3: V12 complete — 22 bugs fixed, all tests pass"
```

## Acceptance Criteria Checklist

Before marking V12 complete, verify ALL of these:

- [ ] No file with `:` in its name exists after scrape/reclean
- [ ] Episodes in nested torrent subdirectories are extracted to `Saison XX/`
- [ ] `result.media_path` is updated after tvshow folder rename
- [ ] qBit pre-check prevents login when IP is banned (403)
- [ ] Verify blocks items with NTFS-illegal filenames
- [ ] Dispatch refuses NTFS-unsafe items before rsync
- [ ] Pipeline cleans crash artifacts at startup
- [ ] pipeline-monitor skill STOPs on auth lockout and rsync errors
- [ ] 22 bugs → 22+ reproducer tests with traceability table
- [ ] All tests pass, 0 regressions
