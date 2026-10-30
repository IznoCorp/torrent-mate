"""Tests of ``personalscraper supervise``: the environment's store, the isolation guard, the watcher's helpers.

No supervisor loop runs for real: ``Supervisor.run`` is replaced by one admission tick, the
application context is a stub (no torrent client, no provider), and no worker is started.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.acquire.watcher import WatcherDecision, WatcherOutput, WatcherState
from personalscraper.app.store.store import AppStore
from personalscraper.app.supervisor.model import Lease
from personalscraper.app.supervisor.supervisor import Supervisor, SupervisorWedged
from personalscraper.cli import app as cli_app
from personalscraper.commands import supervise as supervise_command
from personalscraper.conf.isolation import ENVIRONMENT_MARKER
from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import EventBus
from personalscraper.i18n import Language, t

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


@pytest.fixture
def cli_runner() -> CliRunner:
    """A runner separating stdout from stderr.

    Returns:
        The runner.
    """
    from tests.conftest import make_cli_runner

    return make_cli_runner()


def _staging(test_config: Config, monkeypatch: pytest.MonkeyPatch, marker: str) -> Config:
    """Run as ``staging`` over the synthetic config, its data directory marked *marker*.

    Args:
        test_config: The synthetic configuration.
        monkeypatch: Pytest monkeypatch fixture.
        marker: The environment the data directory's marker names.

    Returns:
        The config, with a stream key of its own (a sandbox may not publish on prod's).
    """
    data_dir = test_config.paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / ENVIRONMENT_MARKER).write_text(f"{marker}\n", encoding="utf-8")
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    return test_config.model_copy(
        update={"web": test_config.web.model_copy(update={"stream_key": "personalscraper:events:staging"})}
    )


# typer's Result
def _invoke(cli_runner: CliRunner, config: Config, leases: list[Lease | None], *, wedged: bool = False) -> Any:
    """Run ``supervise`` for one admission tick over *config*, recording the lease it held.

    Args:
        cli_runner: The runner.
        config: The configuration the CLI loads.
        leases: Receives the lease read from the store during the tick.
        wedged: Whether the loop then gives up, as after too many failing ticks.

    Returns:
        The run's result.
    """
    context = MagicMock(event_bus=EventBus(), acquire=None, torrent_client=None)

    def one_tick(self: Supervisor, should_stop: object, sleep: object = None) -> None:
        self.tick_admission()
        leases.append(self._store.lease.read())
        self.stop()
        if wedged:
            raise SupervisorWedged("tick_admission failed 30 times in a row")

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=config.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=config),
        patch("personalscraper.cli.configure_logging"),
        patch("personalscraper.commands.supervise.build_app_context", return_value=context),
        patch("personalscraper.commands.supervise.build_redis_publisher", return_value=None),
        patch("personalscraper.commands.supervise.signal.signal"),
        patch.object(Supervisor, "run", one_tick),
    ):
        return cli_runner.invoke(cli_app, ["supervise"])


class TestEnvironment:
    """The supervisor works in its environment's store, and only on its own data directory."""

    def test_staging_opens_app_staging_db(
        self, cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under ``PERSONALSCRAPER_ENV=staging`` the lease is taken in ``app-staging.db``, never ``app.db``."""
        config = _staging(test_config, monkeypatch, "staging")
        leases: list[Lease | None] = []

        result = _invoke(cli_runner, config, leases)

        assert result.exit_code == 0, result.output
        data_dir = config.paths.data_dir
        assert (data_dir / "app-staging.db").exists()
        assert not (data_dir / "app.db").exists()
        assert leases and leases[0] is not None
        store = AppStore(data_dir / "app-staging.db")
        try:
            assert store.lease.read() is None, "a clean stop leaves the lease behind"
        finally:
            store.close()

    def test_a_prod_marked_data_dir_is_refused(
        self, cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A staging process pointed at a prod-marked data directory refuses it before opening any store."""
        config = _staging(test_config, monkeypatch, "prod")
        leases: list[Lease | None] = []

        result = _invoke(cli_runner, config, leases)

        assert result.exit_code != 0
        assert leases == []
        assert not list(config.paths.data_dir.glob("app*.db"))


class TestWedged:
    """A loop that gave up ends the process non-zero, so PM2 restarts it."""

    def test_a_wedged_loop_exits_1(self, cli_runner: CliRunner, test_config: Config) -> None:
        """``SupervisorWedged`` from the loop: exit code 1, a clean exit rather than a traceback."""
        result = _invoke(cli_runner, test_config, [], wedged=True)

        assert result.exit_code == 1
        assert not isinstance(result.exception, SupervisorWedged)


class TestWatchHelpers:
    """The watcher half over ``personalscraper watch``'s own helpers."""

    def test_poll_carries_the_deferral_snapshot_between_cycles(self, test_config: Config) -> None:
        """Each poll hands the previous cycle's deferred snapshot to the watch poll."""
        helpers = supervise_command.WatchHelpers(test_config, MagicMock(), None)
        snapshots: list[dict[str, str]] = []

        def poll(*args: object) -> tuple[None, dict[str, str]]:
            snapshots.append(dict(args[-1]))  # type: ignore[call-overload]
            return None, {"hash": "ratio"}

        with patch("personalscraper.commands.supervise.watch_command._poll", side_effect=poll):
            assert helpers.poll() is None
            helpers.poll()

        assert snapshots == [{}, {"hash": "ratio"}]

    def test_cross_seed_keeps_its_failure_counter(self, test_config: Config) -> None:
        """The per-hash failure counter outlives a cycle, as in the watch daemon."""
        helpers = supervise_command.WatchHelpers(test_config, MagicMock(), None)
        counters: list[int] = []

        def cross_seed(out: object, state: WatcherState, config: object, failures: dict[str, int]) -> WatcherState:
            failures["h"] = failures.get("h", 0) + 1
            counters.append(failures["h"])
            return state

        out = WatcherOutput(decision=WatcherDecision.FIRE_CROSS_SEED, new_state=WatcherState(), cross_seed_hashes=["h"])
        with patch("personalscraper.commands.supervise.watch_command._trigger_cross_seed", side_effect=cross_seed):
            helpers.cross_seed(out, WatcherState())
            helpers.cross_seed(out, WatcherState())

        assert counters == [1, 2]

    def test_the_state_goes_to_the_acquire_store(self, test_config: Config) -> None:
        """The pending run and a success are written to the acquire store; none is a no-op."""
        store = MagicMock()
        helpers = supervise_command.WatchHelpers(test_config, MagicMock(), store)
        helpers.publish_pending(fires_at=5.0, active_downloads=2, now=3.0)
        helpers.record_success(7.0)

        store.watch.set_pending_run.assert_called_once_with(fires_at=5.0, active_downloads=2, now=3.0)
        store.watch.set_last_successful_run_at.assert_called_once_with(7.0)

        bare = supervise_command.WatchHelpers(test_config, MagicMock(), None)
        bare.publish_pending(fires_at=None, active_downloads=0, now=1.0)
        bare.record_success(1.0)


class TestCatalogue:
    """Every line the command prints exists in both languages."""

    @pytest.mark.parametrize("key", ["help", "started", "no_client", "stopped"])
    def test_the_lines_exist_in_both_languages(self, key: str) -> None:
        """English and French differ, and neither is the key itself."""
        english = t(f"cli_core.supervise.{key}", language=Language.EN, pid=1)
        french = t(f"cli_core.supervise.{key}", language=Language.FR, pid=1)

        assert english != french
        assert f"cli_core.supervise.{key}" not in (english, french)


class TestDisabledActiveClient:
    """A disabled active client: the supervisor boots, takes the lease and runs without its watcher."""

    def test_the_supervisor_takes_the_lease_without_a_watcher(
        self, cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The boot does not die on the disabled client, holds the lease and builds no watcher half."""
        from personalscraper.conf.models.api_config import TorrentClientEntry, TorrentConfig

        config = _staging(test_config, monkeypatch, "staging")
        config = config.model_copy(
            update={
                "watch": config.watch.model_copy(update={"enabled": True}),
                "torrent": TorrentConfig(
                    active="qbittorrent",
                    clients={"qbittorrent": TorrentClientEntry(enabled=False)},
                ),
            }
        )
        leases: list[Lease | None] = []
        watchers: list[object] = []
        real_from_services = Supervisor.from_services.__func__  # type: ignore[attr-defined]

        def spy(
            cls: type[Supervisor], services: object, cfg: Config, launcher: object, *, watcher: object
        ) -> Supervisor:
            watchers.append(watcher)
            return real_from_services(cls, services, cfg, launcher, watcher=watcher)

        def one_tick(self: Supervisor, should_stop: object, sleep: object = None) -> None:
            self.tick_admission()
            leases.append(self._store.lease.read())
            self.stop()

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=config),
            patch("personalscraper.cli.configure_logging"),
            patch("personalscraper.api.metadata.registry.ProviderRegistry"),
            patch("personalscraper.commands.supervise.build_redis_publisher", return_value=None),
            patch("personalscraper.commands.supervise.signal.signal"),
            patch.object(Supervisor, "from_services", classmethod(spy)),
            patch.object(Supervisor, "run", one_tick),
        ):
            result = cli_runner.invoke(cli_app, ["supervise"])

        assert result.exit_code == 0, result.output
        assert watchers == [None]
        assert leases and leases[0] is not None
