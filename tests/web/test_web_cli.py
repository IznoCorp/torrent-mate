"""Tests for the ``personalscraper web`` CLI command (tm-shell feature).

Named ``test_web_cli.py`` (NOT ``test_cli.py``) to avoid the root conftest's
``_stub_pipeline_steps`` autouse fixture, which scopes to ``test_cli.py`` and
would silently stub pipeline internals inside these tests.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# Import the fully-wired CLI app so the ``web`` sub-app is mounted via
# ``add_typer`` (matching the trailers/library sub-app test convention).
from personalscraper.cli import app as cli_app
from personalscraper.conf.models.web import WebConfig
from personalscraper.config import Settings
from personalscraper.web.auth.passwords import verify_password

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

    def test_help_exit_zero(self, cli_runner: CliRunner, test_config) -> None:
        """``web --help`` exits 0 and shows the command description.

        The top-level CLI callback eagerly loads config even for ``--help``, so
        the load is patched — otherwise CI (no ``config/`` dir) raises
        ``ConfigLoadError: paths.json5 not found`` and the help exits 1.
        """
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        ):
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

    def test_spa_missing_boot_refused(self, cli_runner: CliRunner, test_config, tmp_path, monkeypatch) -> None:
        """Missing index.html + dev_mode=False → exit 1 with SPA not built message."""
        # Create a hermetic static/ dir tree without index.html so the boot
        # guard fires regardless of whether a real Vite build sits in the
        # repo.  The guard resolves Path(__file__).parent.parent / "web"/"static",
        # so we point __file__ at a fake module inside tmp_path.
        fake_web_py = tmp_path / "personalscraper" / "commands" / "web.py"
        fake_web_py.parent.mkdir(parents=True, exist_ok=True)
        fake_web_py.write_text("")
        (tmp_path / "personalscraper" / "web" / "static").mkdir(parents=True, exist_ok=True)
        # NO index.html — the guard must fire.

        monkeypatch.setattr("personalscraper.commands.web.__file__", str(fake_web_py))

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

    def test_cli_host_and_port_override_config(self, cli_runner: CliRunner, test_config) -> None:
        """``web --host 0.0.0.0 --port 8711`` overrides config.web.host/port (staging clone).

        The staging PM2 app shares the single config dir (web.port=8710) but binds
        8711 via the CLI override, so uvicorn must receive the overridden values.
        """
        web_cfg = WebConfig(dev_mode=True)  # Bypass the SPA-missing boot guard.
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
            result = cli_runner.invoke(cli_app, ["web", "--host", "0.0.0.0", "--port", "8711"])

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["host"] == "0.0.0.0"
        assert call_kwargs["port"] == 8711
        # The override must NOT mutate the configured value.
        assert web_cfg.port == 8710


class TestSetPassword:
    """``personalscraper web set-password`` — hash generation and .env writing."""

    def test_piped_stdin_prints_hash(
        self,
        cli_runner: CliRunner,
        test_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Piped stdin → prints WEB_PASSWORD_HASH=scrypt$... and WEB_JWT_SECRET=..."""
        monkeypatch.delenv("WEB_JWT_SECRET", raising=False)
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch(
                "personalscraper.commands.web.get_settings",
                return_value=Settings(_env_file=None),  # type: ignore[call-arg]
            ),
        ):
            result = cli_runner.invoke(
                cli_app,
                ["web", "set-password"],
                input="testuser\ntest-password\ntest-password\n",
            )

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "WEB_PASSWORD_HASH=scrypt$" in result.output
        # WEB_JWT_SECRET is generated because we cleared the ambient env var.
        assert "WEB_JWT_SECRET=" in result.output

    def test_piped_stdin_jwt_already_present_omits_secret(
        self,
        cli_runner: CliRunner,
        test_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When WEB_JWT_SECRET is already in the env, it is NOT regenerated."""
        monkeypatch.setenv("WEB_JWT_SECRET", "existing-secret-value")
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch(
                "personalscraper.commands.web.get_settings",
                return_value=Settings(_env_file=None),  # type: ignore[call-arg]
            ),
        ):
            result = cli_runner.invoke(
                cli_app,
                ["web", "set-password"],
                input="testuser\ntest-password\ntest-password\n",
            )

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "WEB_PASSWORD_HASH=scrypt$" in result.output
        # Secret is already present, so no WEB_JWT_SECRET= line should appear.
        assert "WEB_JWT_SECRET=" not in result.output

    def test_printed_hash_verifies(
        self,
        cli_runner: CliRunner,
        test_config,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The printed scrypt hash verifies against the entered password."""
        monkeypatch.delenv("WEB_JWT_SECRET", raising=False)
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch(
                "personalscraper.commands.web.get_settings",
                return_value=Settings(_env_file=None),  # type: ignore[call-arg]
            ),
        ):
            result = cli_runner.invoke(
                cli_app,
                ["web", "set-password"],
                input="testuser\nmy-secret-pw\nmy-secret-pw\n",
            )

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        match = re.search(r"WEB_PASSWORD_HASH=(scrypt\$[^\s]+)", result.output)
        assert match is not None, f"No WEB_PASSWORD_HASH line found in: {result.output}"
        hash_value = match.group(1)
        assert verify_password("my-secret-pw", hash_value) is True

    def test_write_flag_upserts_keys_into_tmp_env(
        self,
        cli_runner: CliRunner,
        test_config,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--write against a tmp .env (monkeypatched seam) upserts the keys."""
        monkeypatch.delenv("WEB_JWT_SECRET", raising=False)
        tmp_env = tmp_path / ".env"

        with (
            patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
            patch(_PATCH_LOAD_CONFIG, return_value=test_config),
            patch(
                "personalscraper.commands.web.get_settings",
                return_value=Settings(_env_file=None),  # type: ignore[call-arg]
            ),
            patch("personalscraper.commands.web._ENV_PATH", tmp_env),
        ):
            result = cli_runner.invoke(
                cli_app,
                ["web", "set-password", "--write"],
                input="testuser\ntest-password\ntest-password\ny\n",
            )

        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "Updated" in result.output
        assert tmp_env.exists(), f"Expected {tmp_env} to be created by --write"
        content = tmp_env.read_text()
        assert "WEB_PASSWORD_HASH=scrypt$" in content
        assert "WEB_JWT_SECRET=" in content
        # The written hash should verify against the entered password.
        match = re.search(r"WEB_PASSWORD_HASH=(scrypt\$[^\s]+)", content)
        assert match is not None, f"No WEB_PASSWORD_HASH line found in: {content}"
        assert verify_password("test-password", match.group(1)) is True
