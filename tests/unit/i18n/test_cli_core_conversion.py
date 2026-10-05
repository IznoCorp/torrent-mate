"""The CLI's core commands speak through the translation layer (C-core of the i18n plan).

Nothing is translated yet: every ``cli_core`` / ``cli_trailers`` key lives in one language only, so
the real catalogue says the same thing in French and in English. To prove a module really goes
through ``t()``, each test installs a catalogue whose French side is the English text prefixed with
``FR|`` and checks that the line a module prints carries the prefix under French and not under
English. A module that still prints a literal prints the same bytes in both languages and fails.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from pydantic import TypeAdapter, ValidationError
from rich.console import Console
from typer.testing import CliRunner

from personalscraper import i18n
from personalscraper.cli import app
from personalscraper.cli_state import state
from personalscraper.i18n import Language, t, use_language

_PREFIX = "FR|"
_PREFIXED_NAMESPACES = ("cli_core", "cli_trailers")


def _prefixed(tree: Any) -> Any:
    """Return ``tree`` with every string leaf prefixed by the French marker."""
    if isinstance(tree, dict):
        return {name: _prefixed(value) for name, value in tree.items()}
    return _PREFIX + tree


@pytest.fixture
def marked_french(tmp_path: Path) -> Iterator[None]:
    """Install a catalogue whose French side is the English side marked ``FR|``."""
    real = Path(i18n.__file__).parent
    for language in ("fr", "en"):
        (tmp_path / language).mkdir()
    for source in (real / "en").glob("*.json"):
        shutil.copy(source, tmp_path / "en" / source.name)
        french = tmp_path / "fr" / source.name
        if source.stem in _PREFIXED_NAMESPACES:
            french.write_text(json.dumps(_prefixed(json.loads(source.read_text(encoding="utf-8")))), encoding="utf-8")
        else:
            shutil.copy(real / "fr" / source.name, french)
    i18n._use_root_for_tests(tmp_path)
    yield
    i18n._use_root_for_tests(None)


def _says(produce: Callable[[], str], expected: str) -> None:
    """Assert ``produce()`` holds ``expected`` in English and the marked ``expected`` in French."""
    with use_language(Language.EN):
        english = produce()
    with use_language(Language.FR):
        french = produce()
    assert expected in english and _PREFIX not in english
    assert _PREFIX + expected in french


def _capture_echo(capsys: pytest.CaptureFixture[str], action: Callable[[], object]) -> str:
    """Run ``action`` (which may exit) and return what it wrote to stdout and stderr."""
    try:
        action()
    except (SystemExit, typer.Exit):
        pass
    captured = capsys.readouterr()
    return captured.out + captured.err


def _console_state(monkeypatch: pytest.MonkeyPatch) -> StringIO:
    """Point the CLI state at an in-memory console and return its buffer."""
    buffer = StringIO()
    monkeypatch.setitem(state, "console", Console(file=buffer, force_terminal=False, width=200))
    monkeypatch.setitem(state, "format", "rich")
    monkeypatch.setitem(state, "verbose", False)
    return buffer


def test_main_callback_refuses_an_unknown_format_in_the_current_language(marked_french: None) -> None:
    """``cli.py``: the invalid ``--format`` refusal goes through ``cli_core.main.invalid_format``."""

    def produce() -> str:
        return CliRunner().invoke(app, ["--format", "xml", "info"]).output

    _says(produce, "Invalid --format 'xml'. Choose rich, plain, or json.")


def test_app_help_is_a_catalogue_text() -> None:
    """``cli_app.py``: both Typer groups take their help from the catalogue (read at import)."""
    from personalscraper.cli_app import app as shared_app
    from personalscraper.cli_app import config_app

    assert shared_app.info.help == t("cli_core.app.help", language=Language.EN)
    assert config_app.info.help == t("cli_core.app.config_help", language=Language.EN)
    for key in ("cli_core.app.help", "cli_core.app.config_help"):
        assert t(key, language=Language.FR) == t(key, language=Language.EN)


def test_configuration_error_label_is_translated(marked_french: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """``cli_helpers/__init__.py``: ``handle_cli_errors`` words its label through ``cli_core.helpers``."""
    from personalscraper.cli_helpers import handle_cli_errors

    try:
        TypeAdapter(int).validate_python("not a number")
    except ValidationError as exc:
        failure = exc

    @handle_cli_errors
    def failing() -> None:
        raise failure

    def produce() -> str:
        buffer = _console_state(monkeypatch)
        with pytest.raises(typer.Exit):
            failing()
        return buffer.getvalue()

    _says(produce, "Configuration error:")


def test_plain_output_pairs_go_through_the_catalogue(
    marked_french: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``cli_helpers/output.py``: the plain ``key: value`` line is ``cli_core.output.pair``."""
    from personalscraper.cli_helpers.output import emit

    monkeypatch.setitem(state, "format", "plain")

    def produce() -> str:
        emit({"answer": 42}, rich_renderer=lambda: None)
        captured = capsys.readouterr()
        return captured.out + captured.err

    _says(produce, "answer: 42")


def test_step_tally_and_check_row_go_through_the_catalogue(marked_french: None) -> None:
    """``commands/pipeline.py``: the step tally and the ``--list-checks`` row are catalogue texts."""
    from personalscraper.commands.pipeline import _check_row, _counts
    from personalscraper.models import StepReport

    report = StepReport(name="ingest")
    _says(lambda: _counts(report), "0 OK, 0 skipped, 0 errors")
    spec = SimpleNamespace(
        name="x",
        group="g",
        default_severity=SimpleNamespace(value="warning"),
        fixable=True,
        indexable=False,
        description="d",
    )
    _says(lambda: _check_row(spec), "fixable")  # type: ignore[arg-type]


def test_rich_console_words_the_step_name_through_the_code_set(marked_french: None) -> None:
    """``subscribers/rich_console.py``: a step header uses ``t_code("cli_core.step", step)``."""
    from personalscraper.core.event_bus import EventBus
    from personalscraper.subscribers.rich_console import RichConsoleSubscriber, _step_word

    def produce() -> str:
        buffer = StringIO()
        subscriber = RichConsoleSubscriber(EventBus(), Console(file=buffer, force_terminal=False, width=100))
        try:
            subscriber._render_step_start("ingest")
        finally:
            subscriber.close()
        return buffer.getvalue()

    _says(produce, "INGEST")
    assert _step_word("not-a-step") == "not-a-step"


def test_init_config_sync_refuses_force_in_the_current_language(marked_french: None) -> None:
    """``commands/config.py``: the ``--sync`` with ``--force`` refusal is ``cli_core.config.init_config``."""

    def produce() -> str:
        return CliRunner().invoke(app, ["init-config", "--sync", "--force"]).output

    _says(produce, "Error: --sync and --force are mutually exclusive.")


def test_init_config_missing_example_is_translated(
    marked_french: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``commands/init_config.py``: a missing example directory is reported through ``cli_core.init_config``."""
    from personalscraper.commands.init_config import init_config

    missing = tmp_path / "absent"

    def produce() -> str:
        return _capture_echo(capsys, lambda: init_config(missing, tmp_path / "out", interactive=False, force=False))

    _says(produce, "Example directory not found:")


def test_info_providers_help_is_a_catalogue_text() -> None:
    """``commands/info.py``: the ``providers`` help and its line come from ``cli_core.info`` (read at import)."""
    help_text = CliRunner().invoke(app, ["info", "providers", "--help"]).output
    assert "circuit=<state>" in help_text
    line = t("cli_core.info.providers.line", name="x", state="closed", failures=0, language=Language.EN)
    assert line == t("cli_core.info.providers.line", name="x", state="closed", failures=0, language=Language.FR)
    assert line == "x circuit=closed  failures=0"


def test_health_check_ok_line_is_translated(
    marked_french: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``commands/health_check.py``: the healthy verdict is ``cli_core.health_check.ok``."""
    from personalscraper.commands import health_check as hc

    for detector in ("_check_daemons", "_check_recent_errors", "_check_stuck_lock"):
        monkeypatch.setattr(hc, detector, lambda *args, **kwargs: [])
    ctx = SimpleNamespace(obj=SimpleNamespace(config=None))

    def produce() -> str:
        return _capture_echo(capsys, lambda: hc.health_check(ctx, 90, 60, True))  # type: ignore[arg-type]

    _says(produce, "health-check: OK")


def test_schedule_without_a_job_is_refused_in_the_current_language(marked_french: None) -> None:
    """``commands/schedule.py``: the missing-job refusal is ``cli_core.schedule.no_job``."""

    def produce() -> str:
        return CliRunner().invoke(app, ["schedule", "--cron", "* * * * *"]).output

    _says(produce, "schedule: no job given after '--'")


def test_web_daemon_disabled_message_is_translated(marked_french: None, capsys: pytest.CaptureFixture[str]) -> None:
    """``commands/web.py``: a disabled daemon says so through ``cli_core.web.disabled``."""
    from personalscraper.commands import web as web_module

    config = SimpleNamespace(web=SimpleNamespace(enabled=False))
    ctx = SimpleNamespace(invoked_subcommand=None, obj=SimpleNamespace(config=config))

    def produce() -> str:
        return _capture_echo(capsys, lambda: web_module.web(ctx, None, None))  # type: ignore[arg-type]

    _says(produce, "Web daemon is disabled (config.web.enabled=false).")


def test_watch_now_reports_the_sentinel_in_the_current_language(
    marked_french: None, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``commands/watch.py``: ``watch-now`` words the sentinel line through ``cli_core.watch``."""
    from personalscraper.commands.watch import watch_now

    ctx = SimpleNamespace(obj=SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(data_dir=tmp_path))))

    def produce() -> str:
        return _capture_echo(capsys, lambda: watch_now(ctx))  # type: ignore[arg-type]

    _says(produce, "Sentinel written:")


def test_torrent_listing_totals_are_translated(marked_french: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """``commands/torrents.py``: the listing's totals line goes through ``cli_core.torrents``."""
    from personalscraper.commands.torrents import _print_torrents_rich

    payload = {
        "torrents": [{"state": "uploading", "progress": 1.0, "size_gb": 1.5, "name": "n", "seeding": True}],
        "completed": 1,
        "tracked": 2,
    }

    def produce() -> str:
        buffer = _console_state(monkeypatch)
        _print_torrents_rich(payload)
        return buffer.getvalue()

    _says(produce, "1 completed (of 2 tracked torrents)")


def test_trailers_bad_date_is_refused_in_the_current_language(
    marked_french: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """``trailers/cli.py``: the malformed ``--since`` refusal is ``cli_trailers.since_invalid``."""
    from personalscraper.trailers.cli import _parse_since

    def produce() -> str:
        return _capture_echo(capsys, lambda: _parse_since("yesterday"))

    _says(produce, "Error: --since 'yesterday' must be YYYY-MM-DD.")


def test_the_real_catalogue_says_the_same_in_both_languages() -> None:
    """Nothing is translated yet: a sample of keys from each module reads alike in French and English."""
    keys = {
        "cli_core.main.invalid_format": {"value": "x"},
        "cli_core.helpers.config_error_label": {},
        "cli_core.pipeline.counts": {"ok": 1, "skipped": 2, "errors": 3},
        "cli_core.pipeline_run.banner": {},
        "cli_core.step.ingest": {},
        "cli_core.web.disabled": {},
        "cli_trailers.purge.locked": {},
    }
    for key, params in keys.items():
        assert t(key, language=Language.FR, **params) == t(key, language=Language.EN, **params), key
