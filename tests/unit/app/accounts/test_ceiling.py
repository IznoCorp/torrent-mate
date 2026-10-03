"""Unit tests for ``personalscraper.app.accounts.ceiling`` — the instance's ceiling, read per call."""

from __future__ import annotations

import pytest

from personalscraper.app.accounts.ceiling import InstanceCeiling, current_ceiling
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with neither variable set.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)


def test_read_only_clone_forbids_every_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """``PERSONALSCRAPER_WEB_ROLE=staging`` is today's read-only clone: every write, read-only."""
    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

    assert current_ceiling() == InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)


def test_read_only_clone_wins_over_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The web role is read before the environment."""
    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")

    assert current_ceiling() == InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)


def test_preprod_forbids_library_delete_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """``PERSONALSCRAPER_ENV=staging`` is the preprod: ``library.delete`` alone."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")

    assert current_ceiling() == InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)


def test_production_forbids_nothing() -> None:
    """Neither variable: production, nothing forbidden."""
    assert current_ceiling() == InstanceCeiling(forbidden=frozenset(), read_only=False)


def test_read_per_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ceiling follows the environment at each call, never cached."""
    assert not current_ceiling().read_only
    monkeypatch.setenv("PERSONALSCRAPER_WEB_ROLE", "staging")

    assert current_ceiling().read_only
