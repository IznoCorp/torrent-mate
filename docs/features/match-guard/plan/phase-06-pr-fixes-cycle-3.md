# Phase 6 — PR #203 review fixes (cycle 3 / operator-elected robustness)

> Cycle-3 re-review found one minor (safe-degradation) gap: `_recover_title_from_episodes` only recovers when episodes are at the show root or in a `SEASON_DIR_RE`-matching dir (`Saison NN`/`Season NN`). Exotic season dirs — `"Saison 3 - VOSTFR"`, `"Staffel 3"`, `"S03"`, `"Disc 1"`, `"Season 3 [1080p]"` — yield `None` (recovery miss → safe suppression). Operator elected to fix this (French content → VOSTFR dirs are real). PROVEN: those dirs currently return `None` while `"Saison 3"`/root return `"The Orville"`.

## Phase gate (exit)

`make check` green. Recovery works for exotic season dirs (VOSTFR/Staffel/S03/Disc) AND still excludes `Extras/Featurettes/Bonus` even in the fallback path. No regression on the cycle-2 cases. New tests mutation-proof.

---

### Sub-phase 6.1 — fallback scan excluding extras dirs (recover exotic season dirs)

**Files:** `personalscraper/scraper/tv_service.py`, tests `tests/scraper/test_confidence_match_guard.py`.

- [ ] **Failing tests first** (extend the recovery test class): for EACH exotic parent dir name — `"Saison 3 - VOSTFR"`, `"Staffel 3"`, `"S03"`, `"Disc 1"`, `"Season 3 [1080p]"` — a `…/ S03/<exotic>/The Orville - S3E01.mkv` layout → recovery returns `"The Orville"` (today returns `None`). PLUS: an `Extras`-only folder (`…/ S03/Extras/Behind The Scenes.mkv` with NO other video) → returns `None` (extras excluded even in fallback). PLUS a MIXED case (`Extras/Bonus.mkv` + `Saison 3 - VOSTFR/The Orville - S3E01.mkv`) → `"The Orville"` (fallback skips Extras, takes VOSTFR).
- [ ] **Implement** in `_recover_title_from_episodes`:
  - Add a module-level `_EXTRAS_DIR_NAMES` frozenset of lowercased non-episode subdir names: `{"extras", "featurettes", "featurette", "bonus", "bonuses", "behind the scenes", "deleted scenes", "deleted", "interviews", "making of", "trailers", "supplements", "specials feature"}` (keep it focused; `Specials` is a LEGIT Plex season-0 so do NOT exclude bare `specials`).
  - Add `_is_extras_location(path) -> bool`: True if any parent dir name between `show_dir` and the file (exclusive of `show_dir`) lowercases into `_EXTRAS_DIR_NAMES`.
  - Two-tier selection: first build the RESTRICTED set (existing `f.parent == show_dir or SEASON_DIR_RE.match(f.parent.name)`, minus samples). If non-empty → use it (preserves cycle-2 behavior exactly). If EMPTY → build the FALLBACK set = all videos minus samples minus `_is_extras_location`. Use whichever non-empty set (restricted first), `sorted` for deterministic pick.
  - Keep the end-anchored `_SEASON_TOKEN_RE` strip + the narrowed except unchanged.
- [ ] **Mutation**: remove the fallback (only restricted set) → a VOSTFR test FAILS (returns None); restore. Remove the `_is_extras_location` exclusion from the fallback → the MIXED Extras+VOSTFR test could pick the Extras file → that test FAILS; restore.
- [ ] **Regression**: confirm the cycle-2 cases still hold — `Saison 3`+`Extras` → `"The Orville"` (restricted set non-empty, never reaches fallback); plain `Extras`-only → None.
- [ ] **Commit** `fix(match-guard): fallback episode scan (exclude Extras) recovers exotic season dirs (VOSTFR/Staffel/S03/Disc)`

---

### Sub-phase 6.2 — Gate

- [ ] `make check` green (ruff + mypy + full suite, 0 failed/errors). Smoke import. Re-run `tests/scraper/`.
