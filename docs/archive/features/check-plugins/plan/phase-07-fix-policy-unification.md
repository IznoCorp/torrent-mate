# Phase 7 — Fix-Policy Unification (deliberate behavior change)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** This is the **only deliberate behavior change** of the feature. Unify the verify pipeline's auto-fix policy to match library validate's: `{"dir_naming", "no_empty_dirs", "ntfs_safe_names"}`. After this, the `verify` pipeline auto-removes empty subdirectories and renames NTFS-illegal files (today it only fixes `dir_naming`). The characterization golden's `verifier_*` entries are **deliberately updated** here, with dedicated tests that pin the new behavior.

**Architecture:** Change `_VERIFY_FIX_POLICY` in `Verifier` from `{"dir_naming"}` to `{"dir_naming", "no_empty_dirs", "ntfs_safe_names"}`. Re-capture `verifier_movie.json` / `verifier_tvshow.json` golden entries (and only those — `checker_*`, `library_*`, `coherence` are untouched because their fix paths did not change). Add a dedicated test proving the verify pipeline now fixes empty-dirs + NTFS.

**Tech Stack:** Python 3.11, `apply_fixes`, characterization golden, pytest

---

## ⚠️ Post-verification corrections (2026-06-01) — applied in the steps below

- **FIX-1/ACC-2/GND-7**: `test_fix_policy.py` (sub-phase 7.1) uses `MagicMock()` for `settings` + the `test_config` fixture + `from personalscraper.naming_patterns import PATTERNS` — there is **no** `test_settings` fixture.
- **GOLD-2**: the selective `verifier_*` re-capture (sub-phase 7.2 Step 3) uses the env-driven capture `GOLDEN_ONLY=verifier_movie,verifier_tvshow CAPTURE_GOLDEN=1 pytest …` — there is no `capture_golden.py` script.

---

## Gate (previous phase)

- The structural refactor is complete and proven no-behavior-change: `pytest tests/verify/test_characterization_golden.py -q` → all pass (Phases 2–6 green).
- `pytest tests/verify tests/enforce tests/commands -q` → all pass.
- `--check`/`--list-checks` shipped.

> ⚠️ Do NOT start this phase until the golden is green at HEAD. This phase is the first that intentionally diverges from the captured baseline — keeping it last isolates the deliberate change from the refactor's safety proof.

---

## Sub-phase 7.1 — Write the new-behavior tests FIRST (TDD; they fail on current policy)

**Files:**

- Create: `tests/verify/checks/test_fix_policy.py`

- [ ] **Step 1: Write tests that assert the verify pipeline fixes empty-dirs + NTFS**

```python
# tests/verify/checks/test_fix_policy.py
"""Pins the unified verify fix policy: verify now auto-fixes
no_empty_dirs + ntfs_safe_names in the pipeline (not just dir_naming)."""
from pathlib import Path
from unittest.mock import MagicMock
import xml.etree.ElementTree as ET
import pytest
from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.verifier import Verifier


def _valid_movie(d: Path) -> None:
    (d / "M.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = "M"; ET.SubElement(root, "year").text = "2020"
    for t, v in (("tmdb", "1"), ("imdb", "tt1")):
        u = ET.SubElement(root, "uniqueid"); u.set("type", t); u.text = v
    ET.SubElement(root, "genre").text = "Drame"
    ET.ElementTree(root).write(d / "M.nfo", encoding="unicode")
    (d / "M-poster.jpg").write_bytes(b"\xff"); (d / "M-landscape.jpg").write_bytes(b"\xff")


def test_verify_pipeline_fixes_empty_dirs(tmp_path, test_config):
    d = tmp_path / "M (2020)"; d.mkdir(); _valid_movie(d)
    (d / "Empty").mkdir()  # empty subdir → no_empty_dirs ERROR (fixable)
    v = Verifier(MagicMock(), PATTERNS, test_config, dry_run=False, fix=True)
    result = v.verify_movie(d)
    assert not (d / "Empty").exists()           # empty dir removed by verify now
    assert result.status in ("valid", "fixed")


def test_verify_pipeline_fixes_ntfs_names(tmp_path, test_config):
    d = tmp_path / "M (2020)"; d.mkdir(); _valid_movie(d)
    (d / "bad:name.srt").write_bytes(b"1\n")     # NTFS-illegal → fixable
    v = Verifier(MagicMock(), PATTERNS, test_config, dry_run=False, fix=True)
    result = v.verify_movie(d)
    assert not (d / "bad:name.srt").exists()     # renamed by verify now
    assert result.status in ("valid", "fixed")
```

- [ ] **Step 2: Run — expect FAIL** (current policy is `{"dir_naming"}`, so empty/ntfs are not fixed by verify).

```bash
pytest tests/verify/checks/test_fix_policy.py -q
# Expected: 2 failed (empty dir / ntfs file still present)
```

---

## Sub-phase 7.2 — Flip the policy and update the golden deliberately

**Files:**

- Modify: `personalscraper/verify/verifier.py` (`_VERIFY_FIX_POLICY`)
- Update: `tests/verify/golden/verifier_movie.json`, `verifier_tvshow.json`

- [ ] **Step 1: Unify the policy**

```python
# verifier.py — single source for both verify_movie and verify_tvshow
_VERIFY_FIX_POLICY = frozenset({"dir_naming", "no_empty_dirs", "ntfs_safe_names"})
```

- [ ] **Step 2: Run the new-behavior tests — expect pass**

```bash
pytest tests/verify/checks/test_fix_policy.py -q   # ACC-09: 2 passed
```

- [ ] **Step 3: Re-capture ONLY the `verifier_*` golden entries**

The `checker_*`, `library_*`, and `coherence` golden are unaffected (their fix paths did not change). Re-run the capture for the two verifier entry points and confirm the diff is limited to items with empty-dirs / NTFS-illegal files (now `fixed` instead of `blocked`):

```bash
GOLDEN_ONLY=verifier_movie,verifier_tvshow CAPTURE_GOLDEN=1 pytest tests/verify/test_characterization_golden.py -q
git diff --stat tests/verify/golden/
# Expected: only verifier_movie.json + verifier_tvshow.json changed
```

Inspect the diff to confirm the change is exactly the empty-dir/NTFS items flipping `blocked → fixed` (+ their `fixes_applied`). No other item changes.

- [ ] **Step 4: Re-assert the full golden (now reflecting the deliberate change)**

```bash
pytest tests/verify/test_characterization_golden.py -q   # green again, against the UPDATED golden
pytest tests/verify tests/enforce -q                      # ACC-02
```

- [ ] **Step 5: Commit** — `feat(check-plugins): unify verify fix policy (auto-fix empty-dirs + NTFS); update golden`.

  The commit message and the phase doc make the deliberate behavior change explicit and auditable (so review understands why `verifier_*.json` changed).

---

## Phase Gate

```bash
make lint && make test && make check
pytest tests/verify/checks/test_fix_policy.py -q          # ACC-09
pytest tests/verify/test_characterization_golden.py -q   # green vs UPDATED golden
pytest tests/verify tests/enforce tests/commands -q       # ACC-02
python3 scripts/check-module-size.py                      # ACC-07
python -c "import personalscraper"
```

Expected: all green. Verify and library now share one fix policy; the golden divergence is intentional, isolated, and tested.
