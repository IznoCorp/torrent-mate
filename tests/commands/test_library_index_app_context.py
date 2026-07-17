"""Sub-phase 2.5 invariants for ``personalscraper library-index`` CLI entry.

Verifies that the launchd command boundary in
``personalscraper.commands.library.scan`` builds an :class:`AppContext`
via ``_build_app_context``, binds ``current_correlation_id`` for the
duration of the scan, and threads the :class:`EventBus` (NOT the full
``AppContext``) to ``library_index_command``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.cli import app
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus, current_correlation_id

runner = CliRunner()


def _patches():
    """Build a capturing wrapper around the real ``_build_app_context``.

    Returns:
        Tuple of (wrapped callable suitable for ``patch(..., side_effect=...)``,
        list that accumulates every constructed :class:`AppContext`).
    """
    real_app: list[AppContext] = []

    # Bind the real factory once OUTSIDE the wrapper. Using
    # ``from personalscraper.cli_helpers import _build_app_context`` inside
    # ``_capturing_build`` would resolve to the patched mock and recurse
    # infinitely, because the ``library_index`` command body re-imports the
    # name on every call.
    def _capturing_build(config, settings):  # type: ignore[no-untyped-def]
        ctx = AppContext(
            config=config,
            settings=settings,
            event_bus=EventBus(),
            provider_registry=MagicMock(spec=ProviderRegistry),
        )
        real_app.append(ctx)
        return ctx

    return _capturing_build, real_app


class TestLibraryIndexCommandAppContext:
    """The launchd ``library-index`` command builds an AppContext at its boundary."""

    def test_library_index_command_builds_app_context(self) -> None:
        """``_build_app_context`` is invoked exactly once per ``library-index`` run."""
        capturing, captured = _patches()
        with (
            patch("personalscraper.cli_helpers._build_app_context", side_effect=capturing),
            patch(
                "personalscraper.indexer.cli.library_index_command",
                return_value=0,
            ),
        ):
            result = runner.invoke(app, ["library-index", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert len(captured) == 1
        assert isinstance(captured[0], AppContext)
        assert isinstance(captured[0].event_bus, EventBus)

    def test_library_index_command_binds_correlation_id(self) -> None:
        """``current_correlation_id`` is set during the scan and reset on exit."""
        observed: list[str | None] = []
        capturing, _captured = _patches()

        def _spy_orchestrator(**kwargs) -> int:  # type: ignore[no-untyped-def]  # noqa: ANN003
            observed.append(current_correlation_id.get())
            return 0

        with (
            patch("personalscraper.cli_helpers._build_app_context", side_effect=capturing),
            patch(
                "personalscraper.indexer.cli.library_index_command",
                side_effect=_spy_orchestrator,
            ),
        ):
            assert current_correlation_id.get() is None
            result = runner.invoke(app, ["library-index", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert len(observed) == 1
        assert observed[0] is not None
        # 36-char UUID v4 string (8-4-4-4-12 hex).
        assert len(observed[0]) == 36
        # Reset to ``None`` after the command returns.
        assert current_correlation_id.get() is None

    def test_library_index_command_passes_event_bus_to_orchestrator(self) -> None:
        """``library_index_command`` receives ``event_bus`` (NOT the full AppContext)."""
        captured_kwargs: dict = {}
        capturing, _captured = _patches()

        def _spy(**kwargs) -> int:  # type: ignore[no-untyped-def]  # noqa: ANN003
            captured_kwargs.update(kwargs)
            return 0

        with (
            patch("personalscraper.cli_helpers._build_app_context", side_effect=capturing),
            patch(
                "personalscraper.indexer.cli.library_index_command",
                side_effect=_spy,
            ),
        ):
            result = runner.invoke(app, ["library-index", "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "event_bus" in captured_kwargs
        assert isinstance(captured_kwargs["event_bus"], EventBus)
        # The orchestrator receives ONLY the bus, NOT the AppContext.
        assert not any(isinstance(v, AppContext) for v in captured_kwargs.values())


# A MagicMock-friendly assertion guard kept for completeness — see DESIGN
# §Testing strategy: cross-boundary contracts always assert on the exact
# type the receiver is expected to handle (``EventBus`` vs ``AppContext``).
_ = MagicMock


class TestLibraryIndexCommandBusPassThrough:
    """Regression: ``library_index_command`` threads its ``event_bus`` to scan + open_db.

    Pre-fix the function declared ``event_bus`` in its signature but ignored
    the parameter, constructing a throwaway ``EventBus()`` at every internal
    call site (open_db x2, scan x1). Effect: ``DiskFullWarning``,
    ``LibraryScanCompleted``, and every disk-breaker ``CircuitBreaker*`` event
    emitted during a ``personalscraper library-index`` run landed on a bus
    with no subscribers, silently breaking the launchd→Telegram contract.
    """

    def test_library_index_command_forwards_bus_to_scan_and_open_db(self, tmp_path) -> None:
        """The bus given to ``library_index_command`` reaches ``open_db`` and ``scan``."""
        from pathlib import Path

        from personalscraper.conf.models.indexer import IndexerConfig
        from personalscraper.indexer.cli import library_index_command
        from personalscraper.indexer.scanner import ScanRunResult

        caller_bus = EventBus()
        scan_requests: list = []
        open_db_calls: list[dict] = []

        # Minimal config with db_path under tmp_path so indexer_lock works.
        mock_cfg = MagicMock()
        mock_cfg.indexer = IndexerConfig(db_path=tmp_path / "library.db")
        mock_cfg.paths.staging_dir = tmp_path / "staging"
        mock_cfg.disks = []

        # Stub the conn so library_index_command's internal SELECTs return
        # benign empty results without needing a real schema.
        def _fake_open_db(db_path, *, rebuild=False, event_bus):  # type: ignore[no-untyped-def]
            open_db_calls.append({"db_path": db_path, "event_bus": event_bus, "rebuild": rebuild})
            mock_conn = MagicMock()
            # disk COUNT(*) row → 0 (disk table empty branch).
            # MAX(scan_generation) row → 0.
            # SELECT id, uuid, ... FROM disk → 0 rows.
            mock_conn.execute.return_value.fetchone.return_value = [0]
            mock_conn.execute.return_value.fetchall.return_value = []
            return mock_conn

        def _spy_scan(request) -> ScanRunResult:  # type: ignore[no-untyped-def]  # noqa: ANN001
            # library_index_command now builds a ScanRequest and calls
            # scan_with(request); capture the request to assert on its bus.
            scan_requests.append(request)
            return ScanRunResult(scan_run_id=1, files_visited=0, dirs_visited=0, status="ok", disks_skipped=0)

        with (
            patch("personalscraper.conf.loader.load_config", return_value=mock_cfg),
            patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/tmp/cfg.json5")),
            patch("personalscraper.indexer.db.open_db", side_effect=_fake_open_db),
            patch("personalscraper.indexer.db.apply_migrations"),
            patch("personalscraper.indexer.scanner.scan_with", side_effect=_spy_scan),
            patch("personalscraper.indexer.outbox._drain.drain_if_present", return_value=0),
        ):
            rc = library_index_command(
                mode="full",
                dry_run=True,
                event_bus=caller_bus,
            )

        assert rc == 0, f"library_index_command returned {rc}"
        # open_db must have received the caller's bus, not a throwaway.
        assert open_db_calls, "open_db was not called"
        assert open_db_calls[0]["event_bus"] is caller_bus, (
            "open_db must receive the bus passed to library_index_command, not a fresh EventBus() with no subscribers."
        )
        # scan must also have received the caller's bus (via the ScanRequest).
        assert scan_requests, "scan_with was not called"
        assert scan_requests[0].event_bus is caller_bus, (
            "scan must receive the bus passed to library_index_command, not a fresh EventBus() with no subscribers."
        )


class TestLibraryBackfillIdsRegistryWiring:
    """Phase 11 migration: CLI passes the shared registry to ``run_backfill_ids``.

    Before Phase 11 the CLI extracted four typed clients via
    ``registry.get("tmdb")`` / ``"tvdb"`` / ``"imdb"`` / ``"rotten_tomatoes"``,
    each wrapped in ``try/except UnknownProviderError`` that logged a
    ``library_backfill_provider_unavailable`` warning per missing provider.
    Sub-phase 11.5 dropped that scaffolding — provider eligibility is now
    handled inside the registry's ``chain()`` / ``fan_out()`` semantics, and
    the CLI simply forwards ``app_context.provider_registry``.

    The pre-Phase-11 test (``test_library_backfill_logs_warning_on_missing_provider``)
    asserted on the now-removed log line; replaced with an assertion that
    pins the new wiring contract: the registry instance passed to
    ``run_backfill_ids`` is the same one carried by the AppContext.
    """

    def test_library_backfill_forwards_registry_from_app_context(self, tmp_path):
        """``library-backfill-ids`` passes ``app_context.provider_registry`` to the driver."""
        from pathlib import Path

        mock_registry = MagicMock(spec=ProviderRegistry)

        mock_app_ctx = MagicMock(spec=AppContext)
        mock_app_ctx.event_bus = EventBus()
        mock_app_ctx.provider_registry = mock_registry

        mock_cfg = MagicMock()
        mock_cfg.indexer.db_path = tmp_path / "library.db"

        mock_stats = MagicMock()
        mock_stats.items_scanned = 0
        mock_stats.items_updated = 0
        mock_stats.items_skipped = 0
        mock_stats.items_failed = 0
        mock_stats.ids_added_count = 0
        mock_stats.ratings_added_count = 0

        captured: list[dict] = []

        def _spy(conn, **kwargs):
            captured.append(kwargs)
            return mock_stats

        with (
            patch("personalscraper.logger.configure_logging"),
            patch("personalscraper.conf.loader.load_config", return_value=mock_cfg),
            patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/tmp/cfg.json5")),
            patch("personalscraper.cli_helpers._build_app_context", return_value=mock_app_ctx),
            patch("personalscraper.cli_helpers.get_settings", return_value=MagicMock()),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.indexer.db.apply_migrations"),
            patch(
                "personalscraper.indexer.scanner._modes.backfill_ids.run_backfill_ids",
                side_effect=_spy,
            ),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--ids-only"])

        assert result.exit_code == 0, result.output
        assert len(captured) == 1
        # The CLI must hand the AppContext's registry to the driver verbatim —
        # not a copy, not a re-extracted typed-client tuple.
        assert captured[0]["registry"] is mock_registry
        # The four legacy typed-client kwargs no longer exist on the driver
        # signature; pin that no caller silently re-adds them.
        assert "tmdb_client" not in captured[0]
        assert "tvdb_client" not in captured[0]
        assert "imdb_client" not in captured[0]
        assert "rt_client" not in captured[0]

    def test_library_backfill_dry_run_passes_none_registry(self, tmp_path):
        """``--dry-run`` short-circuits the registry path with ``registry=None``."""
        from pathlib import Path

        mock_registry = MagicMock(spec=ProviderRegistry)

        mock_app_ctx = MagicMock(spec=AppContext)
        mock_app_ctx.event_bus = EventBus()
        mock_app_ctx.provider_registry = mock_registry

        mock_cfg = MagicMock()
        mock_cfg.indexer.db_path = tmp_path / "library.db"

        mock_stats = MagicMock()
        mock_stats.items_scanned = 0
        mock_stats.items_updated = 0
        mock_stats.items_skipped = 0
        mock_stats.items_failed = 0
        mock_stats.ids_added_count = 0
        mock_stats.ratings_added_count = 0

        captured: list[dict] = []

        def _spy(conn, **kwargs):
            captured.append(kwargs)
            return mock_stats

        with (
            patch("personalscraper.logger.configure_logging"),
            patch("personalscraper.conf.loader.load_config", return_value=mock_cfg),
            patch("personalscraper.conf.loader.resolve_config_path", return_value=Path("/tmp/cfg.json5")),
            patch("personalscraper.cli_helpers._build_app_context", return_value=mock_app_ctx),
            patch("personalscraper.cli_helpers.get_settings", return_value=MagicMock()),
            patch("personalscraper.indexer.db.open_db", return_value=MagicMock()),
            patch("personalscraper.indexer.db.apply_migrations"),
            patch(
                "personalscraper.indexer.scanner._modes.backfill_ids.run_backfill_ids",
                side_effect=_spy,
            ),
        ):
            result = runner.invoke(app, ["library-backfill-ids", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert captured[0]["registry"] is None
