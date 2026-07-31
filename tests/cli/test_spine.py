"""Tests for the spine-driven targeted actions CLI (feature ``spine-actions``, F4).

- ``acquisition-requeue`` traces info_hash → its grabbed wanted row and sends it to pending.
- ``acquisition-rescrape`` re-scrapes a tracked staging item via the forced id from the
  spine's media_ref seed, keeps current_path live across the rename, and records the scrape
  stage. A manual item (no media_ref) and a dry-run are no-ops.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import build_acquire_store
from personalscraper.cli import app
from personalscraper.core.identity import MediaRef
from tests.conftest import make_cli_runner

runner = make_cli_runner()

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_MOVIE_FORCED = "personalscraper.scraper.orchestrator.Scraper.scrape_movie_forced"


def _cfg_with_acquire(test_config: Any, acquire_db: Path) -> Any:
    """Return *test_config* with its acquire sub-config pointed at *acquire_db*."""
    return test_config.model_copy(update={"acquire": test_config.acquire.model_copy(update={"db_path": acquire_db})})


def _mock_boundary(mock_client: Any) -> Any:
    """A per_step_boundary replacement yielding a mock app_context."""

    @contextmanager
    def _cm(config: Any, settings: Any) -> Any:
        ctx = MagicMock()
        ctx.provider_registry = MagicMock()
        ctx.provider_registry.get.return_value = mock_client
        yield ctx

    return _cm


def _forced_movie_ok(staging_path: Path, provider_id: int) -> Any:
    """Stub forced-movie scrape: land an NFO + return scraped (media_path unchanged)."""
    from personalscraper.scraper._shared import ScrapeResult

    (staging_path / "movie.nfo").write_text("<movie/>")
    result = ScrapeResult(media_path=staging_path, media_type="movie")
    result.action = "scraped"
    return result


# ── acquisition-requeue ─────────────────────────────────────────────────────────


def test_requeue_sends_grabbed_wanted_row_to_pending(test_config: Any, tmp_path: Path) -> None:
    """acquisition-requeue --hash traces the grab → its wanted row → pending (F4 ACC-F4-03)."""
    acquire_db = tmp_path / "acquire.db"
    cfg = _cfg_with_acquire(test_config, acquire_db)

    store = build_acquire_store(cfg.acquire)
    try:
        wid = store.wanted.add(
            WantedItem(media_ref=MediaRef(tmdb_id=27205), kind="movie", status="pending", enqueued_at=1)
        )
        store.wanted.mark_grabbed(wid, "grabHASH")
        store.provenance.upsert_grab(
            "grabHASH", followed_id=None, media_ref=MediaRef(tmdb_id=27205), kind="movie", grabbed_at=1
        )
    finally:
        store.close()

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        result = runner.invoke(app, ["acquisition-requeue", "--hash", "grabHASH"])

    assert result.exit_code == 0, result.output
    store = build_acquire_store(cfg.acquire)
    try:
        row = store.wanted.get(wid)
        assert row is not None
        assert row.status == "pending"  # requeued
        assert row.grabbed_hash is None  # hash cleared
    finally:
        store.close()


def test_requeue_dry_run_does_not_touch_wanted(test_config: Any, tmp_path: Path) -> None:
    """--dry-run previews without transitioning the wanted row."""
    acquire_db = tmp_path / "acquire.db"
    cfg = _cfg_with_acquire(test_config, acquire_db)
    store = build_acquire_store(cfg.acquire)
    try:
        wid = store.wanted.add(WantedItem(media_ref=MediaRef(tmdb_id=1), kind="movie", status="pending", enqueued_at=1))
        store.wanted.mark_grabbed(wid, "h")
        store.provenance.upsert_grab("h", followed_id=None, media_ref=MediaRef(tmdb_id=1), kind="movie", grabbed_at=1)
    finally:
        store.close()

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
    ):
        result = runner.invoke(app, ["acquisition-requeue", "--hash", "h", "--dry-run"])

    assert result.exit_code == 0, result.output
    store = build_acquire_store(cfg.acquire)
    try:
        assert store.wanted.get(wid).status == "grabbed"  # type: ignore[union-attr]
    finally:
        store.close()


# ── acquisition-rescrape ────────────────────────────────────────────────────────


def test_rescrape_by_hash_records_scrape_stage(test_config: Any, tmp_path: Path) -> None:
    """acquisition-rescrape --hash re-scrapes via the media_ref seed + records the stage (ACC-F4-02)."""
    staging = tmp_path / "staging" / "001-MOVIES" / "Inception"
    staging.mkdir(parents=True)
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    acquire_db = tmp_path / "acquire.db"
    cfg = _cfg_with_acquire(test_config, acquire_db)

    store = build_acquire_store(cfg.acquire)
    try:
        store.provenance.upsert_grab(
            "h", followed_id=None, media_ref=MediaRef(tmdb_id=27205), kind="movie", grabbed_at=1
        )
        store.provenance.set_ingest("h", ingest_path=str(staging), ingested_at=2)
    finally:
        store.close()

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch("personalscraper.commands.spine.acquire_scrape_resolve_lock", return_value=Path("/fake/scrape.lock")),
        patch("personalscraper.commands.spine.release_scrape_resolve_lock"),
        patch("personalscraper.commands.spine.per_step_boundary", _mock_boundary(MagicMock())),
        patch(_PATCH_MOVIE_FORCED, side_effect=_forced_movie_ok),
    ):
        result = runner.invoke(app, ["acquisition-rescrape", "--hash", "h"])

    assert result.exit_code == 0, result.output
    store = build_acquire_store(cfg.acquire)
    try:
        row = store.provenance.by_path(str(staging))
        assert row is not None
        assert row.status == "scraped"  # scrape stage recorded
        assert row.scraped_at is not None
    finally:
        store.close()


def test_rescrape_skips_manual_item_without_media_ref(test_config: Any, tmp_path: Path) -> None:
    """A tracked row with NO media_ref (manual seed) is skipped — never scraped."""
    staging = tmp_path / "staging" / "001-MOVIES" / "Manual"
    staging.mkdir(parents=True)
    test_config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    acquire_db = tmp_path / "acquire.db"
    cfg = _cfg_with_acquire(test_config, acquire_db)

    store = build_acquire_store(cfg.acquire)
    try:
        store.provenance.upsert_grab("h", followed_id=None, media_ref=None, kind="movie", grabbed_at=1)
        store.provenance.set_ingest("h", ingest_path=str(staging), ingested_at=2)
    finally:
        store.close()

    forced = MagicMock()
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch("personalscraper.commands.spine.acquire_scrape_resolve_lock", return_value=Path("/fake/scrape.lock")),
        patch("personalscraper.commands.spine.per_step_boundary", _mock_boundary(MagicMock())),
        patch(_PATCH_MOVIE_FORCED, forced),
    ):
        result = runner.invoke(app, ["acquisition-rescrape", "--hash", "h"])

    assert result.exit_code == 0, result.output
    forced.assert_not_called()  # no media_ref → skipped before any scrape
    store = build_acquire_store(cfg.acquire)
    try:
        assert store.provenance.by_hash("h").status == "ingested"  # type: ignore[union-attr]
    finally:
        store.close()
