# match-guard — Phase 1: Directional Length-Ratio Guard (Unit 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing `FuzzyMatchConfig.min_length_ratio` (0.67) into `_score_result` in a DIRECTIONAL way: only reject a candidate when the **query** title is much shorter than the `api_title` (not the reverse), so that legit long-local-title → short-api-title matches (`"The Hack sur ecoute"` → `"The Hack"`) are preserved.

**Architecture:** Add a private `_length_ratio_guard` function in `personalscraper/scraper/confidence.py` that computes `len(query) / len(api_title)` after `media_processor` normalization and returns `True` when the query is shorter than `min_length_ratio * len(api_title)`. Call it inside the `for api_title in titles:` loop in `_score_result` to short-circuit scoring for that candidate title. The check is purely additive — no existing logic is removed.

**Tech Stack:** Python 3.12, rapidfuzz, `personalscraper.text_utils.media_processor`, `personalscraper.conf.models.fuzzy.FuzzyMatchConfig`, pytest.

---

## File map

- Modify: `personalscraper/scraper/confidence.py` — add `_length_ratio_guard` helper (~10 lines), call it inside `_score_result` loop (lines 249-254 currently)
- Test: `tests/scraper/test_confidence_match_guard.py` — new file covering AC-1, AC-3, AC-4, AC-5

---

## Task 1: Write the failing tests (AC-1, AC-3, AC-4, AC-5)

**Files:**

- Create: `tests/scraper/test_confidence_match_guard.py`

- [ ] **Step 1.1: Create the test file with failing tests**

```python
"""Regression tests for the directional length-ratio guard in confidence._score_result.

AC-1: query "S03" does NOT accept "Glina. Nowy rozdział" (ratio 0.150 < 0.67).
AC-3: query "Among" does NOT accept "Love Amongst War" (ratio 0.312 < 0.67).
AC-4: "The Hack sur ecoute" still matches "The Hack" (local-longer direction — guard must NOT fire).
      "Top Chef France" still matches "Top Chef" (local-longer direction — guard must NOT fire).
AC-5: "FROM" → "FROM" at 1.0 is unaffected.
"""

import pytest

from personalscraper.api.metadata._base import SearchResult
from personalscraper.scraper.confidence import HIGH_CONFIDENCE, LOW_CONFIDENCE, _score_result


def _sr(title: str, year: int | None = None, aliases: list[str] | None = None) -> SearchResult:
    """Build a minimal SearchResult for scoring tests."""
    return SearchResult(
        provider="tvdb",
        provider_id="999",
        title=title,
        original_title=title,
        year=year,
        media_type="tvshow",
        aliases=aliases or [],
    )


# ---------------------------------------------------------------------------
# AC-1 — Orville / S03 suppression
# ---------------------------------------------------------------------------


class TestAC1OrvelleSuppression:
    """AC-1: query 'S03' must NOT match 'Glina. Nowy rozdział' despite alias amplification."""

    def test_season_token_rejects_glina_title(self) -> None:
        """_score_result(' S03', None, Glina result) < LOW_CONFIDENCE."""
        result = _sr("Glina. Nowy rozdział", 2025, aliases=["Glina S03"])
        score = _score_result(" S03", None, result)
        assert score < LOW_CONFIDENCE, (
            f"Guard failed: score={score:.3f} — 'S03' matched 'Glina. Nowy rozdział'; "
            "removing the directional guard must be the only way to fix this"
        )

    def test_season_token_normalized_rejects_glina(self) -> None:
        """_score_result('S03', None, Glina result) < LOW_CONFIDENCE (no leading space)."""
        result = _sr("Glina. Nowy rozdział", 2025)
        score = _score_result("S03", None, result)
        assert score < LOW_CONFIDENCE, (
            f"Guard failed: score={score:.3f} for 'S03' vs 'Glina. Nowy rozdział'"
        )


# ---------------------------------------------------------------------------
# AC-3 — Among Us / "Among" suppression
# ---------------------------------------------------------------------------


class TestAC3AmongUsSuppression:
    """AC-3: query 'Among' must NOT match 'Love Amongst War' (ratio 0.312 < 0.67)."""

    def test_among_rejects_love_amongst_war(self) -> None:
        """_score_result('Among', None, 'Love Amongst War') < LOW_CONFIDENCE."""
        result = _sr("Love Amongst War", 2012)
        score = _score_result("Among", None, result)
        assert score < LOW_CONFIDENCE, (
            f"Guard failed: score={score:.3f} — 'Among' matched 'Love Amongst War'; "
            "length ratio is 0.312, well below 0.67"
        )


# ---------------------------------------------------------------------------
# AC-4 — Directional: local-longer must NOT be rejected
# ---------------------------------------------------------------------------


class TestAC4DirectionalPreservation:
    """AC-4: guard must NOT fire when local title is longer than API title."""

    def test_the_hack_sur_ecoute_matches_the_hack(self) -> None:
        """'The Hack sur ecoute' (local-longer) must still match 'The Hack'."""
        result = _sr("The Hack", None)
        score = _score_result("The Hack sur ecoute", None, result)
        # Score may be lower than HIGH_CONFIDENCE (subtitle adds distance),
        # but guard must not reject it entirely — score must be > LOW_CONFIDENCE
        # to prove the guard did not fire on the local-longer direction.
        assert score > LOW_CONFIDENCE, (
            f"Guard incorrectly fired on local-longer match: score={score:.3f} "
            "for 'The Hack sur ecoute' → 'The Hack'"
        )

    def test_top_chef_france_matches_top_chef(self) -> None:
        """'Top Chef France' (local-longer) must still score against 'Top Chef'."""
        result = _sr("Top Chef", None)
        score = _score_result("Top Chef France", None, result)
        assert score > LOW_CONFIDENCE, (
            f"Guard incorrectly fired on local-longer match: score={score:.3f} "
            "for 'Top Chef France' → 'Top Chef'"
        )


# ---------------------------------------------------------------------------
# AC-5 — Exact / short legit titles unaffected
# ---------------------------------------------------------------------------


class TestAC5ExactShortTitlesUnaffected:
    """AC-5: 'FROM' → 'FROM' at 1.0 must be unaffected by any guard."""

    def test_from_matches_from_at_full_score(self) -> None:
        """_score_result('FROM', None, 'FROM') must be >= HIGH_CONFIDENCE."""
        result = _sr("FROM", None)
        score = _score_result("FROM", None, result)
        assert score >= HIGH_CONFIDENCE, (
            f"Legit short exact match broken: score={score:.3f} for 'FROM' → 'FROM'"
        )
```

- [ ] **Step 1.2: Run to confirm ALL tests fail (guard not yet implemented)**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py -v 2>&1 | tail -20
```

Expected: 6 FAILs — `test_season_token_rejects_glina_title`, `test_season_token_normalized_rejects_glina`, `test_among_rejects_love_amongst_war` fail (score is too high); `test_from_matches_from_at_full_score` likely passes already (exact match). The From/The Hack/Top Chef tests may also pass already — what matters is that at least AC-1 and AC-3 tests FAIL (score >= LOW_CONFIDENCE without the guard).

---

## Task 2: Implement the directional length-ratio guard in `_score_result`

**Files:**

- Modify: `personalscraper/scraper/confidence.py`

- [ ] **Step 2.1: Read the current `_score_result` function and the imports block**

Read `personalscraper/scraper/confidence.py` lines 1-32 (imports) and lines 210-260 (`_score_result`).

- [ ] **Step 2.2: Add the `_length_ratio_guard` helper and wire it into `_score_result`**

After line 207 (end of `_superstring_penalty`) and before line 210 (start of `_score_result`), insert the `_length_ratio_guard` helper:

```python
_DEFAULT_MIN_LENGTH_RATIO: float = 0.67  # mirrors FuzzyMatchConfig.min_length_ratio


def _length_ratio_guard(query: str, api_title: str, min_ratio: float = _DEFAULT_MIN_LENGTH_RATIO) -> bool:
    """Return True when the query is too short relative to ``api_title``.

    Implements a DIRECTIONAL guard: only fires when the query title is much
    shorter than the API candidate title (the query-too-short direction).
    It must NOT fire when the local title is longer than the API title —
    that direction covers legit subtitle expansions like
    ``"The Hack sur ecoute"`` → ``"The Hack"`` or
    ``"Top Chef France"`` → ``"Top Chef"``.

    Uses ``media_processor`` (accent-stripping + lowercase) to normalise
    both strings before length comparison, matching the pre-processing done
    inside ``score_match``.

    Args:
        query: Local title extracted from the folder name.
        api_title: Candidate title from the API result (title, original_title, or alias).
        min_ratio: Minimum ``len(query) / len(api_title)`` ratio below which
            the candidate is rejected. Default 0.67 (matches FuzzyMatchConfig default).

    Returns:
        True if the guard fires (candidate should be rejected), False otherwise.
    """
    norm_query = media_processor(query)
    norm_api = media_processor(api_title)
    if not norm_query or not norm_api:
        # Empty after processing — cannot judge; don't reject
        return False
    # Directional: only reject when query is shorter than api_title
    if len(norm_query) >= len(norm_api):
        return False
    ratio = len(norm_query) / len(norm_api)
    return ratio < min_ratio
```

Then modify the `_score_result` loop (currently lines 249-254) to call the guard:

Replace the `for api_title in titles:` loop body:

```python
    best = -1.0
    for api_title in titles:
        # Directional length-ratio guard: skip this candidate title when the
        # query is much shorter than api_title (e.g. "S03" vs "Glina. Nowy
        # rozdział", ratio 0.150).  The guard is NOT applied when the local
        # title is longer — that direction is legit (subtitle expansions).
        if _length_ratio_guard(local_title, api_title):
            continue
        scored = score_match(local_title, local_year, api_title, result.year) + _superstring_penalty(
            local_title, api_title
        )
        best = max(best, scored)
    return max(0.0, best)
```

The full modified `_score_result` function body (replace lines 244-255):

```python
    titles = [result.title]
    if result.original_title and result.original_title != result.title:
        titles.append(result.original_title)
    titles.extend(alias for alias in result.aliases if alias and alias not in titles)
    best = -1.0
    for api_title in titles:
        # Directional length-ratio guard: skip this candidate title when the
        # query is much shorter than api_title (e.g. "S03" vs "Glina. Nowy
        # rozdział", ratio 0.150).  The guard is NOT applied when the local
        # title is longer — that direction is legit (subtitle expansions).
        if _length_ratio_guard(local_title, api_title):
            continue
        scored = score_match(local_title, local_year, api_title, result.year) + _superstring_penalty(
            local_title, api_title
        )
        best = max(best, scored)
    return max(0.0, best)
```

- [ ] **Step 2.3: Run the new tests — all must PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py -v 2>&1 | tail -20
```

Expected: 6 PASSes.

- [ ] **Step 2.4: Run the existing confidence test suite — must stay green**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence.py tests/scraper/test_confidence_tvdb_method_name.py -v 2>&1 | tail -25
```

Expected: all PASS, 0 failed.

- [ ] **Step 2.5: Quick ruff + mypy pass on changed files**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m ruff check personalscraper/scraper/confidence.py tests/scraper/test_confidence_match_guard.py && command python -m mypy personalscraper/scraper/confidence.py --ignore-missing-imports 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 2.6: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/scraper/confidence.py tests/scraper/test_confidence_match_guard.py && git commit -m "$(cat <<'EOF'
feat(match-guard): directional length-ratio guard in _score_result

Adds _length_ratio_guard helper that fires only when query title is
much shorter than the API candidate title (query-too-short direction).
Wired into _score_result's alias loop so degenerate tokens like "S03"
and "Among" can no longer be amplified above LOW_CONFIDENCE by aliases.
Local-longer direction ("The Hack sur ecoute" → "The Hack") unaffected.

Tests: AC-1 (Glina rejection), AC-3 (Love Amongst War rejection),
AC-4 (The Hack / Top Chef France preserved), AC-5 (FROM exact unaffected).
EOF
)"
```

---

## Mutation-proof note

The tests in Task 1 are mutation-proof because:

- AC-1 and AC-3 tests assert `score < LOW_CONFIDENCE`. Removing `_length_ratio_guard` (or inverting its direction check) causes those assertions to fail because `WRatio("S03", "Glina S03") = 0.90` and `WRatio("Among", "Love Amongst War") = 0.90` — both well above `LOW_CONFIDENCE`.
- AC-4 tests assert `score > LOW_CONFIDENCE` for the local-longer direction. Making the guard bidirectional (i.e., firing for both directions) would break these assertions.
