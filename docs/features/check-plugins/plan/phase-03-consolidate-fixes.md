# Phase 3 — Consolidate Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Co-locate `fix()` methods on `dir_naming`, `no_empty_dirs`, and `ntfs_safe_names` plugins. Delete `MediaFixer`. Wire `validate_library` to use `apply_fixes()`. Preserve the fix-policy asymmetry (verify = `{"dir_naming"}`, library = `{"dir_naming","no_empty_dirs","ntfs_safe_names"}`). Prove with residual-import grep = 0.

**Architecture:** Each fixable plugin gains a `fix(ctx)` method extracted verbatim from `fixer.py` / `library_checks.py`. `fixer.py` shrinks to a compatibility shim then is deleted. `library_checks.py` replaces the three manual fix blocks with `apply_fixes()`. `Verifier` replaces `MediaFixer` calls with `apply_fixes(ctx, failed, policy={"dir_naming"})`.

**Tech Stack:** Python 3.11, `FixableCheck` protocol, `apply_fixes()`, pytest

---

## ⚠️ Post-verification corrections (2026-06-01) — reflected in this phase's steps

- **GND-8/CMP-7**: `Verifier.__init__` currently stores only `self._config`, `self._checker`, `self._fixer` — NOT `self._patterns`. Add `self._patterns = patterns` in `__init__` so the `CheckContext(..., patterns=self._patterns)` build in the rewrite works.
- **CMP-3**: `_classify` gains a `ctx` parameter and reads `ctx.resolved_category` (falling back to `classify_from_nfo` only when `None`) — this wires the dual-purpose `category` optimization the DESIGN promises. Add a test pinning the single-`classify_from_nfo`-call behavior.
- **GOLD (critical)**: this phase rewrites `Verifier.verify_movie/verify_tvshow` AND `validate_library` → its gate MUST assert real-equality on the `verifier_movie`, `verifier_tvshow`, and `library_validate` goldens (all captured in Phase 0): `pytest tests/verify/test_characterization_golden.py -q`.

---

## Gate (previous phase)

- `pytest tests/verify/test_characterization_golden.py -q` → all pass.
- `pytest tests/verify tests/enforce -q` → all pass.
- All DISPATCH plugin modules exist in `verify/checks/`.

---

## Sub-phase 3.1 — Add `fix()` to `dir_naming`, `no_empty_dirs`, `ntfs_safe_names`

**Files:**

- Modify: `personalscraper/verify/checks/naming.py` (add `fix()` to `DirNaming`)
- Modify: `personalscraper/verify/checks/structure.py` (add `fix()` to `NoEmptyDirs`)
- Modify: `personalscraper/verify/checks/ntfs.py` (add `fix()` to `NtfsSafeNames`)

- [ ] **Step 1: Write failing fix tests**

```python
# tests/verify/checks/test_fixes.py
"""Unit tests for fix() methods on DirNaming, NoEmptyDirs, NtfsSafeNames."""
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from personalscraper.verify.checks.base import CheckContext, CheckStage
from personalscraper.naming_patterns import NamingPatterns


def _ctx(media_dir: Path, media_type: str = "movie", dry_run: bool = False) -> CheckContext:
    return CheckContext(
        media_dir=media_dir, media_type=media_type, stage=CheckStage.DISPATCH,
        config=MagicMock(), patterns=NamingPatterns(), dry_run=dry_run,
    )


def test_dir_naming_fix_renames_from_nfo(tmp_path):
    from personalscraper.verify.checks.naming import DirNaming
    d = tmp_path / "Bad Name"
    d.mkdir()
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Good Movie"
    ET.SubElement(root, "year").text = "2000"
    ET.ElementTree(root).write(d / "Good Movie.nfo", encoding="unicode")
    ctx = _ctx(d)
    actions = DirNaming().fix(ctx)
    assert len(actions) == 1
    assert actions[0].new_path == tmp_path / "Good Movie (2000)"
    assert (tmp_path / "Good Movie (2000)").exists()


def test_dir_naming_fix_dry_run_no_rename(tmp_path):
    from personalscraper.verify.checks.naming import DirNaming
    d = tmp_path / "Bad Name"
    d.mkdir()
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "Good Movie"
    ET.SubElement(root, "year").text = "2000"
    ET.ElementTree(root).write(d / "Good Movie.nfo", encoding="unicode")
    ctx = _ctx(d, dry_run=True)
    actions = DirNaming().fix(ctx)
    assert len(actions) == 1
    assert not (tmp_path / "Good Movie (2000)").exists()  # dry run: no actual rename


def test_no_empty_dirs_fix_removes_empty(tmp_path):
    from personalscraper.verify.checks.structure import NoEmptyDirs
    d = tmp_path / "Movie (2020)"
    d.mkdir()
    empty = d / "Extras"
    empty.mkdir()
    ctx = _ctx(d)
    actions = NoEmptyDirs().fix(ctx)
    assert not empty.exists()
    assert len(actions) >= 1


def test_ntfs_safe_names_fix_renames_illegal(tmp_path):
    from personalscraper.verify.checks.ntfs import NtfsSafeNames
    d = tmp_path / "Movie (2020)"
    d.mkdir()
    bad = d / "file:bad.srt"
    bad.write_bytes(b"1\n")
    ctx = _ctx(d)
    actions = NtfsSafeNames().fix(ctx)
    assert not bad.exists()
    assert len(actions) == 1
```

- [ ] **Step 2: Run tests — expect FAIL (fix() not yet implemented)**

```bash
pytest tests/verify/checks/test_fixes.py -q
```

Expected: `AttributeError: 'DirNaming' object has no attribute 'fix'`

- [ ] **Step 3: Add `fix()` to `DirNaming` in `naming.py`**

Extract `_fix_dir_naming_from_nfo` logic from `fixer.py` verbatim:

```python
# In naming.py — DirNaming class, add after run():
def fix(self, ctx: CheckContext) -> list[FixAction]:
    """Rename directory using title + year from NFO.

    Args:
        ctx: CheckContext (ctx.dry_run controls whether rename is applied).

    Returns:
        List of FixAction (0 or 1 entries).
    """
    from personalscraper.verify.checks.base import FixAction
    from personalscraper.nfo_utils import glob_nfo_candidates
    import xml.etree.ElementTree as ET
    from personalscraper.logger import get_logger
    log = get_logger("verify.checks.naming")

    if ctx.media_type == "movie":
        nfo_files = glob_nfo_candidates(ctx.media_dir)
    else:
        nfo_files = [ctx.media_dir / "tvshow.nfo"]

    nfo_path = next((f for f in nfo_files if f.exists()), None)
    if not nfo_path:
        return []
    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        root = tree.getroot()
    except (ET.ParseError, OSError) as exc:
        log.warning("dir_naming_fix_nfo_parse_error", nfo=nfo_path.name, error=str(exc))
        return []

    title = (root.findtext("title") or "").strip()
    year = (root.findtext("year") or "").strip()
    if not title:
        return []
    canonical = f"{title} ({year})" if year else title
    if ctx.media_dir.name == canonical:
        return []
    new_dir = ctx.media_dir.parent / canonical
    if new_dir.exists():
        log.warning("dir_naming_fix_target_exists", canonical=canonical)
        return []
    description = f"Renamed '{ctx.media_dir.name}' → '{canonical}'"
    if not ctx.dry_run:
        try:
            ctx.media_dir.rename(new_dir)
            log.info("dir_naming_fix_renamed", description=description)
        except OSError as exc:
            log.error("dir_naming_fix_rename_failed", error=str(exc))
            return []
    return [FixAction(description=description, old_path=ctx.media_dir, new_path=new_dir)]
```

- [ ] **Step 4: Add `fix()` to `NoEmptyDirs` in `structure.py`**

Extract from `library_checks._fix_empty_dirs`:

```python
def fix(self, ctx: CheckContext) -> list[FixAction]:
    """Remove empty subdirectories.

    Args:
        ctx: CheckContext (ctx.dry_run controls whether rmdir is applied).

    Returns:
        One FixAction per removed directory.
    """
    from personalscraper.verify.checks.base import FixAction
    from personalscraper.logger import get_logger
    log = get_logger("verify.checks.structure")
    actions = []
    try:
        for subdir in list(ctx.media_dir.rglob("*")):
            if subdir.is_dir() and not any(subdir.iterdir()):
                prefix = "[DRY-RUN] Would remove" if ctx.dry_run else "Removed"
                desc = f"{prefix} empty dir: {subdir.name}"
                if not ctx.dry_run:
                    try:
                        subdir.rmdir()
                    except OSError as exc:
                        log.warning("no_empty_dirs_fix_failed", subdir=str(subdir), error=str(exc))
                        continue
                actions.append(FixAction(description=desc, old_path=subdir))
    except OSError as exc:
        log.warning("no_empty_dirs_fix_list_error", error=str(exc))
    return actions
```

- [ ] **Step 5: Add `fix()` to `NtfsSafeNames` in `ntfs.py`**

Extract from `library_checks._fix_ntfs_names`:

```python
def fix(self, ctx: CheckContext) -> list[FixAction]:
    """Rename files with NTFS-illegal characters.

    Args:
        ctx: CheckContext (ctx.dry_run controls whether rename is applied).

    Returns:
        One FixAction per renamed file.
    """
    from personalscraper.verify.checks.base import FixAction
    from personalscraper.text_utils import sanitize_filename
    from personalscraper.logger import get_logger
    log = get_logger("verify.checks.ntfs")
    actions = []
    try:
        for item in ctx.media_dir.rglob("*"):
            if item.is_file():
                safe = sanitize_filename(item.name)
                if safe != item.name:
                    prefix = "[DRY-RUN] Would rename" if ctx.dry_run else "Renamed"
                    desc = f"{prefix}: {item.name} → {safe}"
                    if not ctx.dry_run:
                        try:
                            item.rename(item.parent / safe)
                        except OSError as exc:
                            log.warning("ntfs_fix_rename_failed", item=str(item), error=str(exc))
                            continue
                    actions.append(FixAction(description=desc, old_path=item,
                                             new_path=item.parent / safe if not ctx.dry_run else None))
    except OSError as exc:
        log.warning("ntfs_fix_list_error", error=str(exc))
    return actions
```

- [ ] **Step 6: Run fix tests — expect pass**

```bash
pytest tests/verify/checks/test_fixes.py -q
```

Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
git add personalscraper/verify/checks/naming.py personalscraper/verify/checks/structure.py personalscraper/verify/checks/ntfs.py tests/verify/checks/test_fixes.py
git commit -m "feat(check-plugins): co-locate fix() on DirNaming, NoEmptyDirs, NtfsSafeNames"
```

---

## Sub-phase 3.2 — Delete `MediaFixer`; wire `Verifier` + `validate_library` to `apply_fixes`

**Files:**

- Modify: `personalscraper/verify/verifier.py` (replace `MediaFixer` with `apply_fixes`)
- Modify: `personalscraper/verify/library_checks.py` (replace manual fix blocks with `apply_fixes`)
- Delete: `personalscraper/verify/fixer.py`

- [ ] **Step 1: Update `Verifier` to use `apply_fixes` with policy `{"dir_naming"}`**

```python
# In Verifier.__init__ — remove the MediaFixer import + self._fixer,
#   and ADD `self._patterns = patterns` (the rewrite needs it for CheckContext).
# In Verifier.verify_movie:
from personalscraper.verify.checks.registry import apply_fixes
from personalscraper.verify.checks.base import CheckContext, CheckStage
import personalscraper.verify.checks  # trigger registration

def verify_movie(self, movie_dir: Path) -> VerifyResult:
    result = VerifyResult(media_path=movie_dir, media_type="movie")
    ctx = CheckContext(
        media_dir=movie_dir, media_type="movie", stage=CheckStage.DISPATCH,
        config=self._config, patterns=self._patterns, dry_run=self.dry_run,
    )
    checks = self._checker.check_movie(movie_dir)
    if self.fix:
        failed = [c for c in checks if not c.passed and c.fixable]
        if failed:
            _VERIFY_FIX_POLICY = frozenset({"dir_naming"})
            actions = apply_fixes(ctx, failed, _VERIFY_FIX_POLICY)
            result.fixes_applied = [a.description for a in actions]
            for a in actions:
                if a.new_path and not self.dry_run:
                    movie_dir = a.new_path
                    result.media_path = movie_dir
                    ctx = CheckContext(
                        media_dir=movie_dir, media_type="movie",
                        stage=CheckStage.DISPATCH, config=self._config,
                        patterns=self._patterns, dry_run=self.dry_run,
                    )
            checks = self._checker.check_movie(movie_dir)
    self._classify(result, checks, movie_dir, "movie", ctx)   # ctx carries resolved_category
    return result
```

Same pattern for `verify_tvshow`.

**Also update `_classify`'s signature** to accept `ctx` and read `ctx.resolved_category` instead of re-running `classify_from_nfo` (the `category` plugin set it during `check_movie`/`check_tvshow`; fall back to `classify_from_nfo` only when `ctx.resolved_category is None`). Add a test pinning the single-`classify_from_nfo`-call behavior (CMP-3). The `verifier_*` golden (Phase 0) proves the resolved category is identical.

- [ ] **Step 2: Update `validate_library` to use `apply_fixes` with policy `{"dir_naming","no_empty_dirs","ntfs_safe_names"}`**

Replace the three manual fix blocks (Fix 1 / Fix 2 / Fix 3) in `validate_library` with:

```python
from personalscraper.verify.checks.registry import apply_fixes
from personalscraper.verify.checks.base import CheckContext, CheckStage

_LIBRARY_FIX_POLICY = frozenset({"dir_naming", "no_empty_dirs", "ntfs_safe_names"})

# Inside the per-item loop, replacing the three manual fix blocks:
if fix and errors:
    ctx = CheckContext(
        media_dir=media_dir, media_type="tvshow" if is_series else "movie",
        stage=CheckStage.DISPATCH, config=config, patterns=patterns,
        dry_run=not apply,
    )
    actions = apply_fixes(ctx, [c for c in checks if not c.passed], _LIBRARY_FIX_POLICY)
    for a in actions:
        fixes_applied.append(a.description)
        if a.new_path and apply:
            media_dir = a.new_path
    fixed_error_names = {a.old_path.name for a in actions if a.new_path}
```

- [ ] **Step 3: Delete `fixer.py`**

```bash
git rm personalscraper/verify/fixer.py
```

- [ ] **Step 4: Residual-import grep — must be 0**

```bash
rg -t py 'MediaFixer' personalscraper/ tests/
# Expected: rc=1 (no matches) — ACC-06a

rg -t py 'from personalscraper\.verify\.fixer' personalscraper/ tests/
# Expected: rc=1 (no matches)

rg -t py 'from personalscraper\.verify\.checker import.*\b(Severity|CheckResult)\b' personalscraper/ tests/
# Expected: rc=1 (no matches) — ACC-06b (all importers now use base.py)
```

- [ ] **Step 5: Run characterization golden + full suites**

```bash
pytest tests/verify/test_characterization_golden.py -q   # ACC-01
pytest tests/verify tests/enforce -q                      # ACC-02
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/verify/verifier.py personalscraper/verify/library_checks.py
git commit -m "refactor(check-plugins): delete MediaFixer — Verifier and validate_library use apply_fixes()"
```

---

## Phase Gate

```bash
make lint && make test && make check
rg -t py 'MediaFixer' personalscraper/ tests/        # ACC-06a: rc=1
rg -t py 'from personalscraper\.verify\.checker import.*\b(Severity|CheckResult)\b' personalscraper/ tests/  # ACC-06b: rc=1
pytest tests/verify/test_characterization_golden.py -q  # ACC-01
pytest tests/verify tests/enforce -q                     # ACC-02
python3 scripts/check-module-size.py                     # ACC-07
python -c "import personalscraper"
```

Expected: all green. `MediaFixer` fully deleted; fix-policy asymmetry preserved (verify=`{dir_naming}`, library=3-check set).
