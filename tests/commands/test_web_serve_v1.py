"""``personalscraper web serve-v1`` — the standalone v1 server, refused on production stores.

The command builds the standalone v1 application and hands it to uvicorn on the
loopback address; it never starts under production (``PERSONALSCRAPER_ENV`` unset or
``prod``), whose stores a development server must not open.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from personalscraper.cli import app as cli_app
from personalscraper.conf.models.config import Config
from personalscraper.i18n import Language

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_UVICORN_RUN = "personalscraper.commands.web.uvicorn.run"
_CATALOGUES = Path(__file__).resolve().parents[2] / "personalscraper" / "i18n"


@pytest.fixture
def cli_runner() -> CliRunner:
    """A runner separating stdout from stderr.

    Returns:
        The runner.
    """
    from tests.conftest import make_cli_runner

    return make_cli_runner()


def _invoke(cli_runner: CliRunner, test_config: Config, args: list[str]) -> tuple[object, MagicMock]:
    """Run ``web serve-v1`` over the synthetic configuration, with uvicorn patched out.

    Args:
        cli_runner: The runner.
        test_config: The synthetic configuration.
        args: The arguments after ``personalscraper web serve-v1``.

    Returns:
        The run's result and the patched ``uvicorn.run``.
    """
    with (
        patch(_PATCH_RESOLVE_PATH, return_value=test_config.paths.data_dir / "fake.json5"),
        patch(_PATCH_LOAD_CONFIG, return_value=test_config),
        patch(_PATCH_UVICORN_RUN) as run,
    ):
        return cli_runner.invoke(cli_app, ["web", "serve-v1", *args]), run


def _refusal(language: Language) -> str:
    """The refusal line in a language, read from its catalogue.

    Args:
        language: The language.

    Returns:
        The catalogue's line.
    """
    catalogue = json.loads((_CATALOGUES / language.value / "cli_web.json").read_text(encoding="utf-8"))
    return catalogue["serve_v1"]["refused_prod"]


@pytest.mark.parametrize("value", ["", "prod"])
def test_production_is_refused(
    cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Under production: exit 1, the catalogue's refusal, uvicorn never started.

    Args:
        cli_runner: The runner.
        test_config: The synthetic configuration.
        monkeypatch: Pytest monkeypatch fixture.
        value: ``PERSONALSCRAPER_ENV``, empty or ``prod``.
    """
    monkeypatch.setenv("PERSONALSCRAPER_ENV", value)

    result, run = _invoke(cli_runner, test_config, [])

    assert result.exit_code == 1  # type: ignore[attr-defined]
    assert _refusal(Language.EN) in result.stderr  # type: ignore[attr-defined]
    run.assert_not_called()


def test_dev_serves_on_the_loopback_port_8713(
    cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under ``dev``, uvicorn runs the standalone app on 127.0.0.1:8713, with its own logging off.

    Args:
        cli_runner: The runner.
        test_config: The synthetic configuration.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    built = object()

    with patch("personalscraper.commands.web.build_standalone_v1_app", return_value=built) as build:
        result, run = _invoke(cli_runner, test_config, [])

    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    build.assert_called_once()
    assert build.call_args.args[0] is test_config
    run.assert_called_once()
    assert run.call_args.args == (built,)
    kwargs = run.call_args.kwargs
    assert (kwargs["host"], kwargs["port"], kwargs["log_config"]) == ("127.0.0.1", 8713, None)
    # The app's own proxy-headers middleware is the only trust decision.
    assert kwargs["proxy_headers"] is False


def test_host_and_port_can_be_chosen(
    cli_runner: CliRunner, test_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--host`` and ``--port`` reach uvicorn.

    Args:
        cli_runner: The runner.
        test_config: The synthetic configuration.
        monkeypatch: Pytest monkeypatch fixture.
    """
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")

    with patch("personalscraper.commands.web.build_standalone_v1_app"):
        result, run = _invoke(cli_runner, test_config, ["--host", "127.0.0.2", "--port", "9999"])

    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert (run.call_args.kwargs["host"], run.call_args.kwargs["port"]) == ("127.0.0.2", 9999)


def test_the_refusal_is_worded_in_both_languages() -> None:
    """The refusal exists in French and English, and they differ."""
    assert _refusal(Language.FR) and _refusal(Language.EN)
    assert _refusal(Language.FR) != _refusal(Language.EN)
