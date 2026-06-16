# Phase 4 — PR #203 review fixes (cycle 1)

> Adversarial review (4 dimensions × refute-by-default): 16 findings, 14 confirmed (all "minor" per verifiers, 2 refuted). One is functionally significant: **Unit 2's Orville recovery does NOT work on the real folder layout** (episodes live in a `Saison NN/` subdir; the scan is non-recursive → returns `None`). Plus a vacuous AC-1 test and several quality/doc gaps. This cycle fixes the worthwhile ones; one finding (guard also covers the movie path) is accepted as beneficial.

## Gate (starting state)

- `_recover_title_from_episodes` (`tv_service.py:60`) scans `show_dir.iterdir()` (flat, non-recursive) → misses `…/ S03/Saison 3/The Orville - S3E01.mkv`. PROVEN: returns `None` on the real layout, `"The Orville"` only on a flat layout. AC-2 test used the flat layout.
- `_SEASON_TOKEN_RE` (`tv_service.py:57`) `\s*-?\s*S\d+(?:E\d+)*.*$` strips from the FIRST `S\d` → over-strips a recovered title containing an embedded S-number (e.g. `"S4C Documentary S01E01"` → `""`).
- `is_degenerate_title` only matches `^\s*S\d+(E\d+)?\s*$`; the DESIGN also names the **empty-title** case, which is unhandled.
- Bare `except Exception` around `NameCleaner.clean` (`tv_service.py:88`).
- AC-1 (`test_confidence_match_guard.py`) `test_season_token_normalized_rejects_glina` is **vacuous** (no alias → passes even with the guard removed). The real Orville root is alias amplification (`WRatio(" S03","Glina S03")=0.90`).
- Stale `0.67` references in test docstrings/messages + the inline `_score_result` guard comment (actual threshold is 0.40).

## Phase gate (exit)

`make check` green. The Orville recovery works on the **real** (Saison-subdir) layout. AC-1 exercises the alias-amplification path and is mutation-proof. All new tests mutation-proof.

---

### Sub-phase 4.1 — Fix `_recover_title_from_episodes` (recursive + last-token strip + empty branch + narrow except)

**Files:** `personalscraper/scraper/tv_service.py`, `personalscraper/scraper/classifier.py` (empty-title), tests `tests/scraper/test_confidence_match_guard.py`.

- [ ] **Step 1 — failing tests FIRST** (extend `test_confidence_match_guard.py`):
  - **Real-layout recovery** (the headline regression): build `tmp/" S03"/"Saison 3"/"The Orville - S3E01.mkv"` (+ E02) and assert `_recover_title_from_episodes(show_dir) == "The Orville"`. This FAILS today (returns None).
  - **Over-strip regression**: a recovered title whose NameCleaner output embeds an S-number must not be truncated to empty. Construct an episode file that cleans to e.g. `"S4C Documentary S01E01"` and assert the recovery keeps `"S4C Documentary"` (NOT `""`/None). (Verify the actual `NameCleaner.clean` output first and pick a filename that reproduces an embedded `S\d` in the cleaned title; if none reproduces, assert the strip regex directly on a crafted `raw_title`.)
  - **No-video / non-degenerate** branches already partly covered — keep them.
- [ ] **Step 2 — implement**:
  - Recursive scan: replace `show_dir.iterdir()` with a recursive walk (`show_dir.rglob("*")`) filtering `f.is_file()`, the video-extension check, AND excluding `is_sample_path(f)` (already imported, `tv_service.py:17`). Keep `sorted(...)` for deterministic first-file pick.
  - `_SEASON_TOKEN_RE`: change to strip the **last** season/episode token (require the episode marker so a title-internal `S\d` isn't matched), e.g. anchor on `S\d+E\d+` (TDD the exact form against both `"The Orville S03E01"`→`"The Orville"` and `"S4C Documentary S01E01"`→`"S4C Documentary"`).
  - Narrow the `except Exception`: catch the specific exception `NameCleaner.clean` can raise (grep `cleaner.py` for what `clean` raises — likely `guessit.api.GuessitException`; keep `pragma: no cover` only if truly unreachable).
- [ ] **Step 3 — empty-title branch**: extend `is_degenerate_title` (`classifier.py`) to also return True for an empty/whitespace-only title (the DESIGN names "empty OR season token"), OR adjust the `scrape_tvshow` wiring to `if not title.strip() or is_degenerate_title(title):`. Add an AC-6 test for the empty case.
- [ ] **Step 4 — mutation check**: revert the recursive scan to `iterdir()` → the real-layout test FAILS; restore. Revert the last-token regex → the over-strip test FAILS; restore.
- [ ] **Step 5 — commit** `fix(match-guard): recursive episode scan + last-token strip so Orville recovery works on real Saison-subdir layout`

---

### Sub-phase 4.2 — De-vacuum AC-1 + add boundary/Prince-Andrew/recovery-branch tests

**Files:** `tests/scraper/test_confidence_match_guard.py`.

- [ ] **De-vacuum AC-1**: replace/augment the vacuous no-alias test with an **alias-amplification** test — a `SearchResult("Glina. Nowy rozdział", aliases=("Glina S03",))` and assert `_score_result(" S03", None, result) < LOW_CONFIDENCE`. Mutation-proof: removing the guard re-accepts it at ~0.90.
- [ ] **0.40 boundary**: one case at ratio just-below 0.40 (rejected) and one just-above (accepted), to pin the threshold value.
- [ ] **Prince Andrew**: add the floor case `_score_result("Prince Andrew", None, _sr("Andrew: The Problem Prince"))` ≥ LOW_CONFIDENCE (ratio 0.50, the case that set 0.40) into the match-guard suite.
- [ ] **Recovery branches**: non-degenerate skip (a normal title does NOT trigger recovery end-to-end), empty-recovery returns None, multi-file deterministic pick.
- [ ] Commit `test(match-guard): de-vacuum AC-1 (alias path) + boundary/Prince-Andrew/recovery-branch coverage`

---

### Sub-phase 4.3 — Doc/comment threshold sync

**Files:** `tests/scraper/test_confidence_match_guard.py`, `personalscraper/scraper/confidence.py`.

- [ ] Replace stale `0.67` references with `0.40` in test docstrings/assert messages and the inline `_score_result` guard comment so docs match the actual threshold. (Fold into 4.2's commit if trivial.)

---

### Sub-phase 4.4 — Phase gate

- [ ] `make check` green (ruff + mypy + full suite, 0 failed/errors). `command python -c "import personalscraper; print('ok')"`.
- [ ] Re-exercise: `command python -m pytest tests/scraper/test_confidence_match_guard.py tests/scraper/test_classifier_match_guard.py tests/scraper/ -q` + the real-layout recovery assertion.
