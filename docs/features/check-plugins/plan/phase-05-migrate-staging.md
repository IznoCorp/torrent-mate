# Phase 5 — Migrate STAGING (enforce coherence) Checks

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the three enforce coherence checks (`sort_process_coherence`, `nfo_ids` coherence-variant, `genre_coherence`) into `verify/checks/coherence.py` as STAGING-stage plugins. `enforce/coherence_checker.check_coherence` becomes a registry-driven loop with a `CoherenceResult` adapter at the boundary. The public `CoherenceResult` type and `check_coherence` signature are unchanged.

**Architecture:** `coherence.py` hosts three `@register_check` classes with `stages=frozenset({CheckStage.STAGING})`, all `default_severity=WARNING`, read-only (no `fix()`). `check_coherence` builds a `CheckContext(stage=STAGING, media_type=<bucket type>)` per item, loops `registry.checks_for(STAGING, mt)`, and maps the resulting `list[CheckResult]` to `CoherenceResult(path, checks=[r.name…], warnings=[r.message for failed…])`. The `(stage, name)` registry key keeps DISPATCH `nfo_ids` and STAGING `nfo_ids` independent (ACC-05).

**Tech Stack:** Python 3.11, `@register_check`, `CheckStage.STAGING`, `classify_from_nfo`, pytest

---

## ⚠️ PLAN CORRECTIONS (post-verification 2026-06-01)

- **GOLD-4**: the `coherence` golden is now captured in **Phase 0** (using a staging-layout corpus + a `Config` pointing `paths.staging_dir` at it — `check_coherence` iterates `config.paths.staging_dir`, so an arbitrary item corpus does NOT work). This phase **RE-ASSERTS** it after rewriting `check_coherence`; it does NOT capture for the first time. **Ignore sub-phase 5.2 Step 1's "capture the STAGING golden BEFORE rewriting" instruction** — that capture already happened in Phase 0.
- **CMP-4**: `SortProcessCoherence` uses `ctx.media_type` (the bucket-derived type), NOT `ctx.expected_file_type` (removed in Phase 1). The `coherence.py` code in sub-phase 5.1 already uses `ctx.media_type` — keep it.

---

## Gate (previous phase)

- `validate_from_index` is a registry loop over `IndexableCheck`; `pytest tests/verify/test_validate_from_index_registry.py -q` → pass.
- `pytest tests/verify/test_characterization_golden.py -q` → all pass.
- `pytest tests/verify tests/enforce -q` → all pass.

---

## Sub-phase 5.1 — `verify/checks/coherence.py` (3 STAGING plugins)

**Files:**

- Create: `personalscraper/verify/checks/coherence.py`
- Modify: `personalscraper/verify/checks/__init__.py` (import `coherence`)

Fidelity rules extracted verbatim from `enforce/coherence_checker.py`:

- `SortProcessCoherence` (`name="sort_process_coherence"`, movie+tvshow) — **always returns one result**.
  - movie: `passed = not (media_dir / "tvshow.nfo").exists()`; fail msg `"Wrong category: {dir} has tvshow.nfo but is in MOVIES"`.
  - tvshow: if `tvshow.nfo` exists → `passed=True`; else `passed = not <movie NFOs present>`, fail msg `"Wrong category: {dir} has movie NFO but is in TVSHOWS"`.
- `NfoIdsCoherence` (`name="nfo_ids"`, movie+tvshow, STAGING) — returns `[]` when **no NFO to inspect** (movie: no `glob_nfo_candidates`; tvshow: no `tvshow.nfo`); otherwise one result. Parse error → `passed=False`, `"Cannot parse NFO: {name}"`. Neither tmdb nor imdb → `passed=False`, `"Missing IDs: no TMDB or IMDB in {name}"`. Else `passed=True`.
- `GenreCoherence` (`name="genre_coherence"`, **tvshow only**) — returns `[]` unless `tvshow.nfo` exists; `classify_from_nfo` → `TV_PROGRAMS` → `passed=False`, `"Genre suggests TV program ({TV_PROGRAMS}) not series for {name}"`; classify error → `passed=False`, `"Genre check failed: {exc}"`; else `passed=True`.

```python
# personalscraper/verify/checks/coherence.py
"""STAGING-stage coherence checks (enforce). Read-only, WARNING-only."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from personalscraper.conf import ids as CID
from personalscraper.conf.classifier import classify_from_nfo
from personalscraper.logger import get_logger
from personalscraper.nfo_utils import glob_nfo_candidates
from personalscraper.verify.checks.base import CheckContext, CheckResult, CheckStage, Severity
from personalscraper.verify.checks.registry import register_check

log = get_logger("verify.checks.coherence")


@register_check
class SortProcessCoherence:
    name = "sort_process_coherence"
    group = "coherence"
    stages = frozenset({CheckStage.STAGING})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.WARNING
    description = "Media item is in a category coherent with its NFO type"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        if ctx.media_type == "movie":
            wrong = (ctx.media_dir / "tvshow.nfo").exists()
            msg = f"Wrong category: {ctx.media_dir.name} has tvshow.nfo but is in MOVIES" if wrong else ""
            return [CheckResult("sort_process_coherence", not wrong, Severity.WARNING, msg)]
        # tvshow
        if (ctx.media_dir / "tvshow.nfo").exists():
            return [CheckResult("sort_process_coherence", True, Severity.WARNING, "")]
        movie_nfos = [f for f in glob_nfo_candidates(ctx.media_dir) if f.name != "tvshow.nfo"]
        wrong = bool(movie_nfos)
        msg = f"Wrong category: {ctx.media_dir.name} has movie NFO but is in TVSHOWS" if wrong else ""
        return [CheckResult("sort_process_coherence", not wrong, Severity.WARNING, msg)]


@register_check
class NfoIdsCoherence:
    name = "nfo_ids"
    group = "coherence"
    stages = frozenset({CheckStage.STAGING})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.WARNING
    description = "NFO carries at least one external ID (TMDB or IMDB)"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        nfo_path = self._coherence_nfo(ctx)
        if nfo_path is None:
            return []  # nothing to inspect → name absent from CoherenceResult.checks (matches legacy)
        try:
            root = ET.parse(nfo_path).getroot()  # noqa: S314
        except (ET.ParseError, OSError):
            return [CheckResult("nfo_ids", False, Severity.WARNING, f"Cannot parse NFO: {nfo_path.name}")]
        has_tmdb = any(u.get("type") == "tmdb" and (u.text or "").strip() for u in root.findall("uniqueid"))
        has_imdb = any(u.get("type") == "imdb" and (u.text or "").strip() for u in root.findall("uniqueid"))
        ok = has_tmdb or has_imdb
        msg = "" if ok else f"Missing IDs: no TMDB or IMDB in {nfo_path.name}"
        return [CheckResult("nfo_ids", ok, Severity.WARNING, msg)]

    @staticmethod
    def _coherence_nfo(ctx: CheckContext):
        if ctx.media_type == "tvshow":
            p = ctx.media_dir / "tvshow.nfo"
            return p if p.exists() else None
        nfos = glob_nfo_candidates(ctx.media_dir)
        return nfos[0] if nfos else None


@register_check
class GenreCoherence:
    name = "genre_coherence"
    group = "coherence"
    stages = frozenset({CheckStage.STAGING})
    media_types = frozenset({"tvshow"})
    default_severity = Severity.WARNING
    description = "TV show genre does not imply a different category"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        nfo_path = ctx.media_dir / "tvshow.nfo"
        if not nfo_path.exists():
            return []
        try:
            category_id, _ = classify_from_nfo(ctx.config, nfo_path, media_type="tvshow")
        except (ET.ParseError, OSError, ValueError) as exc:
            log.warning("coherence_genre_check_failed", nfo=nfo_path.name, error=str(exc))
            return [CheckResult("genre_coherence", False, Severity.WARNING, f"Genre check failed: {exc}")]
        if category_id == CID.TV_PROGRAMS:
            msg = f"Genre suggests TV program ({CID.TV_PROGRAMS}) not series for {ctx.media_dir.name}"
            return [CheckResult("genre_coherence", False, Severity.WARNING, msg)]
        return [CheckResult("genre_coherence", True, Severity.WARNING, "")]
```

- [ ] **Step 1: Write per-plugin tests** (`tests/verify/checks/test_coherence.py`) — wrong-category movie/tvshow, nfo_ids `[]` on no-NFO, genre→TV_PROGRAMS warning.
- [ ] **Step 2: Implement `coherence.py`; add `coherence` to `checks/__init__.py` imports.**
- [ ] **Step 3: Run `pytest tests/verify/checks/test_coherence.py -q` → pass.**
- [ ] **Step 4: Commit** — `feat(check-plugins): add STAGING coherence check plugins`.

---

## Sub-phase 5.2 — `check_coherence` becomes a registry loop + CoherenceResult adapter

**Files:**

- Modify: `personalscraper/enforce/coherence_checker.py` (`check_coherence`; keep `CoherenceResult`)

- [ ] **Step 1: Capture the STAGING golden** (extend `capture_golden.py` + `test_characterization_golden.py` for `check_coherence`) BEFORE rewriting — the corpus already has wrong-category + genre fixtures; if not, add `tvshow.nfo`-in-MOVIES and movie-NFO-in-TVSHOWS items. Run the capture once on the _pre-rewrite_ `check_coherence`, commit `coherence.json`.

- [ ] **Step 2: Rewrite `check_coherence`** — keep the iteration over `movies_dir` / `tvshows_dir`; per item build the context and adapt:

```python
from personalscraper.verify.checks.base import CheckContext, CheckStage
from personalscraper.verify.checks.registry import registry
import personalscraper.verify.checks  # trigger registration

def _coherence_for(media_dir, media_type, config) -> CoherenceResult:
    # media_type is the bucket the item was found under (movie for 001-MOVIES,
    # tvshow for 002-TVSHOWS); the wrong-category check compares NFO type vs it.
    ctx = CheckContext(media_dir=media_dir, media_type=media_type,
                       stage=CheckStage.STAGING, config=config, patterns=PATTERNS)
    results = [r for check in registry.checks_for(CheckStage.STAGING, media_type) for r in check.run(ctx)]
    return CoherenceResult(
        path=media_dir,
        checks=[r.name for r in results],
        warnings=[r.message for r in results if not r.passed and r.message],
    )
```

The per-media-type order is governed by the `_ORDER` table (`STAGING/movie = [sort_process_coherence, nfo_ids]`, `STAGING/tvshow = [nfo_ids, genre_coherence, sort_process_coherence]`) → reproduces the legacy `checks` list order. Remove `_check_movie`, `_check_tvshow`, `_check_nfo_ids`, `_check_genre_coherence` (now in plugins).

- [ ] **Step 3: Run the STAGING golden + existing coherence suite.**

```bash
pytest tests/verify/test_characterization_golden.py -q   # ACC-01 (now incl. coherence.json)
pytest tests/enforce/test_coherence_checker.py -q        # ACC-02 — must stay green
```

- [ ] **Step 4: ACC-05 — (stage, name) collision resolved**

```bash
python -c "from personalscraper.verify.checks.registry import registry; from personalscraper.verify.checks.base import CheckStage as S; print(registry.get(S.DISPATCH,'nfo_ids') is not registry.get(S.STAGING,'nfo_ids'))"
# Expected: True
```

- [ ] **Step 5: Commit** — `refactor(check-plugins): check_coherence becomes a registry loop with CoherenceResult adapter`.

---

## Phase Gate

```bash
make lint && make test && make check
pytest tests/verify/test_characterization_golden.py -q   # ACC-01 (incl. coherence)
pytest tests/verify tests/enforce -q                      # ACC-02
python3 scripts/check-module-size.py                      # ACC-07
python -c "import personalscraper"
```

Expected: all green. Both stages now flow through the single registry; `coherence_checker.py` shrinks to the iteration + adapter.
