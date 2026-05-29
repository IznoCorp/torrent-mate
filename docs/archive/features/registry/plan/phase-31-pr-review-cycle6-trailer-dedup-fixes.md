# Phase 31 — PR review cycle 6: trailer-aware dedup fixes

Generated 2026-05-28 from a focused adversarial review (3 reviewers: code-reviewer,
silent-failure-hunter, pr-test-analyzer) of the **phase-30** changes after CI went
green on `feat/registry @ 79b345d8`. The prior 5 review cycles predate phase 30;
this is a fresh review of the genuinely-new dedup code. Operator elected "fix
everything before merge".

## Gate

- Phases 0–30 complete. PR #27 OPEN, CI green on 79b345d8.
- The phase-30 dedup fix (Gourou) itself is sound and well-tested (3 reviewers concur).
- This phase closes the cross-feature interaction bug + robustness/test gaps the
  review surfaced. Merge mode = manual.

## Goal

The phase-30 `no_duplicate_videos` VERIFY check and the post-rename orphan-unlink
loop count/act on **every** root-level video file, with **no exemption for the
flat movie trailer** `{media_name}-trailer.{ext}` (Plex Local Media Assets
convention — movies place the trailer FLAT at the movie root; see
`personalscraper/trailers/placement.py:71` + `docs/reference/trailers.md:184-186`;
the extension is in `VIDEO_EXTENSIONS`). Consequences (confirmed):

- **MAJEUR**: any movie that has a trailer (every stored movie with trailers
  enabled, and any idempotent re-run that reached the trailers step) presents two
  flat root videos → the new ERROR check fails → dispatch blocked; and the orphan
  loop could `unlink()` the trailer. `verify/checker.py` has zero trailer handling.
- **MEDIUM (B)**: orphan-unlink `OSError` is logged (`movie_video_orphan_remove_failed`)
  but NOT appended to `result.warnings` — asymmetric with the rename branch above
  it; the scrape self-reports success while a duplicate persists (caught downstream
  by VERIFY, so no storage leak, but an operator-visibility gap).
- **MEDIUM (C)**: `_find_video_file` selects recursively (`rglob`, excludes only
  `.actors`/`Trailers`) but the orphan loop is root-only (`iterdir`); if the
  canonical were ever selected from a subdir, the loop's name-based skip fails →
  it could delete every root video.
- **Test gaps**: the destructive orphan-loop's non-video/subdir skip guard
  (movie_service.py line ~1006) is untested; `_find_video_file`'s `OSError`
  fallback and `Trailers/`-skip are untested.

Fix: introduce ONE shared trailer-filename predicate and apply the exemption at all
three sites, surface the orphan failure, guard the cleanup to a root canonical, and
fill the test gaps.

## Scope

### Sub-phase 31.1 — Shared trailer predicate + VERIFY exemption

**Targets**: Finding A (VERIFY facet).

**Tasks**:

1. Add `is_trailer_filename(name: str) -> bool` to
   `personalscraper/sorter/file_type.py` (the low-level module already importing
   `VIDEO_EXTENSIONS`, imported by both verify and scraper — no new cross-package
   dependency, avoids importing `trailers/` into verify/scraper). Semantics: a flat
   movie trailer is `{media_name}-trailer.{ext}`; return
   `Path(name).stem.casefold().endswith("-trailer")`. Google docstring; note the
   Plex flat-trailer convention and that it is a filename-only check.
2. In `personalscraper/verify/checker.py::_check_no_duplicate_videos`, filter the
   root video list through `is_trailer_filename` BEFORE the `> 1` test:
   `videos = [f for f in self._find_video_files(movie_dir) if not is_trailer_filename(f.name)]`.
   The error message still lists the offending non-trailer filenames. Import the
   predicate (hook-aware: use it in the same edit).
3. Tests in `tests/verify/test_no_duplicate_videos.py`:
   - `Movie.mkv` + `Movie (2020)-trailer.mp4` at root → `passed is True` (trailer exempt).
   - `Movie.mkv` + `orphan.mkv` (no trailer) → still `passed is False` (regression intact).
   - (Keep the existing cases.)

**Commit**: `fix(verify): exempt flat movie trailers from no_duplicate_videos check`.

### Sub-phase 31.2 — Scraper: never select or unlink a flat trailer

**Targets**: Finding A (scraper facets) + test gaps D2/D3.

**Tasks**:

1. `personalscraper/scraper/_shared.py::_find_video_file`: add
   `and not is_trailer_filename(f.name)` to the candidates comprehension so a flat
   trailer is NEVER chosen as the canonical feature (it would otherwise win on
   mtime when downloaded after the movie). Import the predicate. Update the docstring.
2. `personalscraper/scraper/movie_service.py` orphan loop: add an early
   `if is_trailer_filename(entry.name): continue` so a flat trailer is never
   unlinked. (Import the predicate; hook-aware.)
3. Tests:
   - `tests/scraper/test_find_video_file.py`: (a) a flat `X-trailer.mkv` with the
     NEWEST mtime is NOT selected — the real feature is returned; (b) `Trailers/`
     sub-dir video is ignored (D3); (c) `OSError` on `stat()` for one candidate →
     `candidates[0]` returned + `video_stat_failed` logged (D2, patch `Path.stat`).
   - `tests/scraper/test_movie_service_extra.py`: post-scrape, a flat
     `{title}-trailer.mp4` at the movie root is NOT removed by the orphan loop
     (survives alongside the canonical).

**Commit**: `fix(scraper): never select or unlink flat movie trailers in dedup`.

### Sub-phase 31.3 — Orphan-loop robustness (B + C + D1)

**Targets**: Findings B, C, test gap D1.

**Tasks**:

1. `movie_service.py` orphan loop (B): in the `except OSError` branch, after the
   `log.warning`, append `result.warnings.append(f"Orphan video not removed: {entry.name}: {exc}")`
   so the residual duplicate is visible in the scrape result (mirrors the rename
   branch ~L992). Fail-soft `continue` preserved.
2. `movie_service.py` (C): only run the orphan-cleanup loop when the canonical is at
   the movie root — guard with `if video_file.parent == movie_dir:` (or equivalent).
   If the canonical was selected from a sub-dir, skip root cleanup (VERIFY still
   backstops). Add a brief comment explaining the scope-consistency rationale.
3. Tests in `tests/scraper/test_movie_service_extra.py`:
   - D1 (non-destructive guard): a movie dir with the canonical + an orphan `.mkv`
     - a `.nfo` + a poster `.jpg` + an `Extras/bonus.mkv` sub-dir → after scrape the
       orphan is removed but the NFO, poster, and `Extras/bonus.mkv` all survive.
   - B: orphan `unlink` raises `OSError` (patched) → `result.warnings` contains an
     "Orphan video not removed" entry AND the canonical is untouched, no raise.

**Commit**: `fix(scraper): surface orphan-unlink failures + guard cleanup to root canonical`.

## Verification (phase gate)

1. `make lint` → 0 errors. 2. `make check` → exit 0 (full suite green). 3. smoke
   import. 4. `git diff <phase-31-baseline>..HEAD --stat` shows only:
   `personalscraper/sorter/file_type.py`, `personalscraper/verify/checker.py`,
   `personalscraper/scraper/_shared.py`, `personalscraper/scraper/movie_service.py`,
   `tests/verify/test_no_duplicate_videos.py`, `tests/scraper/test_find_video_file.py`,
   `tests/scraper/test_movie_service_extra.py`, this plan file, `IMPLEMENTATION.md`.

## Out of scope

- Reworking trailer placement or the TV-show `Trailers/` subfolder handling.
- The matrix v2.5 (`.claude` repo) — the movie-dedup contract row stays valid; a
  future matrix pass may add a "flat trailer is exempt" note (non-blocking).

## Next action

After phase 31 closes: re-run `make check`, re-push `feat/registry`, confirm CI
green, then operator squash-merges PR #27 (manual). Post-merge: `/pipeline-monitor`
re-validation + optional `/implement:archive`.
