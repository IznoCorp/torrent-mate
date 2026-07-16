"""Tests for the three-state seedtime-aware dispatch policy (DESIGN §7.3).

Covers the per-site deletion policy + write-before-move obligation recording
applied at the dispatch deletion sites (``_movie.dispatch_movie`` replace branch,
``_tv.dispatch_tvshow`` merge branch):

- VETO state: an unmet seed obligation on the OLD on-disk content does NOT skip
  the dispatch (real media wins, O3) but is recorded — ``mark_breach`` is called
  with the dest and an ``acquire.hnr_risk`` warning is logged.
- ALLOW state: the replace/merge proceeds with no breach side effects.
- Write-before-move: ``record_dispatch`` is invoked with the staging source +
  dispatched dest BEFORE the filesystem move (DESIGN §7.2).
- dry-run: no acquire-db side effects (no ``record_dispatch`` / ``mark_breach``).
- New-media branch: ``record_dispatch`` is still called (the new media may seed)
  but no permit consult / ``mark_breach`` (no pre-existing library content).
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.core.delete_permit import ALLOW, PermitDecision, veto
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch import _movie, _tv
from personalscraper.dispatch.disk_scanner import DiskStatus
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import IndexEntry, MediaIndex


@pytest.fixture(autouse=True)
def _rsync_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``shutil.which`` report rsync as available so Dispatcher init passes."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/rsync" if name == "rsync" else None)


class _StubPermit:
    """Permit stub returning a fixed decision; records consulted paths."""

    def __init__(self, decision: PermitDecision) -> None:
        """Store the decision to return and init the consulted-path log.

        Args:
            decision: The ``PermitDecision`` (``ALLOW`` or a veto) returned for
                every ``may_delete`` call.
        """
        self._decision = decision
        self.consulted: list[Path] = []

    def may_delete(self, path: Path) -> PermitDecision:
        """Return the fixed decision and record the consulted path.

        Args:
            path: The path about to be deleted.

        Returns:
            The fixed ``PermitDecision`` supplied at construction time.
        """
        self.consulted.append(path)
        return self._decision


def _disk_status(disk_id: str, root: Path, category: str, free_gb: float) -> DiskStatus:
    """Build a mounted ``DiskStatus`` with the given free space.

    Args:
        disk_id: Disk identifier.
        root: Disk root path.
        category: Single category the disk accepts.
        free_gb: Reported free space in GB.

    Returns:
        A mounted ``DiskStatus`` instance.
    """
    return DiskStatus(
        config=DiskConfig(id=disk_id, path=root, categories=[category]),
        free_space_gb=free_gb,
        is_mounted=True,
    )


def _make_dispatcher(
    test_config: object,
    tmp_path: Path,
    *,
    permit: object,
    recorder: object,
    dry_run: bool = False,
) -> Dispatcher:
    """Construct a Dispatcher wired with the given permit/recorder stubs.

    Args:
        test_config: The synthetic ``Config`` fixture.
        tmp_path: Pytest temp dir for the media-index DB.
        permit: Injected ``DeletePermit`` stub.
        recorder: Injected ``SeedObligationRecorder`` stub.
        dry_run: Whether the dispatcher runs in dry-run mode.

    Returns:
        A ready-to-use ``Dispatcher``.
    """
    idx = MediaIndex(tmp_path / "index.db", event_bus=EventBus())
    return Dispatcher(
        test_config,  # type: ignore[arg-type]
        MagicMock(),
        idx,
        dry_run=dry_run,
        event_bus=EventBus(),
        permit=permit,  # type: ignore[arg-type]
        recorder=recorder,  # type: ignore[arg-type]
    )


def _seed_existing_movie(dispatcher: Dispatcher, tmp_path: Path) -> tuple[Path, Path]:
    """Create a staging movie + an existing on-disk copy primed in the index.

    Args:
        dispatcher: Dispatcher whose index is primed.
        tmp_path: Pytest temp dir.

    Returns:
        A ``(staging_dir, existing_dest_dir)`` tuple.
    """
    folder = "Shrinking (2023)"
    staging_dir = tmp_path / "staging" / folder
    staging_dir.mkdir(parents=True)
    (staging_dir / "Shrinking.mkv").write_bytes(b"\x00" * 2048)

    existing_dir = tmp_path / "drive_a" / "cat_movies" / folder
    existing_dir.mkdir(parents=True)
    (existing_dir / "old.mkv").write_bytes(b"\x00" * 16)

    dispatcher.index.add(
        IndexEntry(
            name=folder,
            disk="drive_a",
            category=CID.MOVIES,
            path=str(existing_dir),
            media_type="movie",
        )
    )
    return staging_dir, existing_dir


def _seed_existing_show(dispatcher: Dispatcher, tmp_path: Path) -> tuple[Path, Path]:
    """Create a staging show + an existing on-disk copy primed in the index.

    Args:
        dispatcher: Dispatcher whose index is primed.
        tmp_path: Pytest temp dir.

    Returns:
        A ``(staging_dir, existing_dest_dir)`` tuple.
    """
    folder = "Fallout (2024)"
    staging_dir = tmp_path / "staging" / folder
    (staging_dir / "Season 01").mkdir(parents=True)
    (staging_dir / "Season 01" / "Fallout S01E01.mkv").write_bytes(b"\x00" * 2048)

    existing_dir = tmp_path / "drive_a" / "cat_tv_shows" / folder
    (existing_dir / "Season 01").mkdir(parents=True)
    (existing_dir / "Season 01" / "Fallout S01E01.mkv").write_bytes(b"\x00" * 16)

    dispatcher.index.add(
        IndexEntry(
            name=folder,
            disk="drive_a",
            category=CID.TV_SHOWS,
            path=str(existing_dir),
            media_type="tvshow",
        )
    )
    return staging_dir, existing_dir


# ---------------------------------------------------------------------------
# Movie replace branch — three states
# ---------------------------------------------------------------------------


class TestMovieThreeState:
    """Three-state policy on the movie replace branch."""

    def test_veto_still_replaces_and_records_breach(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """VETO on the old content: replace PROCEEDS + breach marked + hnr_risk logged."""
        permit = _StubPermit(veto("seedtime not met"))
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, existing_dir = _seed_existing_movie(d, tmp_path)

        replace_mock = MagicMock(return_value=True)
        monkeypatch.setattr(_movie, "replace", replace_mock)
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        with caplog.at_level("WARNING"):
            result = d.dispatch_movie(staging_dir, CID.MOVIES)

        # Real media wins — the replace still happened, NOT skipped.
        assert result.action == "replaced"
        replace_mock.assert_called_once()
        # Breach recorded against the existing (deleted) on-disk path.
        recorder.mark_breach.assert_called_once_with(existing_dir)
        # Never silent — the hnr_risk warning is emitted.
        assert "acquire.hnr_risk" in caplog.text

    def test_allow_replaces_without_breach(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """ALLOW: replace proceeds, no breach, no hnr_risk log."""
        permit = _StubPermit(ALLOW)
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, _existing_dir = _seed_existing_movie(d, tmp_path)

        monkeypatch.setattr(_movie, "replace", MagicMock(return_value=True))
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        with caplog.at_level("WARNING"):
            result = d.dispatch_movie(staging_dir, CID.MOVIES)

        assert result.action == "replaced"
        recorder.mark_breach.assert_not_called()
        assert "acquire.hnr_risk" not in caplog.text

    def test_dispatch_movie_emits_film_acquired_returned_by_recorder(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """D2-A+ — events returned by record_dispatch are emitted on the feed on success.

        Red-on-old: record_dispatch returned None and the dispatch layer emitted
        nothing, so the « Film acquis » feed toast never fired for a film retired
        at dispatch. The recorder now returns a FilmAcquired; the move-success
        path emits it on the dispatcher's bus.
        """
        from personalscraper.acquire.events import FilmAcquired
        from personalscraper.core.identity import MediaRef

        evt = FilmAcquired(media_ref=MediaRef(tmdb_id=42), title="Ferrari", followed_id=7)
        permit = _StubPermit(ALLOW)
        recorder = MagicMock()
        recorder.record_dispatch.return_value = [evt]
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, _existing_dir = _seed_existing_movie(d, tmp_path)

        captured: list[FilmAcquired] = []
        d._event_bus.subscribe(FilmAcquired, captured.append)

        monkeypatch.setattr(_movie, "replace", MagicMock(return_value=True))
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        result = d.dispatch_movie(staging_dir, CID.MOVIES)

        assert result.action == "replaced"
        assert captured == [evt]  # the retired-film toast reached the feed

    def test_dispatch_movie_does_not_emit_on_move_failure(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failed move must NOT announce « Film acquis » (nothing landed)."""
        from personalscraper.acquire.events import FilmAcquired
        from personalscraper.core.identity import MediaRef

        evt = FilmAcquired(media_ref=MediaRef(tmdb_id=42), title="Ferrari", followed_id=7)
        permit = _StubPermit(ALLOW)
        recorder = MagicMock()
        recorder.record_dispatch.return_value = [evt]
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, _existing_dir = _seed_existing_movie(d, tmp_path)

        captured: list[FilmAcquired] = []
        d._event_bus.subscribe(FilmAcquired, captured.append)

        monkeypatch.setattr(_movie, "replace", MagicMock(return_value=False))  # move fails
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        result = d.dispatch_movie(staging_dir, CID.MOVIES)

        assert result.action == "error"
        assert captured == []  # no toast when the film did not actually land

    def test_record_dispatch_called_before_move(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """record_dispatch fires with the right kwargs BEFORE the FS move."""
        permit = _StubPermit(ALLOW)
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, existing_dir = _seed_existing_movie(d, tmp_path)

        order: list[str] = []
        recorder.record_dispatch.side_effect = lambda **_kw: order.append("record") or []

        def _replace_spy(*_a: object, **_kw: object) -> bool:
            order.append("move")
            return True

        monkeypatch.setattr(_movie, "replace", _replace_spy)
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        d.dispatch_movie(staging_dir, CID.MOVIES)

        recorder.record_dispatch.assert_called_once_with(
            staging_source=staging_dir,
            dispatched_dest=existing_dir,
        )
        # Write-before-move invariant: obligation recorded before the move.
        assert order == ["record", "move"]

    def test_dry_run_no_side_effects(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dry-run: no record_dispatch / mark_breach side effects."""
        permit = _StubPermit(veto("seedtime not met"))
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder, dry_run=True)
        staging_dir, _existing_dir = _seed_existing_movie(d, tmp_path)

        replace_mock = MagicMock(return_value=True)
        monkeypatch.setattr(_movie, "replace", replace_mock)
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        result = d.dispatch_movie(staging_dir, CID.MOVIES)

        assert result.action == "replaced"  # dry-run still reports the action
        replace_mock.assert_not_called()
        recorder.record_dispatch.assert_not_called()
        recorder.mark_breach.assert_not_called()

    def test_new_media_records_but_no_consult(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """New-media branch: record_dispatch fires, but no permit consult / breach."""
        permit = _StubPermit(veto("would veto if consulted"))
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)

        folder = "Brand New Movie (2025)"
        staging_dir = tmp_path / "staging" / folder
        staging_dir.mkdir(parents=True)
        (staging_dir / "movie.mkv").write_bytes(b"\x00" * 2048)

        monkeypatch.setattr(d, "_move_new", MagicMock(return_value=True))
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        result = d.dispatch_movie(staging_dir, CID.MOVIES)

        assert result.action == "moved"
        recorder.record_dispatch.assert_called_once()
        # No old library content on the new-media branch — never consult/breach.
        assert permit.consulted == []
        recorder.mark_breach.assert_not_called()


# ---------------------------------------------------------------------------
# TV merge branch — three states
# ---------------------------------------------------------------------------


class TestTvThreeState:
    """Three-state policy on the TV merge branch."""

    def test_veto_still_merges_and_records_breach(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """VETO on the old content: merge PROCEEDS + breach marked + hnr_risk logged."""
        permit = _StubPermit(veto("min_ratio not met"))
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, existing_dir = _seed_existing_show(d, tmp_path)

        merge_mock = MagicMock(return_value=True)
        monkeypatch.setattr(_tv, "merge", merge_mock)
        monkeypatch.setattr(
            _tv,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.TV_SHOWS, 500.0),
        )

        with caplog.at_level("WARNING"):
            result = d.dispatch_tvshow(staging_dir, CID.TV_SHOWS)

        assert result.action == "merged"
        merge_mock.assert_called_once()
        recorder.mark_breach.assert_called_once_with(existing_dir)
        assert "acquire.hnr_risk" in caplog.text

    def test_allow_merges_without_breach(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """ALLOW: merge proceeds, no breach, no hnr_risk log."""
        permit = _StubPermit(ALLOW)
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, _existing_dir = _seed_existing_show(d, tmp_path)

        monkeypatch.setattr(_tv, "merge", MagicMock(return_value=True))
        monkeypatch.setattr(
            _tv,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.TV_SHOWS, 500.0),
        )

        with caplog.at_level("WARNING"):
            result = d.dispatch_tvshow(staging_dir, CID.TV_SHOWS)

        assert result.action == "merged"
        recorder.mark_breach.assert_not_called()
        assert "acquire.hnr_risk" not in caplog.text

    def test_record_dispatch_called_before_move(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """record_dispatch fires with the right kwargs BEFORE the FS merge."""
        permit = _StubPermit(ALLOW)
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder)
        staging_dir, existing_dir = _seed_existing_show(d, tmp_path)

        order: list[str] = []
        recorder.record_dispatch.side_effect = lambda **_kw: order.append("record") or []

        def _merge_spy(*_a: object, **_kw: object) -> bool:
            order.append("move")
            return True

        monkeypatch.setattr(_tv, "merge", _merge_spy)
        monkeypatch.setattr(
            _tv,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.TV_SHOWS, 500.0),
        )

        d.dispatch_tvshow(staging_dir, CID.TV_SHOWS)

        recorder.record_dispatch.assert_called_once_with(
            staging_source=staging_dir,
            dispatched_dest=existing_dir,
        )
        assert order == ["record", "move"]

    def test_dry_run_no_side_effects(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """dry-run: no record_dispatch / mark_breach side effects."""
        permit = _StubPermit(veto("min_ratio not met"))
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=permit, recorder=recorder, dry_run=True)
        staging_dir, _existing_dir = _seed_existing_show(d, tmp_path)

        merge_mock = MagicMock(return_value=True)
        monkeypatch.setattr(_tv, "merge", merge_mock)
        monkeypatch.setattr(
            _tv,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.TV_SHOWS, 500.0),
        )

        result = d.dispatch_tvshow(staging_dir, CID.TV_SHOWS)

        assert result.action == "merged"
        merge_mock.assert_not_called()
        recorder.record_dispatch.assert_not_called()
        recorder.mark_breach.assert_not_called()


# ---------------------------------------------------------------------------
# F2 — fail-open permit consult at the dispatch deletion sites
# ---------------------------------------------------------------------------


class _RaisingPermit:
    """A permit whose may_delete always raises (F2 fail-open consult)."""

    def may_delete(self, path: Path) -> PermitDecision:
        """Raise unconditionally to simulate a broken store consult.

        Args:
            path: Ignored.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("permit boom")


class TestDispatchPermitConsultFailOpen:
    """F2: a raising permit consult must NOT crash dispatch (DESIGN §7.3 / §9).

    The replace/merge proceeds (real media wins), ``dispatch.permit_error`` is
    logged, and ``mark_breach`` is NOT called (a breach is only recorded on a
    positive VETO, never on an errored consult). Pre-fix the RuntimeError
    propagated out of the deletion site and crashed the dispatch.
    """

    def test_movie_replace_raising_permit_proceeds_no_crash(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Movie replace with a raising permit → replaced (ALLOW), logged, no breach."""
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=_RaisingPermit(), recorder=recorder)
        staging_dir, _existing_dir = _seed_existing_movie(d, tmp_path)

        replace_mock = MagicMock(return_value=True)
        monkeypatch.setattr(_movie, "replace", replace_mock)
        monkeypatch.setattr(
            _movie,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.MOVIES, 500.0),
        )

        with caplog.at_level("WARNING"):
            result = d.dispatch_movie(staging_dir, CID.MOVIES)

        # Real media wins — the replace proceeds, no crash.
        assert result.action == "replaced"
        replace_mock.assert_called_once()
        # Errored consult → NOT a breach.
        recorder.mark_breach.assert_not_called()
        assert "dispatch.permit_error" in caplog.text

    def test_tv_merge_raising_permit_proceeds_no_crash(
        self,
        test_config: object,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """TV merge with a raising permit → merged (ALLOW), logged, no breach."""
        recorder = MagicMock()
        d = _make_dispatcher(test_config, tmp_path, permit=_RaisingPermit(), recorder=recorder)
        staging_dir, _existing_dir = _seed_existing_show(d, tmp_path)

        merge_mock = MagicMock(return_value=True)
        monkeypatch.setattr(_tv, "merge", merge_mock)
        monkeypatch.setattr(
            _tv,
            "get_disk_status",
            lambda c: _disk_status(c.id, c.path, CID.TV_SHOWS, 500.0),
        )

        with caplog.at_level("WARNING"):
            result = d.dispatch_tvshow(staging_dir, CID.TV_SHOWS)

        assert result.action == "merged"
        merge_mock.assert_called_once()
        recorder.mark_breach.assert_not_called()
        assert "dispatch.permit_error" in caplog.text
