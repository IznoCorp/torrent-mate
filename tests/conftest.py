"""Shared pytest fixtures for PersonalScraper tests.

Installs structlog via :func:`personalscraper.logger.configure_logging` before any test runs,
so that stdlib-bridged `caplog` assertions see the expected records irrespective of which
subset of tests is collected (e.g. ``pytest tests/sorter/`` in isolation).
"""

import inspect
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv
from typer.testing import CliRunner as _RawCliRunner

import personalscraper.logger as _logger_mod
from personalscraper.config import Settings
from personalscraper.logger import configure_logging

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _patch_tenacity_sleep() -> None:
    """Replace tenacity sleep with a no-op so retries are instant in tests.

    Tenacity's Retrying class captures its sleep function as a default
    parameter at class-definition time (``from .nap import sleep``), so
    patching ``tenacity.nap.sleep`` after the module is loaded has no
    effect on already-created decorator instances.  Overriding the sleep
    argument in ``__init__`` ensures every Retrying object created after
    this patch uses a no-op without touching ``time.sleep`` globally.

    Must run at module level (import time), before any test module
    imports ``personalscraper.scraper.*`` which triggers ``@retry``
    decoration on ``TMDBClient._get`` and similar.
    """
    import tenacity as _tenacity

    def _noop_sleep(seconds: float) -> None:
        pass

    _original_init = _tenacity.Retrying.__init__

    def _patched_init(
        self: _tenacity.Retrying,
        *args: object,
        **kwargs: object,
    ) -> None:
        kwargs["sleep"] = _noop_sleep
        _original_init(self, *args, **kwargs)

    _tenacity.Retrying.__init__ = _patched_init


_patch_tenacity_sleep()


def make_cli_runner() -> _RawCliRunner:
    """Return a CliRunner that separates stdout from stderr across click versions.

    Click 8.2 removed the ``mix_stderr`` keyword (separated streams became the
    default).  Older click required ``mix_stderr=False`` to get the same behaviour.
    Typer subclasses click's CliRunner, so the keyword propagates through.  This
    helper inspects the constructor signature and passes the keyword only when
    it is still accepted.
    """
    if "mix_stderr" in inspect.signature(_RawCliRunner.__init__).parameters:
        # Older Click signatures still accept mix_stderr; the runtime check
        # above guards against newer versions where it has been removed.
        return _RawCliRunner(mix_stderr=False)  # type: ignore[call-arg]
    return _RawCliRunner()


# Expose shared fixtures from the fixtures package
pytest_plugins = ["tests.fixtures.config", "tests.fixtures.settings_stub"]

# Disable Rich/Typer color output so help-text assertions (e.g. "--disk" in output)
# match the rendered text without ANSI escape codes splitting option names.
os.environ.setdefault("NO_COLOR", "1")
os.environ.setdefault("TERM", "dumb")

# Patch targets for the eager config load in the CLI callback.
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"


@pytest.fixture(autouse=True)
def _neutralize_external_notify_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force external-notification credentials empty for every test.

    This module calls :func:`load_dotenv` (top of file) so the real ``.env`` —
    including ``TELEGRAM_BOT_TOKEN`` / ``TELEGRAM_CHAT_ID`` / ``HEALTHCHECK_URL`` —
    leaks into ``os.environ`` for the whole session. Any test that invokes the
    real ``run`` command (e.g. the E2E dry-run staging tests) then builds a
    *real* ``TelegramNotifier`` from :class:`~personalscraper.config.Settings`
    and POSTs a pipeline report to the operator's chat — firing on every local
    ``pytest`` run, i.e. every ``git push`` via the pre-push hook.

    Setting these vars to ``""`` makes the corresponding ``Settings`` fields
    empty (an explicit environment variable overrides the on-disk ``.env`` in
    pydantic-settings), so ``TelegramNotifier.is_configured`` /
    ``HealthcheckClient.is_configured`` return ``False`` and no external send is
    ever attempted. Tests that genuinely exercise the notifier construct it
    directly with explicit arguments and are unaffected; tests asserting the
    "configured" branch patch ``is_configured`` themselves, overriding this
    default.
    """
    for _var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "HEALTHCHECK_URL"):
        monkeypatch.setenv(_var, "")


@pytest.fixture(scope="session", autouse=True)
def _configure_logging_for_tests(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Configure structlog once per session for caplog interop.

    Points LOGS_DIR to a temporary directory so tests never write to the
    real ``logs/`` directory at the repository root.  Wraps the call in
    try/except so a misconfiguration surfaces as an explicit pytest failure
    rather than a silent no-op that lets later assertions fail for obscure
    reasons.

    Args:
        tmp_path_factory: Session-scoped factory for temporary directories.
    """
    # Redirect log output to a per-session temp dir so the real logs/ dir is
    # never touched during the test run.
    session_logs_dir: Path = tmp_path_factory.mktemp("logs", numbered=True)

    # Use pytest.MonkeyPatch.context() for session-scoped attribute patching
    # (the function-scoped monkeypatch fixture is not available here).
    mp = pytest.MonkeyPatch()
    mp.setattr(_logger_mod, "LOGS_DIR", session_logs_dir)
    # Session-scoped patch: no undo needed (all tests share the same logs dir).

    try:
        configure_logging(verbose=False, quiet=False)
    except Exception as exc:  # noqa: BLE001 — surface any misconfiguration
        pytest.fail(f"configure_logging() failed: {exc}")

    # Replace the expensive ConsoleRenderer on the console handler with a fast
    # KeyValueRenderer.  ConsoleRenderer can take ~1 s per log call (coloring,
    # rich formatting), which adds up to 4+ s per tenacity-based timeout test.
    _replace_console_renderer_for_tests()


def _replace_console_renderer_for_tests() -> None:
    """Swap ConsoleRenderer → KeyValueRenderer on the console logging handler.

    Called once per session after ``configure_logging()`` so that log output
    remains inspectable (via ``caplog``) but does not pay the ~1 s per-call
    formatting cost of the colored dev renderer.
    """
    import logging

    import structlog.dev
    import structlog.processors

    root = logging.getLogger()
    for handler in root.handlers:
        if handler.get_name() == "console":
            fmt = handler.formatter
            if hasattr(fmt, "processors"):
                # ProcessorFormatter stores processors as a list; swap the
                # ConsoleRenderer for a cheap KeyValueRenderer.
                new_procs = [
                    structlog.processors.KeyValueRenderer(sort_keys=False)
                    if isinstance(p, structlog.dev.ConsoleRenderer)
                    else p
                    for p in fmt.processors
                ]
                fmt.processors = new_procs
            break


# NOTE: The legacy autouse `_patch_provider_registry_for_cli_tests` fixture was
# removed in feat/registry Phase 15. CLI tests now rely on:
#   - tests/fixtures/settings_stub.make_typed_settings_stub() — typed Settings
#     with dummy credentials that boot ProviderRegistry cleanly (Phase 9.1).
#   - TVDBClient deferred bootstrap (Phase 14) — no HTTP call at __init__.
# Real ProviderRegistry boots silently end-to-end on every CLI test.


@pytest.fixture(autouse=True)
def _mock_cli_config_load(request, test_config):
    """Patch the eager config load in the CLI callback for CLI test files only.

    Intercepts load_config / resolve_config_path so tests do not need a
    real config.json5 on disk. Only active for test files that invoke the
    Typer CLI via CliRunner (test_cli.py, test_logger_cli.py). Other test
    files (e.g. tests/conf/) call the loader directly and are unaffected.

    Args:
        request: Pytest request object for introspection.
        test_config: Synthetic Config fixture from tests/fixtures/config.py.
    """
    # Only intercept in files that drive the CLI via CliRunner.
    # The skill + indexer/scanner test files were added to this set on
    # 2026-05-23 because their cmd-existence smoke tests invoke `--help`
    # via CliRunner / subprocess and sometimes trip the eager config load
    # via cross-worker xdist state leak (pre-existing intermittent failures
    # documented in IMPLEMENTATION.md "Known flaky / env-dependent tests").
    cli_test_files = {
        "test_cli.py",
        "test_logger_cli.py",
        "test_matrix_cli_refs.py",
        "test_init_canonical.py",
        "test_scrape_resolve.py",
    }
    if request.fspath.basename not in cli_test_files:
        yield
        return

    with (
        patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
        patch(_PATCH_LOAD_CONFIG, return_value=test_config),
    ):
        yield


@pytest.fixture(autouse=True)
def _stub_pipeline_steps(request, monkeypatch):
    """No-op stub for all pipeline step run_* functions, scoped to test_cli.py.

    Eliminates the repetitive per-test ``@patch("personalscraper.<module>.run_*")``
    decorators that stub out step execution in CLI tests.  Only active when
    ``test_cli.py`` is being collected; all other test files are unaffected.

    The fixture patches:

    * ``personalscraper.cli.acquire_lock``     → returns ``True``
    * ``personalscraper.cli.release_lock``     → no-op
    * ``personalscraper.cli.run_ingest``       → returns a no-op ``StepReport``
    * ``personalscraper.sorter.run.run_sort``  → returns a no-op ``StepReport``
    * ``personalscraper.scraper.run.run_scrape`` → returns a no-op ``StepReport``
    * ``personalscraper.process.run.run_process`` → returns a 3-tuple of ``StepReport``
    * ``personalscraper.pipeline.Pipeline.run``  → returns a minimal ``PipelineReport``
    * ``personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured`` → returns ``False``
    * ``personalscraper.logger.cleanup_old_logs``               → returns ``0``
    * ``personalscraper.api.notify.telegram.TelegramNotifier.is_configured`` → returns ``False``

    Per-test ``@patch`` decorators override these defaults where a test must
    assert on specific call arguments or return values (wiring tests).

    Args:
        request: Pytest request object used to inspect the active test file.
        monkeypatch: Pytest monkeypatch fixture for attribute replacement.
    """
    if request.fspath.basename != "test_cli.py":
        yield
        return

    from datetime import datetime, timedelta

    from personalscraper.models import PipelineReport, StepReport

    # Build a minimal 7-step PipelineReport for the `run` command default stub.
    _report = PipelineReport(started_at=datetime(2026, 1, 1))
    for _name in ("ingest", "sort", "clean", "scrape", "cleanup", "verify", "dispatch"):
        _report.add_step(_name, StepReport(name=_name))
    _report.finished_at = datetime(2026, 1, 1) + timedelta(seconds=1)

    # Lock helpers — every CLI command acquires/releases the pipeline lock.
    # Pipeline commands route through acquire_pipeline_lock (global lock +
    # scrape-dir fail-closed check, webui-ux phase 4); acquire_lock is kept
    # stubbed for any residual raw callers.
    monkeypatch.setattr("personalscraper.cli.acquire_lock", lambda *a, **kw: True)
    monkeypatch.setattr("personalscraper.cli.acquire_pipeline_lock", lambda *a, **kw: True)
    monkeypatch.setattr("personalscraper.cli.release_lock", lambda *a, **kw: None)
    # Migrated pipeline step commands (ingest/sort/scrape/…) take the lock via
    # the ``cli_helpers.boundary`` decorator, which imports the lock helpers into
    # its own module namespace — patching ``personalscraper.cli.*`` does not
    # intercept them. Patch the boundary module too so no real ``pipeline.lock``
    # is ever created during test_cli.py. (``run`` still uses ``personalscraper.cli``.)
    import importlib  # noqa: PLC0415

    _bmod = importlib.import_module("personalscraper.cli_helpers.boundary")
    monkeypatch.setattr(_bmod, "acquire_pipeline_lock", lambda *a, **kw: True)
    monkeypatch.setattr(_bmod, "release_lock", lambda *a, **kw: None)

    # Standalone step commands.
    monkeypatch.setattr(
        "personalscraper.cli.run_ingest",
        lambda *a, **kw: StepReport(name="ingest"),
    )
    monkeypatch.setattr(
        "personalscraper.sorter.run.run_sort",
        lambda *a, **kw: StepReport(name="sort"),
    )
    monkeypatch.setattr(
        "personalscraper.scraper.run.run_scrape",
        lambda *a, **kw: StepReport(name="scrape"),
    )
    monkeypatch.setattr(
        "personalscraper.process.run.run_process",
        lambda *a, **kw: (
            StepReport(name="clean"),
            StepReport(name="scrape"),
            StepReport(name="cleanup"),
        ),
    )

    # Pipeline orchestrator used by `personalscraper run`.
    import personalscraper.pipeline as _pipeline_mod

    # ``Pipeline.run`` accepts run-scope flags as keyword-only kwargs
    # (``dry_run``, ``interactive``, ``verbose``, ``step_overrides``,
    # ``skip_trailers``, ``continue_on_trailer_error``). The stub must
    # accept and discard any of them.
    monkeypatch.setattr(_pipeline_mod.Pipeline, "run", lambda self, **_kw: _report)

    # Notifier + healthcheck helpers called inside the `run` command.
    monkeypatch.setattr(
        "personalscraper.api.notify.healthchecks.HealthcheckClient.is_configured",
        staticmethod(lambda *a, **kw: False),
    )
    monkeypatch.setattr("personalscraper.logger.cleanup_old_logs", lambda *a, **kw: 0)
    monkeypatch.setattr(
        "personalscraper.api.notify.telegram.TelegramNotifier.is_configured",
        staticmethod(lambda *a, **kw: False),
    )

    # TelegramSubscriber.close is only called when the subscriber was constructed
    # (i.e. __init__ ran, not patched to return None).  Patching close here as a
    # no-op means tests that patch __init__ → None (the common case) no longer
    # need a redundant @patch for close — the ``is not None`` guard in the CLI
    # ``finally`` block (commands/pipeline.py:518) already skips it.
    monkeypatch.setattr(
        "personalscraper.subscribers.telegram.TelegramSubscriber.close",
        lambda self, *a, **kw: None,
    )

    yield


@pytest.fixture(scope="session", autouse=True)
def _no_magicmock_files_leaked(tmp_path_factory: pytest.TempPathFactory):
    """Assert that no ``<MagicMock …>`` files are leaked to the working directory.

    Session-scoped sentinel that snapshots the current working directory before
    any test runs and fails at session teardown if any file whose name starts
    with ``<MagicMock`` still exists.  These files are produced when a
    ``MagicMock()`` config is passed to code that calls
    ``state_file.with_suffix(".lock")`` — the mock's ``__str__`` repr is used
    as the file-system path (finding 10.5/C1).

    The fixture is session-scoped and autouse so it always runs, regardless of
    which subset of tests is collected.

    Args:
        tmp_path_factory: Required by session-scoped fixtures; unused directly
            but ensures this fixture runs in the same session as the other
            session-scoped autouse fixtures.
    """
    # Common cache/tooling dirs that are never leak targets — skip them to keep
    # the rglob fast and avoid false positives on read-only vendor dirs.
    _SKIP_DIRS = frozenset({"__pycache__", ".git", ".venv", ".tox", "node_modules", ".mypy_cache"})

    cwd = Path.cwd()
    yield
    # Teardown: walk cwd recursively (including subdirs like .data/, logs/),
    # but skip tooling directories that can never contain leaked state files.
    leaked: list[Path] = [p for p in cwd.rglob("<MagicMock*") if not any(part in _SKIP_DIRS for part in p.parts)]
    if leaked:
        paths_str = "\n  ".join(str(p) for p in leaked)
        pytest.fail(
            f"MagicMock file(s) leaked to working directory — a test passed a "
            f"bare MagicMock to code that writes to the filesystem:\n  {paths_str}"
        )


@pytest.fixture
def mock_settings(tmp_path, monkeypatch):
    """Provide a Settings instance with temp paths and no real .env.

    V15: disk paths and staging/torrent dirs removed from Settings — they now
    live in Config (conf/models.py). This fixture only sets env vars for
    fields that still exist in Settings.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture for env vars.

    Returns:
        A Settings instance with neutral test values.
    """
    return Settings(_env_file=None)  # type: ignore[call-arg]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip ``darwin_only`` tests when not running on macOS.

    Applied unconditionally at collection time so the marker works without
    any per-test ``@pytest.mark.skipif`` decorator.

    Args:
        items: Collected test items (mutated in place).
    """
    import sys

    if sys.platform == "darwin":
        return  # All platforms supported; nothing to skip.

    skip_non_darwin = pytest.mark.skip(reason="darwin_only: requires macOS launchctl")
    for item in items:
        if item.get_closest_marker("darwin_only"):
            item.add_marker(skip_non_darwin)


@pytest.fixture(autouse=True)
def _fresh_web_torrent_session() -> None:
    """Drop the web layer's process-wide cached torrent client between tests.

    The shared session cache (``personalscraper.web.torrent_session``) is a
    module global; without this reset a MagicMock client cached by one test
    would be served to every later test in the same process.
    """
    from personalscraper.web.torrent_session import invalidate_torrent_session

    invalidate_torrent_session()
