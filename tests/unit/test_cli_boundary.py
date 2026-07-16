"""Unit tests for the ``cli_helpers.boundary()`` decorator (P3.1).

Exercise the decorator's orchestration — tier bundle selection, lock acquire/
release exactly-once semantics (incl. on exception), journal opening, staging
gating, injected lock path (no config re-load), and error/exit-code parity with
``per_step_boundary`` — with the heavy ``per_step_boundary`` / journal / lock
collaborators monkeypatched to probes so each concern is asserted in isolation.

No production command is touched: bespoke test commands are decorated inline.
"""

from __future__ import annotations

import importlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from personalscraper.cli_helpers import CommandContext, boundary
from personalscraper.core.event_bus import EventBus

# The cli_helpers package re-exports the ``boundary`` function, shadowing the
# ``boundary`` submodule attribute — so string-based monkeypatch targets fail.
# Grab the real module object and patch its attributes directly.
_BMOD = importlib.import_module("personalscraper.cli_helpers.boundary")


def _fake_config(*, data_dir: Path, db_path: Path | None) -> SimpleNamespace:
    """Build a minimal fake ``Config`` exposing only the boundary's touch points."""
    return SimpleNamespace(
        paths=SimpleNamespace(data_dir=data_dir),
        indexer=SimpleNamespace(db_path=db_path),
    )


def _fake_ctx(config: SimpleNamespace) -> SimpleNamespace:
    """Build a fake Typer ``ctx`` whose ``ctx.obj.config`` is *config*."""
    return SimpleNamespace(obj=SimpleNamespace(config=config))


@pytest.fixture(autouse=True)
def _neutralise_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``get_settings()`` return a sentinel so no real env/.env is read."""
    monkeypatch.setattr(_BMOD, "get_settings", lambda: SimpleNamespace(_sentinel="settings"))


@contextmanager
def _fake_per_step_boundary_cm(app_context: Any):
    """A stand-in ``per_step_boundary`` context manager yielding *app_context*."""
    yield app_context


class _PerStepSpy:
    """Records ``per_step_boundary`` calls and yields a sentinel AppContext."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.app_context = SimpleNamespace(event_bus=EventBus(), torrent_client=None)

    def __call__(self, config: Any, settings: Any, **kwargs: Any):  # noqa: ANN204
        self.calls.append({"config": config, "settings": settings, **kwargs})
        return _fake_per_step_boundary_cm(self.app_context)


# --------------------------------------------------------------------------- #
# Tier bundle selection
# --------------------------------------------------------------------------- #


def test_config_tier_builds_no_app_context_and_no_conn(tmp_path, monkeypatch):
    """needs="config": no AppContext, no indexer conn, a fresh unobserved bus."""
    spy = _PerStepSpy()
    monkeypatch.setattr(_BMOD, "per_step_boundary", spy)
    captured: dict[str, CommandContext] = {}

    @boundary(needs="config", lock=False, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        captured["bundle"] = bundle

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))

    bundle = captured["bundle"]
    assert spy.calls == []  # per_step_boundary / AppContext never built
    assert bundle.needs == "config"
    assert bundle.app_context is None
    assert bundle.indexer_conn is None
    assert isinstance(bundle.event_bus, EventBus)


def test_db_read_tier_opens_readonly_conn_and_no_writer(tmp_path, monkeypatch):
    """needs="db-read": read-only conn (writes fail), no torrent client / AppContext."""
    spy = _PerStepSpy()
    monkeypatch.setattr(_BMOD, "per_step_boundary", spy)

    db = tmp_path / "library.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t (x) VALUES (1)")
    conn.commit()
    conn.close()

    captured: dict[str, CommandContext] = {}

    @boundary(needs="db-read", lock=False, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        captured["bundle"] = bundle
        # Connection is live inside the boundary and genuinely read-only.
        assert bundle.indexer_conn is not None
        assert bundle.indexer_conn.execute("SELECT x FROM t").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError):
            bundle.indexer_conn.execute("INSERT INTO t (x) VALUES (2)")

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=db)))

    bundle = captured["bundle"]
    assert spy.calls == []  # no AppContext / no torrent client built
    assert bundle.app_context is None
    # Conn closed on unwind (registered on the ExitStack).
    with pytest.raises(sqlite3.ProgrammingError):
        bundle.indexer_conn.execute("SELECT 1")  # type: ignore[union-attr]


def test_db_read_tier_missing_db_yields_none_conn(tmp_path, monkeypatch):
    """needs="db-read": absent DB file → ``indexer_conn`` is None (fresh clone)."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    captured: dict[str, CommandContext] = {}

    @boundary(needs="db-read", lock=False, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        captured["bundle"] = bundle

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=tmp_path / "absent.db")))
    assert captured["bundle"].indexer_conn is None


def test_app_tier_yields_app_context_and_forwards_flags(tmp_path, monkeypatch):
    """needs="app": bundle carries the AppContext + its bus; flags are forwarded."""
    spy = _PerStepSpy()
    monkeypatch.setattr(_BMOD, "per_step_boundary", spy)
    captured: dict[str, CommandContext] = {}

    @boundary(needs="app", lock=False, journal=False, staging=False, build_torrent_client=True, stream_events=True)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        captured["bundle"] = bundle

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))

    assert len(spy.calls) == 1
    assert spy.calls[0]["build_torrent_client"] is True
    assert spy.calls[0]["stream_events"] is True
    bundle = captured["bundle"]
    assert bundle.app_context is spy.app_context
    assert bundle.event_bus is spy.app_context.event_bus


# --------------------------------------------------------------------------- #
# Lock — acquire / release exactly once, incl. on exception; read-only never locks
# --------------------------------------------------------------------------- #


def test_lock_acquired_and_released_exactly_once_on_success(tmp_path, monkeypatch):
    """needs="app", lock=True: acquire + release each fire once with injected path."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    acquired: list[Path] = []
    released: list[Path] = []
    monkeypatch.setattr(_BMOD, "acquire_pipeline_lock", lambda lock_file, _dir: acquired.append(lock_file) or True)
    monkeypatch.setattr(_BMOD, "release_lock", lambda *, lock_file: released.append(lock_file))

    data_dir = tmp_path / ".data"

    @boundary(needs="app", lock=True, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        pass

    cmd(_fake_ctx(_fake_config(data_dir=data_dir, db_path=None)))

    expected = data_dir / "pipeline.lock"
    assert acquired == [expected]
    assert released == [expected]


def test_lock_released_exactly_once_on_exception(tmp_path, monkeypatch):
    """A raising body still releases the lock exactly once; the error propagates."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    monkeypatch.setattr(_BMOD, "acquire_pipeline_lock", lambda lock_file, _dir: True)
    released: list[Path] = []
    monkeypatch.setattr(_BMOD, "release_lock", lambda *, lock_file: released.append(lock_file))

    @boundary(needs="app", lock=True, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        raise RuntimeError("body boom")

    with pytest.raises(RuntimeError, match="body boom"):
        cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))

    assert released == [tmp_path / ".data" / "pipeline.lock"]


def test_lock_busy_raises_exit_1_and_never_releases(tmp_path, monkeypatch):
    """A lost lock race prints the busy message, raises Exit(1), never releases."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    monkeypatch.setattr(_BMOD, "acquire_pipeline_lock", lambda lock_file, _dir: False)
    released: list[Path] = []
    monkeypatch.setattr(_BMOD, "release_lock", lambda *, lock_file: released.append(lock_file))
    ran: list[bool] = []

    @boundary(needs="app", lock=True, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        ran.append(True)

    with pytest.raises(typer.Exit) as excinfo:
        cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))

    assert excinfo.value.exit_code == 1
    assert ran == []  # body never ran
    assert released == []  # nothing to release — lock was never acquired


def test_readonly_tier_never_locks_even_with_lock_true(tmp_path, monkeypatch):
    """Read-only tiers never take pipeline.lock, regardless of the lock= flag."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    acquired: list[Path] = []
    monkeypatch.setattr(_BMOD, "acquire_pipeline_lock", lambda lock_file, _dir: acquired.append(lock_file) or True)
    monkeypatch.setattr(_BMOD, "release_lock", lambda *, lock_file: None)

    @boundary(needs="db-read", lock=True, journal=True, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        pass

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))
    assert acquired == []


def test_lock_end_to_end_creates_and_removes_lock_file(tmp_path, monkeypatch):
    """With the REAL lock helpers, the lock file exists in-body and is gone after."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    data_dir = tmp_path / ".data"
    lock_file = data_dir / "pipeline.lock"
    seen: dict[str, bool] = {}

    @boundary(needs="app", lock=True, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        seen["in_body"] = lock_file.exists()

    cmd(_fake_ctx(_fake_config(data_dir=data_dir, db_path=None)))

    assert seen["in_body"] is True  # held during the body
    assert not lock_file.exists()  # released on exit


# --------------------------------------------------------------------------- #
# Journal — opened with the command name; read-only tiers never journal
# --------------------------------------------------------------------------- #


def test_journal_opened_with_command_name(tmp_path, monkeypatch):
    """needs="app", journal=True: cli_step_journal opens with func name + dry_run."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    monkeypatch.setattr(_BMOD, "acquire_pipeline_lock", lambda lock_file, _dir: True)
    monkeypatch.setattr(_BMOD, "release_lock", lambda *, lock_file: None)
    journal_calls: list[dict[str, Any]] = []

    @contextmanager
    def fake_journal(config, *, command, dry_run):  # noqa: ANN001, ANN202
        journal_calls.append({"command": command, "dry_run": dry_run})
        yield "run-uid-123"

    monkeypatch.setattr(_BMOD, "cli_step_journal", fake_journal)
    captured: dict[str, CommandContext] = {}

    @boundary(needs="app", journal=True, staging=False)
    def dispatch(ctx, *, bundle: CommandContext, dry_run: bool = False) -> None:
        captured["bundle"] = bundle

    dispatch(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)), dry_run=True)

    assert journal_calls == [{"command": "dispatch", "dry_run": True}]
    assert captured["bundle"].run_uid == "run-uid-123"


def test_journal_command_override(tmp_path, monkeypatch):
    """An explicit command= overrides the wrapped function name in the journal."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    monkeypatch.setattr(_BMOD, "acquire_pipeline_lock", lambda lock_file, _dir: True)
    monkeypatch.setattr(_BMOD, "release_lock", lambda *, lock_file: None)
    names: list[str] = []

    @contextmanager
    def fake_journal(config, *, command, dry_run):  # noqa: ANN001, ANN202
        names.append(command)
        yield None

    monkeypatch.setattr(_BMOD, "cli_step_journal", fake_journal)

    @boundary(needs="app", journal=True, staging=False, command="custom-step")
    def cmd(ctx, *, bundle: CommandContext) -> None:
        pass

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))
    assert names == ["custom-step"]


def test_readonly_tier_never_journals(tmp_path, monkeypatch):
    """Read-only tiers never open a pipeline_run journal row."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    opened: list[str] = []

    @contextmanager
    def fake_journal(config, *, command, dry_run):  # noqa: ANN001, ANN202
        opened.append(command)
        yield None

    monkeypatch.setattr(_BMOD, "cli_step_journal", fake_journal)

    @boundary(needs="config", journal=True, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        pass

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))
    assert opened == []


# --------------------------------------------------------------------------- #
# Staging — gated purely by the flag
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("staging_flag", [True, False])
def test_staging_bootstrap_gated_by_flag(tmp_path, monkeypatch, staging_flag):
    """_bootstrap_staging fires iff staging=True."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    bootstrap_calls: list[Any] = []
    monkeypatch.setattr(_BMOD, "_bootstrap_staging", lambda ctx: bootstrap_calls.append(ctx))

    @boundary(needs="app", lock=False, journal=False, staging=staging_flag)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        pass

    ctx = _fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None))
    cmd(ctx)

    assert bootstrap_calls == ([ctx] if staging_flag else [])


# --------------------------------------------------------------------------- #
# Lock path injection — config is not re-loaded on the primary path
# --------------------------------------------------------------------------- #


def test_lock_path_injected_config_not_reloaded(tmp_path, monkeypatch):
    """With the REAL lock helpers, load_config is never called (path injected)."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    reloads: list[Any] = []
    # If lock.py fell back to _default_lock_file it would call load_config here.
    monkeypatch.setattr(
        "personalscraper.conf.loader.load_config",
        lambda *a, **k: reloads.append((a, k)),
    )

    @boundary(needs="app", lock=True, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        pass

    cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))
    assert reloads == []  # lock path injected — no config re-load


# --------------------------------------------------------------------------- #
# Error / exit-code parity with per_step_boundary (exceptions propagate)
# --------------------------------------------------------------------------- #


def test_exit_code_propagates_unchanged(tmp_path, monkeypatch):
    """A typer.Exit raised in the body propagates with its code intact."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())
    monkeypatch.setattr(_BMOD, "acquire_pipeline_lock", lambda lock_file, _dir: True)
    released: list[Path] = []
    monkeypatch.setattr(_BMOD, "release_lock", lambda *, lock_file: released.append(lock_file))

    @boundary(needs="app", lock=True, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        raise typer.Exit(2)

    with pytest.raises(typer.Exit) as excinfo:
        cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))

    assert excinfo.value.exit_code == 2
    assert released == [tmp_path / ".data" / "pipeline.lock"]  # still released


def test_boundary_does_not_swallow_body_exceptions(tmp_path, monkeypatch):
    """The boundary never suppresses a body error (parity with per_step_boundary)."""
    monkeypatch.setattr(_BMOD, "per_step_boundary", _PerStepSpy())

    @boundary(needs="config", lock=False, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext) -> None:
        raise ValueError("surfaced")

    with pytest.raises(ValueError, match="surfaced"):
        cmd(_fake_ctx(_fake_config(data_dir=tmp_path / ".data", db_path=None)))


# --------------------------------------------------------------------------- #
# Decoration-time contracts
# --------------------------------------------------------------------------- #


def test_invalid_tier_rejected_at_decoration_time():
    """An unknown needs= tier fails loudly at decoration time."""
    with pytest.raises(ValueError, match="invalid"):
        boundary(needs="bogus")


def test_missing_bundle_parameter_rejected():
    """A command without a bundle parameter is rejected at decoration time."""
    with pytest.raises(TypeError, match="bundle"):

        @boundary(needs="config")
        def cmd(ctx, dry_run: bool = False) -> None:
            pass


def test_bundle_hidden_from_typer_signature():
    """The injected bundle parameter is stripped from the CLI-visible signature."""
    import inspect

    @boundary(needs="config", lock=False, journal=False, staging=False)
    def cmd(ctx, *, bundle: CommandContext, dry_run: bool = False) -> None:
        pass

    params = list(inspect.signature(cmd).parameters)
    assert "bundle" not in params
    assert params == ["ctx", "dry_run"]
