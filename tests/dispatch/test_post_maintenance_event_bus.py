"""The post-dispatch scan must emit on the CALLER's bus, not a throwaway one (D4).

A fresh ``EventBus()`` inside ``_scan_disk_incremental`` silently disconnected the
post-dispatch reconciliation: ``PostDispatchReconcileSubscriber`` subscribes to the process
bus, so a scan emitting elsewhere left owned ``wanted`` rows frozen at 'grabbed'.

Live evidence (2026-08-04 03:40 run): four scans completed between 03:46:50 and 03:46:51,
zero ``acquire.*`` log lines followed, and ``scripts/check-acquisition-coherence.py`` exited
4 with four ``GRABBED_OWNED`` phantoms.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest

# Pre-load cli so personalscraper.indexer.commands.scan is importable (circular import
# between scan.py and cli.py — same reason as tests/dispatch/test_post_maintenance.py).
import personalscraper.indexer.cli  # noqa: F401
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch import post_maintenance
from personalscraper.indexer.events import LibraryScanCompleted


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config with a resolved indexer.db_path."""
    cfg = MagicMock()
    cfg.indexer.db_path = "/tmp/test_library.db"
    cfg.indexer.post_dispatch_maintenance.enabled = True
    return cfg


class TestScanUsesCallerBus:
    """``_scan_disk_incremental`` forwards the injected bus verbatim."""

    def test_forwards_caller_bus_to_library_index_command(self, mock_config: MagicMock) -> None:
        """The bus handed to the scan is the exact object the caller passed."""
        seen: dict[str, object] = {}

        def _fake_library_index_command(**kwargs: object) -> int:
            seen["event_bus"] = kwargs["event_bus"]
            return 0

        caller_bus = EventBus()
        with patch(
            "personalscraper.indexer.commands.scan.library_index_command",
            _fake_library_index_command,
        ):
            post_maintenance._scan_disk_incremental(mock_config, "disk_1", event_bus=caller_bus)

        assert seen["event_bus"] is caller_bus, (
            "the scan must emit on the caller's bus — a fresh EventBus() has no subscribers "
            "and silently drops LibraryScanCompleted (D4)"
        )


class TestEventBusIsRequired:
    """A default would let D4 come back silently — the parameter is required."""

    @pytest.mark.parametrize(
        "func_name",
        [
            "_scan_disk_incremental",
            "run_post_dispatch_maintenance",
            "maybe_run_post_dispatch_maintenance",
        ],
    )
    def test_event_bus_parameter_has_no_default(self, func_name: str) -> None:
        """``event_bus`` is keyword-only and carries no default value."""
        func = getattr(post_maintenance, func_name)
        params = inspect.signature(func).parameters
        assert "event_bus" in params, f"{func_name} must accept event_bus"
        param = params["event_bus"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, f"{func_name}: event_bus must be keyword-only"
        assert param.default is inspect.Parameter.empty, (
            f"{func_name} must REQUIRE event_bus — a default is exactly what produced D4"
        )


class TestScanCompletionReachesCallerSubscribers:
    """The end-to-end shape of D4: a subscriber on the caller's bus hears the scan."""

    def test_subscriber_on_caller_bus_receives_scan_completed(self, mock_config: MagicMock) -> None:
        """A LibraryScanCompleted emitted by the scan reaches the caller's subscribers.

        Regression for the 2026-08-04 03:40 run: the reconcile subscriber heard none of
        the four completed scans, so four wanted rows stayed 'grabbed' while the library
        already owned the episodes.
        """
        caller_bus = EventBus()
        received: list[LibraryScanCompleted] = []
        caller_bus.subscribe(LibraryScanCompleted, received.append)

        def _emitting_library_index_command(**kwargs: object) -> int:
            # Stand-in for the real scanner, which emits once per call on the bus it got.
            bus = kwargs["event_bus"]
            bus.emit(  # type: ignore[attr-defined]
                LibraryScanCompleted(mode="incremental", scanned=0, errors=0, elapsed_s=0.0)
            )
            return 0

        with patch(
            "personalscraper.indexer.commands.scan.library_index_command",
            _emitting_library_index_command,
        ):
            post_maintenance._scan_disk_incremental(mock_config, "disk_1", event_bus=caller_bus)

        assert received, "the post-dispatch scan must emit LibraryScanCompleted on the caller's bus"


class TestBusReachesTheScanThroughThePublicEntryPoints:
    """The bus must survive the whole call chain, not just the leaf."""

    def test_run_post_dispatch_maintenance_forwards_the_bus(self, mock_config: MagicMock) -> None:
        """``run_post_dispatch_maintenance`` hands its bus to every per-disk scan."""
        caller_bus = EventBus()
        with (
            patch(
                "personalscraper.dispatch.post_maintenance._scan_disk_incremental",
                return_value=0,
            ) as mock_scan,
            patch(
                "personalscraper.dispatch.post_maintenance._run_relink",
                return_value={"linked": 0, "unmatched": 0, "errors": 0},
            ),
            patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        ):
            post_maintenance.run_post_dispatch_maintenance(
                mock_config,
                {"disk_1"},
                event_bus=caller_bus,
                enabled=True,
            )

        mock_scan.assert_called_once_with(mock_config, "disk_1", event_bus=caller_bus)

    def test_maybe_run_post_dispatch_maintenance_forwards_the_bus(self, mock_config: MagicMock) -> None:
        """The policy wrapper forwards the bus to the runner it delegates to."""
        from pathlib import Path

        from personalscraper.dispatch._types import DispatchResult

        caller_bus = EventBus()
        results = [DispatchResult(source=Path("/staging/Show S01E01"), action="moved", disk="disk_1")]
        with patch("personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance") as mock_run:
            post_maintenance.maybe_run_post_dispatch_maintenance(
                mock_config,
                results,
                dry_run=False,
                event_bus=caller_bus,
            )

        assert mock_run.call_args.kwargs["event_bus"] is caller_bus


class TestReconcileSubscriberOutlivesThePostDispatchScan:
    """The subscriber must still be subscribed when the maintenance scan emits (D4-bis).

    Threading the bus is necessary but not sufficient: both dispatch composition roots
    closed the reconcile subscriber in a ``finally`` that ran BEFORE
    ``maybe_run_post_dispatch_maintenance``. The maintenance scan is precisely the one
    that indexes the freshly dispatched files, so closing first meant the reconcile
    could never see them — the two defects compounded.
    """

    def test_dispatch_step_runs_maintenance_before_closing_the_subscriber(self) -> None:
        """DispatchStep: maintenance is called while the subscriber is still live."""
        from types import SimpleNamespace
        from uuid import uuid4

        from personalscraper.models import StepReport
        from personalscraper.pipeline_steps import DispatchStep, StepContext

        order: list[str] = []

        class _SpySubscriber:
            def settle(self) -> None:
                order.append("settle")

            def close(self) -> None:
                order.append("close")

        app = SimpleNamespace(
            settings=MagicMock(name="settings"),
            config=MagicMock(name="config"),
            event_bus=EventBus(),
            acquire=None,
        )
        ctx = StepContext(
            app=app,  # type: ignore[arg-type]
            run_id=uuid4(),
            dry_run=False,
            interactive=False,
            verbose=False,
            upstream={},
            extras={},
        )

        with (
            patch(
                "personalscraper.dispatch.run.run_dispatch",
                return_value=(StepReport(name="dispatch"), []),
            ),
            patch(
                "personalscraper.subscribers.dispatch_reconcile.build_post_dispatch_reconcile_subscriber",
                return_value=_SpySubscriber(),
            ),
            patch(
                "personalscraper.dispatch.post_maintenance.maybe_run_post_dispatch_maintenance",
                side_effect=lambda *a, **k: order.append("maintenance"),
            ),
        ):
            DispatchStep()(ctx)

        # §14.3 — l'ordre porte tout le sens : la maintenance (donc les scans) d'abord,
        # PUIS le second passage déterministe, PUIS seulement le désabonnement. Un settle
        # avant la maintenance relirait la médiathèque à mi-écriture, exactement la course
        # qu'il existe pour supprimer.
        assert order == ["maintenance", "settle", "close"], (
            f"the reconcile subscriber must settle after the maintenance scan, then close — got {order}"
        )

    def test_the_dispatch_cli_command_settles_the_same_way(self) -> None:
        """§14.3 — « il n'existe pas deux chemins » : la commande CLI se comporte pareil.

        Les deux racines de composition du dispatch (l'étape du run complet et la commande
        ``personalscraper dispatch``) ont déjà divergé une fois sur exactement ce point
        (D4-bis). Le même ordre est donc exigé des deux, sinon la fermeture d'acquisition
        dépendrait de la porte d'entrée choisie.
        """
        from types import SimpleNamespace

        from personalscraper.commands.pipeline import dispatch as dispatch_command
        from personalscraper.models import StepReport

        order: list[str] = []

        class _SpySubscriber:
            def settle(self) -> None:
                order.append("settle")

            def close(self) -> None:
                order.append("close")

        app = SimpleNamespace(event_bus=EventBus(), acquire=None)
        ctx = SimpleNamespace(obj=SimpleNamespace(config=MagicMock(name="config")))
        bundle = SimpleNamespace(app_context=app, settings=MagicMock(name="settings"))

        with (
            patch(
                "personalscraper.dispatch.run.run_dispatch",
                return_value=(StepReport(name="dispatch"), []),
            ),
            patch(
                "personalscraper.subscribers.dispatch_reconcile.build_post_dispatch_reconcile_subscriber",
                return_value=_SpySubscriber(),
            ),
            patch("personalscraper.subscribers.plex.build_plex_subscriber", return_value=None),
            patch("personalscraper.pipeline_steps.resolve_dispatch_authority", return_value={}),
            patch(
                "personalscraper.dispatch.post_maintenance.maybe_run_post_dispatch_maintenance",
                side_effect=lambda *a, **k: order.append("maintenance"),
            ),
            patch.dict("personalscraper.commands.pipeline.state", {"console": MagicMock(), "verbose": False}),
        ):
            dispatch_command.__wrapped__.__wrapped__.__wrapped__(  # type: ignore[attr-defined]
                ctx,  # type: ignore[arg-type]
                dry_run=False,
                no_post_maintenance=False,
                bundle=bundle,  # type: ignore[arg-type]
            )

        assert order == ["maintenance", "settle", "close"], f"the CLI path must settle too — got {order}"
