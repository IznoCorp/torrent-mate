"""F2 regression: the standalone ``dispatch`` CLI resolves the delete permit.

The full-run path (``pipeline_steps.DispatchStep``) reads the acquire lobe's
``delete_authority`` off the :class:`AppContext` and injects it into
``run_dispatch`` as both ``permit=`` and ``recorder=``. The standalone
``personalscraper dispatch`` command must resolve the SAME authority through the
SAME single owner, otherwise the two entry points diverge: the CLI would fall
back to ``run_dispatch``'s library-level ``AllowAllPermit`` defaults and delete
a still-seeding payload the full run would veto (product-intent §7 HnR).

These tests capture at the ``run_dispatch`` seam and assert the resolved
kwargs, plus parity with what ``DispatchStep`` would resolve for the same
context.
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.core.delete_permit import AllowAllPermit
from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport

# The migrated ``dispatch`` command runs inside the ``cli_helpers.boundary``
# scaffold, which enters ``per_step_boundary`` and takes the lock from its OWN
# module namespace — patch that module, not ``personalscraper.commands.pipeline``
# / ``personalscraper.cli``.
_BOUNDARY_MOD = importlib.import_module("personalscraper.cli_helpers.boundary")

runner = CliRunner()


class _FakeAcquire:
    """Minimal stand-in for the acquire lobe carrying a delete authority."""

    def __init__(self, authority: Any) -> None:
        self.delete_authority = authority


class _FakeAppContext:
    """Minimal AppContext exposing ``event_bus`` + ``acquire.delete_authority``.

    The dispatch command only reads ``app_context.event_bus`` and (after the
    fix) ``app_context.acquire.delete_authority``. Patching the per-step
    boundary to yield this fake isolates the permit-resolution behaviour from
    the real registry / acquire construction.
    """

    def __init__(self, authority: Any) -> None:
        self.event_bus = EventBus()
        self.acquire = _FakeAcquire(authority)


def _patch_boundary(authority: Any):
    """Return a context manager patching ``per_step_boundary`` to a fake ctx."""

    @contextmanager
    def _boundary(*_args: Any, **_kwargs: Any):
        yield _FakeAppContext(authority)

    return patch.object(_BOUNDARY_MOD, "per_step_boundary", _boundary)


def _invoke_dispatch_capturing_run_dispatch(authority: Any) -> MagicMock:
    """Invoke ``dispatch`` with *authority* configured; return the run_dispatch mock.

    Args:
        authority: The object placed on ``acquire.delete_authority`` (or None).

    Returns:
        The ``MagicMock`` that replaced ``run_dispatch``; inspect
        ``.call_args.kwargs`` for the resolved ``permit``/``recorder``.
    """
    mock_dispatch = MagicMock(return_value=(StepReport(name="dispatch"), []))
    with (
        _patch_boundary(authority),
        patch("personalscraper.dispatch.run.run_dispatch", mock_dispatch),
        patch.object(_BOUNDARY_MOD, "acquire_pipeline_lock", return_value=True),
        patch.object(_BOUNDARY_MOD, "release_lock"),
    ):
        result = runner.invoke(app, ["dispatch"])
    assert result.exit_code == 0, result.output
    assert mock_dispatch.call_count == 1
    return mock_dispatch


class _ConfiguredAuthority(AllowAllPermit):
    """A distinct authority the operator configured (a real DeletePermit).

    Subclasses ``AllowAllPermit`` only to satisfy the DeletePermit /
    SeedObligationRecorder protocols with zero boilerplate; ``isinstance`` on
    the exact subclass still distinguishes it from the library-level
    ``AllowAllPermit`` default that the F2 gap would silently apply.
    """


class TestStandaloneDispatchResolvesPermit:
    """F2: the CLI dispatch command routes the same permit as the full run."""

    def test_standalone_dispatch_resolves_configured_delete_permit(self) -> None:
        """A configured ``delete_authority`` becomes ``run_dispatch``'s permit+recorder.

        Proves the standalone command does NOT fall back to the
        ``AllowAllPermit`` default when an authority is configured — it injects
        the SAME object as ``permit`` and ``recorder``, byte-for-byte with what
        ``DispatchStep`` injects on the full-run path.
        """
        authority = _ConfiguredAuthority()
        mock_dispatch = _invoke_dispatch_capturing_run_dispatch(authority)

        kwargs = mock_dispatch.call_args.kwargs
        assert "permit" in kwargs, (
            "standalone dispatch must resolve and pass a permit; the CLI still "
            "omits it, so run_dispatch falls back to its AllowAllPermit default (F2 gap)"
        )
        assert kwargs["permit"] is authority
        assert kwargs["recorder"] is authority
        assert not isinstance(kwargs["permit"], AllowAllPermit) or type(kwargs["permit"]) is _ConfiguredAuthority

    def test_standalone_dispatch_matches_dispatch_step_resolution(self) -> None:
        """The CLI resolves the SAME kwargs a DispatchStep would for the same ctx.

        Pins single-owner parity: whatever the resolver yields for the standalone
        command's app-context, ``DispatchStep``'s resolution of the same context
        yields an identical mapping.
        """
        from personalscraper.pipeline_steps import resolve_dispatch_authority

        authority = _ConfiguredAuthority()
        mock_dispatch = _invoke_dispatch_capturing_run_dispatch(authority)
        cli_kwargs = {k: mock_dispatch.call_args.kwargs[k] for k in ("permit", "recorder")}

        step_kwargs = resolve_dispatch_authority(_FakeAppContext(authority))
        assert cli_kwargs == step_kwargs

    def test_no_authority_preserves_run_dispatch_defaults(self) -> None:
        """No configured authority ⇒ the CLI passes no permit/recorder.

        Byte-identical to the pre-resolution behaviour: ``run_dispatch``'s
        library-level ``AllowAllPermit`` defaults apply when acquire has no
        ``delete_authority``, so the resolver must contribute an empty mapping
        rather than an explicit ``AllowAllPermit``.
        """
        mock_dispatch = _invoke_dispatch_capturing_run_dispatch(None)

        kwargs = mock_dispatch.call_args.kwargs
        assert "permit" not in kwargs
        assert "recorder" not in kwargs
