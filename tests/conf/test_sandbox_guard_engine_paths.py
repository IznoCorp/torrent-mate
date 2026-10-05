"""Tests for the sandbox guard on every engine write and purge path, driven under preprod.

Each family is driven twice: under ``PERSONALSCRAPER_ENV=staging`` a path aimed outside
preprod's marked, mounted roots is refused and nothing on disk is touched; with the
environment unset the same call behaves as before (the guard is a no-op).

``tmp_path`` is never a mount point, so ``is_mounted`` is patched. The Config is built
before the environment is switched to ``staging``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.conf import sandbox_guard
from personalscraper.conf.environment import Environment
from personalscraper.conf.sandbox_guard import SandboxGuardError, assert_all_within_sandbox, root_marker
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch._item import _refused_by_sandbox_guard
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.crash_recovery import (
    DISPATCH_TMP_PREFIX,
    INGEST_TMP_PREFIX,
    RootKind,
    SweepRoot,
    sweep_orphans,
)
from tests.conf.test_sandbox_guard import _config, _root

JUNK_NAME = ".DS_Store"


# Every sandbox environment (not prod): the guard must hold under each, with its own marker.
SANDBOX_ENVS = pytest.mark.parametrize("preprod", [Environment.STAGING, Environment.DEV], indirect=True, ids=str)


@pytest.fixture
def preprod(request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Build a Config over a marked disk and an UNMARKED staging tree, then mount everything.

    The roots carry the marker of ``request.param`` (staging unless a test parametrizes it
    with :data:`SANDBOX_ENVS`); ``.env`` holds that environment for :func:`_staging`.

    The staging tree holds a ``001-MOVIES`` category with a media folder carrying junk, a
    ``097-TEMP`` ingest dir with one loose item, so a step that touched it would show.
    """
    env: Environment = getattr(request, "param", Environment.STAGING)
    disk = _root(tmp_path, "disk", marked=False)
    (disk / root_marker(env)).write_text("", encoding="utf-8")
    stage = _root(tmp_path, "stage", marked=False)
    config = _config(tmp_path, disk, stage)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    movies = stage / "001-MOVIES"
    media = movies / "Film (2024)"
    media.mkdir(parents=True)
    (media / JUNK_NAME).write_bytes(b"x")
    (movies / "Empty Folder").mkdir()
    ingest = stage / "097-TEMP"
    ingest.mkdir()
    (ingest / "Loose.Film.2024.mkv").write_bytes(b"x" * 8)
    return SimpleNamespace(env=env, config=config, disk=disk, stage=stage, movies=movies, media=media, ingest=ingest)


def _staging(monkeypatch: pytest.MonkeyPatch, env: Environment = Environment.STAGING) -> None:
    """Put the process in a sandbox environment, ``staging`` by default (after the Config is built)."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", env.value)


# --- helper -----------------------------------------------------------------------------------


def test_assert_all_within_sandbox_judges_every_path(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One path outside the roots refuses the whole call, under staging only."""
    outside = tmp_path / "prod-media"
    inside = preprod.disk / "movies"
    with pytest.raises(SandboxGuardError):
        _staging(monkeypatch)
        assert_all_within_sandbox(preprod.config, inside, outside)
    monkeypatch.delenv("PERSONALSCRAPER_ENV")
    assert_all_within_sandbox(preprod.config, inside, outside)


# --- sweep_orphans (crash recovery) --------------------------------------------------------------


def _orphans(tmp_path: Path) -> tuple[Path, Path]:
    """Create a ``_tmp_dispatch_`` media orphan and an ``.ingest_tmp_`` orphan outside every root."""
    media_orphan = tmp_path / "prod-media" / "movies" / f"{DISPATCH_TMP_PREFIX}Film (2024)"
    media_orphan.mkdir(parents=True)
    (media_orphan / "partial.mkv").write_bytes(b"x")
    ingest_orphan = tmp_path / "prod-ingest" / f"{INGEST_TMP_PREFIX}Film"
    ingest_orphan.mkdir(parents=True)
    return media_orphan, ingest_orphan


@SANDBOX_ENVS
def test_sweep_orphans_refuses_roots_outside_preprod_under_staging(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under staging a sweep root outside the marked roots is skipped; its orphans stay."""
    media_orphan, ingest_orphan = _orphans(tmp_path)
    _staging(monkeypatch, preprod.env)
    cleaned = sweep_orphans(
        [
            SweepRoot(tmp_path / "prod-media", RootKind.MEDIA_TREE),
            SweepRoot(tmp_path / "prod-ingest", RootKind.INGEST_DIR),
        ],
        dry_run=False,
        config=preprod.config,
    )
    assert cleaned == 0
    assert media_orphan.exists()
    assert ingest_orphan.exists()


@SANDBOX_ENVS
def test_sweep_orphans_needs_the_config_under_staging(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under staging, a sweep with no config cannot know preprod's roots and removes nothing."""
    media_orphan, _ = _orphans(tmp_path)
    _staging(monkeypatch, preprod.env)
    with pytest.raises(SandboxGuardError):
        sweep_orphans([SweepRoot(tmp_path / "prod-media", RootKind.MEDIA_TREE)], dry_run=False)
    assert media_orphan.exists()


@SANDBOX_ENVS
def test_sweep_orphans_cleans_inside_preprod_under_staging(
    preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A root inside a marked, mounted preprod root is swept as usual."""
    orphan = preprod.disk / "movies" / f"{DISPATCH_TMP_PREFIX}Film (2024)"
    orphan.mkdir(parents=True)
    _staging(monkeypatch, preprod.env)
    assert sweep_orphans([SweepRoot(preprod.disk, RootKind.MEDIA_TREE)], dry_run=False, config=preprod.config) == 1
    assert not orphan.exists()


def test_sweep_orphans_is_unchanged_outside_staging(preprod: SimpleNamespace, tmp_path: Path) -> None:
    """Environment unset: the same outside-root sweep removes the orphan, with or without a config."""
    media_orphan, ingest_orphan = _orphans(tmp_path)
    assert sweep_orphans([SweepRoot(tmp_path / "prod-media", RootKind.MEDIA_TREE)], dry_run=False) == 1
    assert (
        sweep_orphans([SweepRoot(tmp_path / "prod-ingest", RootKind.INGEST_DIR)], dry_run=False, config=preprod.config)
        == 1
    )
    assert not media_orphan.exists()
    assert not ingest_orphan.exists()


def test_sweep_orphans_without_a_config_is_unchanged_in_prod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``PERSONALSCRAPER_ENV`` unset: a sweep with no config and no marker removes the orphan, as before."""
    monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: False)
    media_orphan, _ = _orphans(tmp_path)
    assert sweep_orphans([SweepRoot(tmp_path / "prod-media", RootKind.MEDIA_TREE)], dry_run=False) == 1
    assert not media_orphan.exists()


# --- ingest ---------------------------------------------------------------------------------------


def test_run_ingest_refuses_an_unmarked_staging_tree(preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ingest creates, sweeps and moves nothing when staging is not a marked root."""
    from personalscraper.ingest.ingest import run_ingest

    orphan = preprod.ingest / f"{INGEST_TMP_PREFIX}Film"
    orphan.mkdir()
    elsewhere = preprod.stage.parent / "other-ingest"
    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        run_ingest(MagicMock(), config=preprod.config, event_bus=EventBus())
    with pytest.raises(SandboxGuardError):
        run_ingest(MagicMock(), ingest_dir=elsewhere, config=preprod.config, event_bus=EventBus())
    assert orphan.exists()
    assert not elsewhere.exists()


# --- sort -----------------------------------------------------------------------------------------


def test_sorter_refuses_a_move_outside_preprod(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sorted item and its destination must both be inside a root: the move is refused."""
    from personalscraper.sorter.cleaner import NameCleaner
    from personalscraper.sorter.sorter import Sorter

    source = tmp_path / "prod-ingest" / "Film.2024.1080p.mkv"
    source.parent.mkdir()
    source.write_bytes(b"x")
    dest_root = tmp_path / "prod-staging"
    dest_root.mkdir()
    sorter = Sorter(config=preprod.config, cleaner=NameCleaner(), dry_run=False)
    _staging(monkeypatch)
    result = sorter.sort_item(source, dest_root)
    assert result.status == "error"
    assert "sandbox root" in (result.message or "")
    assert source.exists()
    assert list(dest_root.iterdir()) == []


def test_sorter_moves_as_before_outside_staging(preprod: SimpleNamespace, tmp_path: Path) -> None:
    """Environment unset: the same move outside the roots goes through."""
    from personalscraper.sorter.cleaner import NameCleaner
    from personalscraper.sorter.sorter import Sorter

    source = tmp_path / "prod-ingest" / "Film.2024.1080p.mkv"
    source.parent.mkdir()
    source.write_bytes(b"x")
    dest_root = tmp_path / "prod-staging"
    dest_root.mkdir()
    result = Sorter(config=preprod.config, cleaner=NameCleaner(), dry_run=False).sort_item(source, dest_root)
    assert result.status == "moved"
    assert not source.exists()


def test_run_sort_refuses_an_unmarked_staging_tree(preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sort step moves nothing out of an ingest dir that is not under a marked root."""
    from personalscraper.sorter.run import run_sort

    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        run_sort(MagicMock(), preprod.stage, preprod.config, event_bus=EventBus())
    assert (preprod.ingest / "Loose.Film.2024.mkv").exists()


# --- process (clean, cleanup) -----------------------------------------------------------------------


def test_run_clean_refuses_an_unmarked_staging_tree(preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean (extract, reclean, dedup) touches nothing when staging is not a marked root."""
    from personalscraper.process.run import run_clean

    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        run_clean(MagicMock(), preprod.config, event_bus=EventBus())
    assert (preprod.media / JUNK_NAME).exists()


def test_run_cleanup_refuses_an_unmarked_staging_tree(
    preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cleanup removes no empty directory when staging is not a marked root."""
    from personalscraper.process.run import run_cleanup

    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        run_cleanup(MagicMock(), preprod.config, event_bus=EventBus())
    assert (preprod.movies / "Empty Folder").exists()


def test_run_cleanup_is_unchanged_outside_staging(preprod: SimpleNamespace) -> None:
    """Environment unset: the same cleanup removes the empty directory."""
    from personalscraper.process.run import run_cleanup

    run_cleanup(MagicMock(), preprod.config, event_bus=EventBus())
    assert not (preprod.movies / "Empty Folder").exists()


# --- scrape ---------------------------------------------------------------------------------------


def test_run_scrape_refuses_an_unmarked_staging_tree(preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """The scrape step writes no NFO or artwork when staging is not a marked root."""
    from personalscraper.scraper.run import run_scrape

    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        run_scrape(MagicMock(), preprod.config, event_bus=EventBus(), registry=MagicMock())
    assert sorted(p.name for p in preprod.media.iterdir()) == [JUNK_NAME]


# --- enforce --------------------------------------------------------------------------------------


def test_run_enforce_refuses_an_unmarked_staging_tree(
    preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Enforce (sanitize, structure) deletes and renames nothing when staging is not a marked root."""
    from personalscraper.enforce.run import run_enforce

    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        run_enforce(MagicMock(), preprod.config, event_bus=EventBus())
    assert (preprod.media / JUNK_NAME).exists()


def test_run_enforce_is_unchanged_outside_staging(preprod: SimpleNamespace) -> None:
    """Environment unset: the same enforce deletes the junk file."""
    from personalscraper.enforce.run import run_enforce

    run_enforce(MagicMock(), preprod.config, event_bus=EventBus())
    assert not (preprod.media / JUNK_NAME).exists()


# --- verify ---------------------------------------------------------------------------------------


@SANDBOX_ENVS
def test_run_verify_refuses_an_unmarked_staging_tree(preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify (with its auto-fixes) touches nothing when staging is not a marked root."""
    from personalscraper.verify.run import run_verify

    _staging(monkeypatch, preprod.env)
    with pytest.raises(SandboxGuardError):
        run_verify(MagicMock(), preprod.config, event_bus=EventBus())
    assert (preprod.media / JUNK_NAME).exists()


def test_run_verify_is_unchanged_in_prod(preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    """``PERSONALSCRAPER_ENV`` unset: verify runs over the same unmarked staging tree without a refusal."""
    from personalscraper.verify.run import run_verify

    monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)
    report, _ = run_verify(MagicMock(), preprod.config, event_bus=EventBus())
    assert report.name == "verify"


# --- dispatch (staging source purge) ----------------------------------------------------------------


def test_dispatch_refuses_a_source_outside_preprod(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A destination inside a root is not enough: the staging source the transfer purges is judged too."""
    dispatcher: Any = SimpleNamespace(config=preprod.config)
    result = DispatchResult(source=tmp_path / "prod-staging" / "Film (2024)")
    _staging(monkeypatch)
    assert _refused_by_sandbox_guard(dispatcher, result, preprod.disk / "movies" / "Film (2024)") is True
    assert result.action == "error"


# --- maintenance rescraper ----------------------------------------------------------------------------


def test_rescrape_library_refuses_an_item_outside_preprod(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rescrape candidate outside the roots is reported as an error and never rescraped."""
    from personalscraper.maintenance import rescraper

    outside = tmp_path / "prod-media" / "Film (2024)"
    outside.mkdir(parents=True)
    rescrape_item = MagicMock()
    monkeypatch.setattr(rescraper, "_collect_rescrape_candidates", lambda *a, **k: [(outside, "movie", "d", "c", None)])
    monkeypatch.setattr(rescraper, "_rescrape_item", rescrape_item)
    _staging(monkeypatch)
    result = rescraper.rescrape_library(preprod.config, dry_run=False, event_bus=EventBus(), registry=MagicMock())
    assert result.error_count == 1
    rescrape_item.assert_not_called()


# --- trailers -------------------------------------------------------------------------------------


def test_trailer_download_is_refused_outside_preprod(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The orchestrator downloads no trailer to a path outside the roots; it counts an error."""
    from personalscraper.trailers.orchestrator import TrailersOrchestrator

    orchestrator = object.__new__(TrailersOrchestrator)
    orchestrator._config = preprod.config
    orchestrator._downloader = MagicMock()
    ctx = MagicMock()
    ctx.min_size = 1
    counts = {"error": 0}
    _staging(monkeypatch)
    orchestrator._download_and_record(
        MagicMock(title="Film"), "key", tmp_path / "prod-media" / "Film-trailer.mp4", "https://x", ctx, counts
    )
    assert counts["error"] == 1
    orchestrator._downloader.download.assert_not_called()


def test_trailers_purge_refuses_a_trailer_outside_preprod(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``trailers purge`` unlinks no orphan trailer outside the roots under staging; unset, it does."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from personalscraper.cli import app
    from tests.trailers.test_cli import _PATCH_LOAD_CONFIG, _fake_config

    trailer = tmp_path / "prod-media" / "Film (2024)" / "Film (2024)-trailer.mp4"
    trailer.parent.mkdir(parents=True)
    trailer.write_bytes(b"x")
    cfg = _fake_config(tmp_path)
    cfg.paths.staging_dir = preprod.disk
    cfg.disks = []
    cfg.torrent.clients = {}

    def purge() -> None:
        with (
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch("personalscraper.trailers.cli.TrailerStateStore") as store,
            patch("personalscraper.trailers.cli._discover_fs_orphan_trailers", return_value=([trailer], [])),
            patch("personalscraper.trailers.cli._disk_paths_for", return_value=[]),
            patch("personalscraper.trailers.cli._heal_index_gaps", return_value=0),
        ):
            store.return_value.all_entries.return_value = {}
            result = CliRunner().invoke(app, ["trailers", "purge"], catch_exceptions=False)
        assert result.exit_code == 0, result.output

    _staging(monkeypatch)
    purge()
    assert trailer.exists()
    monkeypatch.delenv("PERSONALSCRAPER_ENV")
    purge()
    assert not trailer.exists()


def test_library_fix_nfo_refuses_an_nfo_outside_preprod(
    preprod: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``library-fix-nfo --apply`` writes neither the backup nor the NFO outside the roots; unset, it does."""
    import sqlite3

    from personalscraper.commands.library.fix_nfo import library_fix_nfo
    from tests.commands._e2e_helpers import make_synthetic_db
    from tests.commands.test_library_fix_nfo_e2e import (
        _insert_media_item,
        _set_dispatch_path,
        _trailing_url_tvshow_nfo,
    )

    show = tmp_path / "prod-media" / "My Show"
    show.mkdir(parents=True)
    nfo = show / "tvshow.nfo"
    original = _trailing_url_tvshow_nfo()
    nfo.write_text(original, encoding="utf-8")
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    _set_dispatch_path(conn, _insert_media_item(conn), str(show))
    conn.close()
    ctx: Any = SimpleNamespace(obj=SimpleNamespace(config=preprod.config))

    _staging(monkeypatch)
    library_fix_nfo(ctx, apply=True, config=None, db=db_path)
    assert nfo.read_text(encoding="utf-8") == original
    assert not (show / "tvshow.nfo.bak").exists()
    monkeypatch.delenv("PERSONALSCRAPER_ENV")
    library_fix_nfo(ctx, apply=True, config=None, db=db_path)
    assert nfo.read_text(encoding="utf-8") != original
    assert (show / "tvshow.nfo.bak").exists()


# --- forced scrape (spine rescrape, scrape-resolve) --------------------------------------------------


def _tree(root: Path) -> list[str]:
    """Snapshot every entry under *root* (relative), to prove nothing was written or renamed."""
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _forced_scraper(preprod: SimpleNamespace) -> Any:
    """Build a Scraper over the preprod Config whose provider call fails soft when reached."""
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper.orchestrator import Scraper

    registry = MagicMock()
    registry.get.return_value.get_movie.side_effect = RuntimeError("provider down")
    scraper = Scraper(MagicMock(), NamingPatterns(), config=preprod.config, event_bus=EventBus(), registry=registry)
    registry.get.reset_mock()  # drop the construction-time lookups; keeps the configured side effect
    return scraper


def test_scrape_movie_forced_refuses_a_folder_outside_preprod(
    preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The forced movie scrape raises on an unmarked folder: no provider call, no NFO, no rename."""
    (preprod.media / "Film.2024.1080p.mkv").write_bytes(b"x")
    scraper = _forced_scraper(preprod)
    before = _tree(preprod.stage)
    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        scraper.scrape_movie_forced(preprod.media, 603)
    assert _tree(preprod.stage) == before
    scraper._registry.get.assert_not_called()


def test_scrape_movie_forced_is_unchanged_outside_staging(preprod: SimpleNamespace) -> None:
    """Env unset: the guard is a no-op and the forced scrape reaches the provider (fail-soft error result)."""
    scraper = _forced_scraper(preprod)
    result = scraper.scrape_movie_forced(preprod.media, 603)
    assert result.action == "error"
    scraper._registry.get.assert_called_once_with("tmdb")


def test_scrape_tvshow_forced_refuses_a_folder_outside_preprod(
    preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The forced TV scrape raises on an unmarked folder: no series lookup, no NFO, no rename."""
    show = preprod.stage / "002-TVSHOWS" / "Show.2024"
    (show / "Season 1").mkdir(parents=True)
    (show / "Season 1" / "Show.S01E01.mkv").write_bytes(b"x")
    scraper = _forced_scraper(preprod)
    scraper._forced_series_lookup = MagicMock(return_value=None)
    before = _tree(preprod.stage)
    _staging(monkeypatch)
    with pytest.raises(SandboxGuardError):
        scraper.scrape_tvshow_forced(show, "tvdb", 1)
    assert _tree(preprod.stage) == before
    scraper._forced_series_lookup.assert_not_called()


def test_scrape_tvshow_forced_is_unchanged_outside_staging(preprod: SimpleNamespace) -> None:
    """Env unset: the guard is a no-op and the forced TV scrape proceeds to the series lookup."""
    show = preprod.stage / "002-TVSHOWS" / "Show.2024"
    show.mkdir(parents=True)
    scraper = _forced_scraper(preprod)
    scraper._forced_series_lookup = MagicMock(return_value=None)
    scraper.scrape_tvshow_forced(show, "tvdb", 1)
    scraper._forced_series_lookup.assert_called_once()


def test_spine_rescrape_row_fails_the_refused_item_only(
    preprod: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refusal inside the spine's per-item try/except is a 'failed' item, never a raised batch abort."""
    from contextlib import nullcontext

    from personalscraper.commands import spine

    row: Any = SimpleNamespace(
        current_path=str(preprod.media), kind="movie", media_ref=SimpleNamespace(tmdb_id=603, tvdb_id=None)
    )
    monkeypatch.setattr("personalscraper.scraper.run._open_provenance_store", lambda config: None)
    monkeypatch.setattr(
        spine,
        "per_step_boundary",
        lambda config, settings: nullcontext(SimpleNamespace(event_bus=EventBus(), provider_registry=MagicMock())),
    )
    before = _tree(preprod.stage)
    _staging(monkeypatch)
    assert spine._rescrape_row(row, preprod.config, MagicMock(), "run-1") == "failed"
    assert _tree(preprod.stage) == before


# --- ingest: the per-torrent transfer -----------------------------------------------------------------


def test_ingest_refuses_a_torrent_source_outside_preprod_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under staging a torrent whose payload is outside the roots fails alone: untouched, batch goes on."""
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.ingest.ingest import run_ingest

    disk = _root(tmp_path, "disk")
    stage = _root(tmp_path, "stage")
    config = _config(tmp_path, disk, stage)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    ingest_dir = stage / "097-TEMP"
    bad = tmp_path / "prod-downloads" / "Bad.Film.2024"
    bad.mkdir(parents=True)
    (bad / "Bad.Film.2024.mkv").write_bytes(b"x" * 8)
    good = disk / "downloads" / "Good.Film.2024"
    good.mkdir(parents=True)
    (good / "Good.Film.2024.mkv").write_bytes(b"x" * 8)

    torrents = [
        TorrentItem(hash=h, name=n, size_bytes=8, progress=1.0, state="uploading", ratio=2.0, tags=[])
        for h, n in (("a" * 40, "Bad.Film.2024"), ("b" * 40, "Good.Film.2024"))
    ]
    client = MagicMock()
    client.get_completed.return_value = torrents
    client.get_all_hashes.return_value = {t.hash for t in torrents}
    client.get_content_path.side_effect = lambda t: {"Bad.Film.2024": bad, "Good.Film.2024": good}[t.name]
    client.is_seeding.return_value = True  # copy: a refused move would purge the download dir

    _staging(monkeypatch)
    report = run_ingest(MagicMock(), ingest_dir=ingest_dir, config=config, event_bus=EventBus(), torrent_client=client)

    assert report.error_count == 1
    assert report.success_count == 1
    assert (bad / "Bad.Film.2024.mkv").read_bytes() == b"x" * 8
    assert not (ingest_dir / "Bad.Film.2024").exists()
    assert (ingest_dir / "Good.Film.2024" / "Good.Film.2024.mkv").exists()
