# Phase 1 — RP10a: TorrentLayout parser + structural match

## Gate

- **Requires**: Nothing — this phase has no upstream dependency; it builds net-new primitives on the existing bencode parser in `api/torrent/_base.py`.
- **Produces for Phase 2**: `TorrentLayout` dataclass, `structural_match()` pure function, and the `parse_torrent_layout(bytes) -> TorrentLayout` entry point that Phase 2's `list_files` + `properties` adapters consume.

## Overview

Extend the existing bencode parser in `api/torrent/_base.py` (functions `_bencode_info_hash`, `_bencode_str`, `_bencode_end`, depth cap 100) with a file-list extractor. Define typed `TorrentLayout` + `MatchVerdict` + pure `structural_match()`. Golden fixtures from **real** `.torrent` files (single-file, multi-file, nested dirs). Adversarial: malformed bencode, deep nesting, v2/hybrid detection.

### Sub-phases (6 commits)

| #   | Commit                                                                      | Scope        |
| --- | --------------------------------------------------------------------------- | ------------ |
| 1.1 | `feat(watch-seed): add TorrentLayout and MatchVerdict data models`          | Data models  |
| 1.2 | `feat(watch-seed): extend bencode parser with file-list extractor`          | Parser       |
| 1.3 | `feat(watch-seed): implement structural_match pure function`                | Matcher      |
| 1.4 | `feat(watch-seed): add golden fixture tests for real .torrent files`        | Golden tests |
| 1.5 | `feat(watch-seed): add adversarial parse + v2-hybrid rejection tests`       | Adversarial  |
| 1.6 | `test(watch-seed): add structural_match unit tests (positives + negatives)` | Match tests  |

## Sub-phase 1.1 — TorrentLayout + MatchVerdict data models

**Files:**

- Create: `personalscraper/api/torrent/_layout.py`

**Data models:**

```python
"""Typed .torrent layout primitives for structural matching (RP10a).

See docs/features/watch-seed/DESIGN.md §RP10a.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class MatchVerdict(enum.Enum):
    """Outcome of :func:`structural_match`."""

    MATCH = "match"
    PIECE_LENGTH_MISMATCH = "piece_length_mismatch"
    FILE_LIST_MISMATCH = "file_list_mismatch"
    ROOT_NAME_MISMATCH = "root_name_mismatch"
    V2_HYBRID = "v2_hybrid"


@dataclass(frozen=True, slots=True)
class TorrentLayout:
    """Immutable file-tree layout extracted from a .torrent's ``info`` dict.

    Attributes:
        name: ``info.name`` — the root directory (multi-file) or base filename
            (single-file). Structural matching requires identical names; a
            renamed root cannot match without linking (D11).
        piece_length: ``info.piece length`` in bytes.
        files: Ordered list of ``(relative_path, size)`` — the slash-separated
            path joined to ``name/`` at the torrent root, with the declared
            byte size.
        total_size: Sum of every file's declared size (computed, not parsed).
        meta_version: ``info.meta version`` if present (1 = v1, 2 = v2/hybrid),
            or ``1`` when absent (default v1).
    """

    name: str
    piece_length: int
    files: list[tuple[str, int]]
    total_size: int
    meta_version: int = 1
```

## Sub-phase 1.2 — bencode file-list extractor

**Files:**

- Modify: `personalscraper/api/torrent/_base.py` (add `parse_torrent_layout()` + helpers)

Extend the existing parser with a function that walks the `info` dict structurally (same pattern as `_bencode_info_hash`) and extracts `info.name`, `info.piece length`, `info.files[]` (multi-file: list of dicts with `length` + `path[]`) / `info.length` (single-file). Detect `info.meta version == 2` → `meta_version=2`. Single-file: a synthetic one-entry file-list `[(info.name, info.length)]`. Guard against the existing `_MAX_BENCODE_DEPTH` (100). New function signature:

```python
def parse_torrent_layout(data: bytes) -> TorrentLayout:
    """Parse a .torrent's ``info`` dict into a :class:`TorrentLayout`.

    Args:
        data: Raw .torrent file bytes (full bencode).

    Returns:
        A populated TorrentLayout.

    Raises:
        ValueError: Malformed bencode, missing required keys, or nesting
            beyond the depth cap.
    """
```

## Sub-phase 1.3 — structural_match pure function

**Files:**

- Modify: `personalscraper/api/torrent/_layout.py` (add `structural_match()`)

```python
def structural_match(local: TorrentLayout, candidate: TorrentLayout) -> MatchVerdict:
    """Full-match strict comparator (DESIGN D4).

    Returns MATCH only when piece_length, file-list (relative paths + sizes
    + order), and root name are all identical.  Rejects v2/hybrid candidates.

    Args:
        local: The source torrent's layout (from the local qBit copy).
        candidate: The remotely-fetched candidate's layout.

    Returns:
        ``MatchVerdict.MATCH`` or the first mismatch reason encountered,
        in priority order: v2_hybrid → piece_length → root_name → file_list.
    """
```

Checks in order: `candidate.meta_version == 2` → `V2_HYBRID`; `local.piece_length != candidate.piece_length` → `PIECE_LENGTH_MISMATCH`; `local.name != candidate.name` → `ROOT_NAME_MISMATCH`; file-list length mismatch or any `(path, size)` pair differs → `FILE_LIST_MISMATCH`; else `MATCH`.

## Sub-phase 1.4 — golden fixture tests

**Files:**

- Create: `tests/unit/test_torrent_layout.py`
- Create: `tests/unit/fixtures/torrent_layout/` (directory for real `.torrent` files)

Collect **3+ real `.torrent` files** from qBittorrent's `BT_backup/` on the production host — must include: a single-file torrent, a multi-file torrent, and a multi-file torrent with nested directories (e.g. `Season 01/` + `Season 02/` subdirs). Drop them in the fixture dir. Write tests:

```python
"""Golden + adversarial tests for parse_torrent_layout + structural_match."""

from pathlib import Path

import pytest

from personalscraper.api.torrent._base import parse_torrent_layout
from personalscraper.api.torrent._layout import MatchVerdict, structural_match

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "torrent_layout"


class TestParseTorrentLayout:
    """Golden-file tests for the layout parser."""

    FILES = sorted(FIXTURE_DIR.glob("*.torrent"))

    @pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
    def test_parses_real_torrent(self, path: Path) -> None:
        """Every real .torrent fixture parses without error."""
        data = path.read_bytes()
        layout = parse_torrent_layout(data)
        assert layout.name
        assert layout.piece_length > 0
        assert layout.files
        assert layout.total_size > 0
        # Every file entry has a non-empty rel path and positive size.
        for rel_path, size in layout.files:
            assert rel_path, f"empty rel_path in {path.name}"
            assert size > 0, f"zero-size file in {path.name}: {rel_path}"

    def test_single_file_fixture_has_synthetic_filelist(self) -> None:
        """A single-file .torrent yields one-entry file-list with info.name."""
        path = FIXTURE_DIR / "single_file.torrent"
        if not path.exists():
            pytest.skip("fixture not present")
        layout = parse_torrent_layout(path.read_bytes())
        assert len(layout.files) == 1
        assert layout.files[0][0] == layout.name
        assert layout.files[0][1] == layout.total_size
```

## Sub-phase 1.5 — adversarial parse + v2/hybrid tests

**Files:**

- Modify: `tests/unit/test_torrent_layout.py` (extend)

Tests for:

- Corrupted bencode (truncated mid-integer → `ValueError`; empty bytes → `ValueError`).
- Missing `info.name`, `info.piece length`, or `info.files`/`info.length` → `ValueError`.
- Deep nesting past `_MAX_BENCODE_DEPTH` → `ValueError` (craft a deeply nested dict).
- BitTorrent v2/hybrid: a `.torrent` with `info.meta version = 2` → `layout.meta_version == 2`.

```python
def test_truncated_bencode_raises_valueerror(self) -> None:
    with pytest.raises(ValueError):
        parse_torrent_layout(b"di1e")  # missing 'e' for dict

def test_missing_info_name_raises_valueerror(self) -> None:
    # dict with 'info' but no 'name' inside it
    data = b"d4:infod12:piece lengthi262144e6:pieces0:e"
    with pytest.raises(ValueError):
        parse_torrent_layout(data)

def test_v2_hybrid_detected(self) -> None:
    # A valid v1 dict + meta version = 2 inside info
    data = b"d4:infod4:name5:test412:piece lengthi262144e12:meta versioni2e6:pieces0:ee"
    layout = parse_torrent_layout(data)
    assert layout.meta_version == 2
```

## Sub-phase 1.6 — structural_match unit tests

**Files:**

- Create: `tests/unit/test_structural_match.py`

```python
from personalscraper.api.torrent._layout import MatchVerdict, TorrentLayout, structural_match


BASE = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
)

IDENTICAL = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
)

PIECE_DIFF = TorrentLayout(
    name="Release.Name.2024",
    piece_length=524288,  # different
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
)

NAME_DIFF = TorrentLayout(
    name="Release.Name.2024.REPACK",  # renamed root
    piece_length=262144,
    files=[("Release.Name.2024.REPACK.mkv", 1_000_000)],
    total_size=1_000_000,
)

EXTRA_FILE = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000), ("Sample.mkv", 50_000)],  # extra
    total_size=1_050_000,
)

V2_HYBRID = TorrentLayout(
    name="Release.Name.2024",
    piece_length=262144,
    files=[("Release.Name.2024.mkv", 1_000_000)],
    total_size=1_000_000,
    meta_version=2,
)


class TestStructuralMatch:
    def test_identical_is_match(self) -> None:
        assert structural_match(BASE, IDENTICAL) == MatchVerdict.MATCH

    def test_piece_length_diff_rejected(self) -> None:
        assert structural_match(BASE, PIECE_DIFF) == MatchVerdict.PIECE_LENGTH_MISMATCH

    def test_root_name_diff_rejected(self) -> None:
        assert structural_match(BASE, NAME_DIFF) == MatchVerdict.ROOT_NAME_MISMATCH

    def test_extra_file_rejected(self) -> None:
        assert structural_match(BASE, EXTRA_FILE) == MatchVerdict.FILE_LIST_MISMATCH

    def test_v2_hybrid_rejected(self) -> None:
        assert structural_match(BASE, V2_HYBRID) == MatchVerdict.V2_HYBRID

    def test_symmetric(self) -> None:
        assert structural_match(BASE, IDENTICAL) == structural_match(IDENTICAL, BASE)
```

## Gate check (before advancing to Phase 2)

- [ ] `make lint` — ruff + mypy: 0 errors.
- [ ] `python -m pytest tests/unit/test_torrent_layout.py tests/unit/test_structural_match.py -q` — all pass.
- [ ] ACC-1 + ACC-2 pass (validated via `make test` at phase end — the full-suite check waits for Phase 9, but the targeted test files must be green now).
- [ ] `personalscraper/api/torrent/_layout.py` exists and is importable.
- [ ] Module under 200 LOC (small data model + pure function).
