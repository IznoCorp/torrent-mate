# Phase 10: Foundation — Public API, Models, Invariants

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Promote private scanner functions to public API, add rescrape result models with action constants, add `ValidationItem.__post_init__` enforcement.

**Architecture:** Rename `_extract_nfo_ids` → `extract_nfo_ids` and `_parse_title_year` → `parse_title_year` in scanner.py, update all 4 consumers. Add `RescrapeAction` + `LibraryRescrapeResult` to models.py with `__post_init__` invariants. Add `ValidationItem.__post_init__` for status/errors/fixes consistency.

**Tech Stack:** Python, dataclasses, pytest

---

## Task 1: Promote scanner private functions to public API

**Files:**

- Modify: `personalscraper/library/scanner.py`
- Modify: `personalscraper/library/validator.py`
- Modify: `personalscraper/library/analyzer.py`
- Modify: `tests/library/test_scanner.py`

- [ ] **Step 1: Rename functions in scanner.py**

In `personalscraper/library/scanner.py`, rename:

- `_parse_title_year` → `parse_title_year` (remove leading underscore)
- `_extract_nfo_ids` → `extract_nfo_ids` (remove leading underscore)

Also update the internal references within scanner.py (calls to these functions in `scan_movie_dir` and `scan_tvshow_dir`).

- [ ] **Step 2: Update imports in validator.py**

In `personalscraper/library/validator.py`, change:

```python
from personalscraper.library.scanner import _SERIES_CATEGORIES, _parse_title_year
```

to:

```python
from personalscraper.library.scanner import _SERIES_CATEGORIES, parse_title_year
```

Update the call site (line 81): `_parse_title_year(media_dir.name)` → `parse_title_year(media_dir.name)`

- [ ] **Step 3: Update imports in analyzer.py**

In `personalscraper/library/analyzer.py`, change:

```python
from personalscraper.library.scanner import _SERIES_CATEGORIES, _VIDEO_EXTENSIONS, _parse_title_year
```

to:

```python
from personalscraper.library.scanner import _SERIES_CATEGORIES, _VIDEO_EXTENSIONS, parse_title_year
```

Update the call site: `_parse_title_year(media_dir.name)` → `parse_title_year(media_dir.name)`

- [ ] **Step 4: Update test imports**

In `tests/library/test_scanner.py`, if any test references `_parse_title_year` or `_extract_nfo_ids` directly, update the import.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass (pure rename, no behavior change)

- [ ] **Step 6: Commit**

```bash
git add personalscraper/library/scanner.py personalscraper/library/validator.py personalscraper/library/analyzer.py tests/library/test_scanner.py
git commit -m "v14.10.1: Promote scanner parse_title_year and extract_nfo_ids to public API"
```

---

## Task 2: Add rescrape models and action constants

**Files:**

- Modify: `personalscraper/library/models.py`
- Modify: `tests/library/test_models.py`

- [ ] **Step 1: Write failing tests for new models**

Add to `tests/library/test_models.py`:

```python
from personalscraper.library.models import (
    ACTION_NFO_REGENERATED,
    ACTION_ARTWORK_DOWNLOADED,
    ACTION_EPISODES_RENAMED,
    SKIP_NO_MATCH,
    LibraryRescrapeResult,
    RescrapeAction,
)


class TestRescrapeAction:
    """Tests for RescrapeAction model."""

    def test_valid_action(self) -> None:
        """Action with valid fields should work."""
        action = RescrapeAction(
            path="/tmp/Movie (2024)", title="Movie", media_type="movie",
            disk="Disk1", category="films",
            actions_taken=[ACTION_NFO_REGENERATED],
            actions_skipped=[], errors=[],
            tmdb_id="123", id_source="nfo", match_confidence=None,
            rescraped_at="2026-04-17T12:00:00",
        )
        assert action.tmdb_id == "123"
        assert action.id_source == "nfo"

    def test_invalid_media_type_raises(self) -> None:
        """Invalid media_type should raise ValueError."""
        with pytest.raises(ValueError, match="media_type"):
            RescrapeAction(
                path="/tmp/X", title="X", media_type="audiobook",
                disk="Disk1", category="films",
                actions_taken=["test"], actions_skipped=[], errors=[],
                tmdb_id=None, id_source=None, match_confidence=None,
            )

    def test_confidence_out_of_range_raises(self) -> None:
        """Confidence > 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="match_confidence"):
            RescrapeAction(
                path="/tmp/X", title="X", media_type="movie",
                disk="Disk1", category="films",
                actions_taken=["test"], actions_skipped=[], errors=[],
                tmdb_id="1", id_source="api_match", match_confidence=95.0,
            )

    def test_no_tmdb_clears_confidence(self) -> None:
        """If tmdb_id is None, confidence should be cleared."""
        action = RescrapeAction(
            path="/tmp/X", title="X", media_type="movie",
            disk="Disk1", category="films",
            actions_taken=[], actions_skipped=[SKIP_NO_MATCH], errors=[],
            tmdb_id=None, id_source=None, match_confidence=0.5,
        )
        assert action.match_confidence is None


class TestLibraryRescrapeResult:
    """Tests for LibraryRescrapeResult container."""

    def test_valid_result(self) -> None:
        """Result with valid fields."""
        result = LibraryRescrapeResult(
            rescraped_at="2026-04-17T12:00:00",
            disk_filter=None, category_filter=None, only_filter=None,
            dry_run=True, fixed_count=0, skipped_count=0, error_count=0,
        )
        assert result.dry_run is True

    def test_invalid_only_filter_raises(self) -> None:
        """Invalid only_filter should raise ValueError."""
        with pytest.raises(ValueError, match="only_filter"):
            LibraryRescrapeResult(
                rescraped_at="2026-04-17T12:00:00",
                disk_filter=None, category_filter=None, only_filter="invalid",
                dry_run=True, fixed_count=0, skipped_count=0, error_count=0,
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_models.py::TestRescrapeAction -v`
Expected: FAIL — classes not defined

- [ ] **Step 3: Implement models**

Add to `personalscraper/library/models.py` (after `LibraryRecommendationResult`, before JSON helpers):

```python
# --- Rescrape action constants ---

ACTION_NFO_REGENERATED = "nfo_regenerated"
ACTION_ARTWORK_DOWNLOADED = "artwork_downloaded"
ACTION_EPISODES_RENAMED = "episodes_renamed"
SKIP_LOW_CONFIDENCE = "low_confidence_match"
SKIP_NO_MATCH = "no_match"
SKIP_ALREADY_OK = "already_conforming"

_VALID_ONLY_FILTERS = {"nfo", "artwork", "episodes"}


@dataclass
class RescrapeAction:
    """Single repair action taken on a media item.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        title: Media title.
        media_type: "movie" or "tvshow".
        disk: Disk name.
        category: Category name.
        actions_taken: List of action constants performed.
        actions_skipped: List of skip reason constants.
        errors: Per-item errors (API failure, NTFS write error, etc.).
        tmdb_id: TMDB ID used for API calls (str for JSON, converted from int).
        id_source: How the ID was obtained: "nfo" or "api_match".
        match_confidence: Match confidence 0.0-1.0 (None if ID from NFO).
        rescraped_at: ISO 8601 timestamp of this action.
    """

    path: str
    title: str
    media_type: str
    disk: str
    category: str
    actions_taken: list[str]
    actions_skipped: list[str]
    errors: list[str]
    tmdb_id: str | None
    id_source: str | None
    match_confidence: float | None
    rescraped_at: str = ""

    def __post_init__(self) -> None:
        """Enforce media_type and confidence constraints."""
        if self.media_type not in ("movie", "tvshow"):
            raise ValueError(f"media_type must be 'movie' or 'tvshow', got '{self.media_type}'")
        if self.match_confidence is not None and not (0.0 <= self.match_confidence <= 1.0):
            raise ValueError(f"match_confidence must be 0.0-1.0, got {self.match_confidence}")
        if self.tmdb_id is None and self.match_confidence is not None:
            self.match_confidence = None


@dataclass
class LibraryRescrapeResult:
    """Top-level container for library_rescrape.json.

    Attributes:
        rescraped_at: ISO 8601 timestamp of rescrape start.
        disk_filter: Disk filter applied (None = all disks).
        category_filter: Category filter applied (None = all).
        only_filter: Action filter ("nfo", "artwork", "episodes", or None = all).
        dry_run: Whether this was a dry-run (no actual changes).
        fixed_count: Items successfully repaired.
        skipped_count: Items skipped (low confidence, already OK, etc.).
        error_count: Items with errors.
        items: List of per-item rescrape actions.
    """

    rescraped_at: str
    disk_filter: str | None
    category_filter: str | None
    only_filter: str | None
    dry_run: bool
    fixed_count: int
    skipped_count: int
    error_count: int
    items: list[RescrapeAction] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate only_filter."""
        if self.only_filter is not None and self.only_filter not in _VALID_ONLY_FILTERS:
            raise ValueError(f"only_filter must be one of {_VALID_ONLY_FILTERS} or None")
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_models.py -v -k "Rescrape"`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/models.py tests/library/test_models.py
git commit -m "v14.10.2: Add RescrapeAction, LibraryRescrapeResult models with invariants"
```

---

## Task 3: Add ValidationItem.**post_init** enforcement

**Files:**

- Modify: `personalscraper/library/models.py`
- Modify: `tests/library/test_models.py`
- Modify: `personalscraper/library/validator.py` (fix status="blocked" leftover)

- [ ] **Step 1: Write failing tests**

Add to `tests/library/test_models.py`:

```python
class TestValidationItemInvariant:
    """Tests for ValidationItem.__post_init__ enforcement."""

    def test_valid_status_accepted(self) -> None:
        """Valid status values should be accepted."""
        for status in ("valid", "fixed", "issues"):
            item = ValidationItem(
                path="/tmp/X", disk="Disk1", category="films",
                media_type="movie", title="X", year=2024,
                status=status,
                errors=["err"] if status == "issues" else [],
                fixes_applied=["fix"] if status == "fixed" else [],
            )
            assert item.status == status

    def test_invalid_status_raises(self) -> None:
        """Unknown status should raise ValueError."""
        with pytest.raises(ValueError, match="status"):
            ValidationItem(
                path="/tmp/X", disk="Disk1", category="films",
                media_type="movie", title="X", year=2024,
                status="blocked",
            )

    def test_fixed_without_fixes_raises(self) -> None:
        """status='fixed' with empty fixes_applied should raise."""
        with pytest.raises(ValueError, match="fixes_applied"):
            ValidationItem(
                path="/tmp/X", disk="Disk1", category="films",
                media_type="movie", title="X", year=2024,
                status="fixed", fixes_applied=[],
            )

    def test_valid_with_errors_raises(self) -> None:
        """status='valid' with errors should raise."""
        with pytest.raises(ValueError, match="valid"):
            ValidationItem(
                path="/tmp/X", disk="Disk1", category="films",
                media_type="movie", title="X", year=2024,
                status="valid", errors=["nfo_present"],
            )
```

- [ ] **Step 2: Run to verify failures**

Run: `python -m pytest tests/library/test_models.py::TestValidationItemInvariant -v`
Expected: FAIL — no `__post_init__` on ValidationItem

- [ ] **Step 3: Add **post_init** to ValidationItem**

In `personalscraper/library/models.py`, add to `ValidationItem`:

```python
_VALID_VALIDATION_STATUSES = {"valid", "fixed", "issues"}

# Add inside the ValidationItem class:
    def __post_init__(self) -> None:
        """Enforce status/errors/fixes_applied consistency."""
        if self.status not in _VALID_VALIDATION_STATUSES:
            raise ValueError(f"status must be one of {_VALID_VALIDATION_STATUSES}, got '{self.status}'")
        if self.status == "fixed" and not self.fixes_applied:
            raise ValueError("status='fixed' requires non-empty fixes_applied")
        if self.status == "valid" and (self.errors or self.fixes_applied):
            raise ValueError("status='valid' must have empty errors and fixes_applied")
```

- [ ] **Step 4: Fix validator.py status="blocked" leftover**

In `personalscraper/library/validator.py`, the OSError handler at line 94 still uses `status="blocked"`. Change to `status="issues"`:

```python
                    items.append(ValidationItem(
                        path=str(media_dir), disk=config.name,
                        category=category_dir.name,
                        media_type="tvshow" if is_series else "movie",
                        title=title, year=year, status="issues",
                        errors=[f"os_error: {exc}"],
                    ))
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/library/models.py personalscraper/library/validator.py tests/library/test_models.py
git commit -m "v14.10.3: Add ValidationItem.__post_init__ enforcement for status consistency"
```

---

## Acceptance Criteria — Phase 10

- [ ] `parse_title_year` and `extract_nfo_ids` are public functions (no underscore)
- [ ] All existing imports updated (validator, analyzer, scanner internal calls)
- [ ] `RescrapeAction` enforces media_type and confidence invariants
- [ ] `LibraryRescrapeResult` validates only_filter
- [ ] `ValidationItem.__post_init__` rejects invalid status/errors/fixes combinations
- [ ] No "blocked" status anywhere in validator.py
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
