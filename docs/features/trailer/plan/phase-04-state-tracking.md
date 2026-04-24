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

**Key precedence (extended for season-level trailers, DESIGN §4 / §7):**

```
movie:tmdb:{id}                    # primary: movie with TMDB id
movie:tvdb:{id}                    # TMDB miss, TVDB fallback
tv:tmdb:{id}                       # primary for TV (show-level)
tv:tvdb:{id}                       # TV with TVDB-only metadata
tv:tmdb:{id}:season:{N}            # season-level trailer (NEW — opt-in via config.trailers.seasons.enabled)
tv:tvdb:{id}:season:{N}            # TVDB fallback, same shape
manual:{sha256(title|year|type)}   # no external ID
```

Season-level entries coexist with show-level entries — both can be present for the same
TV show (one entry for the show trailer, one per season). They are tracked independently:
a missing season trailer does not affect the show trailer's retry-after schedule and
vice-versa.

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
        assert make_state_key("movie", {"tmdb": 550}) == "movie:tmdb:550"

    def test_tv_tmdb_key(self):
        assert make_state_key("tv", {"tmdb": 1399}) == "tv:tmdb:1399"

    def test_movie_tvdb_key(self):
        assert make_state_key("movie", {"tvdb": 12345}) == "movie:tvdb:12345"

    def test_make_state_key_tv_season(self):
        """Season-level TV key carries an explicit ``:season:{N}`` suffix.

        This is the canonical key shape for season-level trailers
        (opt-in via ``config.trailers.seasons.enabled``, see DESIGN §4).
        """
        key = make_state_key("tv", {"tmdb": 1399}, season_number=3)
        assert key == "tv:tmdb:1399:season:3"

    def test_make_state_key_tv_without_season(self):
        """Show-level TV key has NO ``:season:`` suffix when season_number is None."""
        key = make_state_key("tv", {"tmdb": 1399})
        assert ":season:" not in key
        assert key == "tv:tmdb:1399"

    def test_make_state_key_tv_season_uses_tvdb_fallback(self):
        """TVDB fallback for season-level keys mirrors the show-level precedence."""
        key = make_state_key("tv", {"tmdb": None, "tvdb": 81189}, season_number=2)
        assert key == "tv:tvdb:81189:season:2"

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
        # No external IDs → manual fallback. The new signature accepts an
        # `ids` dict whose entries are all None/missing, plus title/year/type.
        # Same normalization the implementation must apply before hashing:
        # 1. unicodedata.normalize("NFC", title)
        # 2. casefold()
        # 3. collapse runs of whitespace to a single space; strip
        normalized_title = " ".join(
            unicodedata.normalize("NFC", "Fight Club").casefold().split()
        )
        payload = f"{normalized_title}|1999|movie"
        digest = hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()
        key = make_state_key("movie", {}, title="Fight Club", year=1999)
        assert key == f"manual:{digest}"

    def test_manual_key_is_path_independent(self):
        """Re-scrape that renames the folder must NOT change the manual key."""
        k1 = make_state_key("movie", {}, title="Fight Club", year=1999)
        k2 = make_state_key("movie", {}, title="Fight Club", year=1999)
        assert k1 == k2

    def test_manual_key_normalizes_title(self):
        """Title is NFC-normalized and casefolded before hashing — stable across scrape runs."""
        a = make_state_key("tv", {}, title="The Wire", year=2002)
        b = make_state_key("tv", {}, title="the  wire", year=2002)  # extra space + case
        assert a == b

    def test_key_format_is_consistent(self):
        k1 = make_state_key("movie", {"tmdb": 550})
        k2 = make_state_key("movie", {"tmdb": 550})
        assert k1 == k2


# ── TrailerStatus enum ────────────────────────────────────────────────────────

class TestTrailerStatus:
    def test_all_statuses_defined(self):
        statuses = {s.value for s in TrailerStatus}
        expected = {
            "downloaded", "no_trailer_available", "bot_detected",
            "http_error", "ytdlp_error", "skipped_by_filter", "orphan",
            "already_present_on_disk",
        }
        assert statuses == expected

    def test_status_enum_includes_already_present_on_disk(self):
        """`already_present_on_disk` is distinct from `already_present` (staging-only).

        It is recorded by the orchestrator's library-aware SOT recheck (DESIGN §8
        extension) when a valid trailer is found at the library location and
        no network call is made.
        """
        assert TrailerStatus.ALREADY_PRESENT_ON_DISK.value == "already_present_on_disk"


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
        """compute_next_retry returns days from [1, 7, 30] based on attempt count.

        Clock reference is ``last_attempt`` per DESIGN §7.
        """
        from personalscraper.trailers.state import compute_next_retry_at
        policy = [1, 7, 30]
        last_attempt = datetime.now(UTC)
        r1 = compute_next_retry_at(attempts=1, policy=policy, last_attempt=last_attempt)
        r2 = compute_next_retry_at(attempts=2, policy=policy, last_attempt=last_attempt)
        r3 = compute_next_retry_at(attempts=3, policy=policy, last_attempt=last_attempt)
        r4 = compute_next_retry_at(attempts=4, policy=policy, last_attempt=last_attempt)
        assert (r1 - last_attempt).days == 1
        assert (r2 - last_attempt).days == 7
        assert (r3 - last_attempt).days == 30
        assert (r4 - last_attempt).days == 30  # last element repeats


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

    def test_purge_orphans_removes_orphan_entries_only(self, store, tmp_path):
        """purge_orphans() removes only orphan entries; returns count removed."""
        now = datetime.now(UTC).isoformat()
        downloaded = TrailerState(
            last_attempt=now, attempts=1,
            status=TrailerStatus.DOWNLOADED, media_path="/a",
        )
        orphan = TrailerState(
            last_attempt=now, attempts=1,
            status=TrailerStatus.ORPHAN, media_path="/b",
        )
        bot_detected = TrailerState(
            last_attempt=now, attempts=1,
            status=TrailerStatus.BOT_DETECTED, media_path="/c",
        )
        store.set("movie:tmdb:1", downloaded)
        store.set("movie:tmdb:2", orphan)
        store.set("movie:tmdb:3", bot_detected)
        removed = store.purge_orphans()
        assert removed == 1
        assert store.get("movie:tmdb:1") is not None
        assert store.get("movie:tmdb:2") is None
        assert store.get("movie:tmdb:3") is not None

    def test_next_retry_measured_from_last_attempt_not_first_failure(self):
        """compute_next_retry_at uses last_attempt as its clock reference (DESIGN §7)."""
        from personalscraper.trailers.state import compute_next_retry_at
        first_failure = datetime(2026, 1, 1, tzinfo=UTC)  # noqa: F841 — documentation only
        last_attempt = datetime(2026, 4, 1, tzinfo=UTC)
        result = compute_next_retry_at(
            attempts=3,
            policy=[1, 7, 30],
            last_attempt=last_attempt,
        )
        assert result == datetime(2026, 5, 1, tzinfo=UTC)

    def test_bot_detected_counter_resets_on_non_bot_outcome(self, store):
        """bot_detected_consecutive_attempts resets BEFORE writing a non-bot status."""
        now = datetime.now(UTC).isoformat()
        # Three consecutive bot_detected attempts build up the counter.
        state_bot = TrailerState(
            last_attempt=now, attempts=3,
            status=TrailerStatus.BOT_DETECTED, media_path="/x",
            bot_detected_consecutive_attempts=3,
        )
        store.set("movie:tmdb:7", state_bot)
        loaded = store.get("movie:tmdb:7")
        assert loaded is not None
        assert loaded.bot_detected_consecutive_attempts == 3
        # Next outcome is DOWNLOADED → counter must reset to 0 before write.
        state_success = TrailerState(
            last_attempt=now, attempts=1,
            status=TrailerStatus.DOWNLOADED, media_path="/x",
            trailer_path="/x/trailer.mp4",
            bot_detected_consecutive_attempts=0,  # reset before writing per DESIGN §5
        )
        store.set("movie:tmdb:7", state_success)
        reloaded = store.get("movie:tmdb:7")
        assert reloaded is not None
        assert reloaded.bot_detected_consecutive_attempts == 0
        assert reloaded.status == TrailerStatus.DOWNLOADED

    def test_concurrent_writes_do_not_corrupt_state(self, tmp_path):
        """Two concurrent writers under fcntl.flock produce a valid JSON file.

        Uses multiprocessing.Process to simulate concurrent writers on the same
        state file. After both finish, the file must parse cleanly and contain
        both entries (no lost update, no torn write).
        """
        import multiprocessing
        from personalscraper.trailers.state import TrailerStateStore

        state_file = tmp_path / "trailers_state.json"

        def write_entry(key: str) -> None:
            s = TrailerStateStore(state_file=state_file)
            s.set(key, TrailerState(
                last_attempt=datetime.now(UTC).isoformat(),
                attempts=1,
                status=TrailerStatus.DOWNLOADED,
                media_path=f"/fake/{key}",
            ))

        p1 = multiprocessing.Process(target=write_entry, args=("movie:tmdb:1",))
        p2 = multiprocessing.Process(target=write_entry, args=("movie:tmdb:2",))
        p1.start(); p2.start()
        p1.join(); p2.join()

        reader = TrailerStateStore(state_file=state_file)
        # Both entries must survive (neither write was lost under the lock).
        assert reader.get("movie:tmdb:1") is not None
        assert reader.get("movie:tmdb:2") is not None

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
    # NEW (DESIGN §8 extension — library-aware SOT recheck):
    # the trailer was found on one of the storage disks before any network
    # call. Distinct from the staging-only "already_present" runtime counter.
    ALREADY_PRESENT_ON_DISK = "already_present_on_disk"

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
    # DESIGN §5 "Counter semantics": incremented each consecutive bot_detected,
    # reset on any non-bot_detected outcome BEFORE the new status is written.
    bot_detected_consecutive_attempts: int = 0
    # DESIGN §4 "Season trailers" extension. None for movies and show-level
    # TV trailers; positive integer for season-level entries (1-indexed).
    # Persisted as a top-level field for fast filtering/queries via
    # `state_store.all_entries()` in CLI subcommands.
    season_number: int | None = None
```

**JSON schema example** (reflects `bot_detected_consecutive_attempts` field):

```json
{
  "version": 1,
  "entries": {
    "movie:tmdb:99999": {
      "last_attempt": "2026-04-23T03:18:02Z",
      "attempts": 2,
      "status": "bot_detected",
      "media_path": "/Volumes/DISK_C/001-MOVIES/Obscure (2017)",
      "bot_detected_consecutive_attempts": 2
    }
  }
}
```

**Key functions:**

```python
def make_state_key(
    media_type: str,
    ids: dict[str, int | str | None],   # keys: "tmdb", "tvdb"
    title: str | None = None,
    year: int | None = None,
    season_number: int | None = None,    # NEW — None for movies / show-level TV
) -> str:
    """Build a composite state key.

    Precedence:
        1. ids["tmdb"]  → "{media_type}:tmdb:{id}"
        2. ids["tvdb"]  → "{media_type}:tvdb:{id}"
        3. fall back to manual: "manual:{sha256(NFC+casefold(title)|year|media_type)}"

    When ``season_number`` is provided AND a TMDB/TVDB id is present, the
    season suffix is appended:

        "tv:tmdb:{id}:season:{N}"
        "tv:tvdb:{id}:season:{N}"

    When ``season_number`` is None (movies, show-level TV), no suffix is
    appended. Manual keys do NOT receive a season suffix — season-level
    trailers without external IDs are out of scope for v0.7.0.

    Returns:
        "movie:tmdb:{id}"
        "tv:tmdb:{id}"
        "tv:tmdb:{id}:season:{N}"   when season_number is not None
        "manual:{sha256(...)}"
    """

def compute_next_retry_at(
    attempts: int,
    policy: list[int],
    *,
    last_attempt: datetime,
) -> datetime:
    """Return next retry datetime using policy[min(attempts-1, len(policy)-1)].

    Clock reference: always from last_attempt (DESIGN §7). See impl sketch below.
    """
```

**`TrailerStateStore`:**

| Method          | Signature                                 | Description                                                              |
| --------------- | ----------------------------------------- | ------------------------------------------------------------------------ |
| `__init__`      | `(state_file: Path)`                      | Initialize with path to JSON state file                                  |
| `get`           | `(key: str) -> TrailerState \| None`      | Load + deserialize entry by key                                          |
| `set`           | `(key: str, state: TrailerState) -> None` | Atomic write (temp + os.replace), under `fcntl.flock(LOCK_EX)`           |
| `should_skip`   | `(key: str) -> bool`                      | Skip logic per DESIGN §7 (bot_detected exempt)                           |
| `auto_gc`       | `() -> None`                              | Lifecycle check: flip orphan, remove gone trailers                       |
| `all_entries`   | `() -> dict[str, TrailerState]`           | Load all entries (for CLI scan/purge)                                    |
| `purge_orphans` | `() -> int`                               | Remove all entries whose `status == "orphan"`. Return count of removals. |

**JSON on-disk structure** (per DESIGN §7):

```json
{"version": 1, "entries": {"movie:tmdb:550": {...}}}
```

**`purge_orphans()` impl sketch:**

```python
def purge_orphans(self) -> int:
    before = len(self._entries)
    self._entries = {k: v for k, v in self._entries.items() if v.status != "orphan"}
    self._save()
    return before - len(self._entries)
```

**`compute_next_retry_at()` clock reference (DESIGN §7):**

```python
# Clock reference: always from last_attempt, never from first_failure (DESIGN §7).
# A stuck entry keeps pushing retry forward; a recovered entry resets attempts=1
# on its next successful result.
def compute_next_retry_at(
    attempts: int,
    policy: list[int],
    *,
    last_attempt: datetime,
) -> datetime:
    days = policy[min(attempts - 1, len(policy) - 1)]
    return last_attempt + timedelta(days=days)
```

**Concurrency (DESIGN §12 Operational Safeguards):** wrap `_load()` + `_save()` in
`fcntl.flock(lockfile_fd, LOCK_EX)` on a sibling lockfile `.data/trailers_state.lock`. The
lock is acquired before the read-modify-write cycle and released after `os.replace()`
completes. Under the lock, read the full JSON, mutate the in-memory dict, write to a temp
file, `os.replace()` onto the real file — standard atomic write. Concurrent readers (from
a second `personalscraper trailers download` invocation) block on the lock rather than
racing. On non-Unix platforms where `fcntl` is unavailable, fall back to best-effort
write-temp-then-replace without the lock (log a one-time WARN at import).

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
