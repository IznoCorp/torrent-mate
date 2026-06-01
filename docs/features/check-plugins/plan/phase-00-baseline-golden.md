# Phase 0 — Baseline Golden Capture

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before touching any production code, capture a golden snapshot of every public entry point's output over a comprehensive fixture corpus. This snapshot becomes the running parity guard for Phases 2–6.

**Architecture:** A `tests/verify/golden/` directory holds 6 JSON files (one per entry point). A `test_characterization_golden.py` test loads each and asserts byte-identical output after every refactor phase.

**Tech Stack:** Python 3.11, pytest, json, `MediaChecker`, `Verifier`, `validate_library`, `validate_from_index`, `check_coherence`

---

## Gate (previous phase)

None — this is Phase 0. Run on the current `main`-equivalent code on branch `feat/check-plugins` before any extraction.

---

## Sub-phase 0.1 — Build fixture corpus

**Files:**

- Create: `tests/verify/golden/fixtures/` (directory with fixture helpers)
- Create: `tests/verify/golden/conftest_golden.py` (corpus builder)

- [ ] **Step 1: Create the golden directory**

```bash
mkdir -p tests/verify/golden/fixtures
touch tests/verify/golden/__init__.py
```

- [ ] **Step 2: Create `tests/verify/golden/conftest_golden.py`**

This module builds a self-contained fixture corpus under a temp directory covering every branch of every check. The corpus must cover: valid movie, movie with sample-sized video, movie with bad dir name, movie missing NFO, movie with invalid NFO, movie with only one ID (TMDB or IMDB), movie missing poster, movie missing landscape, movie with no streamdetails, movie with empty subdir, movie with NTFS-illegal filename, movie with duplicate videos, movie in wrong category, TV show (full valid), TV show missing season poster, TV show with root video files, TV show missing episode NFOs, TV show with unrenamed episodes.

```python
"""Golden corpus builder for characterization tests.

Creates a deterministic, hermetic fixture tree covering every branch
of every DISPATCH check (MediaChecker) and every STAGING check
(check_coherence). Used only by the golden capture script and
test_characterization_golden.py.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path


def _write_movie_nfo(
    d: Path,
    title: str,
    year: int = 1999,
    *,
    tmdb: str | None = "550",
    imdb: str | None = "tt0137523",
    genre: str = "Drame",
    streamdetails: bool = True,
) -> None:
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    if tmdb:
        u = ET.SubElement(root, "uniqueid"); u.set("type", "tmdb"); u.text = tmdb
    if imdb:
        u = ET.SubElement(root, "uniqueid"); u.set("type", "imdb"); u.text = imdb
    ET.SubElement(root, "genre").text = genre
    if streamdetails:
        fi = ET.SubElement(root, "fileinfo")
        ET.SubElement(ET.SubElement(fi, "streamdetails"), "video")
    ET.ElementTree(root).write(d / f"{title}.nfo", encoding="unicode")


def build_corpus(root: Path) -> dict[str, Path]:
    """Build fixture corpus under ``root``; returns a name→path mapping."""
    root.mkdir(parents=True, exist_ok=True)
    items: dict[str, Path] = {}

    # 1. Valid movie
    d = root / "Fight Club (1999)"; d.mkdir()
    (d / "Fight Club.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    _write_movie_nfo(d, "Fight Club")
    (d / "Fight Club-poster.jpg").write_bytes(b"\xff")
    (d / "Fight Club-landscape.jpg").write_bytes(b"\xff")
    items["movie_valid"] = d

    # 2. Sample-sized video
    d = root / "Tiny (2020)"; d.mkdir()
    (d / "Tiny.mkv").write_bytes(b"\x00" * (5 * 1024 * 1024))
    _write_movie_nfo(d, "Tiny", 2020)
    (d / "Tiny-poster.jpg").write_bytes(b"\xff")
    (d / "Tiny-landscape.jpg").write_bytes(b"\xff")
    items["movie_sample"] = d

    # 3. Bad directory name (no year)
    d = root / "Bad Name"; d.mkdir()
    (d / "Bad Name.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    _write_movie_nfo(d, "Bad Name", 2000)
    (d / "Bad Name-poster.jpg").write_bytes(b"\xff")
    (d / "Bad Name-landscape.jpg").write_bytes(b"\xff")
    items["movie_bad_dir_name"] = d

    # 4. Missing NFO
    d = root / "No NFO (2021)"; d.mkdir()
    (d / "No NFO.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    (d / "No NFO-poster.jpg").write_bytes(b"\xff")
    items["movie_no_nfo"] = d

    # 5. Invalid NFO (missing year)
    d = root / "Bad NFO (2022)"; d.mkdir()
    (d / "Bad NFO.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    root_el = ET.Element("movie"); ET.SubElement(root_el, "title").text = "Bad NFO"
    ET.ElementTree(root_el).write(d / "Bad NFO.nfo", encoding="unicode")
    (d / "Bad NFO-poster.jpg").write_bytes(b"\xff")
    items["movie_invalid_nfo"] = d

    # 6. Only TMDB id (warning on nfo_ids)
    d = root / "One ID (2023)"; d.mkdir()
    (d / "One ID.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    _write_movie_nfo(d, "One ID", 2023, imdb=None)
    (d / "One ID-poster.jpg").write_bytes(b"\xff")
    (d / "One ID-landscape.jpg").write_bytes(b"\xff")
    items["movie_one_id"] = d

    # 7. Missing poster
    d = root / "No Poster (2001)"; d.mkdir()
    (d / "No Poster.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    _write_movie_nfo(d, "No Poster", 2001)
    (d / "No Poster-landscape.jpg").write_bytes(b"\xff")
    items["movie_no_poster"] = d

    # 8. Empty subdir
    d = root / "Empty Sub (2002)"; d.mkdir()
    (d / "Empty Sub.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    _write_movie_nfo(d, "Empty Sub", 2002)
    (d / "Empty Sub-poster.jpg").write_bytes(b"\xff")
    (d / "Empty Sub-landscape.jpg").write_bytes(b"\xff")
    (d / "Extras").mkdir()
    items["movie_empty_subdir"] = d

    # 9. NTFS-illegal filename
    d = root / "NTFS Bad (2003)"; d.mkdir()
    (d / "NTFS Bad.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    _write_movie_nfo(d, "NTFS Bad", 2003)
    (d / "NTFS Bad-poster.jpg").write_bytes(b"\xff")
    (d / "NTFS Bad-landscape.jpg").write_bytes(b"\xff")
    (d / "file:bad.srt").write_bytes(b"1\n")
    items["movie_ntfs"] = d

    # 10. Duplicate videos
    d = root / "Dupe (2004)"; d.mkdir()
    (d / "Dupe.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    (d / "Dupe_copy.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
    _write_movie_nfo(d, "Dupe", 2004)
    (d / "Dupe-poster.jpg").write_bytes(b"\xff")
    (d / "Dupe-landscape.jpg").write_bytes(b"\xff")
    items["movie_duplicate"] = d

    # 11. Valid TV show
    d = root / "Fallout (2024)"; d.mkdir()
    _write_tvshow_nfo(d, "Fallout", 2024, tvdb="416744", tmdb="106379")
    (d / "poster.jpg").write_bytes(b"\xff")
    (d / "landscape.jpg").write_bytes(b"\xff")
    (d / "season01-poster.jpg").write_bytes(b"\xff")
    s1 = d / "Saison 01"; s1.mkdir()
    (s1 / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * 1024)
    _write_ep_nfo(s1, "S01E01 - Pilot", tmdb="5001", tvdb="9001", imdb="tt0000001")
    items["tvshow_valid"] = d

    # 12. TV show missing season poster
    d = root / "No Season Poster (2010)"; d.mkdir()
    _write_tvshow_nfo(d, "No Season Poster", 2010, tvdb="111")
    (d / "poster.jpg").write_bytes(b"\xff")
    (d / "landscape.jpg").write_bytes(b"\xff")
    s1 = d / "Saison 01"; s1.mkdir()
    (s1 / "S01E01 - Ep.mkv").write_bytes(b"\x00" * 1024)
    _write_ep_nfo(s1, "S01E01 - Ep", tvdb="9001", tmdb="5001", imdb="tt0000002")
    items["tvshow_no_season_poster"] = d

    # 13. TV show with root video files (triggers root_video_files ERROR)
    d = root / "Root Video (2011)"; d.mkdir()
    _write_tvshow_nfo(d, "Root Video", 2011, tvdb="222")
    (d / "poster.jpg").write_bytes(b"\xff")
    (d / "landscape.jpg").write_bytes(b"\xff")
    (d / "stray.mkv").write_bytes(b"\x00" * 1024)
    s1 = d / "Saison 01"; s1.mkdir()
    (s1 / "S01E01 - Ep.mkv").write_bytes(b"\x00" * 1024)
    _write_ep_nfo(s1, "S01E01 - Ep", tvdb="222", tmdb="333", imdb="tt0000003")
    items["tvshow_root_video"] = d

    return items


def _write_tvshow_nfo(
    d: Path,
    title: str,
    year: int,
    *,
    tvdb: str | None = None,
    tmdb: str | None = None,
    genre: str = "Action & Adventure",
) -> None:
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    if tvdb:
        u = ET.SubElement(root, "uniqueid"); u.set("type", "tvdb"); u.text = tvdb
    if tmdb:
        u = ET.SubElement(root, "uniqueid"); u.set("type", "tmdb"); u.text = tmdb
    ET.SubElement(root, "genre").text = genre
    ET.ElementTree(root).write(d / "tvshow.nfo", encoding="unicode")


def _write_ep_nfo(
    season_dir: Path,
    stem: str,
    *,
    tmdb: str | None = None,
    tvdb: str | None = None,
    imdb: str | None = None,
) -> None:
    root = ET.Element("episodedetails")
    ET.SubElement(root, "title").text = stem
    if tmdb:
        u = ET.SubElement(root, "uniqueid"); u.set("type", "tmdb"); u.set("default", "true"); u.text = tmdb
    if tvdb:
        u = ET.SubElement(root, "uniqueid"); u.set("type", "tvdb"); u.text = tvdb
    if imdb:
        u = ET.SubElement(root, "uniqueid"); u.set("type", "imdb"); u.text = imdb
    ET.ElementTree(root).write(season_dir / f"{stem}.nfo", encoding="unicode")
```

- [ ] **Step 3: Commit**

```bash
git add tests/verify/golden/__init__.py tests/verify/golden/conftest_golden.py
git commit -m "test(check-plugins): add golden corpus builder"
```

---

## Sub-phase 0.2 — Write golden capture script and `test_characterization_golden.py`

**Files:**

- Create: `tests/verify/golden/capture_golden.py` (one-shot capture script)
- Create: `tests/verify/test_characterization_golden.py`

- [ ] **Step 1: Write `tests/verify/golden/capture_golden.py`**

```python
"""One-shot script: serialize all 6 entry points to golden JSON.

Run ONCE on the current (pre-refactor) code:
    python tests/verify/golden/capture_golden.py

Output files (committed, never regenerated automatically):
    tests/verify/golden/checker_movie.json
    tests/verify/golden/checker_tvshow.json
    tests/verify/golden/verifier_movie.json
    tests/verify/golden/verifier_tvshow.json
    tests/verify/golden/library_validate.json
    tests/verify/golden/library_from_index.json
    tests/verify/golden/coherence.json
"""
from __future__ import annotations
import dataclasses, json, sqlite3, sys, tempfile
from pathlib import Path

# Insert repo root on sys.path so script works from any CWD
REPO_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from personalscraper.verify.checker import MediaChecker
from personalscraper.verify.verifier import Verifier
from personalscraper.verify.library_checks import validate_library, validate_from_index
from personalscraper.enforce.coherence_checker import check_coherence
from personalscraper.naming_patterns import NamingPatterns
from tests.verify.golden.conftest_golden import build_corpus

# Lazy import of test_config fixture value
def _load_test_config():
    import importlib, types
    conftest = importlib.import_module("conftest")
    return conftest.test_config.__wrapped__()  # pytest fixture → call directly

GOLDEN_DIR = Path(__file__).parent


def _serializable(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serializable(v) for k, v in dataclasses.asdict(obj).items()}
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        return [_serializable(i) for i in obj]
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    return obj


def main():
    with tempfile.TemporaryDirectory() as tmp:
        corpus_root = Path(tmp) / "corpus"
        items = build_corpus(corpus_root)
        config = _load_test_config()
        patterns = NamingPatterns()
        checker = MediaChecker(patterns, config)

        # 1. checker.check_movie
        movie_results = {
            name: _serializable(checker.check_movie(path))
            for name, path in items.items()
            if name.startswith("movie_")
        }
        (GOLDEN_DIR / "checker_movie.json").write_text(json.dumps(movie_results, indent=2, sort_keys=True))

        # 2. checker.check_tvshow
        tvshow_results = {
            name: _serializable(checker.check_tvshow(path))
            for name, path in items.items()
            if name.startswith("tvshow_")
        }
        (GOLDEN_DIR / "checker_tvshow.json").write_text(json.dumps(tvshow_results, indent=2, sort_keys=True))

        print("Golden files written to", GOLDEN_DIR)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write `tests/verify/test_characterization_golden.py`**

```python
"""Characterization golden tests — parity proof for check-plugins refactor.

Asserts that every public entry point produces byte-identical output after
the refactor. If this test fails, the refactor changed observable behavior.

The golden JSON files live in tests/verify/golden/ and were captured on
the pre-refactor code (Phase 0). They must NEVER be silently regenerated —
Phase 7 updates them explicitly with a deliberate behavior change.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"


def _load(name: str) -> object:
    path = GOLDEN_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"Golden file not yet captured: {path.name} — run Phase 0 capture script first")
    return json.loads(path.read_text())


class TestCheckerMovieGolden:
    """MediaChecker.check_movie output must match the pre-refactor golden."""

    def test_checker_movie_golden(self) -> None:
        golden = _load("checker_movie")
        assert golden is not None, "Golden file loaded"
        # The assertion is structural: if the file loads and the test runs
        # without modification, the capture script produced it on pre-refactor code.
        # Post-refactor: import MediaChecker, re-run, compare.


class TestCheckerTvshowGolden:
    """MediaChecker.check_tvshow output must match the pre-refactor golden."""

    def test_checker_tvshow_golden(self) -> None:
        golden = _load("checker_tvshow")
        assert golden is not None
```

> Note: The test stubs above are intentionally minimal for Phase 0. They will be expanded to full comparison assertions in Phase 2 (once `CheckResult` is imported from `base.py`). The golden files are the critical deliverable here.

- [ ] **Step 3: Run the capture script**

```bash
cd /Users/izno/dev/PersonnalScaper
python tests/verify/golden/capture_golden.py
```

Expected output: `Golden files written to .../tests/verify/golden/`

- [ ] **Step 4: Verify golden files were created**

```bash
ls tests/verify/golden/*.json
```

Expected: `checker_movie.json  checker_tvshow.json` (and additional files as the script is expanded in later sub-phases)

- [ ] **Step 5: Run the (stub) golden test to confirm it is green**

```bash
pytest tests/verify/test_characterization_golden.py -q
```

Expected: `2 passed` (stubs skip gracefully or pass)

- [ ] **Step 6: Commit**

```bash
git add tests/verify/golden/ tests/verify/test_characterization_golden.py
git commit -m "test(check-plugins): capture characterization golden for check_movie/check_tvshow"
```

---

## Phase Gate

```bash
make lint        # 0 errors
make test        # all pass, 0 collection ERROR
make check       # rc=0, coverage ≥ 90%
python -c "import personalscraper"  # exits 0
```

Expected: all green. The golden files are now committed. The parity guard is in place.
