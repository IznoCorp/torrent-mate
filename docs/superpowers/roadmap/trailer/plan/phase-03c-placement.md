# Phase 3c — Placement (`placement.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §3 (`trailers/placement.py`) and DESIGN §4 (placement strategy).
Create `personalscraper/trailers/placement.py` with:

- `trailer_path_for(media_dir, media_name, ext='mp4') -> Path` — single flat convention
  used for both movies and TV shows
- `find_existing_trailer(media_dir, media_name) -> Path | None` — tolerant lookup across
  `.mp4`/`.mkv`/`.webm` extensions
- `trailer_exists(path, min_size_bytes) -> bool` — size-gated existence check
- `write_trailer_url_to_nfo(nfo_path, youtube_url) -> None` — populate the NFO `<trailer>`
  tag (currently emitted empty by `scraper/nfo_generator.py` lines 160, 269) for Plex remote
  trailer fallback and cross-scraper traceability

All tests use tmpdir fixtures — no real media files or network required.

**Architecture:** Pure filesystem path computation + size check + one tiny XML write. No
network, no yt-dlp. Never creates directories — the media directory already exists (created
upstream by `sort`/`scrape`).

**Tech Stack:** Python, `pathlib`, `xml.etree.ElementTree`, `pytest`.

---

## Gate (entry condition)

Phase 3a must be complete. Phase 3b does not need to be complete before 3c.

```bash
git rev-parse --show-toplevel                              # any working copy path is fine
git branch --show-current                                  # expected: feat/trailer
python -c "from personalscraper.scraper.trailer_finder import TrailerFinder; print('OK')"
```

---

## Dependencies

- Phase 3a (discovery shape informs placement expectations — `Video.site`, `Video.key`,
  `Video.iso_639_1` are already stable).

---

## Invariants for this phase

- No network calls. No yt-dlp imports.
- `placement.py` does NOT download media — it only computes paths, checks existence, and
  writes a tiny XML tag. The actual download/write is done by `YtdlpDownloader` (Phase 3b)
  and `Orchestrator` (Phase 6).
- Existing tests remain green.
- **Flat convention for both movies AND TV shows.** Derived from DESIGN §4: maximum
  compatibility across Plex Local Media Assets + Kodi + Jellyfin/Emby. No `trailers/`
  subfolder — that is Plex-specific and has no TV-show support.
- **Dynamic extension.** yt-dlp may deliver `.mp4`, `.mkv`, or `.webm` depending on the
  source; the existence check looks for any of them and the path computation accepts the
  final extension determined by the downloader (Phase 3b resolves it via `YoutubeDL`'s
  `filename` callback).

---

## Sub-phase 3c.1 — `trailers/` package skeleton

### Files

| Action | Path                                   | Responsibility       |
| ------ | -------------------------------------- | -------------------- |
| Create | `personalscraper/trailers/__init__.py` | Empty package marker |
| Create | `tests/trailers/__init__.py`           | Empty test package   |

### Step 1: Create both `__init__.py` files

Run from the repository root (works regardless of where the checkout lives):

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
mkdir -p "$REPO_ROOT/personalscraper/trailers"
mkdir -p "$REPO_ROOT/tests/trailers"
: > "$REPO_ROOT/personalscraper/trailers/__init__.py"
: > "$REPO_ROOT/tests/trailers/__init__.py"
```

### Step 2: Commit sub-phase 3c.1

```bash
git add personalscraper/trailers/__init__.py tests/trailers/__init__.py
git commit -m "chore(trailer): scaffold trailers/ package and tests/trailers/ skeleton"
```

---

## Sub-phase 3c.2 — `placement.py` + tests (flat convention + NFO tag)

### Files

| Action | Path                                      | Responsibility                                      |
| ------ | ----------------------------------------- | --------------------------------------------------- |
| Create | `personalscraper/trailers/placement.py`   | Flat path computation + existence check + NFO write |
| Create | `tests/trailers/test_placement.py`        | Tmpdir-based unit tests                             |

### Step 1: Write failing tests

Create `tests/trailers/test_placement.py`:

```python
"""Unit tests for trailers/placement.py — flat Plex/Kodi/Jellyfin naming convention.

All tests use tmpdir fixtures. No network, no yt-dlp.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from personalscraper.trailers.placement import (
    find_existing_trailer,
    trailer_exists,
    trailer_path_for,
    write_trailer_url_to_nfo,
)


# ── path computation (flat convention, shared for movies and TV) ─────────────

class TestTrailerPathFor:
    def test_movie_follows_flat_name_dash_trailer_ext(self, tmp_path):
        """Movies use {folder}/{name}-trailer.{ext}."""
        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()
        path = trailer_path_for(movie_dir, "Fight Club (1999)", ext="mp4")
        assert path == movie_dir / "Fight Club (1999)-trailer.mp4"

    def test_tvshow_follows_same_flat_convention(self, tmp_path):
        """TV shows use the SAME convention — no trailers/ subfolder."""
        show_dir = tmp_path / "Breaking Bad (2008)"
        show_dir.mkdir()
        path = trailer_path_for(show_dir, "Breaking Bad (2008)", ext="mp4")
        assert path == show_dir / "Breaking Bad (2008)-trailer.mp4"
        # Guard against regressions toward the old Plex Trailers/ subfolder convention.
        assert "trailers" not in [p.name.lower() for p in path.parents]

    def test_default_extension_is_mp4(self, tmp_path):
        """Default `ext` parameter is 'mp4' since most yt-dlp outputs are mp4."""
        d = tmp_path / "X"
        d.mkdir()
        assert trailer_path_for(d, "X").suffix == ".mp4"

    def test_extension_can_be_webm_or_mkv(self, tmp_path):
        """Extension is dynamic — yt-dlp may return webm/mkv in edge cases."""
        d = tmp_path / "Interstellar (2014)"
        d.mkdir()
        assert trailer_path_for(d, "Interstellar (2014)", ext="webm").suffix == ".webm"
        assert trailer_path_for(d, "Interstellar (2014)", ext="mkv").suffix == ".mkv"

    def test_leading_dot_in_ext_is_tolerated(self, tmp_path):
        """Caller may pass 'mp4' or '.mp4' — either works."""
        d = tmp_path / "X"
        d.mkdir()
        a = trailer_path_for(d, "X", ext="mp4")
        b = trailer_path_for(d, "X", ext=".mp4")
        assert a == b


# ── tolerant lookup across known extensions ──────────────────────────────────

class TestFindExistingTrailer:
    def test_finds_mp4(self, tmp_path):
        """find_existing_trailer prefers mp4 when multiple candidates exist."""
        d = tmp_path / "X"
        d.mkdir()
        (d / "X-trailer.mp4").write_bytes(b"x" * 200000)
        assert find_existing_trailer(d, "X") == d / "X-trailer.mp4"

    def test_finds_mkv_when_only_mkv_present(self, tmp_path):
        """Falls back to .mkv if no .mp4."""
        d = tmp_path / "X"
        d.mkdir()
        (d / "X-trailer.mkv").write_bytes(b"x" * 200000)
        assert find_existing_trailer(d, "X") == d / "X-trailer.mkv"

    def test_prefers_mp4_over_webm(self, tmp_path):
        """When both mp4 and webm exist, mp4 wins (Plex-friendliness)."""
        d = tmp_path / "X"
        d.mkdir()
        (d / "X-trailer.webm").write_bytes(b"x" * 200000)
        (d / "X-trailer.mp4").write_bytes(b"x" * 200000)
        assert find_existing_trailer(d, "X") == d / "X-trailer.mp4"

    def test_returns_none_when_nothing_present(self, tmp_path):
        """Returns None when no trailer file exists with any known extension."""
        d = tmp_path / "X"
        d.mkdir()
        assert find_existing_trailer(d, "X") is None


# ── trailer_exists ────────────────────────────────────────────────────────────

class TestTrailerExists:
    def test_returns_false_when_file_absent(self, tmp_path):
        """trailer_exists returns False when the file does not exist."""
        path = tmp_path / "nonexistent-trailer.mp4"
        assert trailer_exists(path, min_size_bytes=102400) is False

    def test_returns_false_when_file_too_small(self, tmp_path):
        """trailer_exists returns False when file exists but is below size threshold."""
        trailer = tmp_path / "tiny-trailer.mp4"
        trailer.write_bytes(b"x" * 1000)  # 1 KB
        assert trailer_exists(trailer, min_size_bytes=102400) is False

    def test_returns_true_when_file_large_enough(self, tmp_path):
        """trailer_exists returns True when file exists and meets size threshold."""
        trailer = tmp_path / "real-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)  # 200 KB
        assert trailer_exists(trailer, min_size_bytes=102400) is True

    def test_zero_min_size_returns_true_for_any_existing_file(self, tmp_path):
        """trailer_exists with min_size_bytes=0 returns True for any file present."""
        trailer = tmp_path / "empty-trailer.mp4"
        trailer.write_bytes(b"")
        assert trailer_exists(trailer, min_size_bytes=0) is True

    def test_returns_false_for_directory(self, tmp_path):
        """trailer_exists returns False when the path is a directory."""
        d = tmp_path / "trailers"
        d.mkdir()
        assert trailer_exists(d, min_size_bytes=0) is False


# ── NFO trailer tag population ───────────────────────────────────────────────

class TestWriteTrailerUrlToNfo:
    def _make_nfo(self, tmp_path: Path, trailer_text: str = "") -> Path:
        """Build a minimal movie NFO that matches what nfo_generator.py emits."""
        nfo = tmp_path / "Fight Club (1999).nfo"
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Fight Club"
        ET.SubElement(root, "year").text = "1999"
        ET.SubElement(root, "trailer").text = trailer_text
        ET.ElementTree(root).write(nfo, encoding="utf-8", xml_declaration=True)
        return nfo

    def test_populates_empty_trailer_tag(self, tmp_path):
        """write_trailer_url_to_nfo fills the pre-existing empty <trailer> tag."""
        nfo = self._make_nfo(tmp_path)
        write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=ABC")
        tree = ET.parse(nfo)
        assert tree.find("trailer").text == "https://www.youtube.com/watch?v=ABC"

    def test_overwrites_existing_url(self, tmp_path):
        """An existing URL is replaced (re-scrape case)."""
        nfo = self._make_nfo(tmp_path, trailer_text="https://old.example/x")
        write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=NEW")
        tree = ET.parse(nfo)
        assert tree.find("trailer").text == "https://www.youtube.com/watch?v=NEW"

    def test_creates_trailer_tag_if_absent(self, tmp_path):
        """If the NFO was written by an older generator without <trailer>, add it."""
        nfo = tmp_path / "X.nfo"
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "X"
        ET.ElementTree(root).write(nfo, encoding="utf-8", xml_declaration=True)
        write_trailer_url_to_nfo(nfo, "https://www.youtube.com/watch?v=Z")
        tree = ET.parse(nfo)
        elem = tree.find("trailer")
        assert elem is not None
        assert elem.text == "https://www.youtube.com/watch?v=Z"

    def test_missing_nfo_is_noop(self, tmp_path, caplog):
        """A missing NFO logs a warning and returns — never raises."""
        missing = tmp_path / "does_not_exist.nfo"
        write_trailer_url_to_nfo(missing, "https://example")  # must not raise
        assert any("NFO not found" in rec.message for rec in caplog.records)
```

### Step 2: Run failing tests

```bash
pytest tests/trailers/test_placement.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError`.

### Step 3: Implement `personalscraper/trailers/placement.py`

```python
"""Flat trailer placement + NFO trailer-tag population.

Naming convention (see DESIGN §4):

    {media_dir}/{media_name}-trailer.{ext}

Used for both movies and TV shows — this is the single convention that works
across Plex (Local Media Assets agent), Kodi, Jellyfin and Emby. The old YTS
`trailers/trailer.mp4` subfolder layout is Plex-specific and not adopted here.

This module is pure path computation + a small NFO XML tweak. It does NOT
write media files — the download is owned by `YtdlpDownloader` (Phase 3b) and
orchestrated by `Orchestrator` (Phase 6).
"""

from __future__ import annotations

import logging
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# Extensions yt-dlp may produce, ordered by Plex-friendliness.
_KNOWN_TRAILER_EXTENSIONS: tuple[str, ...] = ("mp4", "mkv", "webm")


def trailer_path_for(media_dir: Path, media_name: str, *, ext: str = "mp4") -> Path:
    """Compute the expected trailer path for a movie or TV show.

    Flat convention: ``{media_dir}/{media_name}-trailer.{ext}``. Used for both
    movies and TV shows. See DESIGN §4 for the rationale.

    Args:
        media_dir: Absolute path to the media directory on disk.
        media_name: Folder name of the media directory
            (e.g. ``"Fight Club (1999)"`` or ``"Breaking Bad (2008)"``).
        ext: File extension for the trailer (``"mp4"`` default; leading dot
            accepted and stripped).

    Returns:
        Absolute Path where the trailer file should be placed.
    """
    ext_clean = ext.lstrip(".")
    return media_dir / f"{media_name}-trailer.{ext_clean}"


def find_existing_trailer(media_dir: Path, media_name: str) -> Path | None:
    """Locate an existing trailer file across known extensions.

    Iterates through ``_KNOWN_TRAILER_EXTENSIONS`` in Plex-preference order
    and returns the first candidate that exists.

    Args:
        media_dir: Absolute path to the media directory.
        media_name: Folder name of the media directory.

    Returns:
        Absolute Path to the existing trailer file, or ``None`` when none
        of the candidates exist.
    """
    for ext in _KNOWN_TRAILER_EXTENSIONS:
        candidate = trailer_path_for(media_dir, media_name, ext=ext)
        if candidate.is_file():
            return candidate
    return None


def trailer_exists(path: Path, min_size_bytes: int) -> bool:
    """Check whether a trailer file exists and meets the minimum size requirement.

    This is the canonical "already present" check — callers use this before
    initiating any download to ensure idempotence.

    Args:
        path: Absolute path to the expected trailer file.
        min_size_bytes: Minimum file size in bytes to consider the trailer valid.
            A file smaller than this threshold is treated as absent (partially
            written or corrupt).

    Returns:
        True if the file exists, is a regular file, and its size is at least
        ``min_size_bytes``. False in all other cases.
    """
    if not path.is_file():
        return False
    try:
        return path.stat().st_size >= min_size_bytes
    except OSError:
        return False


def write_trailer_url_to_nfo(nfo_path: Path, youtube_url: str) -> None:
    """Populate the ``<trailer>`` tag in a Kodi/Plex-style NFO with a YouTube URL.

    ``scraper/nfo_generator.py`` currently emits an empty ``<trailer></trailer>``
    tag (lines 160 for movies, 269 for TV shows). Filling it with the discovered
    YouTube URL gives Plex a remote-trailer fallback (used when Local Media
    Assets does not pick up the file) and gives Kodi/downstream tools a
    cross-referenceable source URL. The actual on-disk trailer file is still
    the primary surface.

    Failure modes are soft: a missing NFO or a parse error logs a WARNING
    and returns — this function never raises. The caller (Orchestrator) has
    already performed the download and should not be forced to roll back on
    a non-critical NFO annotation failure.

    Args:
        nfo_path: Absolute path to the NFO file to update.
        youtube_url: Full YouTube URL to write into the ``<trailer>`` tag.
    """
    if not nfo_path.is_file():
        logger.warning("NFO not found — skipping trailer URL write: %s", nfo_path)
        return

    try:
        tree = ET.parse(nfo_path)
    except ET.ParseError as exc:
        logger.warning("Cannot parse NFO %s — skipping trailer URL write: %s", nfo_path, exc)
        return

    root = tree.getroot()
    trailer_elem = root.find("trailer")
    if trailer_elem is None:
        trailer_elem = ET.SubElement(root, "trailer")
    trailer_elem.text = youtube_url

    try:
        tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    except OSError as exc:
        logger.warning("Cannot write NFO %s — trailer URL not persisted: %s", nfo_path, exc)
```

### Step 4: Run tests — all must pass

```bash
pytest tests/trailers/test_placement.py -v
```

### Step 5: Commit sub-phase 3c.2

```bash
git add personalscraper/trailers/placement.py tests/trailers/test_placement.py
git commit -m "feat(trailer): flat placement convention + NFO trailer-URL population"
```

---

## Phase 3c quality gate

- [ ] `pytest tests/trailers/test_placement.py -q` — all green
- [ ] `python -m ruff check personalscraper/trailers/placement.py tests/trailers/test_placement.py` — no errors
- [ ] `python -m mypy personalscraper/trailers/placement.py` — no type errors
- [ ] `pytest tests/ -q` — no regressions in any other test

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/trailers/test_placement.py -q
python -m ruff check personalscraper/trailers/placement.py tests/trailers/test_placement.py
python -m mypy personalscraper/trailers/placement.py
pytest tests/ -q
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 03c gate — flat placement + NFO trailer tag"
```

## Exit condition for Phase 4

Phase 4 may start only when:

- `trailer_path_for`, `find_existing_trailer`, `trailer_exists`, `write_trailer_url_to_nfo`
  are importable from `personalscraper.trailers.placement`
- `pytest tests/trailers/ -q` exits 0
- The milestone commit is on the branch
