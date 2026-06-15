"""Tests for the opt-in seed-pure sort guard (phase 4, sub-phase 4.2).

Two layers are exercised:

* ``Sorter.process(skip_names=...)`` — the load-bearing real-exclusion test
  proves that a skipped name is reported as a ``seed_pure`` skip and that
  ``sort_item`` is *never* called for it (genuine exclusion, not a vacuous
  count), while a non-skipped sibling IS sorted.
* ``run_sort(..., torrent_client=...)`` — proves the guard only queries the
  client when ``config.sort.verify_seed_pure`` is on, threads the resulting
  name set into ``Sorter.process``, and stays inert (no crash) when the flag
  is on but no client is supplied.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import EventBus
from personalscraper.core.tags import SEED_PURE
from personalscraper.models import SortResult
from personalscraper.sorter.run import run_sort
from personalscraper.sorter.sorter import Sorter
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_config(tmp_path: Path, *, verify_seed_pure: bool = False) -> Config:
    """Build a Config rooted at ``tmp_path`` with the sort guard flag set.

    Args:
        tmp_path: Pytest temporary directory.
        verify_seed_pure: Value for ``config.sort.verify_seed_pure``.

    Returns:
        A validated Config with canonical staging dirs.
    """
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": [s.model_dump() for s in CANONICAL_STAGING_DIRS],
            "sort": {"verify_seed_pure": verify_seed_pure},
        }
    )


def _seed_ingest(config: Config, name: str = "leftover.mkv") -> Path:
    """Create the ingest dir (097-TEMP) with a single visible item.

    Without a visible item ``run_sort`` fast-skips before reaching the guard.

    Args:
        config: Pipeline config used to resolve the staging path.
        name: File name to create in the ingest directory.

    Returns:
        Path to the seeded item inside the ingest dir.
    """
    staging = config.paths.staging_dir
    staging.mkdir(parents=True, exist_ok=True)
    ingest = staging / "097-TEMP"
    ingest.mkdir(parents=True, exist_ok=True)
    item = ingest / name
    item.write_text("payload")
    return item


def _seed_pure_torrent(name: str) -> TorrentItem:
    """Build a completed TorrentItem tagged seed-pure.

    Args:
        name: Torrent display name (matched against staging item names).

    Returns:
        A TorrentItem carrying the SEED_PURE tag.
    """
    return TorrentItem(
        hash="abc123",
        name=name,
        size_bytes=1,
        progress=1.0,
        state="pausedUP",
        tags=[SEED_PURE],
    )


class TestSorterProcessSkipNames:
    """Real-exclusion behaviour of ``Sorter.process(skip_names=...)``."""

    def test_sort_process_excludes_skip_names(self, tmp_path: Path) -> None:
        """skip_names items are seed_pure-skipped; sort_item never runs for them.

        Load-bearing, mutation-proof: uses the REAL Sorter with two real dir
        items. ``sort_item`` is stubbed to a fake ``moved`` result so the test
        asserts genuine exclusion via the call record — if ``skip_names`` were
        ignored, ``sort_item`` would be called for the seed item and there would
        be no ``seed_pure`` skip result.
        """
        config = _make_config(tmp_path)
        ingest = tmp_path / "ingest"
        ingest.mkdir()
        dest_root = tmp_path / "dest"
        dest_root.mkdir()
        # Two real directory items whose names do NOT collide with staging_dirs
        # folder names (001-MOVIES, ... 097-TEMP), so neither is skip_dirs-skipped.
        seed_dir = ingest / "Seed.Movie.2024"
        keep_dir = ingest / "Keep.Show.2024"
        seed_dir.mkdir()
        keep_dir.mkdir()

        sorter = Sorter(config=config, dry_run=True)

        def _fake_sort_item(_self: Sorter, item: Path, dest: Path) -> SortResult:
            """Return a fake moved result without touching the filesystem.

            Note: autospec=True binds the Sorter instance as the first arg.
            """
            return SortResult(
                source=item,
                destination=dest / item.name,
                media_type="movie",
                title=item.name,
                year=None,
                season=None,
                episode=None,
                status="moved",
                message=None,
            )

        with patch.object(Sorter, "sort_item", side_effect=_fake_sort_item, autospec=True) as mock_sort_item:
            results = sorter.process(
                ingest,
                dest_root=dest_root,
                skip_names=frozenset({"Seed.Movie.2024"}),
            )

        by_name = {r.source.name: r for r in results}

        # The seed item is a genuine seed_pure skip.
        assert by_name["Seed.Movie.2024"].status == "skipped"
        assert by_name["Seed.Movie.2024"].message == "seed_pure"

        # The kept item was actually sorted.
        assert by_name["Keep.Show.2024"].status == "moved"

        # Genuine exclusion: sort_item was called for the kept item only.
        sorted_names = {call.args[1].name for call in mock_sort_item.call_args_list}
        assert sorted_names == {"Keep.Show.2024"}
        assert "Seed.Movie.2024" not in sorted_names


class TestRunSortGuard:
    """``run_sort`` seed-pure guard threading and gating."""

    def test_run_sort_guard_off_no_client_query(self, tmp_path: Path) -> None:
        """Flag off: get_completed is never called; process gets an empty set."""
        config = _make_config(tmp_path, verify_seed_pure=False)
        _seed_ingest(config, "some_item.mkv")
        mock_client = MagicMock()
        settings = MagicMock()

        with patch("personalscraper.sorter.run.Sorter") as MockSorter:
            MockSorter.return_value.process.return_value = []
            run_sort(
                settings,
                staging_dir=config.paths.staging_dir,
                config=config,
                event_bus=EventBus(),
                torrent_client=mock_client,
            )

        mock_client.get_completed.assert_not_called()
        _, kwargs = MockSorter.return_value.process.call_args
        assert kwargs["skip_names"] == frozenset()

    def test_run_sort_guard_on_threads_skip_names(self, tmp_path: Path) -> None:
        """Flag on: get_completed runs once; seed-pure names reach process."""
        config = _make_config(tmp_path, verify_seed_pure=True)
        _seed_ingest(config, "some_item.mkv")
        mock_client = MagicMock()
        mock_client.get_completed.return_value = [
            _seed_pure_torrent("Seed.Movie.2024"),
            # A completed torrent WITHOUT the tag must not be excluded.
            TorrentItem(hash="def", name="Other.2024", size_bytes=1, progress=1.0, state="pausedUP", tags=[]),
        ]
        settings = MagicMock()

        with patch("personalscraper.sorter.run.Sorter") as MockSorter:
            MockSorter.return_value.process.return_value = []
            run_sort(
                settings,
                staging_dir=config.paths.staging_dir,
                config=config,
                event_bus=EventBus(),
                torrent_client=mock_client,
            )

        mock_client.get_completed.assert_called_once_with()
        _, kwargs = MockSorter.return_value.process.call_args
        assert "Seed.Movie.2024" in kwargs["skip_names"]
        assert "Other.2024" not in kwargs["skip_names"]

    def test_run_sort_guard_on_no_client_inert(self, tmp_path: Path) -> None:
        """Flag on but no client: no crash, empty skip set, zero errors."""
        config = _make_config(tmp_path, verify_seed_pure=True)
        _seed_ingest(config, "some_item.mkv")
        settings = MagicMock()

        with patch("personalscraper.sorter.run.Sorter") as MockSorter:
            MockSorter.return_value.process.return_value = []
            report = run_sort(
                settings,
                staging_dir=config.paths.staging_dir,
                config=config,
                event_bus=EventBus(),
                torrent_client=None,
            )

        _, kwargs = MockSorter.return_value.process.call_args
        assert kwargs["skip_names"] == frozenset()
        assert report.error_count == 0


@pytest.mark.parametrize("flag", [True, False])
def test_run_sort_guard_fail_soft_on_client_error(tmp_path: Path, flag: bool) -> None:
    """A client error never aborts the sort; skip set stays empty (flag on)."""
    config = _make_config(tmp_path, verify_seed_pure=flag)
    _seed_ingest(config, "some_item.mkv")
    mock_client = MagicMock()
    mock_client.get_completed.side_effect = RuntimeError("client down")
    settings = MagicMock()

    with patch("personalscraper.sorter.run.Sorter") as MockSorter:
        MockSorter.return_value.process.return_value = []
        report = run_sort(
            settings,
            staging_dir=config.paths.staging_dir,
            config=config,
            event_bus=EventBus(),
            torrent_client=mock_client,
        )

    _, kwargs = MockSorter.return_value.process.call_args
    assert kwargs["skip_names"] == frozenset()
    assert report.error_count == 0
