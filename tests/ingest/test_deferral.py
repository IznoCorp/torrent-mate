"""Tests for ingest.deferral — the transient-skip classifier.

The classifier mirrors ingest's own transient guards (ratio / content /
space) WITHOUT touching ingest semantics: it only decides which completed
torrents the watcher should exclude from its pipeline-trigger predicate this
cycle. Every predicate must be self-healing — a cleared condition removes the
hash from the result on the next call.
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.api.torrent._base import TorrentItem
from personalscraper.ingest.deferral import (
    REASON_CONTENT_MISSING,
    REASON_INSUFFICIENT_SPACE,
    REASON_RATIO,
    classify_deferrals,
)


def _torrent(
    *,
    hash_: str = "aaaa",
    name: str = "Some.Show.S01E01",
    size: int = 1_000,
    ratio: float = 2.0,
    content_path: Path | None = None,
) -> TorrentItem:
    """Build a completed TorrentItem with sensible defaults."""
    return TorrentItem(
        hash=hash_,
        name=name,
        size_bytes=size,
        progress=1.0,
        state="uploading",
        content_path=content_path,
        ratio=ratio,
    )


def _space_ok(*_args: object) -> bool:
    return True


def _space_full(*_args: object) -> bool:
    return False


class TestRatioDeferral:
    """min_ratio guard — the dominant transient skip."""

    def test_below_threshold_is_deferred(self, tmp_path: Path) -> None:
        """Ratio < min_ratio → deferred with the ingest reason string."""
        content = tmp_path / "payload"
        content.mkdir()
        t = _torrent(ratio=0.4, content_path=content)
        out = classify_deferrals([t], min_ratio=1.0, ingest_dir=tmp_path, min_free_gb=0, disk_space_ok=_space_ok)
        assert out == {"aaaa": REASON_RATIO}

    def test_threshold_reached_not_deferred(self, tmp_path: Path) -> None:
        """Ratio ≥ min_ratio → hash re-enters the trigger set (self-healing)."""
        content = tmp_path / "payload"
        content.mkdir()
        t = _torrent(ratio=1.2, content_path=content)
        out = classify_deferrals([t], min_ratio=1.0, ingest_dir=tmp_path, min_free_gb=0, disk_space_ok=_space_ok)
        assert out == {}

    def test_guard_disabled_when_min_ratio_zero(self, tmp_path: Path) -> None:
        """min_ratio=0.0 (default config) disables the ratio guard entirely."""
        content = tmp_path / "payload"
        content.mkdir()
        t = _torrent(ratio=0.0, content_path=content)
        out = classify_deferrals([t], min_ratio=0.0, ingest_dir=tmp_path, min_free_gb=0, disk_space_ok=_space_ok)
        assert out == {}


class TestContentMissingDeferral:
    """content_path unavailable — volume unmounted / client path stale."""

    def test_missing_content_is_deferred(self, tmp_path: Path) -> None:
        """content_path absent on disk and no staging copy → deferred."""
        t = _torrent(content_path=tmp_path / "gone")
        out = classify_deferrals([t], min_ratio=0.0, ingest_dir=tmp_path, min_free_gb=0, disk_space_ok=_space_ok)
        assert out == {"aaaa": REASON_CONTENT_MISSING}

    def test_none_content_path_is_deferred(self, tmp_path: Path) -> None:
        """A client that reports no content_path at all defers too."""
        t = _torrent(content_path=None)
        out = classify_deferrals([t], min_ratio=0.0, ingest_dir=tmp_path, min_free_gb=0, disk_space_ok=_space_ok)
        assert out == {"aaaa": REASON_CONTENT_MISSING}

    def test_staging_copy_means_actionable(self, tmp_path: Path) -> None:
        """Source gone but staging copy present → NOT deferred.

        A run WOULD progress via the ``found_in_staging`` marker.
        """
        staging = tmp_path / "staging"
        (staging / "Some.Show.S01E01").mkdir(parents=True)
        t = _torrent(content_path=tmp_path / "gone")
        out = classify_deferrals(
            [t],
            min_ratio=0.0,
            ingest_dir=tmp_path,
            min_free_gb=0,
            staging_probe_dirs=[staging],
            disk_space_ok=_space_ok,
        )
        assert out == {}


class TestSpaceDeferral:
    """Staging disk full — clears when space frees."""

    def test_insufficient_space_is_deferred(self, tmp_path: Path) -> None:
        """Space predicate false → deferred with the ingest reason."""
        content = tmp_path / "payload"
        content.mkdir()
        t = _torrent(content_path=content)
        out = classify_deferrals([t], min_ratio=0.0, ingest_dir=tmp_path, min_free_gb=10, disk_space_ok=_space_full)
        assert out == {"aaaa": REASON_INSUFFICIENT_SPACE}

    def test_space_freed_not_deferred(self, tmp_path: Path) -> None:
        """Space predicate true again → hash re-enters (self-healing)."""
        content = tmp_path / "payload"
        content.mkdir()
        t = _torrent(content_path=content)
        out = classify_deferrals([t], min_ratio=0.0, ingest_dir=tmp_path, min_free_gb=10, disk_space_ok=_space_ok)
        assert out == {}


class TestExclusions:
    """Already-ingested / seed-pure hashes never appear in the result."""

    def test_excluded_hashes_skipped(self, tmp_path: Path) -> None:
        """An excluded hash is never classified, whatever its state."""
        t = _torrent(ratio=0.1, content_path=None)
        out = classify_deferrals(
            [t],
            min_ratio=1.0,
            ingest_dir=tmp_path,
            min_free_gb=0,
            exclude_hashes=frozenset({"aaaa"}),
            disk_space_ok=_space_ok,
        )
        assert out == {}

    def test_reason_order_matches_ingest(self, tmp_path: Path) -> None:
        """Ratio is checked first — mirrors run_ingest's guard order."""
        t = _torrent(ratio=0.1, content_path=None)
        out = classify_deferrals([t], min_ratio=1.0, ingest_dir=tmp_path, min_free_gb=10, disk_space_ok=_space_full)
        assert out == {"aaaa": REASON_RATIO}
