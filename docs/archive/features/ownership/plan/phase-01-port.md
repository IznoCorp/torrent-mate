# Phase 1 — Core port

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `personalscraper/core/ownership.py` with the `OwnershipChecker` `@runtime_checkable` Protocol and `NullOwnershipChecker` (fail-open default), plus unit tests.

**Architecture:** This phase mirrors `personalscraper/core/delete_permit.py` exactly — a neutral, stdlib-only port living in `core/`. `acquire/` will import only this port, never `indexer/`. `NullOwnershipChecker` returns `False` on every call so that a wanted item is never silently skipped when no library is wired (fail-open: "not owned" is the safe default).

**Tech Stack:** Python 3.12, `typing.Protocol`, `@runtime_checkable`, `dataclasses.dataclass(frozen=True)`, pytest.

---

## Gate — what this phase requires

- `personalscraper/core/identity.py::MediaRef` exists (tvdb_id, tmdb_id, imdb_id optional fields). **Verify:**
  ```bash
  python -c "from personalscraper.core.identity import MediaRef; print(MediaRef(tvdb_id=1))"
  ```
  Expected: prints `MediaRef(tvdb_id=1, tmdb_id=None, imdb_id=None)`.

---

## File map

| Action     | Path                                |
| ---------- | ----------------------------------- |
| **Create** | `personalscraper/core/ownership.py` |
| **Create** | `tests/core/test_ownership.py`      |

**Do NOT touch** `personalscraper/core/delete_permit.py` — read it only as a pattern reference.

---

## Task 1.1 — Write the failing tests

**Files:**

- Create: `tests/core/test_ownership.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for core.ownership: OwnershipChecker Protocol + NullOwnershipChecker."""

from __future__ import annotations

from personalscraper.core.identity import MediaRef
from personalscraper.core.ownership import NullOwnershipChecker, OwnershipChecker


def test_null_checker_always_returns_false() -> None:
    """NullOwnershipChecker.owns always returns False (fail-open default)."""
    checker = NullOwnershipChecker()
    ref = MediaRef(tvdb_id=12345)
    assert checker.owns(ref, kind="movie") is False


def test_null_checker_episode_always_returns_false() -> None:
    """NullOwnershipChecker returns False for episode kind with season/episode args."""
    checker = NullOwnershipChecker()
    ref = MediaRef(tvdb_id=99)
    assert checker.owns(ref, kind="episode", season=1, episode=3) is False


def test_null_checker_tmdb_only_ref_returns_false() -> None:
    """NullOwnershipChecker returns False even for a tmdb-only MediaRef."""
    checker = NullOwnershipChecker()
    ref = MediaRef(tmdb_id=555)
    assert checker.owns(ref, kind="movie") is False


def test_null_checker_imdb_only_ref_returns_false() -> None:
    """NullOwnershipChecker returns False for an imdb-only MediaRef."""
    checker = NullOwnershipChecker()
    ref = MediaRef(imdb_id="tt0000001")
    assert checker.owns(ref, kind="movie") is False


def test_null_checker_implements_protocol() -> None:
    """NullOwnershipChecker satisfies the OwnershipChecker runtime-checkable Protocol."""
    checker = NullOwnershipChecker()
    assert isinstance(checker, OwnershipChecker)
```

- [ ] **Step 2: Run the tests — they must FAIL (module does not exist yet)**

```bash
pytest tests/core/test_ownership.py -v --tb=short
```

Expected: `ModuleNotFoundError: No module named 'personalscraper.core.ownership'` (or similar import error — all 5 tests fail at collection).

---

## Task 1.2 — Implement `core/ownership.py`

**Files:**

- Create: `personalscraper/core/ownership.py`

- [ ] **Step 3: Write the module**

Pattern reference: `personalscraper/core/delete_permit.py` — same `from __future__ import annotations`, stdlib-only imports, `@runtime_checkable`, frozen-dataclass null impl, `__all__`.

```python
"""Neutral ownership-checker port (RP6).

Import direction: stdlib + typing only (mirrors core/delete_permit.py).
Never imported by indexer/ at the top level — inject via the composition root.

The acquire lobe depends ONLY on these core port types. The concrete
IndexerOwnershipChecker implementation (indexer/ownership.py) is injected
at the composition root. This ensures acquire/ never imports indexer/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from personalscraper.core.identity import MediaRef


@runtime_checkable
class OwnershipChecker(Protocol):
    """Protocol for ownership-check implementations.

    An ``OwnershipChecker`` answers "does the library already contain this
    work?" Implementations MUST be fail-open: any lookup error → False
    (not owned). False is only returned on a positively-known live file;
    True means ownership is confirmed.
    """

    def owns(
        self,
        media_ref: "MediaRef",
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Return True iff the library contains a live file for this work.

        Args:
            media_ref: Provider IDs for the work (tvdb primary, tmdb fallback,
                imdb last resort).
            kind: ``"movie"`` or ``"episode"``.
            season: Season number; required when ``kind="episode"``.
            episode: Episode number; required when ``kind="episode"``.

        Returns:
            ``True`` if a live (non-soft-deleted) file exists for the work;
            ``False`` otherwise, including on any lookup error (fail-open).
        """
        ...


class NullOwnershipChecker:
    """Fail-open no-op OwnershipChecker — always returns False.

    Used as the default for tests, for commands when no library.db is
    configured, and as the fallback when the DB connection is unavailable.
    Returning False ("not owned") keeps the pipeline safe: a wanted item
    is never silently skipped because ownership could not be verified.
    """

    def owns(
        self,
        media_ref: "MediaRef",
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Always return False (not owned).

        Args:
            media_ref: Ignored.
            kind: Ignored.
            season: Ignored.
            episode: Ignored.

        Returns:
            Always ``False``.
        """
        return False


__all__ = [
    "NullOwnershipChecker",
    "OwnershipChecker",
]
```

- [ ] **Step 4: Run the tests — they must PASS**

```bash
pytest tests/core/test_ownership.py -v --tb=short
```

Expected: `5 passed`.

- [ ] **Step 5: Verify the layering guard still passes (core/ must not import upward)**

```bash
pytest tests/architecture/test_layering.py::test_core_does_not_import_upward -v --tb=short
```

Expected: `1 passed`.

- [ ] **Step 6: Smoke import**

```bash
python -c "from personalscraper.core.ownership import OwnershipChecker, NullOwnershipChecker; print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/core/ownership.py tests/core/test_ownership.py
git commit -m "feat(ownership): core port — OwnershipChecker Protocol + NullOwnershipChecker"
```
