# Phase 30 — Scraper same-TMDB multi-source dedup gap fix

Generated 2026-05-28 after running `/pipeline-monitor` (matrix v2.4) on the
merge-ready HEAD (post phase 29). The pipeline-monitor surfaced **1 new
MAJEUR DEVIATION** that the prior PR-monitor runs did not see, plus a
matrix-coverage gap. The operator elected to ship the fix in this PR rather
than open a separate one.

## Gate

- Phases 0–29 complete (all [x] in IMPLEMENTATION.md).
- PR #27 currently `OPEN` and merge-ready before this phase.
- CI green on the head of `feat/registry`.
- Pipeline-monitor 2026-05-28 17h50 run STOPPED at GATE 6 on DEVIATION #1.
- Staging fully reset (no orphans) — see
  `docs/pipeline-runs/2026-05-28-17h50-pipeline-run.md` §Traitement for the
  reset receipt (8 hashes removed from tracker, 4 staging dirs deleted).

## Goal

Close the same-TMDB multi-source DEVIATION discovered by pipeline-monitor:
when two distinct staged movie folders both resolve to the same TMDB id, the
scraper merges them into the canonical folder but leaves orphan `.mkv` files
behind. No pipeline step (CLEAN / CLEANUP / ENFORCE / VERIFY) currently
catches the duplicate. Apply defense-in-depth: root-cause fix + automatic
cleanup + safety net. Bump pipeline-monitor matrix to v2.5 to document the
new contract.

Operator spec, verbatim from the 2026-05-28 17h50 run interaction: « la
dernière version (le dernier téléchargé) doit être celui qui reste à la
fin » — the canonical video must be the most recently downloaded one, and
no orphan must remain.

## Scope

### Sub-phase 30.1 — Root cause: `_find_video_file` mtime preference

**Target finding** : DEVIATION #1, axis 1 (canonical selection logic).

**Evidence** : `personalscraper/scraper/_shared.py::_find_video_file`
currently returns the LARGEST video file via `max(candidates, key=size)`.
This is wrong: per operator spec the LAST DOWNLOADED (= most recent
`st_mtime`) must win. In the Gourou test scenario the largest happened to
match the last downloaded by coincidence (HDR 22 GB ingested at 19:47:14 >
1080p 2.9 GB ingested at 19:43:21), but the contract was never enforced.

**Tasks** :

1. Edit `personalscraper/scraper/_shared.py::_find_video_file`:
   - Replace the `max(... key=size)` reduction with a sort by
     `(mtime, size)` descending so mtime drives selection and size is the
     tie-breaker for identical mtimes.
   - Keep the existing recursion, hidden-file skip, and `.actors/` skip.
   - Update the docstring to document the mtime-first semantics.

2. Add unit tests in `tests/scraper/test_find_video_file.py`
   (create the file if missing — check the project's existing scraper test
   layout in `tests/scraper/` first to match the established pattern):
   - 2 candidates, different mtimes, same size → newest wins.
   - 2 candidates, same mtime, different sizes → largest wins (tie-break).
   - 1 candidate → returned as-is.
   - 0 candidates → returns `None`.
   - Recursion: candidate in `Saison 01/` sub-dir → picked up.
   - Skip: hidden file `.foo.mkv` → ignored.

3. Run `make test` scoped: `pytest tests/scraper/test_find_video_file.py
-xvs`. Must be green.

**Commit** : `fix(scraper): _find_video_file prefers last-modified over largest`.

### Sub-phase 30.2 — Post-rename orphan unlink

**Target finding** : DEVIATION #1, axis 2 (automatic cleanup).

**Evidence** : `personalscraper/scraper/movie_service.py` lines 977–991 rename
the chosen video file to the canonical name (e.g. `Gourou.mkv`) but never
revisit the directory to remove any leftover video files. In the Gourou
scenario, after the rename the 1080p `.mkv` persisted at the movie root.

**Tasks** :

1. In `movie_service.py`, after the canonical rename succeeds (after line
   982 `log.info("movie_video_renamed", ...)`), iterate over the movie
   directory and unlink any other file whose extension is in
   `VIDEO_EXTENSIONS` and whose path is not the canonical one. Emit a new
   structured-log event `movie_video_orphan_removed` per removal with
   `filename` and `parent` fields. Wrap each unlink in a try/except
   `OSError` that emits `movie_video_orphan_remove_failed` and continues;
   one orphan failing must not abort the others. Guard the loop behind the
   non-dry-run branch (do nothing in dry-run, but emit
   `movie_video_orphan_would_remove` for visibility).

2. Add unit tests in `tests/unit/scraper/test_movie_service_orphan_cleanup.py`
   (or extend the closest existing module after grep'ing
   `tests/unit/scraper/test_movie_*` for the prevailing pattern):
   - 2 `.mkv` in the same movie dir post-merge → after `process()` only the
     canonical remains, the other unlinked, `movie_video_orphan_removed`
     emitted once.
   - Same setup in dry-run → both files still on disk,
     `movie_video_orphan_would_remove` emitted, no `unlink` called.
   - Orphan unlink fails (mock `OSError`) → log
     `movie_video_orphan_remove_failed`, canonical untouched, no raise.

3. `make test` scoped: `pytest tests/unit/scraper/ -xvs -k orphan`.

**Commit** : `fix(scraper): unlink non-canonical video files after movie rename`.

### Sub-phase 30.3 — VERIFY safety net

**Target finding** : DEVIATION #1, axis 3 (defense if 30.1+30.2 regress).

**Evidence** : `personalscraper/verify/checker.py` runs 12 checks on movies
and 18 on TV shows. None of the 12 movie checks counts the video files at
the movie root. If 30.1+30.2 regress in the future, VERIFY currently
returns `status=valid` despite duplicate `.mkv` files, and DISPATCH copies
both to storage.

**Tasks** :

1. Add a new check `_check_no_duplicate_videos` in `verify/checker.py`:
   - Movie scope only (TV shows have multi-file seasons by design — do not
     apply).
   - Iterate the movie directory non-recursively; collect files whose
     extension is in `VIDEO_EXTENSIONS`.
   - If `> 1` → return a `CheckResult` with `passed=False, error=f"Multiple
video files at root: {sorted(filenames)}"`.
   - Wire it into the movie checks pipeline so `checks_total` becomes
     `13/13` for movies (verify the matrix-aware agent prompt expects the
     new denominator — see 30.5).

2. Add unit tests in `tests/unit/verify/test_no_duplicate_videos.py`:
   - 1 video at root → passes.
   - 2 videos at root → fails with the error string above.
   - 1 video at root + 1 video in `Extras/` sub-dir → passes (sub-dir
     ignored; movies are flat).
   - 0 videos → other movie checks already cover this, do not re-test.

3. `make test` scoped: `pytest tests/unit/verify/ -xvs -k duplicate`.

**Commit** : `feat(verify): block movies with multiple video files at root`.

### Sub-phase 30.4 — E2E regression test reproducing the Gourou scenario

**Target finding** : pin the bug under regression per the project memory
`feedback_regression_test_per_bug` — every detected bug needs a test that
reproduces it.

**Evidence** : currently no E2E covers two distinct staged movie folders
resolving to the same TMDB id.

**Tasks** :

1. Add `tests/e2e/test_scrape_same_tmdb_multi_source.py`:
   - Fixture: 2 movie dirs in a temp staging
     (`Gourou (2025)/A.mkv` with older mtime, `Gourou (2026)/B.mkv` with
     newer mtime).
   - Mocked TMDB returning the same canonical id for both folder probes.
   - Run the scrape pipeline against the fixture.
   - Assert post-scrape: only `Gourou (2026)/Gourou.mkv` exists, contents
     match `B.mkv` (the newest), `Gourou (2025)/` is gone (merged + empty
     dir removed), NFO + poster + landscape present, no orphan `.mkv` at
     the canonical root.
   - Assert log capture: `movie_folder_merged`, `movie_video_renamed`,
     `movie_video_orphan_removed` (exactly once), no
     `movie_video_orphan_remove_failed`.
   - Assert VERIFY on the result: `verify_item_done status=valid
checks_passed=13 checks_total=13`.

2. Hook the test into the existing E2E test harness — look up
   `tests/e2e/conftest.py` and `pytest.ini` markers; if `@pytest.mark.e2e`
   is the convention, apply it.

3. `make test` scoped: `pytest tests/e2e/test_scrape_same_tmdb_multi_source.py
-xvs`.

**Commit** : `test(scraper): e2e regression for same-TMDB multi-source dedup`.

### Sub-phase 30.5 — Matrix v2.4 → v2.5 bump (pipeline-monitor skill)

**Target finding** : DEVIATION coverage gap in the matrix.

**Evidence** : matrix v2.4 has no row for the same-TMDB multi-source
scenario. The pipeline-monitor run had to escalate it as a "weird output"
and the operator had to interpret manually.

**Tasks** :

1. Edit `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md`:
   - Header bump: `**Matrix version**: 2.4` → `**Matrix version**: 2.5`.
   - Section PROCESS:scrape (movies subsection): add a new
     DESIGN_CONFORM row:
     > `movie_video_orphan_removed` — observed when two distinct movie
     > folders resolve to the same TMDB id and are merged. Canonical video
     > = mtime-latest; all other video files in the canonical dir are
     > unlinked. Contract: scraper preserves at most one video file at the
     > root of a movie folder. Operator spec captured in the 2026-05-28
     > 17h50 run.
   - Section VERIFY: update the movie denominator from `12/12` to `13/13`
     and document the new check
     `verify_item_done errors=['Multiple video files at root: [...]']`
     as DESIGN_DEVIATION (critique) — never expected after a clean scrape.
   - Changelog entry at the matrix footer: `v2.5 (2026-05-28): movie
dedup contract documented; verify movie denominator bumped to 13`.

2. Edit `.claude/skills/pipeline-monitor/SKILL.md` (or whichever file holds
   the `MATRIX_VERSION` assertion): bump the constant to `"2.5"` so the
   assertion-at-start check passes against the new matrix header. Grep for
   `MATRIX_VERSION = "2.4"` to locate.

3. Update the matrix-aware agent prompts under `.claude/agents/`:
   - `pipeline-output-analyzer.md`: add `movie_video_orphan_removed` and
     `movie_video_orphan_would_remove` to the DESIGN_CONFORM event list.
   - `pipeline-scrape-checker.md`: add explicit instruction to count `.mkv`
     at the movie root and flag any case where `> 1` as
     DESIGN_DEVIATION (critique).
   - `pipeline-invariant-checker.md`: no change (the contract is enforced
     by VERIFY, not by a transverse invariant).

4. No new sub-phase test — the matrix update is documentation; its
   correctness is verified by the next pipeline-monitor invocation passing
   the `MATRIX_VERSION` assertion and not re-surfacing DEVIATION #1.

**Commit** : `docs(pipeline-monitor): matrix v2.5 — movie dedup contract`.

## Verification (phase gate)

After all 5 sub-phases :

1. `make lint` → 0 errors.
2. `make test` → all suites green, including the new unit + E2E added in
   30.1, 30.2, 30.3, 30.4.
3. `make check` → exit 0 (lint + test + module-size + typed-api).
4. Smoke test: `python -c "import personalscraper"` exits 0.
5. `git diff phase-29-baseline..HEAD --stat` reflects only the expected
   touched files:
   - `personalscraper/scraper/_shared.py`
   - `personalscraper/scraper/movie_service.py`
   - `personalscraper/verify/checker.py`
   - `tests/unit/scraper/test_find_video_file.py` (new)
   - `tests/unit/scraper/test_movie_service_orphan_cleanup.py` (new or
     extended)
   - `tests/unit/verify/test_no_duplicate_videos.py` (new)
   - `tests/e2e/test_scrape_same_tmdb_multi_source.py` (new)
   - `.claude/skills/pipeline-monitor/references/design-conformity-matrix.md`
   - `.claude/skills/pipeline-monitor/SKILL.md` (matrix version constant)
   - `.claude/agents/pipeline-output-analyzer.md`
   - `.claude/agents/pipeline-scrape-checker.md`
   - `docs/features/registry/plan/phase-30-scrape-dedup-gap-fix.md` (this
     file)
   - `IMPLEMENTATION.md` (phase 30 row + next-action update)
6. Re-run `/pipeline-monitor` after re-staging the 2 Gourou torrents from
   qBit (delete their tracker entries first if needed). DEVIATION #1
   must NOT reappear. The 2 sources must converge to a single
   `Gourou (<year>)/Gourou.mkv` (the newer torrent's content).

## Out of scope

- TV-show duplicate-video detection — TV shows have multi-file seasons by
  design; the new VERIFY check is movie-only.
- Refactoring `_merge_dirs` itself — its contract (source wins on conflict,
  recursive on dirs) is unchanged.
- Refining the `pipeline-bdd-validator` and `pipeline-state-validator`
  prompts for the 2026-05-28 17h50 run's TOOLING_BUG false positives
  (DEVIATIONs #2, #4, #5). Defer to a separate skill-maintenance pass.
- Fixing AG/AH storage drift (DEVIATIONs #7, #8). Defer to a targeted
  `library-clean` invocation after merge.
- Adding `LIBRARY_ANALYZER_MAX_WORKERS` to `.env.example` (DEVIATION #3).
  Phase 28 already established the canonical form
  (`# LIBRARY_ANALYZER_MAX_WORKERS=4`) is present; the v2.4 invariant-checker
  agent still grep-mismatches the commented form. Defer to the same
  skill-maintenance pass.
- A `Versions/` sub-folder mechanism for users who legitimately want to
  keep multiple quality versions of the same film. The current operator
  spec is "one file per movie folder, mtime-latest wins". Future enhancement
  out of scope.

## Next action

After phase 30 closes :

1. Push to `feat/registry`. CI must stay green.
2. `merge_mode=manual` — operator squash-merges PR #27 via GitHub UI.
3. After merge, run `/pipeline-monitor` once more in read-only mode against
   `main` with the 2 Gourou torrents re-ingested. Confirm DEVIATION #1 is
   resolved and matrix v2.5 holds.
4. Optionally `/implement:archive` to move `docs/features/registry/` into
   `docs/archive/features/`.
