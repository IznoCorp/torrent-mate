# Phase 0 — Baseline Golden Capture (all 7 entry points)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before touching any production code, capture a golden snapshot of **every** public entry point's output over a comprehensive fixture corpus, on the **pre-refactor** code. This snapshot is the running parity guard for Phases 2–6 (and the deliberate, isolated update point in Phase 7). The proof is worthless if it covers only some entry points or doesn't actually compare — so this phase captures **all 7** and the test asserts **real equality** and **fails (not skips)** on a missing golden.

**Architecture:** `tests/verify/golden/` holds 7 JSON files. A single parametrized `test_characterization_golden.py` both **captures** (when `CAPTURE_GOLDEN=1`) and **asserts** (normal run) each entry point, using pytest fixtures (`test_config`) + corpus builders. Non-deterministic fields (`LibraryValidationResult.validated_at`) are normalized out before serialization.

**The 7 entry points and their harness:**

| golden file               | entry point                         | corpus / harness                                                                       | mutates? |
| ------------------------- | ----------------------------------- | -------------------------------------------------------------------------------------- | -------- |
| `checker_movie.json`      | `MediaChecker.check_movie`          | flat item corpus (movie dirs)                                                          | no       |
| `checker_tvshow.json`     | `MediaChecker.check_tvshow`         | flat item corpus (tvshow dirs)                                                         | no       |
| `verifier_movie.json`     | `Verifier.verify_movie` (fix=True)  | **fresh copy** per item (fix mutates)                                                  | yes      |
| `verifier_tvshow.json`    | `Verifier.verify_tvshow` (fix=True) | **fresh copy** per item                                                                | yes      |
| `library_validate.json`   | `validate_library` (fix+apply)      | disk-layout corpus + `Config` disks                                                    | yes      |
| `library_from_index.json` | `validate_from_index`               | in-memory SQLite seeded rows                                                           | no       |
| `coherence.json`          | `check_coherence`                   | **staging-layout** corpus (`001-MOVIES/`, `002-TVSHOWS/`) + `Config.paths.staging_dir` | no       |

**Tech Stack:** Python 3.11, pytest, json, dataclasses, sqlite3, the 7 verify/enforce entry points, `tests/fixtures/config.test_config`

---

## Gate (previous phase)

None — Phase 0. Run on the current `feat/check-plugins` HEAD before any extraction.

---

## Sub-phase 0.1 — Corpus builders (flat / staging / disk / DB)

**Files:**

- Create: `tests/verify/golden/__init__.py`, `tests/verify/golden/_corpus.py`

- [ ] **Step 1: `mkdir -p tests/verify/golden && touch tests/verify/golden/__init__.py`**

- [ ] **Step 2: `tests/verify/golden/_corpus.py`** — deterministic, hermetic builders covering **every branch** of every check. Reuse the item-builder shape below; **add the branches the original draft missed**: missing-episode-NFO TV show, unrenamed-episode TV show, TV show with empty subdir, TV show with NTFS-illegal name, movie missing landscape, movie with no streamdetails, and a movie with neither TMDB nor IMDB (nfo_ids ERROR). Provide four builders:
  - `build_item_corpus(root) -> dict[str, Path]` — flat media-item dirs (the existing 13 items + the missing branches above). Used by `check_movie`/`check_tvshow`/`verify_*`.
  - `build_staging_corpus(root) -> None` — lays items under `root/001-MOVIES/` and `root/002-TVSHOWS/` (incl. a `tvshow.nfo`-in-MOVIES and a movie-NFO-in-TVSHOWS for wrong-category, and a genre→TV_PROGRAMS show). Used by `check_coherence`.
  - `build_disk_corpus(root) -> None` — lays items under category folders for a disk (per `config.category(id).folder_name`). Used by `validate_library`.
  - `seed_index_db(conn) -> None` — creates `media_item` + `item_attribute` and inserts rows covering `nfo_status` ∈ {missing, invalid, valid, NULL} and `artwork_json` with/without poster/landscape, for movie + show. Used by `validate_from_index`.

  The movie/tvshow/episode NFO writers from the original draft (`_write_movie_nfo`, `_write_tvshow_nfo`, `_write_ep_nfo`) move into `_corpus.py` unchanged. **Determinism:** fixed bytes, no `datetime`, no randomness.

- [ ] **Step 3: Commit** — `test(check-plugins): add golden corpus builders (flat/staging/disk/db)`.

---

## Sub-phase 0.2 — Capture-or-assert characterization test (all 7 entry points)

**Files:**

- Create: `tests/verify/test_characterization_golden.py`

- [ ] **Step 1: Write `test_characterization_golden.py`** — one module that captures (env `CAPTURE_GOLDEN=1`) or asserts. Uses the `test_config` fixture (real `Config`); builds a **fresh** corpus per mutating entry point.

```python
"""Characterization golden — parity proof for the check-plugins refactor.

Run-mode (default): load each golden JSON and assert BYTE-IDENTICAL output from
every public entry point. FAILS (does not skip) if a golden file is missing —
a vanished baseline must never mask a regression.

Capture-mode (CAPTURE_GOLDEN=1): (re)write the golden files from the CURRENT code.
Run ONCE on pre-refactor HEAD in Phase 0; re-run selectively in Phase 7 via
GOLDEN_ONLY=verifier_movie,verifier_tvshow for the deliberate fix-policy change.

The golden files are committed and NEVER auto-regenerated by a normal test run.
"""
from __future__ import annotations

import dataclasses, json, os, shutil, sqlite3
from pathlib import Path

import pytest

from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.checker import MediaChecker
from personalscraper.verify.verifier import Verifier
from personalscraper.verify.library_checks import validate_library, validate_from_index
from personalscraper.enforce.coherence_checker import check_coherence
from tests.verify.golden import _corpus

GOLDEN_DIR = Path(__file__).parent / "golden"
_CAPTURE = os.environ.get("CAPTURE_GOLDEN") == "1"
_ONLY = set(filter(None, os.environ.get("GOLDEN_ONLY", "").split(",")))

# Fields that are non-deterministic and must be normalized out before compare.
_DROP_KEYS = {"validated_at"}


def _ser(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _ser(v) for k, v in dataclasses.asdict(obj).items() if k not in _DROP_KEYS}
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items() if k not in _DROP_KEYS}
    if isinstance(obj, (list, tuple)):
        return [_ser(i) for i in obj]
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    return obj


def _check(name, produce):
    """Capture or assert one entry point. produce() -> JSON-able structure."""
    if _ONLY and name not in _ONLY:
        return
    path = GOLDEN_DIR / f"{name}.json"
    actual = _ser(produce())
    if _CAPTURE:
        path.write_text(json.dumps(actual, indent=2, sort_keys=True))
        return
    assert path.exists(), f"Golden {name}.json MISSING — capture it (CAPTURE_GOLDEN=1) before asserting"
    assert actual == json.loads(path.read_text()), f"Golden mismatch for {name}"


def test_checker_movie(test_config, tmp_path):
    items = _corpus.build_item_corpus(tmp_path / "c_mov")
    chk = MediaChecker(PATTERNS, test_config)
    _check("checker_movie", lambda: {n: chk.check_movie(p) for n, p in items.items() if n.startswith("movie_")})


def test_checker_tvshow(test_config, tmp_path):
    items = _corpus.build_item_corpus(tmp_path / "c_tv")
    chk = MediaChecker(PATTERNS, test_config)
    _check("checker_tvshow", lambda: {n: chk.check_tvshow(p) for n, p in items.items() if n.startswith("tvshow_")})


def test_verifier_movie(test_config, tmp_path):
    def produce():
        out = {}
        for n, p in _corpus.build_item_corpus(tmp_path / "v_mov").items():
            if n.startswith("movie_"):
                v = Verifier(_settings_stub(), PATTERNS, test_config, dry_run=False, fix=True)
                out[n] = v.verify_movie(p)
        return out
    _check("verifier_movie", produce)


def test_verifier_tvshow(test_config, tmp_path):
    def produce():
        out = {}
        for n, p in _corpus.build_item_corpus(tmp_path / "v_tv").items():
            if n.startswith("tvshow_"):
                v = Verifier(_settings_stub(), PATTERNS, test_config, dry_run=False, fix=True)
                out[n] = v.verify_tvshow(p)
        return out
    _check("verifier_tvshow", produce)


def test_library_validate(test_config, tmp_path):
    cfg = _corpus.build_disk_corpus(tmp_path / "disk", test_config)  # returns a Config with a disk at tmp
    _check("library_validate", lambda: validate_library(cfg, fix=True, apply=True))


def test_library_from_index(tmp_path):
    conn = sqlite3.connect(":memory:")
    _corpus.seed_index_db(conn)
    _check("library_from_index", lambda: validate_from_index(conn))


def test_coherence(test_config, tmp_path):
    cfg = _corpus.build_staging_corpus(tmp_path / "stg", test_config)  # Config with paths.staging_dir at tmp
    _check("coherence", lambda: check_coherence(_settings_stub(), cfg))
```

Notes for the implementer:

- `_settings_stub()` — return the value existing verifier tests use for `settings` (a `MagicMock()`), or import `typed_settings_stub` from `tests/fixtures/settings_stub.py`. Do **not** invent a `test_settings` fixture (it does not exist).
- `build_disk_corpus` / `build_staging_corpus` return a `Config` derived from `test_config` with `disks` / `paths.staging_dir` repointed at the tmp tree (use `dataclasses.replace` or the config's mutation API).
- `validate_library(..., apply=True)` mutates — that's why it runs on a throwaway disk tree.

- [ ] **Step 2: Capture the baseline (pre-refactor)**

```bash
CAPTURE_GOLDEN=1 pytest tests/verify/test_characterization_golden.py -q
ls tests/verify/golden/*.json   # expect 7 files
```

- [ ] **Step 3: Assert mode is green against the just-captured baseline**

```bash
pytest tests/verify/test_characterization_golden.py -q   # 7 passed
```

- [ ] **Step 4: Commit** — `test(check-plugins): capture characterization golden for all 7 entry points`.

---

## Phase Gate

```bash
make lint && make test && make check
pytest tests/verify/test_characterization_golden.py -q   # 7 passed (real equality, fail-on-missing)
ls tests/verify/golden/*.json | wc -l                    # 7
python -c "import personalscraper"
```

Expected: all green; 7 golden files committed; the parity guard is real (asserts equality, fails on a missing baseline) and complete (all entry points). This is the safety spine for Phases 2–6.
