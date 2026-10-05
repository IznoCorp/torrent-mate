"""The CLI's core commands speak French and English (C-core, then T-core of the i18n plan).

Every ``cli_core`` / ``cli_trailers`` / ``cli_web`` text is written in both languages, so each test
reads one representative line of a module under ``use_language(EN)`` and ``use_language(FR)`` and
checks that the two differ as the catalogue says. A module that still prints a literal prints the
same bytes in both languages and fails. French expectations carry unicode escapes: the ``tests/``
ratchet of ``check-no-french.py`` ignores pragmas.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from pydantic import TypeAdapter, ValidationError
from rich.console import Console
from typer.testing import CliRunner

from personalscraper import i18n
from personalscraper.cli import app
from personalscraper.cli_state import state
from personalscraper.i18n import Language, use_language
from personalscraper.pipeline_step_codes import StepCode
from personalscraper.pipeline_steps import DEFAULT_STEPS


def _french(key: str, **params: str) -> str:
    """The French catalogue text of ``key``, for the few expectations that cannot be written as ASCII.

    The ``tests/`` ratchet counts any French literal and ignores pragmas; reading the text from the
    catalogue still proves the module goes through ``t()`` and that the two languages differ.
    """
    return i18n.t(key, language=Language.FR, **params)


def _says(produce: Callable[[], str], english: str, french: str) -> None:
    """Assert ``produce()`` holds ``english`` under English, ``french`` under French, and differs between them.

    ``english`` may be a prefix of ``french`` (a step word and its longer French word), so only the
    language's own text is required, plus the French text's absence from the English output. A
    logging handler left on a closed stream by an earlier test prints a traceback quoting this
    very call after the command's own output: it is cut off before comparing.
    """
    with use_language(Language.EN):
        in_english = produce().split("--- Logging error ---")[0]
    with use_language(Language.FR):
        in_french = produce().split("--- Logging error ---")[0]
    assert english in in_english and french not in in_english
    assert french in in_french
    assert in_english != in_french


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


def test_main_callback_refuses_an_unknown_format_in_the_current_language() -> None:
    """``cli.py``: the invalid ``--format`` refusal goes through ``cli_core.main.invalid_format``."""

    def produce() -> str:
        return CliRunner().invoke(app, ["--format", "xml", "info"]).output

    _says(
        produce,
        "Invalid --format 'xml'. Choose rich, plain, or json.",
        "--format \u00ab xml \u00bb invalide. Choisissez rich, plain ou json.",
    )


def _help_values(relative: str) -> list[ast.expr]:
    """The value of every ``help=`` keyword in a package module, read from its source."""
    tree = ast.parse((Path(i18n.__file__).parents[1] / relative).read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    return [kw.value for call in calls for kw in call.keywords if kw.arg == "help"]


def _is_t_call(node: ast.expr) -> bool:
    """Whether ``node`` is a ``t(...)`` call."""
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "t"


def test_app_help_is_a_catalogue_text() -> None:
    """``cli_app.py``: both Typer groups take their help from a ``t(...)`` call (read at import)."""
    helps = _help_values("cli_app.py")
    assert len(helps) == 2
    assert all(_is_t_call(value) for value in helps)


def test_configuration_error_label_is_translated(monkeypatch: pytest.MonkeyPatch) -> None:
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

    _says(produce, "Configuration error:", "Erreur de configuration :")


def test_plain_output_pairs_go_through_the_catalogue(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``cli_helpers/output.py``: the plain ``key: value`` line is layout, never translated."""
    from personalscraper.cli_helpers.output import emit

    monkeypatch.setitem(state, "format", "plain")

    def produce() -> str:
        emit({"answer": 42}, rich_renderer=lambda: None)
        captured = capsys.readouterr()
        return captured.out + captured.err

    for language in Language:
        with use_language(language):
            assert produce() == "answer: 42\n"


def test_step_tally_and_check_row_go_through_the_catalogue() -> None:
    """``commands/pipeline.py``: the step tally and the ``--list-checks`` row are catalogue texts."""
    from personalscraper.commands.pipeline import _check_row, _counts
    from personalscraper.models import StepReport

    report = StepReport(name="ingest")
    _says(lambda: _counts(report), "0 OK, 0 skipped, 0 errors", "0 OK, 0 ignor\u00e9(s), 0 erreur(s)")
    spec = SimpleNamespace(
        name="x",
        group="g",
        default_severity=SimpleNamespace(value="warning"),
        fixable=True,
        indexable=False,
        description="d",
    )
    _says(lambda: _check_row(spec), "fixable", "corrigeable")  # type: ignore[arg-type]


def test_rich_console_words_the_step_name_through_the_code_set() -> None:
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

    _says(produce, "INGEST", "INGESTION")
    assert _step_word("not-a-step") == "not-a-step"


def test_init_config_sync_refuses_force_in_the_current_language() -> None:
    """``commands/config.py``: the ``--sync`` with ``--force`` refusal is ``cli_core.config.init_config``."""

    def produce() -> str:
        return CliRunner().invoke(app, ["init-config", "--sync", "--force"]).output

    _says(
        produce,
        "Error: --sync and --force are mutually exclusive.",
        _french("cli_core.config.init_config.sync_force_exclusive"),
    )


def test_init_config_missing_example_is_translated(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``commands/init_config.py``: a missing example directory is reported through ``cli_core.init_config``."""
    from personalscraper.commands.init_config import init_config

    missing = tmp_path / "absent"

    def produce() -> str:
        return _capture_echo(capsys, lambda: init_config(missing, tmp_path / "out", interactive=False, force=False))

    _says(produce, "Example directory not found:", "R\u00e9pertoire mod\u00e8le introuvable :")


def test_info_helps_are_catalogue_texts() -> None:
    """``commands/info.py``: every ``help=`` is a ``t(...)`` call; the providers help renders its placeholders."""
    helps = _help_values("commands/info.py")
    assert len(helps) == 3
    assert all(_is_t_call(value) for value in helps)
    assert "circuit=<state>" in CliRunner().invoke(app, ["info", "providers", "--help"]).output


@pytest.mark.parametrize(
    ("relative", "command", "key"),
    [
        ("commands/health_check.py", "health-check", "cli_core.health_check.help"),
        ("commands/watch.py", "watch", "cli_core.watch.help"),
        ("commands/watch.py", "watch-now", "cli_core.watch.now_help"),
        ("commands/torrents.py", "torrents-list", "cli_core.torrents.list_help"),
    ],
)
def test_docstring_helped_commands_take_their_help_from_the_catalogue(relative: str, command: str, key: str) -> None:
    """``health-check``, ``watch``, ``watch-now``, ``torrents-list``: the decorator's ``help=`` is the catalogue key.

    Their help used to be the docstring, so ``--help`` stayed English under French. The English
    catalogue text stays the docstring byte for byte, and the French one differs.
    """
    tree = ast.parse((Path(i18n.__file__).parents[1] / relative).read_text(encoding="utf-8"))
    decorated = {
        decorator.args[0].value: decorator
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call) and decorator.args and isinstance(decorator.args[0], ast.Constant)
    }
    helps = [kw.value for kw in decorated[command].keywords if kw.arg == "help"]
    assert len(helps) == 1 and _is_t_call(helps[0])
    assert isinstance(helps[0], ast.Call) and ast.literal_eval(helps[0].args[0]) == key
    docstring = next(
        ast.get_docstring(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and decorated[command] in node.decorator_list
    )
    assert i18n.t(key, language=Language.EN, hash="<H>") == docstring  # the markup value stays in code
    assert i18n.t(key, language=Language.FR, hash="<H>") != docstring


def test_health_check_ok_line_is_translated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``commands/health_check.py``: the healthy verdict is ``cli_core.health_check.ok``."""
    from personalscraper.commands import health_check as hc

    for detector in ("_check_daemons", "_check_recent_errors", "_check_stuck_lock"):
        monkeypatch.setattr(hc, detector, lambda *args, **kwargs: [])
    ctx = SimpleNamespace(obj=SimpleNamespace(config=None))

    def produce() -> str:
        return _capture_echo(capsys, lambda: hc.health_check(ctx, 90, 60, True))  # type: ignore[arg-type]

    _says(produce, "health-check: OK", "health-check : OK")


def test_schedule_without_a_job_is_refused_in_the_current_language() -> None:
    """``commands/schedule.py``: the missing-job refusal is ``cli_core.schedule.no_job``."""

    def produce() -> str:
        return CliRunner().invoke(app, ["schedule", "--cron", "* * * * *"]).output

    _says(produce, "schedule: no job given after '--'", _french("cli_core.schedule.no_job"))


def test_web_daemon_disabled_message_is_translated(capsys: pytest.CaptureFixture[str]) -> None:
    """``commands/web.py``: a disabled daemon says so through ``cli_web.disabled``."""
    from personalscraper.commands import web as web_module

    config = SimpleNamespace(web=SimpleNamespace(enabled=False))
    ctx = SimpleNamespace(invoked_subcommand=None, obj=SimpleNamespace(config=config))

    def produce() -> str:
        return _capture_echo(capsys, lambda: web_module.web(ctx, None, None))  # type: ignore[arg-type]

    _says(
        produce,
        "Web daemon is disabled (config.web.enabled=false).",
        "Le d\u00e9mon web est d\u00e9sactiv\u00e9 (config.web.enabled=false).",
    )


def test_watch_now_reports_the_sentinel_in_the_current_language(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``commands/watch.py``: ``watch-now`` words the sentinel line through ``cli_core.watch``."""
    from personalscraper.commands.watch import watch_now

    ctx = SimpleNamespace(obj=SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(data_dir=tmp_path))))

    def produce() -> str:
        return _capture_echo(capsys, lambda: watch_now(ctx))  # type: ignore[arg-type]

    _says(produce, "Sentinel written:", "Sentinelle \u00e9crite :")


def test_torrent_listing_totals_are_translated(monkeypatch: pytest.MonkeyPatch) -> None:
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

    _says(produce, "1 completed (of 2 tracked torrents)", "1 termin\u00e9s (sur 2 torrents suivis)")


def test_trailers_bad_date_is_refused_in_the_current_language(capsys: pytest.CaptureFixture[str]) -> None:
    """``trailers/cli.py``: the malformed ``--since`` refusal is ``cli_trailers.since_invalid``."""
    from personalscraper.trailers.cli import _parse_since

    def produce() -> str:
        return _capture_echo(capsys, lambda: _parse_since("yesterday"))

    _says(
        produce,
        "Error: --since 'yesterday' must be YYYY-MM-DD.",
        "Erreur : --since 'yesterday' doit \u00eatre au format AAAA-MM-JJ.",
    )


def test_step_codes_are_the_pipeline_steps() -> None:
    """``StepCode`` (the ``cli_core.step`` code set) names exactly the steps ``DEFAULT_STEPS`` registers."""
    assert {code.value for code in StepCode} == set(DEFAULT_STEPS)


def test_step_label_is_the_step_word_with_the_languages_colon() -> None:
    """``commands/pipeline.py``: one word per step (``cli_core.step``), the colon typography per language."""
    from personalscraper.commands.pipeline import _step_label

    _says(
        lambda: _step_label(StepCode.CLEANUP),
        "Cleanup:",
        _french("cli_core.pipeline.step_label", step=_french("cli_core.step.cleanup").capitalize()),
    )
    _says(lambda: _step_label(StepCode.INGEST), "Ingest:", "Ingestion :")


def test_step_header_upper_cases_an_accented_french_word() -> None:
    """``subscribers/rich_console.py``: ``.upper()`` on the translated word keeps the accent's capital."""
    from personalscraper.core.event_bus import EventBus
    from personalscraper.subscribers.rich_console import RichConsoleSubscriber

    def produce() -> str:
        buffer = StringIO()
        subscriber = RichConsoleSubscriber(EventBus(), Console(file=buffer, force_terminal=False, width=100))
        try:
            subscriber._render_step_start("verify")
        finally:
            subscriber.close()
        return buffer.getvalue()

    _says(produce, "VERIFY", _french("cli_core.step.verify").upper())


def test_verify_help_keeps_the_markup_value_in_both_languages() -> None:
    """``commands/pipeline.py``: the ``{{marker}}`` value is passed by the code, the words around it are translated."""
    from personalscraper.commands.pipeline import verify

    def produce() -> str:
        return i18n.t("cli_core.pipeline.verify.help", marker="**")

    _says(produce, "**before**", "**avant**")
    assert verify  # the command still exists
