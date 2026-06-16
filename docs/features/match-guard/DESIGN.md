# Design — Scraper match guard for degenerate/truncated titles

**Codename**: match-guard
**Type**: bugfix (0.34.0 → 0.34.1)
**Origin**: caught live in a pipeline-monitor dry-run (run 2026-06-16-18h28); root cause adversarially verified (study `tasks/wgnfxw5l9.output`, 14 agents).

## Problem

The TV scraper produces **confidently-wrong matches** when a degenerate/truncated show-folder title reaches the TVDB matcher. Two confirmed cases:

1. **The Orville S3** — torrent named `Saison 3` (no show title) → SORT folder ` S03` → scraper queries TVDB with `"S03"` → matches **`Glina. Nowy rozdział`** (Polish, 2025) @ **0.82** → would rename The Orville to the Polish show + wrong NFO/artwork.
2. **Among Us S1** — `Among.Us.S01` → guessit strips `Us` as ISO country `US` → SORT folder `Among` → scraper queries `"Among"` → matches **`Love Amongst War`** (2012) @ **0.90**.

A wrong match is worse than no match: it silently writes wrong metadata and can dispatch to the wrong library folder.

## Root cause (verified)

The scraper confidence path — `personalscraper/scraper/confidence.py` `score_match` (117-124) and `_score_result` (245-255) — applies **no query length-ratio guard**. `text_utils.fuzzy_match_score` (`personalscraper/text_utils.py:147-165`) already implements exactly that guard (`FuzzyMatchConfig.min_length_ratio = 0.67`, `conf/models/fuzzy.py:27`) but it is **not wired into the scraper confidence path**.

Consequently a short/degenerate query is scored only by `WRatio`, which a substring or a season-token alias amplifies above `HIGH_CONFIDENCE` (0.8):

- `WRatio(" S03", "Glina. Nowy rozdział") = 0.0`, but `_score_result` aggregates aliases and takes the best — `WRatio(" S03", "Glina S03") = 0.90` rescues the wrong show.
- `WRatio("Among", "Love Amongst War") = 0.90` (substring `among` ⊂ `amongst`); length ratio 0.312, far below 0.67.
- The season-veto (`confidence.py:580`) only engages with ≥2 viable candidates, so a single alias-amplified candidate passes.

## Design (two complementary units)

### Unit 1 — Directional length-ratio guard in the confidence path

Wire the existing `min_length_ratio` (0.67) into `_score_result` / `score_match`: when scoring a candidate, if the **query** title is much shorter than the `api_title` (the _query-too-short_ direction only), reject that candidate (it cannot become the accepted match → item falls to `skipped_low_confidence`).

- **Where**: `personalscraper/scraper/confidence.py` `_score_result` loop (≈245-255) and/or `score_match` (≈117-124).
- **Directional is mandatory**: the guard must fire ONLY when `len(query) << len(api_title)`. It must NOT fire when the local title is _longer_ than the api title — otherwise it breaks legit matches where the staging title carries an extra subtitle (`"The Hack sur ecoute"` → `"The Hack"`, ratio 0.421; `"Top Chef France"` → `"Top Chef"`, ratio 0.533).
- **Effect**: rejects Orville (`"S03"` vs `"Glina…"`, ratio 0.150) and Among Us (`"Among"` vs `"Love Amongst War"`, ratio 0.312).

### Unit 2 — Episode-filename fallback for degenerate show titles

At the scraper entry point, when the parsed show title is empty or matches `^\s*S\d+(E\d+)?$` (a pure season token), re-derive the show title from the first episode filename via guessit, before querying the provider.

- **Where**: `personalscraper/scraper/classifier.py:103-105` (`_parse_folder_name`) or `personalscraper/scraper/tv_service.py:110` (after `title, year = _parse_folder_name(show_dir.name)`).
- **Verified recovery**: guessit(`"The Orville - S3E01.mkv"`) → `"The Orville S03E01"` → strip `Sxx[Eyy]` → `"The Orville"` → correct TVDB match.
- **Regex safety (verified)**: `^\s*S\d+(E\d+)?$` matches ` S03`, `S3`, `S01E01` but NOT `FROM`, `The Hack`, `Among`, `Top Chef France`, nor adversarial S-titles `S.W.A.T.`, `S Club 7`, `S-Town`, `S4C`, `Sense8`. Legit titles never enter the fallback.

### Combined effect

- **The Orville → auto-fixed** (Unit 2 recovers "The Orville"; Unit 1 also suppresses the Polish false-positive).
- **Among Us → wrong-match suppressed** (Unit 1 rejects "Love Amongst War") but **NOT auto-recovered**: "Among" is not a season token (Unit 2 does not trigger) and guessit re-strips `Us`→`US` on the episode files too, so no automatic recovery is possible. The item falls to `skipped_low_confidence` / unmatched → blocks at VERIFY (safe, no corruption) → operator renames `Among`→`Among Us`.

## Non-goals (explicitly out of scope — verified to break legit matches)

- **Do NOT touch guessit country detection** (`sorter/cleaner.py`). Distinguishing "Us" the country from "Us" the title word is structurally undecidable; any heuristic breaks other titles (verified `breaks-legit-matches`).
- **Do NOT add a blanket adaptive confidence floor** at the acceptance gate (`tv_service.py:463`): a 0.95 floor on short queries newly rejects legit short titles that match via localized/alias titles (verified `breaks-legit-matches`).
- Among Us auto-recovery is **not** in scope (undecidable). The fix only guarantees no corruption.

## Acceptance (executable — regression tests)

All tests live under `tests/` and run in `make check`. Each must be mutation-proof.

- **AC-1** (Orville suppression): with show folder ` S03` (or title `"S03"`), the matcher does NOT accept `Glina. Nowy rozdział` (length-ratio guard rejects it). Reproduces the bug; mutation = removing the guard re-accepts it.
- **AC-2** (Orville recovery): with episode files `The Orville - S3E0x.mkv` under a season-token folder, the scraper queries `"The Orville"` and matches the correct TVDB show.
- **AC-3** (Among Us suppression): query `"Among"` does NOT accept `Love Amongst War` (ratio 0.312 < 0.67); item → `skipped_low_confidence`.
- **AC-4** (legit preserved — directional): `"The Hack sur ecoute"` still matches `"The Hack"` (local-longer, ratio 0.421, guard does NOT fire); `"Top Chef France"` still matches `"Top Chef"` (ratio 0.533).
- **AC-5** (legit preserved — exact/short): `"FROM"` → `"FROM"` @1.0 unaffected.
- **AC-6** (regex guard scoping): `degenerate?` helper returns True for ` S03`/`S3`/`S01E01`, False for `FROM`/`The Hack`/`Among`/`Top Chef France`/`S.W.A.T.`/`Sense8`.
- **AC-7**: `make check` green (ruff + mypy + full suite, 0 failed/errors).

## SemVer

bugfix → Z+1: **0.34.0 → 0.34.1**, branch `fix/match-guard`.
