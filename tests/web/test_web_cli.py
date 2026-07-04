"""Tests for the ``personalscraper web`` CLI command (tm-shell feature).

Named ``test_web_cli.py`` (NOT ``test_cli.py``) to avoid the root conftest's
``_stub_pipeline_steps`` autouse fixture, which scopes to ``test_cli.py`` and
would silently stub pipeline internals inside these tests.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Trigger registration of the ``web`` command on the shared Typer app.
import personalscraper.commands.web  # noqa: F401,PLC0415
from personalscraper.cli_app import app as cli_app
from personalscraper.conf.models.web import WebConfig

# Patch targets for the eager config load in the CLI callback.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_BUILD_CTX = "personalscraper.commands.web._build_app_context"
_PATCH_UVICORN_RUN = "personalscraper.commands.web.uvicorn.run"


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a CliRunner that separates stdout from stderr."""
    from tests.conftest import make_cli_runner

    return make_cli_runner()


class TestWebHelp:
    """``personalscraper web --help`` prints usage and exits 0."""

    def test_help_exit_zero(self, cli_runner: CliRunner) -> None:
        """``web --help`` exits 0 and shows the command description."""
        result = cli_runner.invoke(cli_app, ["web", "--help"])

        assert result.exit_code == 0
        assert "TorrentMate" in result.output or "web" in result.output


class TestWebDisabled:
    """When ``config.web.enabled`` is False, the command exits 1."""

    def test_disabled_exits_1(self, cli_runner: CliRunner, test_config) -> None:
        """``web`` with enabled=False prints message and exits 1."""
        web_cfg = WebConfig(enabled=False)
        cfg = test_config.model_copy(update={"web": web_cfg})

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        ):
            result = cli_runner.invoke(cli_app, ["web"])

        assert result.exit_code == 1
        assert "disabled" in result.output.lower()


class TestBootRefusal:
    """When the SPA is missing and dev_mode is False, the command exits 1."""

    def test_spa_missing_boot_refused(self, cli_runner: CliRunner, test_config) -> None:
        """Missing index.html + dev_mode=False → exit 1 with SPA not built message."""
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
            result = cli_runner.invoke(cli_app, ["web"])

        assert result.exit_code == 1
        assert "SPA not built" in result.output


class TestWebHappyPath:
    """Happy path: config loads, app context built, uvicorn.run called."""

    def test_uvicorn_called_with_config_host_and_port(self, cli_runner: CliRunner, test_config) -> None:
        """uvicorn.run is invoked once with the host/port from WebConfig."""
        web_cfg = WebConfig(
            host=test_config.web.host,
            port=test_config.web.port,
            dev_mode=True,  # Bypass the SPA-missing boot guard.
        )
        cfg = test_config.model_copy(update={"web": web_cfg})

        mock_ctx = MagicMock()
        mock_ctx.provider_registry.close = MagicMock()
        mock_ctx.acquire = None

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_BUILD_CTX, return_value=mock_ctx),
            patch(_PATCH_UVICORN_RUN) as mock_run,
        ):
            result = cli_runner.invoke(cli_app, ["web"])

        # uvicorn.run raises no exception → exit 0 in the test harness
        # (the real uvicorn.run blocks, but we patched it to a no-op).
        assert result.exit_code == 0
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["host"] == web_cfg.host
        assert call_kwargs["port"] == web_cfg.port
