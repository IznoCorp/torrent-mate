"""Tests for the preprod guard on the dispatch target folder."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from personalscraper.conf import preprod_guard
from personalscraper.dispatch._item import _refused_by_preprod_guard
from personalscraper.dispatch._types import DispatchResult
from tests.conf.test_preprod_guard import _config, _root


def _dispatcher(tmp_path: Path) -> tuple[Any, Path]:
    disk = _root(tmp_path, "disk")
    return SimpleNamespace(config=_config(tmp_path, disk, _root(tmp_path, "stage"))), disk


def test_destination_outside_the_roots_is_refused_under_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under staging a destination outside every root ends the result as an error."""
    dispatcher, _ = _dispatcher(tmp_path)
    monkeypatch.setattr(preprod_guard, "is_mounted", lambda path: True)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    result = DispatchResult(source=tmp_path / "src")
    assert _refused_by_preprod_guard(dispatcher, result, tmp_path / "prod-media" / "Film (2024)") is True
    assert result.action == "error"
    assert "Preprod guard" in result.reason


def test_destination_inside_a_root_passes_under_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A destination and a staging source under marked, mounted roots are not refused."""
    dispatcher, disk = _dispatcher(tmp_path)
    monkeypatch.setattr(preprod_guard, "is_mounted", lambda path: True)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    result = DispatchResult(source=tmp_path / "stage" / "001-MOVIES" / "Film (2024)")
    assert _refused_by_preprod_guard(dispatcher, result, disk / "movies" / "Film (2024)") is False
    assert result.action == "error"  # untouched: the DispatchResult default


def test_unset_environment_never_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside staging the guard refuses nothing."""
    dispatcher, _ = _dispatcher(tmp_path)
    monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)
    result = DispatchResult(source=tmp_path / "src")
    assert _refused_by_preprod_guard(dispatcher, result, tmp_path / "anywhere") is False
