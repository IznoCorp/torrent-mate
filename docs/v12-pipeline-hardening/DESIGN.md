# V12 — PIPELINE HARDENING & BUG FIXES — Design Spec

> Fix 22 bugs exposed by the 2026-04-13 pipeline run, organized into 9 root
> patterns. Every fix MUST include a reproducer test that fails before the
> fix and passes after. No exception.

## Origin

Pipeline run `docs/pipeline-runs/2026-04-13-20h00-pipeline-run.md` exposed
22 bugs across all pipeline steps. Two independent analyses (contextual +
fresh agent) identified 9 root patterns.

## Critical Testing Requirement

Previous versions had tests that passed but completely missed real-world
bugs (torrent structures with nested subdirectories, filenames with colons,
artwork residuals after rename). V12 enforces:

1. Every bug fix MUST have a test that REPRODUCES the exact bug scenario
2. Tests MUST use realistic data (real torrent structures, real special
   characters like `:`, real NTFS constraints)
3. The test MUST fail before the fix and pass after
4. Phase 9 (test audit) verifies 22 bugs → 22+ tests with traceability

## Phase 1: sanitize_filename cohérent (bugs #3, #4, #5, #9, #10, #13, #16)

### Problem

When the scraper renames a folder (strips `:`), old artwork/NFO files inside
keep the old name with `:`. New files are created with sanitized names →
duplicates. The `reclean.py` `_format_clean_name()` also omits
`sanitize_filename()`, letting folders with `:` survive reclean. Files with
`:` crash rsync on NTFS with "Invalid argument".

### Design

Two corrections:

**1a. Cleanup post-rename in scraper.py `scrape_movie()` and `scrape_tvshow()`:**

After folder rename (strip `:`), scan for stale files whose stem starts with
the OLD title prefix and delete them if a sanitized version exists:

```python
# After movie_dir = new_path (line 534)
if old_name != clean_name:
    _cleanup_stale_files(movie_dir, old_name, clean_name)
```

New function `_cleanup_stale_files(directory, old_prefix, new_prefix)`:

- Iterate directory files
- For each file whose stem starts with old_prefix:
  - Build the expected sanitized equivalent
  - If the sanitized version exists → delete the old file
  - Log at INFO: "Cleaned stale file: {old_name}"

**1b. sanitize_filename in reclean.py:**

Apply `sanitize_filename()` to the result of `_format_clean_name()` (line 126):

```python
clean_name = sanitize_filename(_format_clean_name(title, year))
```

### Files modified

- `personalscraper/scraper/scraper.py` — add `_cleanup_stale_files()`, call
  after rename in `scrape_movie()` and `scrape_tvshow()`
- `personalscraper/process/reclean.py` — apply `sanitize_filename()` in
  `_reclean_folder()`

### Tests

- Create folder `"Title : Subtitle (2025)/"` with artwork files
  `"Title : Subtitle-poster.jpg"`, `"Title : Subtitle.nfo"`. Run
  `_cleanup_stale_files()`. Verify old files deleted, new files kept.
- Create folder with `:` in name, run `_reclean_folder()`. Verify output
  name has no `:`.
- End-to-end: mock `scrape_movie()` on a folder with `:` → verify no `:` files
  remain after scrape.

## Phase 2: Restructuration épisodes (bugs #6, #7, #8)

### Problem

Torrents like Jury Duty package episodes as one subdirectory per episode:
`Show/S01E01.Release.Group/S01E01.mkv`. The scraper's `_find_video_file()`
uses `iterdir()` (flat scan) and doesn't find nested .mkv files. Episodes
are not extracted from nested dirs into `Saison XX/`.

Note: the `scrape_tvshow()` rglob on line 812 DOES find nested files for
episode matching. The issue is that after matching and renaming, the empty
release-group subdirectories are not cleaned up, AND `_find_video_file()`
(used for movies) doesn't recurse.

### Design

**2a. Make `_find_video_file()` recursive:**

Replace `directory.iterdir()` with `directory.rglob("*")`, filtering for
video extensions. If multiple video files are found, pick the largest one
(main feature, not sample/extra).

```python
def _find_video_file(directory: Path) -> Path | None:
    candidates = [
        f for f in directory.rglob("*")
        if f.is_file()
        and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not f.name.startswith(".")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_size)
```

**2b. Clean empty release-group subdirectories after episode rename:**

After `rename_episodes()` in `scrape_tvshow()`, scan show_dir for empty
subdirectories (excluding `Saison XX/` and `.actors/`) and remove them.

```python
# After rename_episodes(), clean empty release-group dirs
for subdir in show_dir.iterdir():
    if (subdir.is_dir()
        and not subdir.name.startswith(".")
        and not re.match(r"^Saison \d+$", subdir.name)):
        try:
            if not any(subdir.iterdir()):
                subdir.rmdir()
                logger.info("Removed empty release dir: %s", subdir.name)
        except OSError:
            pass
```

### Files modified

- `personalscraper/scraper/scraper.py` — rewrite `_find_video_file()`, add
  cleanup of empty release dirs after episode rename

### Tests

- Create `Show/S01E01.Release/S01E01.mkv` + `Show/S01E02.Release/S01E02.mkv`.
  Run episode matching. Verify files end up in `Show/Saison 01/` and empty
  `S01E01.Release/` dirs are removed.
- `_find_video_file()` with nested structure: verify it finds the deepest .mkv.
- `_find_video_file()` with multiple nested video files: verify it picks the
  largest.

## Phase 3: result.media_path stale (bug #17)

### Problem

`scrape_tvshow()` updates `show_dir = new_dir` after rename (line 776) but
does not update `result.media_path`. `scrape_movie()` does it correctly
(line 535).

### Design

One-line fix: add `result.media_path = new_dir` after `show_dir = new_dir`.

### Files modified

- `personalscraper/scraper/scraper.py` — line 776

### Tests

- Mock a tvshow folder that requires rename (different name from API).
  Verify `result.media_path` equals the new path after scrape.

## Phase 4: qBit auth pre-check (bugs #1, #2, #12, #20)

### Problem

qBit returns 403 (IP banned). `auth_log_in()` fails → lockout file created
→ pipeline blocked. No way to detect the ban before attempting login.

### Design

Add a health check before `auth_log_in()` in `QBitClient.__enter__()`:

```python
# Pre-check: verify qBit is accessible before auth attempt
try:
    resp = requests.get(
        f"http://{self._client.host}:{self._client.port}/api/v2/app/version",
        timeout=5,
    )
    if resp.status_code == 403:
        raise qbittorrentapi.Forbidden403Error(
            "IP is already banned by qBittorrent. "
            "Unban in Preferences > Web UI > IP Banning."
        )
except requests.ConnectionError:
    raise qbittorrentapi.APIConnectionError(
        f"qBittorrent unreachable at {self._client.host}:{self._client.port}"
    )
```

This prevents `auth_log_in()` from being called when the IP is already
banned, avoiding further ban accumulation.

### Files modified

- `personalscraper/ingest/qbit_client.py` — add pre-check in `__enter__()`

### Tests

- Mock `requests.get` returning 403 → verify `auth_log_in()` is NEVER called
  and `Forbidden403Error` is raised.
- Mock `requests.get` raising `ConnectionError` → verify `APIConnectionError`
  is raised.
- Mock `requests.get` returning 200 → verify `auth_log_in()` IS called
  (normal flow).

## Phase 5: Verify/Dispatch NTFS-safe (bugs #18, #19)

### Problem

Verify doesn't check for NTFS-illegal characters in filenames. Dispatch
launches rsync without pre-scanning. Items with `:` pass verify but crash
at dispatch with rsync rc=23.

### Design

**5a. New check `ntfs_safe_names` in `checker.py`:**

Scan all files in the item directory. For each file, check if the name
contains any of `<>:"/\|?*`. If yes → check FAIL with the filename.

Use `_FILENAME_ILLEGAL` regex from `text_utils.py` (already defined).

**5b. Pre-scan in `dispatcher.py` before rsync:**

Before calling rsync, scan the source directory for NTFS-illegal filenames.
If any found → skip the item with a clear error message listing the
offending files. Do not attempt rsync.

### Files modified

- `personalscraper/verify/checker.py` — add `ntfs_safe_names` check
- `personalscraper/dispatch/dispatcher.py` — add `_has_ntfs_illegal_names()`
  pre-scan before rsync

### Tests

- Verify: create item with `"poster : title.jpg"` → check `ntfs_safe_names`
  fails with the filename.
- Verify: create item with clean names → check passes.
- Dispatch: mock item with `:` file → verify it's skipped, rsync never called.

## Phase 6: Crash recovery pipeline (bug #15)

### Problem

When the pipeline is interrupted, no cleanup at next startup. Orphan
`_tmp_dispatch_*` dirs remain on storage disks, stale lockout files block
ingest, state files may be inconsistent.

### Design

Add `_recover_from_previous_run()` at the beginning of `Pipeline.run()`,
before INGEST:

```python
def _recover_from_previous_run(self) -> None:
    """Clean up artifacts from a previous interrupted pipeline run."""
    cleaned = 0
    # 1. Clean _tmp_dispatch_* on ALL storage disks
    for disk_config in self.settings.disk_configs:
        if disk_config.path.exists():
            for category_dir in disk_config.path.iterdir():
                if not category_dir.is_dir():
                    continue
                for item in category_dir.iterdir():
                    if item.name.startswith("_tmp_dispatch_"):
                        try:
                            shutil.rmtree(item)
                            cleaned += 1
                        except OSError:
                            pass

    # 2. Clean expired qBit lockout
    lockout = Path.home() / ".cache" / "personalscraper" / "qbit_auth_lockout"
    if lockout.exists():
        age = time.time() - lockout.stat().st_mtime
        if age > 3600:  # Expired (> 1 hour)
            lockout.unlink(missing_ok=True)
            cleaned += 1

    # 3. Clean _tmp_ingest_* in staging
    cleaned += _cleanup_orphan_temps(self.settings.ingest_dir)

    if cleaned:
        self._log.info("crash_recovery", cleaned=cleaned)
```

### Files modified

- `personalscraper/pipeline.py` — add `_recover_from_previous_run()`,
  call at start of `run()`

### Tests

- Create `_tmp_dispatch_Test/` on a mock disk + expired lockout file.
  Run `_recover_from_previous_run()`. Verify both cleaned.
- Create non-expired lockout (< 1h). Verify NOT cleaned.

## Phase 7: Améliorations mineures (bugs #21, #22)

### Design

1. **Regex Saison**: Change `r"^Saison \d{2}$"` to `r"^Saison \d+$"` in
   `scraper.py` line 815.

2. **Junk files**: Add `"desktop.ini"` to `_JUNK_FILES` in `cleanup.py`
   line 16.

### Tests

- Episode filter: create file in `Saison 1/` (single digit) → verify
  it's excluded from re-processing.
- Cleanup: create dir with only `desktop.ini` → verify it's treated as
  effectively empty.

## Phase 8: pipeline-monitor skill (bug #14)

### Problem

The `pipeline-monitor` skill continued the pipeline after `QBitAuthLockoutError`
(INGEST) and `rsync rc=23 Invalid argument` (DISPATCH) instead of triggering
the STOP PROTOCOL. The error classification was too lenient — it treated these
as "operational" issues instead of critical pipeline-blocking errors.

### Design

Modify `.claude/skills/pipeline-monitor/SKILL.md`:

**8a. Expand critical error detection in section "2.3 Display output and analyze":**

Current list:

```
- 2+ identical errors → SYSTEMIC
- "Operation not permitted" → PERMISSIONS
- "Forbidden403Error" → IP BAN
- "No space left" → DISK FULL
```

Add:

```
- "QBitAuthLockoutError" → AUTH LOCKOUT → STOP PROTOCOL
- "rsync failed" + "Invalid argument" → NTFS ILLEGAL CHARS → STOP PROTOCOL
- "auth lockout active" → AUTH LOCKOUT → STOP PROTOCOL
- error_count > 0 in INGEST step → INGEST FAILED → STOP PROTOCOL
  (if ingest fails, nothing new enters the pipeline — continuing is pointless)
```

**8b. Add rule: INGEST error = pipeline abort**

INGEST is the entry point. If it fails (error_count > 0), subsequent steps
process only stale data. The pipeline should STOP and report why ingest
failed, rather than running sort/process/verify/dispatch on nothing new.

Exception: if 097-TEMP already has items (from a previous partial run),
continuing makes sense. Add this nuance:

```
- INGEST error_count > 0 AND 097-TEMP is empty → STOP PROTOCOL
- INGEST error_count > 0 AND 097-TEMP has items → WARNING, continue
```

**8c. Strengthen gate checks:**

Each gate check (section 2.6) should verify that the step's error_count
is 0 for critical steps (INGEST, DISPATCH). Currently the gate only checks
"No critical error detected" which was interpreted too loosely.

Change to:

```
- [ ] No critical error detected
- [ ] For INGEST: error_count == 0 (or 097-TEMP has items from prior run)
- [ ] For DISPATCH: no rsync failures with "Invalid argument"
```

### Files modified

- `.claude/skills/pipeline-monitor/SKILL.md` — update error detection,
  gate checks, and INGEST abort rule

## Phase 9: Test audit final (bug #11 — transversal)

### Problem

Previous versions had tests that passed but didn't cover real-world
scenarios. The pipeline run exposed bugs that existing tests completely
missed.

### Design

After all fixes are applied (phases 1-8), audit test coverage:

1. For each of the 22 bugs in the pipeline run report:
   - Identify which test covers it
   - If no test exists → write one
   - Verify the test would FAIL on the pre-V12 code

2. Create a traceability table in IMPLEMENTATION.md:

```markdown
| Bug # | Description          | Test file           | Test name                      | Phase |
| ----- | -------------------- | ------------------- | ------------------------------ | ----- |
| 1     | qBit lockout         | test_qbit_client.py | test_pre_check_403_skips_login | 4     |
| 2     | Torrents non ingérés | (consequence of #1) | —                              | —     |

| ...
```

3. Run full test suite. Verify 0 failures and count increase (expect
   ~20+ new tests from phases 1-8).

### Files modified

- `docs/IMPLEMENTATION.md` — traceability table
- Various test files — gap-filling tests if any bug lacks coverage

## Phase Dependencies

```
Phase 1 (sanitize) → Phase 5 (NTFS checks reference sanitize_filename)
Phase 2 (episodes) → independent
Phase 3 (media_path) → independent
Phase 4 (qBit) → independent
Phase 5 (verify/dispatch) → depends on Phase 1
Phase 6 (crash recovery) → independent
Phase 7 (minor) → independent
Phase 8 (skill) → independent
Phase 9 (test audit) → depends on ALL phases 1-8
```

Recommended order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

## Acceptance Criteria

V12 is complete when:

1. No file with `:` in its name exists after scrape/reclean
2. Episodes in nested torrent subdirectories are extracted to `Saison XX/`
3. `result.media_path` is updated after tvshow folder rename
4. qBit pre-check prevents login when IP is banned (403)
5. Verify blocks items with NTFS-illegal filenames
6. Dispatch refuses items with NTFS-unsafe names before rsync
7. Pipeline cleans crash artifacts at startup
8. pipeline-monitor skill STOPs on auth lockout and rsync errors
9. 22 bugs → 22+ reproducer tests, traceability table complete
10. All tests pass, 0 regressions

## Commit Convention

Format: `v12.{phase}.{sub}: Description`

- Phase 1: v12.1.x
- Phase 2: v12.2.x
- ...
- Phase 9: v12.9.x
