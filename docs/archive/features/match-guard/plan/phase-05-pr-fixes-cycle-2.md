# Phase 5 — PR #203 review fixes (cycle 2)

> Cycle-2 re-review found the cycle-1 fix introduced TWO regressions (both concretely reproduced). This cycle fixes them and adds the missing regression tests.

## Gate (starting state — both PROVEN live)

- **MAJOR** — `_recover_title_from_episodes` uses `show_dir.rglob("*")` excluding only `is_sample_path` (`SAMPLE_DIR_NAMES={proof,sample,samples}`). An `Extras/Featurettes/Bonus` subdir video sorts before `Saison NN/` and is picked → wrong title. PROVEN: ` S03/Extras/Some Behind The Scenes Doc.mkv` + ` S03/Saison 3/The Orville - S3E01.mkv` → recovered `"Some Behind The Scenes Doc"`.
- **MEDIUM** — cycle-1 narrowed `_SEASON_TOKEN_RE` to require `S\d+E\d+`, breaking the season-only case: `NameCleaner.clean` returns `"{title} S{NN}"` (no episode) for season-pack files. PROVEN: `clean("The Orville Saison 3")="The Orville S03"` → recovered `"The Orville S03"` (S03 leaked; old regex gave `"The Orville"`).

## Phase gate (exit)

`make check` green. Extras-subdir videos cannot win recovery; season-only AND episode files both strip correctly; no over-strip. New regression tests mutation-proof.

---

### Sub-phase 5.1 — End-anchor the strip regex (fix season-only under-strip)

**Files:** `personalscraper/scraper/tv_service.py`, tests.

- [ ] **Failing tests first** (extend `tests/scraper/test_confidence_match_guard.py`): season-only recovery — a file cleaning to `"The Orville S03"` (e.g. `"The Orville Saison 3.mkv"`) → recovery returns `"The Orville"` (NOT `"The Orville S03"`); also `"Shrinking S03"`→`"Shrinking"`. Keep the episode-marked + S4C-over-strip tests passing.
- [ ] **Implement**: change `_SEASON_TOKEN_RE` to end-anchored, optional episode marker, NO trailing `.*`:
      `re.compile(r"\s*-?\s*S\d+(?:E\d+)?\s*$", re.IGNORECASE)`.
      This strips the trailing appended token only (NameCleaner appends `S{NN}` or `S{NN}E{MM}` at the end), so `"The Orville S03E01"`→`"The Orville"`, `"The Orville S03"`→`"The Orville"`, and `"S4C Documentary S01E01"`→`"S4C Documentary"` (S4C is NOT at the end). Verify all four cases by TDD.
- [ ] **Mutation**: revert to the cycle-1 `S\d+E\d+.*$` → the season-only test FAILS; restore. Revert to the original `S\d+(?:E\d+)*.*$` → the S4C over-strip test FAILS; restore. (Proves the new regex is the unique fix for BOTH.)

---

### Sub-phase 5.2 — Restrict recovery to episode locations (fix Extras-dir wrong-pick)

**Files:** `personalscraper/scraper/tv_service.py`, tests.

- [ ] **Failing test first**: ` S03/Extras/Some Behind The Scenes Doc.mkv` + ` S03/Saison 3/The Orville - S3E01.mkv` → recovery returns `"The Orville"` (NOT the Extras title). Today returns the Extras title.
- [ ] **Implement**: in `_recover_title_from_episodes`, restrict the candidate videos to those whose parent is the show root (`f.parent == show_dir`) OR whose parent matches a season-dir pattern. Reuse the existing `SEASON_DIR_RE` (grep its definition — used at `tv_service.py:309`/`existing_validator.py:314`). VERIFY `SEASON_DIR_RE` matches BOTH `"Saison 3"` (single digit, real torrent layout) AND `"Saison 01"` (pipeline-created); if it does not match `"Saison 3"`, broaden the season-dir test (case-insensitive `^(saison|season)\s*\d+$`) rather than weakening it. Keep `is_sample_path` exclusion + `sorted` deterministic pick. Extras/Featurettes/Bonus/Behind-The-Scenes parents are excluded (not season dirs, not root).
- [ ] **Mutation**: revert the parent-dir restriction → the Extras test FAILS (recovers the Extras title); restore.

---

### Sub-phase 5.3 — Gate

- [ ] `make check` green (ruff + mypy + full suite, 0 failed/errors). Smoke import. Re-run `tests/scraper/` + the new regression tests.
