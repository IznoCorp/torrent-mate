# Phase 2 — Migrate DISPATCH Checks

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract every DISPATCH check from `verify/checker.py` into per-group plugin modules under `verify/checks/`. `MediaChecker.check_movie` and `check_tvshow` become thin registry-driven loops with unchanged public signatures. Prove no behavior change by re-asserting the Phase 0 characterization golden.

**Architecture:** 9 plugin modules (`nfo.py`, `artwork.py`, `naming.py`, `structure.py`, `streams.py`, `dedup.py`, `ntfs.py`, `category.py`, `provider_ids.py`). `checks/__init__.py` imports all modules to trigger registration. `MediaChecker` loops `registry.checks_for(DISPATCH, mt)`. Signatures of `check_movie` / `check_tvshow` are unchanged.

**Tech Stack:** Python 3.11, `@register_check` decorator, `CheckContext`, pytest

---

## ⚠️ PLAN CORRECTIONS (post-verification 2026-06-01)

- **MOVE-1 (NEW sub-phase 2.0, run FIRST)**: before migrating any check, MOVE `Severity`/`CheckResult` from `checker.py` to `base.py`, DELETE checker.py's own definitions, and repoint every importer (`verifier.py`, `library_checks.py`, `fixer.py`, and all `tests/` that do `from personalscraper.verify.checker import … Severity|CheckResult`). Add the residual grep `rg -t py 'from personalscraper\.verify\.checker import.*\b(Severity|CheckResult)\b' personalscraper/ tests/` → rc=1 to THIS phase's gate (ACC-06b applies from Phase 2, not just Phase 3).
- **CMP-3**: the `Category` plugin's `run()` must SET `ctx.resolved_category` to the resolved category id (so Phase 3's `_classify` can read it instead of re-running `classify_from_nfo`).
- **GOLD**: this phase's gate must assert the `checker_movie` + `checker_tvshow` golden via real equality (sub-phase 2.2 already does this — keep it).

---

## Gate (previous phase)

- `personalscraper/verify/checks/base.py`, `registry.py`, `catalog.py` exist and tests pass.
- `pytest tests/verify/checks/test_registry.py tests/verify/checks/test_base.py -q` → all pass.

---

## Sub-phase 2.1 — Plugin modules (groups: nfo, artwork, naming, structure, streams, dedup, ntfs, category, provider_ids)

**Files:**

- Create: `personalscraper/verify/checks/nfo.py`
- Create: `personalscraper/verify/checks/artwork.py`
- Create: `personalscraper/verify/checks/naming.py`
- Create: `personalscraper/verify/checks/structure.py`
- Create: `personalscraper/verify/checks/streams.py`
- Create: `personalscraper/verify/checks/dedup.py`
- Create: `personalscraper/verify/checks/ntfs.py`
- Create: `personalscraper/verify/checks/category.py`
- Create: `personalscraper/verify/checks/provider_ids.py`

Each plugin follows this pattern (example: `nfo.py`):

```python
# personalscraper/verify/checks/nfo.py
"""NFO presence, validity, and IDs checks (DISPATCH stage)."""
from __future__ import annotations
import xml.etree.ElementTree as ET
from personalscraper.verify.checks.base import (
    Check, CheckContext, CheckResult, CheckStage, Severity,
)
from personalscraper.verify.checks.registry import register_check


@register_check
class NfoPresent:
    """Check that the expected NFO file exists."""
    name = "nfo_present"
    group = "nfo"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "NFO file must be present"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        """Return [CheckResult] — passed=False if NFO absent."""
        nfo_path = ctx.nfo_path()
        exists = nfo_path is not None and nfo_path.exists()
        if ctx.media_type == "movie":
            from personalscraper.naming_patterns import NamingPatterns
            title = _extract_title(ctx.media_dir.name)
            nfo_name = ctx.patterns.format("movie_nfo", Title=title)
            nfo_path2 = ctx.media_dir / nfo_name
            exists = nfo_path2.exists()
            msg = f"NFO not found: {nfo_name}" if not exists else ""
        else:
            msg = "tvshow.nfo not found" if not exists else ""
        return [CheckResult(name="nfo_present", passed=exists, severity=Severity.ERROR, message=msg)]


@register_check
class NfoValid:
    """Check that the NFO has required fields (title + year for movies; title for TV)."""
    name = "nfo_valid"
    group = "nfo"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "NFO must contain required fields"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        """Return [] if NFO absent; [CheckResult] otherwise."""
        if ctx.nfo_root() is None and ctx.nfo_path() is not None and not ctx.nfo_path().exists():
            return []  # NFO absent — nfo_present handles that
        root = ctx.nfo_root()
        if root is None:
            return []
        if ctx.media_type == "movie":
            valid = bool(root.findtext("title")) and bool(root.findtext("year"))
            msg = "" if valid else "NFO missing <title> or <year>"
        else:
            valid = bool(root.findtext("title"))
            msg = "" if valid else "tvshow.nfo invalid or missing <title>"
        return [CheckResult(name="nfo_valid", passed=valid, severity=Severity.ERROR, message=msg)]


@register_check
class NfoIds:
    """Check NFO external IDs (dynamic severity — DISPATCH stage)."""
    name = "nfo_ids"
    group = "nfo"
    stages = frozenset({CheckStage.DISPATCH})
    media_types = frozenset({"movie", "tvshow"})
    default_severity = Severity.ERROR
    description = "NFO must contain required external IDs"

    def run(self, ctx: CheckContext) -> list[CheckResult]:
        """Return [] if nfo_root is None; severity dynamic for movies."""
        root = ctx.nfo_root()
        if root is None:
            return []
        ids = _extract_ids(root)
        if ctx.media_type == "movie":
            has_tmdb = bool(ids.get("tmdb"))
            has_imdb = bool(ids.get("imdb"))
            has_both = has_tmdb and has_imdb
            has_any = has_tmdb or has_imdb
            sev = Severity.ERROR if not has_any else Severity.WARNING
            msg = "" if has_both else f"Missing IDs: tmdb={has_tmdb}, imdb={has_imdb}"
            return [CheckResult(name="nfo_ids", passed=has_both, severity=sev, message=msg)]
        else:
            has_tvdb = bool(ids.get("tvdb")) or bool(ids.get("tmdb"))
            msg = "" if has_tvdb else "No TVDB or TMDB uniqueid"
            return [CheckResult(name="nfo_ids", passed=has_tvdb, severity=Severity.ERROR, message=msg)]


def _extract_ids(root: ET.Element) -> dict[str, str]:
    return {u.get("type", ""): u.text or "" for u in root.findall("uniqueid") if u.get("type") and u.text}


def _extract_title(dir_name: str) -> str:
    import re
    m = re.match(r"^(.+?)\s*\(\d{4}\)$", dir_name)
    return m.group(1).strip() if m else dir_name
```

> **Note:** The remaining 8 plugin files (`artwork.py`, `naming.py`, `structure.py`, `streams.py`, `dedup.py`, `ntfs.py`, `category.py`, `provider_ids.py`) follow the identical pattern — extract the corresponding methods from `checker.py` verbatim into `@register_check` classes. Fidelity notes from DESIGN §5 apply: `not_sample` is conditional on video presence, `nfo_valid`/`nfo_ids`/`category` return `[]` on missing NFO, `season_posters` emits N results or one `passed=True`, `episode_canonical_uniqueid_present` is a no-op when `canonical_family` is None.

- [ ] **Step 1: Write per-plugin failing tests**

```python
# tests/verify/checks/test_nfo.py
"""Unit tests for nfo.py check plugins."""
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from personalscraper.verify.checks.base import CheckContext, CheckStage, Severity
from personalscraper.verify.checks import nfo as nfo_mod


def _ctx(tmp_path, media_type="movie"):
    from personalscraper.naming_patterns import NamingPatterns
    d = tmp_path / ("Fight Club (1999)" if media_type == "movie" else "Fallout (2024)")
    d.mkdir(exist_ok=True)
    return CheckContext(
        media_dir=d, media_type=media_type, stage=CheckStage.DISPATCH,
        config=MagicMock(), patterns=NamingPatterns(),
    )


def test_nfo_present_missing(tmp_path):
    ctx = _ctx(tmp_path)
    results = nfo_mod.NfoPresent().run(ctx)
    assert len(results) == 1
    assert not results[0].passed
    assert results[0].severity == Severity.ERROR


def test_nfo_ids_dynamic_severity_movie(tmp_path):
    ctx = _ctx(tmp_path)
    d = ctx.media_dir
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Fight Club"
    ET.SubElement(root, "year").text = "1999"
    u = ET.SubElement(root, "uniqueid"); u.set("type", "tmdb"); u.text = "550"
    ET.ElementTree(root).write(d / "Fight Club.nfo", encoding="unicode")
    results = nfo_mod.NfoIds().run(ctx)
    assert len(results) == 1
    assert results[0].severity == Severity.WARNING  # only TMDB, no IMDB
    assert not results[0].passed
```

- [ ] **Step 2: Run tests — expect ImportError or FAIL**

```bash
pytest tests/verify/checks/test_nfo.py -q
```

Expected: ImportError or attribute error (plugins not yet written)

- [ ] **Step 3: Implement all 9 plugin files** (extract logic verbatim from `checker.py`)

Implement each file. Key fidelity rules:

- `naming.py` → `DirNaming` check; `fix()` stub (added in Phase 3)
- `structure.py` → `VideoPresent`, `NotSample`, `NoEmptyDirs`, `SeasonStructure`, `EpisodeRenamed`, `RootVideoFiles`
- `artwork.py` → `PosterPresent`, `ArtworkLandscape`, `SeasonPosters`
- `streams.py` → `Streamdetails`
- `dedup.py` → `NoDuplicateVideos`
- `ntfs.py` → `NtfsSafeNames`; `fix()` stub (added in Phase 3)
- `category.py` → `Category` (stashes `ctx.resolved_category`)
- `provider_ids.py` → `EpisodeNfo`, `EpisodeCanonicalUniqueidPresent`, `EpisodeXrefSecondaryIdPresent`, `EpisodeXrefImdbIdPresent`

- [ ] **Step 4: Update `checks/__init__.py` to import all plugin modules**

```python
# personalscraper/verify/checks/__init__.py
"""Check plugin package — importing this module registers all check plugins."""
from personalscraper.verify.checks import (  # noqa: F401
    nfo, artwork, naming, structure, streams, dedup, ntfs, category, provider_ids,
)
from personalscraper.verify.checks.registry import registry  # noqa: F401

__all__ = ["registry"]
```

- [ ] **Step 5: Run per-plugin tests**

```bash
pytest tests/verify/checks/ -q
```

Expected: all pass

- [ ] **Step 6: Commit plugin modules**

```bash
git add personalscraper/verify/checks/ tests/verify/checks/
git commit -m "feat(check-plugins): migrate all DISPATCH check plugins into verify/checks/"
```

---

## Sub-phase 2.2 — `MediaChecker` becomes a registry-driven loop

**Files:**

- Modify: `personalscraper/verify/checker.py` (shrink to facade loop; keep public signatures)

- [ ] **Step 1: Replace `check_movie` and `check_tvshow` bodies**

The new bodies import `registry` and `CheckContext` from `checks/`, build a context, and return `[r for check in registry.checks_for(DISPATCH, mt) for r in check.run(ctx)]`. Keep all private helpers (`_parse_nfo`, `_extract_ids`, etc.) until Phase 3 — plugins use their own copies for now.

```python
# In MediaChecker.check_movie (new body — signature unchanged):
from personalscraper.verify.checks import registry  # noqa: F811
from personalscraper.verify.checks.base import CheckContext, CheckStage

def check_movie(self, movie_dir: Path) -> list[CheckResult]:
    ctx = CheckContext(
        media_dir=movie_dir, media_type="movie",
        stage=CheckStage.DISPATCH, config=self.config, patterns=self.patterns,
    )
    import personalscraper.verify.checks  # trigger registration
    results = [r for check in registry.checks_for(CheckStage.DISPATCH, "movie") for r in check.run(ctx)]
    return results
```

Same pattern for `check_tvshow`.

- [ ] **Step 2: Expand `test_characterization_golden.py` to assert full equality**

After substituting `MediaChecker` loops, re-run the capture script is NOT needed. Instead, assert the current output matches the golden:

```python
def test_checker_movie_golden(self, tmp_path, test_config):
    from personalscraper.verify.checker import MediaChecker
    from personalscraper.naming_patterns import NamingPatterns
    from tests.verify.golden.conftest_golden import build_corpus
    checker = MediaChecker(NamingPatterns(), test_config)
    items = build_corpus(tmp_path / "corpus")
    golden = _load("checker_movie")
    for name, path in items.items():
        if name.startswith("movie_"):
            actual = _serializable(checker.check_movie(path))
            assert actual == golden[name], f"Golden mismatch for {name}"
```

- [ ] **Step 3: Run characterization golden — must be green**

```bash
pytest tests/verify/test_characterization_golden.py -q
```

Expected: all pass (behavior unchanged)

- [ ] **Step 4: Run full existing verify suite**

```bash
pytest tests/verify tests/enforce -q
```

Expected: all pass (ACC-02)

- [ ] **Step 5: Commit**

```bash
git add personalscraper/verify/checker.py tests/verify/test_characterization_golden.py
git commit -m "refactor(check-plugins): MediaChecker.check_movie/check_tvshow become registry-driven loops"
```

---

## Phase Gate

```bash
make lint && make test && make check
pytest tests/verify/test_characterization_golden.py -q   # ACC-01: golden green
pytest tests/verify tests/enforce -q                      # ACC-02: existing suites green
python3 scripts/check-module-size.py                      # ACC-07: all modules << 800 LOC
python -c "import personalscraper"
```

Expected: all green. `checker.py` shrinks; 9 plugin files created; golden asserted.
