import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from personalscraper.trailers.state import (
    TrailerState,
    TrailerStateStore,
    TrailerStatus,
    compute_next_retry_at,
    make_state_key,
)


def _write_entry(key: str, state_file: Path) -> None:
    """Write a state entry to the store for concurrent test use."""
    s = TrailerStateStore(state_file=state_file)
    s.set(
        key,
        TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=f"/fake/{key}",
        ),
    )


class TestMakeStateKey:
    """Tests for make_state_key() composite key builder."""

    def test_movie_tmdb_key(self) -> None:
        """TMDB movie key has correct format."""
        assert make_state_key("movie", {"tmdb": 550}) == "movie:tmdb:550"

    def test_tv_tmdb_key(self) -> None:
        """TMDB TV key has correct format."""
        assert make_state_key("tv", {"tmdb": 1399}) == "tv:tmdb:1399"

    def test_movie_tvdb_key(self) -> None:
        """TVDB movie key has correct format."""
        assert make_state_key("movie", {"tvdb": 12345}) == "movie:tvdb:12345"

    def test_make_state_key_tv_season(self) -> None:
        """Season-level TV key has :season:N suffix."""
        key = make_state_key("tv", {"tmdb": 1399}, season_number=3)
        assert key == "tv:tmdb:1399:season:3"

    def test_make_state_key_tv_without_season(self) -> None:
        """Show-level TV key has no :season: suffix."""
        key = make_state_key("tv", {"tmdb": 1399})
        assert ":season:" not in key
        assert key == "tv:tmdb:1399"

    def test_make_state_key_tv_season_uses_tvdb_fallback(self) -> None:
        """Season key falls back to TVDB when TMDB is None."""
        key = make_state_key("tv", {"tmdb": None, "tvdb": 81189}, season_number=2)
        assert key == "tv:tvdb:81189:season:2"

    def test_manual_key_hashes_title_year_type(self) -> None:
        """Manual key hashes normalized title+year+type."""
        import unicodedata

        normalized_title = " ".join(unicodedata.normalize("NFC", "Fight Club").casefold().split())
        payload = f"{normalized_title}|1999|movie"
        digest = hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()
        key = make_state_key("movie", {}, title="Fight Club", year=1999)
        assert key == f"manual:{digest}"

    def test_manual_key_is_path_independent(self) -> None:
        """Manual key is stable across scrape runs."""
        k1 = make_state_key("movie", {}, title="Fight Club", year=1999)
        k2 = make_state_key("movie", {}, title="Fight Club", year=1999)
        assert k1 == k2

    def test_manual_key_normalizes_title(self) -> None:
        """Title is NFC-normalized and casefolded before hashing."""
        a = make_state_key("tv", {}, title="The Wire", year=2002)
        b = make_state_key("tv", {}, title="the  wire", year=2002)
        assert a == b

    def test_key_format_is_consistent(self) -> None:
        """Identical inputs always produce the same key."""
        k1 = make_state_key("movie", {"tmdb": 550})
        k2 = make_state_key("movie", {"tmdb": 550})
        assert k1 == k2


class TestTrailerStatus:
    """Tests for the TrailerStatus enum values."""

    def test_all_statuses_defined(self) -> None:
        """All expected status values are present."""
        statuses = {s.value for s in TrailerStatus}
        expected = {
            "downloaded",
            "no_trailer_available",
            "bot_detected",
            "http_error",
            "ytdlp_error",
            "skipped_by_filter",
            "orphan",
            "already_present_on_disk",
        }
        assert statuses == expected

    def test_status_enum_includes_already_present_on_disk(self) -> None:
        """ALREADY_PRESENT_ON_DISK has the correct string value."""
        assert TrailerStatus.ALREADY_PRESENT_ON_DISK.value == "already_present_on_disk"


class TestTrailerState:
    """Tests for the TrailerState dataclass."""

    def test_create_basic_state(self) -> None:
        """TrailerState initializes with the given values."""
        now = datetime.now(timezone.utc)
        state = TrailerState(
            last_attempt=now.isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/Volumes/DISK_A/movies/Fight Club (1999)",
        )
        assert state.attempts == 1
        assert state.status == TrailerStatus.DOWNLOADED


@pytest.fixture()
def store(tmp_path: Path) -> TrailerStateStore:
    """Create a TrailerStateStore backed by a temp file."""
    return TrailerStateStore(state_file=tmp_path / "trailers_state.json")


class TestTrailerStateStore:
    """Tests for TrailerStateStore persistence and retrieval."""

    def test_missing_file_returns_no_entries(self, store: TrailerStateStore) -> None:
        """get() returns None when the state file does not exist."""
        assert store.get("movie:tmdb:550") is None

    def test_set_then_get_round_trip(self, store: TrailerStateStore) -> None:
        """set() then get() returns the stored state."""
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
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

    def test_state_file_has_version_field(self, store: TrailerStateStore, tmp_path: Path) -> None:
        """Written JSON file contains a version=1 field."""
        import json as _j

        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/fake",
        )
        store.set("movie:tmdb:1", state)
        raw = _j.loads((tmp_path / "trailers_state.json").read_text())
        assert raw["version"] == 1

    def test_get_nonexistent_key_returns_none(self, store: TrailerStateStore) -> None:
        """get() returns None for unknown keys."""
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/fake",
        )
        store.set("movie:tmdb:1", state)
        assert store.get("movie:tmdb:999") is None


class TestShouldSkip:
    """Tests for TrailerStateStore.should_skip() logic."""

    def test_skip_when_no_trailer_available_and_not_expired(self, store: TrailerStateStore) -> None:
        """should_skip returns True when no_trailer_available and next_retry is future."""
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=2,
            status=TrailerStatus.NO_TRAILER_AVAILABLE,
            media_path="/fake",
            next_retry_at=future,
        )
        store.set("movie:tmdb:550", state)
        assert store.should_skip("movie:tmdb:550") is True

    def test_no_skip_when_retry_expired(self, store: TrailerStateStore) -> None:
        """should_skip returns False when next_retry_at is in the past."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=2,
            status=TrailerStatus.NO_TRAILER_AVAILABLE,
            media_path="/fake",
            next_retry_at=past,
        )
        store.set("movie:tmdb:550", state)
        assert store.should_skip("movie:tmdb:550") is False

    def test_bot_detected_never_skipped(self, store: TrailerStateStore) -> None:
        """should_skip returns False for bot_detected regardless of next_retry_at."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.BOT_DETECTED,
            media_path="/fake",
            next_retry_at=future,
        )
        store.set("movie:tmdb:550", state)
        assert store.should_skip("movie:tmdb:550") is False

    def test_missing_key_not_skipped(self, store: TrailerStateStore) -> None:
        """should_skip returns False for unknown keys (first run)."""
        assert store.should_skip("movie:tmdb:99999") is False

    def test_retry_after_progression(self) -> None:
        """Retry intervals progress through [1, 7, 30] then repeat the last."""
        policy = [1, 7, 30]
        last_attempt = datetime.now(timezone.utc)
        r1 = compute_next_retry_at(attempts=1, policy=policy, last_attempt=last_attempt)
        r2 = compute_next_retry_at(attempts=2, policy=policy, last_attempt=last_attempt)
        r3 = compute_next_retry_at(attempts=3, policy=policy, last_attempt=last_attempt)
        r4 = compute_next_retry_at(attempts=4, policy=policy, last_attempt=last_attempt)
        assert (r1 - last_attempt).days == 1
        assert (r2 - last_attempt).days == 7
        assert (r3 - last_attempt).days == 30
        assert (r4 - last_attempt).days == 30


class TestAutoGC:
    """Tests for auto_gc(), purge_orphans(), and retry-after semantics."""

    def test_gc_marks_orphan_when_media_path_missing(self, store: TrailerStateStore, tmp_path: Path) -> None:
        """auto_gc flips status to orphan when media_path no longer exists."""
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
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

    def test_gc_removes_entry_when_trailer_deleted(self, store: TrailerStateStore, tmp_path: Path) -> None:
        """auto_gc removes entries whose trailer_path is gone (re-download)."""
        media = tmp_path / "Movie (2020)"
        media.mkdir()
        trailer = media / "Movie (2020)-trailer.mp4"
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path=str(media),
            trailer_path=str(trailer),
        )
        store.set("movie:tmdb:2", state)
        store.auto_gc()
        assert store.get("movie:tmdb:2") is None

    def test_purge_orphans_removes_orphan_entries_only(self, store: TrailerStateStore, tmp_path: Path) -> None:
        """purge_orphans removes only orphan entries and returns count."""
        now = datetime.now(timezone.utc).isoformat()
        downloaded = TrailerState(last_attempt=now, attempts=1, status=TrailerStatus.DOWNLOADED, media_path="/a")
        orphan = TrailerState(last_attempt=now, attempts=1, status=TrailerStatus.ORPHAN, media_path="/b")
        bot = TrailerState(last_attempt=now, attempts=1, status=TrailerStatus.BOT_DETECTED, media_path="/c")
        store.set("movie:tmdb:1", downloaded)
        store.set("movie:tmdb:2", orphan)
        store.set("movie:tmdb:3", bot)
        removed = store.purge_orphans()
        assert removed == 1
        assert store.get("movie:tmdb:1") is not None
        assert store.get("movie:tmdb:2") is None
        assert store.get("movie:tmdb:3") is not None

    def test_next_retry_measured_from_last_attempt_not_first_failure(self) -> None:
        """compute_next_retry_at uses last_attempt as the clock reference."""
        first_failure = datetime(2026, 1, 1, tzinfo=timezone.utc)
        last_attempt = datetime(2026, 4, 1, tzinfo=timezone.utc)
        result = compute_next_retry_at(attempts=3, policy=[1, 7, 30], last_attempt=last_attempt)
        assert result == datetime(2026, 5, 1, tzinfo=timezone.utc)
        _ = first_failure

    def test_bot_detected_counter_resets_on_non_bot_outcome(self, store: TrailerStateStore) -> None:
        """bot_detected_consecutive_attempts resets to 0 on non-bot outcome."""
        now = datetime.now(timezone.utc).isoformat()
        state_bot = TrailerState(
            last_attempt=now,
            attempts=3,
            status=TrailerStatus.BOT_DETECTED,
            media_path="/x",
            bot_detected_consecutive_attempts=3,
        )
        store.set("movie:tmdb:7", state_bot)
        loaded = store.get("movie:tmdb:7")
        assert loaded is not None
        assert loaded.bot_detected_consecutive_attempts == 3
        state_ok = TrailerState(
            last_attempt=now,
            attempts=1,
            status=TrailerStatus.DOWNLOADED,
            media_path="/x",
            trailer_path="/x/trailer.mp4",
            bot_detected_consecutive_attempts=0,
        )
        store.set("movie:tmdb:7", state_ok)
        reloaded = store.get("movie:tmdb:7")
        assert reloaded is not None
        assert reloaded.bot_detected_consecutive_attempts == 0
        assert reloaded.status == TrailerStatus.DOWNLOADED

    def test_concurrent_writes_do_not_corrupt_state(self, tmp_path: Path) -> None:
        """Two concurrent writers under fcntl.flock produce a valid JSON file."""
        import multiprocessing

        state_file = tmp_path / "trailers_state.json"

        p1 = multiprocessing.Process(target=_write_entry, args=("movie:tmdb:1", state_file))
        p2 = multiprocessing.Process(target=_write_entry, args=("movie:tmdb:2", state_file))
        p1.start()
        p2.start()
        p1.join(timeout=5)
        p2.join(timeout=5)

        reader = TrailerStateStore(state_file=state_file)
        assert reader.get("movie:tmdb:1") is not None
        assert reader.get("movie:tmdb:2") is not None

    def test_gc_leaves_valid_entries_intact(self, store: TrailerStateStore, tmp_path: Path) -> None:
        """auto_gc does not modify entries with existing media and trailer."""
        media = tmp_path / "Good Movie (2020)"
        media.mkdir()
        trailer = media / "Good Movie (2020)-trailer.mp4"
        trailer.write_bytes(b"x" * 200000)
        state = TrailerState(
            last_attempt=datetime.now(timezone.utc).isoformat(),
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
