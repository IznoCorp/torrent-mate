"""Tests for the advisory ``kanban doctor`` Health-field check (:mod:`kanbanmate.cli.doctor_health`).

The check is ADVISORY — it never FAILs doctor: present-with-all-5 → PASS; missing options → WARN
(``ok=True`` with a ``WARNING:`` detail); no project → advisory skip; probe raises → WARN.
"""

from __future__ import annotations

from kanbanmate.cli.doctor_health import _check_health_field
from kanbanmate.core.status_update import STATUS_VALUES


def test_all_options_present_is_pass() -> None:
    """A Health field carrying all 5 options → advisory PASS (no WARNING)."""
    name, ok, detail = _check_health_field(health_check=lambda: set(STATUS_VALUES))
    assert name == "health field"
    assert ok is True
    assert "WARNING" not in detail
    assert "provisioned" in detail


def test_missing_options_is_warn_not_fail() -> None:
    """A field missing an option → advisory WARN (ok=True, WARNING: detail naming the gap)."""
    partial = set(STATUS_VALUES) - {"COMPLETE"}
    name, ok, detail = _check_health_field(health_check=lambda: partial)
    assert ok is True  # ADVISORY — never FAILs doctor
    assert detail.startswith("WARNING:")
    assert "COMPLETE" in detail


def test_no_project_is_advisory_skip() -> None:
    """No resolver (no project registered) → advisory PASS-skip."""
    name, ok, detail = _check_health_field(health_check=None)
    assert ok is True
    assert "skipped" in detail


def test_probe_raise_is_failsoft_warn() -> None:
    """A probe error (missing token / unreachable API) → advisory WARN, never a FAIL/crash."""

    def _boom() -> set[str]:
        raise RuntimeError("github unreachable")

    name, ok, detail = _check_health_field(health_check=_boom)
    assert ok is True  # ADVISORY — fail-soft
    assert detail.startswith("WARNING:")
    assert "github unreachable" in detail
