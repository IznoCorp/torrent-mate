# Phase 4 — State tracking (`state.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement DESIGN §7 (State tracking) in full. Create
`personalscraper/trailers/state.py` with: `TrailerState` dataclass, `TrailerStateStore`
(JSON persistence at `.data/trailers_state.json`), composite key scheme, `TrailerStatus`
enum, retry-after progression policy, auto-GC lifecycle, and the should-skip lookup helper.
Tests use tmpdir with fake media trees.

**Architecture:** `TrailerStateStore` wraps a single JSON file. `auto_gc()` runs at the
start of every `trailers` command/step. Retry-after respects DESIGN §7's explicit progression:
`config.trailers.retry_after_days[min(attempts-1, len-1)]`.

**Tech Stack:** Python, `dataclasses`, `datetime`, `json`, `hashlib`, `pytest`.

---

## Gate (entry condition)

Phases 3a and 3c must be complete:

```bash
python -c "from personalscraper.trailers.placement import trailer_exists; print('OK')"
```

---

## Dependencies

- Phase 3a (composite key scheme uses media type vocabulary from TrailerFinder)
- Phase 3c (placement module defines the `trailers/` subdirectory structure relied on by GC)

---

## Invariants for this phase

- State file is written atomically (temp + os.replace — same pattern as `JsonTTLCache`).
- `TrailerStateStore` never mutates state entries in-place — always read-modify-write.
- All timestamps stored as UTC ISO 8601 strings.
- `bot_detected` status is exempt from retry-after (always retried on next run).

---

## Sub-phase 4.1 — Data model: `TrailerStatus` + `TrailerState` + key helpers

### Files

| Action | Path                                | Responsibility                          |
| ------ | ----------------------------------- | --------------------------------------- |
| Create | `personalscraper/trailers/state.py` | Full state module (built incrementally) |
| Create | `tests/trailers/test_state.py`      | Unit tests                              |

### Step 1: Write failing tests for data model

Create `tests/trailers/test_state.py`:

```python
"""Unit tests for trailers/state.py — state tracking for trailer downloads.

Uses tmpdir-based fixtures to avoid touching the real .data/ directory.
All timestamps are in UTC ISO 8601.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from personalscraper.trailers.state import (
    TrailerState,
    TrailerStateStore,
    TrailerStatus,
    make_state_key,
)


# ── make_state_key ────────────────────────────────────────────────────────────

class TestMakeStateKey:
    def test_movie_tmdb_key(self):
        assert make_state_key("movie", "tmdb", 550) == "movie:tmdb:550"

    def test_tv_tmdb_key(self):
        assert make_state_key("tv", "tmdb", 1399) == "tv:tmdb:1399"

    def test_movie_tvdb_key(self):
        assert make_state_key("movie", "tvdb", 12345) == "movie:tvdb:12345"

    def test_manual_key_hashes_title_year_type(self):
        """Manual keys hash (title, year, media_type) — NOT the on-disk path.

        Paths move frequently (dispatch merge/replace rules; re-scrape renames
        folders to canonical titles). Hashing title+year+type yields a stable
        key across those moves, closing the reviewer-flagged regression where
        a rename spawned a duplicate state entry.

        The title is normalized before hashing — see
        ``test_manual_key_normalizes_title`` for the full pipeline
        (Unicode NFC + casefold + whitespace collapse). So the expected
        digest is computed from the NORMALIZED string, not from the raw input.
        """
        import unicodedata
        manual_id = ("Fight Club", 1999, "movie")
        # Same normalization the implementation must apply before hashing:
        # 1. unicodedata.normalize("NFC", title)
        # 2. casefold()
        # 3. collapse runs of whitespace to a single space; strip
        normalized_title = " ".join(
            unicodedata.normalize("NFC", "Fight Club").casefold().split()
        )
        payload = f"{normalized_title}|1999|movie"
        digest = hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()
        key = make_state_key("movie", "manual", manual_id)
        assert key == f"manual:{digest}"

    def test_manual_key_is_path_independent(self):
        """Re-scrape that renames the folder must NOT change the manual key."""
        manual_id = ("Fight Club", 1999, "movie")
        k1 = make_state_key("movie", "manual", manual_id)
        k2 = make_state_key("movie", "manual", manual_id)
        assert k1 == k2

    def test_manual_key_normalizes_title(self):
        """Title is NFC-normalized and casefolded before hashing — stable across scrape runs."""
        a = make_state_key("movie", "manual", ("The Wire", 2002, "tv"))
        b = make_state_key("movie", "manual", ("the  wire", 2002, "tv"))  # extra space + case
        assert a == b

    def test_key_format_is_consistent(self):
        k1 = make_state_key("movie", "tmdb", 550)
        k2 = make_state_key("movie", "tmdb", 550)
        assert k1 == k2


# ── TrailerStatus enum ────────────────────────────────────────────────────────

class TestTrailerStatus:
    def test_all_statuses_defined(self):
        statuses = {s.value for s in TrailerStatus}
        expected = {
            "downloaded", "no_trailer_available", "bot_detected",
            "http_error", "ytdlp_error", "skipped_by_filter", "orphan",
        }
        assert statuses == expected


# ── TrailerState dataclass ────────────────────────────────────────────────────

class TestTrailerState:
    def test_create_basic_state(self):
        now = datetime.now(UTC)
        state = TrailerState(
            last_attempt=now.isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/Volumes/DISK_A/movies/Fight Club (1999)",
        )
        assert state.attempts == 1
        assert state.status == TrailerStatus.DOWNLOADED


# ── TrailerStateStore ─────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path: Path) -> TrailerStateStore:
    return TrailerStateStore(state_file=tmp_path / "trailers_state.json")


class TestTrailerStateStore:
    def test_missing_file_returns_no_entries(self, store):
        """get() returns None when the state file does not exist."""
        assert store.get("movie:tmdb:550") is None

    def test_set_then_get_round_trip(self, store):
        """get() returns state previously written with set()."""
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/fake/path",
            trailer_path="/fake/path/movie-trailer.mp4",
            youtube_url="https://www.youtube.com/watch?v=test",
        )
        store.set("movie:tmdb:550", state)
        result = store.get("movie:tmdb:550")
        assert result is not None
        assert result.status == TrailerStatus.DOWNLOADED
        assert result.attempts == 1

    def test_state_file_has_version_field(self, store, tmp_path):
        """The written JSON file contains a top-level 'version' field."""
        import json
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/fake",
        )
        store.set("movie:tmdb:1", state)
        raw = json.loads((tmp_path / "trailers_state.json").read_text())
        assert raw["version"] == 1

    def test_get_nonexistent_key_returns_none(self, store):
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/fake",
        )
        store.set("movie:tmdb:1", state)
        assert store.get("movie:tmdb:999") is None


# ── retry-after logic ─────────────────────────────────────────────────────────

class TestShouldSkip:
    def test_skip_when_no_trailer_available_and_not_expired(self, store):
        """should_skip returns True when status=no_trailer_available and next_retry_at is future."""
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=2,
            status=TrailerStatus.NO_TRAILER_AVAILABLE,
            media_path="/fake",
            next_retry_at=future,
        )
        store.set("movie:tmdb:550", state)
        assert store.should_skip("movie:tmdb:550") is True

    def test_no_skip_when_retry_expired(self, store):
        """should_skip returns False when next_retry_at is in the past."""
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=2,
            status=TrailerStatus.NO_TRAILER_AVAILABLE,
            media_path="/fake",
            next_retry_at=past,
        )
        store.set("movie:tmdb:550", state)
        assert store.should_skip("movie:tmdb:550") is False

    def test_bot_detected_never_skipped(self, store):
        """should_skip returns False for bot_detected regardless of next_retry_at."""
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=1,
            status=TrailerStatus.BOT_DETECTED,
            media_path="/fake",
            next_retry_at=future,
        )
        store.set("movie:tmdb:550", state)
        assert store.should_skip("movie:tmdb:550") is False

    def test_missing_key_not_skipped(self, store):
        """should_skip returns False for unknown keys (first run)."""
        assert store.should_skip("movie:tmdb:99999") is False

    def test_retry_after_progression(self):
        """compute_next_retry returns days from [1, 7, 30] based on attempt count."""
        from personalscraper.trailers.state import compute_next_retry_at
        policy = [1, 7, 30]
        now = datetime.now(UTC)
        r1 = compute_next_retry_at(attempts=1, policy=policy, now=now)
        r2 = compute_next_retry_at(attempts=2, policy=policy, now=now)
        r3 = compute_next_retry_at(attempts=3, policy=policy, now=now)
        r4 = compute_next_retry_at(attempts=4, policy=policy, now=now)
        assert (r1 - now).days == 1
        assert (r2 - now).days == 7
        assert (r3 - now).days == 30
        assert (r4 - now).days == 30  # last element repeats


# ── auto-GC ───────────────────────────────────────────────────────────────────

class TestAutoGC:
    def test_gc_marks_orphan_when_media_path_missing(self, store, tmp_path):
        """auto_gc flips status to orphan when media_path no longer exists."""
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(tmp_path / "Media That Was Deleted"),
            trailer_path=str(tmp_path / "Media That Was Deleted" / "trailer.mp4"),
        )
        store.set("movie:tmdb:1", state)
        store.auto_gc()
        result = store.get("movie:tmdb:1")
        assert result is not None
        assert result.status == TrailerStatus.ORPHAN

    def test_gc_removes_entry_when_trailer_deleted(self, store, tmp_path):
        """auto_gc removes downloaded entries whose trailer_path is gone."""
        media = tmp_path / "Movie (2020)"
        media.mkdir()
        trailer = media / "Movie (2020)-trailer.mp4"
        # Do NOT create the trailer file — it was deleted
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(media),
            trailer_path=str(trailer),
        )
        store.set("movie:tmdb:2", state)
        store.auto_gc()
        # Entry is removed so the trailer can be re-downloaded
        assert store.get("movie:tmdb:2") is None

    def test_gc_leaves_valid_entries_intact(self, store, tmp_path):
        """auto_gc does not modify entries with existing media and trailer."""
        media = tmp_path / "Good Movie (2020)"
        media.mkdir()
        trailer = media / "Good Movie (2020)-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)
        state = TrailerState(
            last_attempt=datetime.now(UTC).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(media),
            trailer_path=str(trailer),
        )
        store.set("movie:tmdb:3", state)
        store.auto_gc()
        result = store.get("movie:tmdb:3")
        assert result is not None
        assert result.status == TrailerStatus.DOWNLOADED
```

### Step 2: Implement `personalscraper/trailers/state.py`

**Enum and dataclass:**

```python
class TrailerStatus(Enum):
    DOWNLOADED = "downloaded"
    NO_TRAILER_AVAILABLE = "no_trailer_available"
    BOT_DETECTED = "bot_detected"
    HTTP_ERROR = "http_error"
    YTDLP_ERROR = "ytdlp_error"
    SKIPPED_BY_FILTER = "skipped_by_filter"
    ORPHAN = "orphan"

@dataclass
class TrailerState:
    last_attempt: str        # UTC ISO 8601
    attempts: int
    status: TrailerStatus
    media_path: str
    next_retry_at: str | None = None
    trailer_path: str | None = None
    source: str | None = None       # "tmdb" or "youtube"
    youtube_url: str | None = None
    notes: str | None = None
```

**Key functions:**

```python
def make_state_key(media_type: str, id_kind: str, id_value: int | str) -> str:
    """Build a composite state key. id_kind="manual" hashes id_value as a path."""

def compute_next_retry_at(attempts: int, policy: list[int], now: datetime) -> datetime:
    """Return next retry datetime using policy[min(attempts-1, len(policy)-1)]."""
```

**`TrailerStateStore`:**

| Method        | Signature                                 | Description                                        |
| ------------- | ----------------------------------------- | -------------------------------------------------- |
| `__init__`    | `(state_file: Path)`                      | Initialize with path to JSON state file            |
| `get`         | `(key: str) -> TrailerState \| None`      | Load + deserialize entry by key                    |
| `set`         | `(key: str, state: TrailerState) -> None` | Atomic write (temp + os.replace)                   |
| `should_skip` | `(key: str) -> bool`                      | Skip logic per DESIGN §7 (bot_detected exempt)     |
| `auto_gc`     | `() -> None`                              | Lifecycle check: flip orphan, remove gone trailers |
| `all_entries` | `() -> dict[str, TrailerState]`           | Load all entries (for CLI scan/purge)              |

**JSON on-disk structure** (per DESIGN §7):

```json
{"version": 1, "entries": {"movie:tmdb:550": {...}}}
```

### Step 3: Run tests — all must pass

```bash
pytest tests/trailers/test_state.py -v
```

### Step 4: Commit sub-phase 4.1

```bash
git add personalscraper/trailers/state.py tests/trailers/test_state.py
git commit -m "feat(trailer): add TrailerStateStore with composite keys, retry policy, and auto-GC"
```

---

## Phase 4 quality gate

- [ ] `pytest tests/trailers/test_state.py -q` — all green
- [ ] `pytest tests/ -q` — no regressions
- [ ] `python -m ruff check personalscraper/trailers/state.py` — no errors
- [ ] `python -m mypy personalscraper/trailers/state.py` — no type errors

```bash
cd "$(git rev-parse --show-toplevel)"
pytest tests/trailers/test_state.py -q
pytest tests/ -q
python -m ruff check personalscraper/trailers/state.py
python -m mypy personalscraper/trailers/state.py
```

## Milestone commit

```bash
git commit --allow-empty -m "chore(trailer): phase 04 gate — state tracking with composite keys and retry policy"
```

## Exit condition for Phase 5 and Phase 6

Phases 5 and 6 may start only when:

- `TrailerStateStore`, `TrailerStatus`, `TrailerState`, `make_state_key` importable
- `pytest tests/trailers/ -q` exits 0
- The milestone commit is on the branch
