"""Tests for the isolation guard: a data directory names its environment.

A ``.tm-environment`` file in ``paths.data_dir`` names the environment that owns it.
A process of another environment refuses to load its config; ``staging`` refuses an
unmarked data directory and the production stream key. Production with no marker
loads exactly as before.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from personalscraper.conf import ids as CID
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.web import WebConfig
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# Spelled out rather than imported, so these load-level tests run (and fail) on a
# base that has no isolation module; ``test_marker_constant`` pins the two together.
_MARKER = ".tm-environment"
_STAGING_KEY = "personalscraper:events:staging"


def _data_dir(tmp_path: Path, marker: str | None = None) -> Path:
    """Create a data directory, optionally marked.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        marker: The marker file's content; ``None`` leaves the directory unmarked.

    Returns:
        The data directory.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    if marker is not None:
        (data_dir / _MARKER).write_text(marker, encoding="utf-8")
    return data_dir


def _config(data_dir: Path, tmp_path: Path, **extra: object) -> Config:
    """Build the minimal valid Config over ``data_dir``.

    Args:
        data_dir: The data directory.
        tmp_path: Pytest tmp_path fixture value.
        **extra: Extra ``Config`` fields (e.g. ``web``).

    Returns:
        A loaded ``Config``.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "complete",
            staging_dir=tmp_path / "staging",
            data_dir=data_dir,
        ),
        disks=[DiskConfig(id="disk_a", path=tmp_path / "disk_a", categories=list(CID.BUILTIN_CATEGORY_IDS))],
        staging_dirs=CANONICAL_STAGING_DIRS,
        **extra,  # type: ignore[arg-type]
    )


def test_prod_refuses_a_staging_data_dir(tmp_path: Path) -> None:
    """With the variable unset (prod), a data directory marked ``staging`` fails, naming both."""
    data_dir = _data_dir(tmp_path, "staging\n")
    with pytest.raises(ValidationError) as excinfo:
        _config(data_dir, tmp_path)
    message = str(excinfo.value)
    assert "staging" in message
    assert "prod" in message


def test_staging_refuses_an_unmarked_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``staging`` never runs on a data directory nobody marked as its own."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    data_dir = _data_dir(tmp_path)
    with pytest.raises(ValidationError) as excinfo:
        _config(data_dir, tmp_path, web=WebConfig(stream_key=_STAGING_KEY))
    assert _MARKER in str(excinfo.value)


def test_staging_refuses_the_production_stream_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A marked ``staging`` data directory still fails on the default (production) stream key."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    data_dir = _data_dir(tmp_path, "staging")
    with pytest.raises(ValidationError) as excinfo:
        _config(data_dir, tmp_path)
    assert "stream_key" in str(excinfo.value)


def test_staging_loads_on_its_own_data_dir_and_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``staging`` on a ``staging``-marked directory with its own stream key loads."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    data_dir = _data_dir(tmp_path, "staging")
    cfg = _config(data_dir, tmp_path, web=WebConfig(stream_key=_STAGING_KEY))
    assert cfg.indexer.db_path == data_dir / "library-staging.db"


def test_prod_unmarked_loads_as_today(tmp_path: Path) -> None:
    """Production with no marker loads, with the historical store names (the no-change proof)."""
    data_dir = _data_dir(tmp_path)
    cfg = _config(data_dir, tmp_path)
    assert cfg.indexer.db_path == data_dir / "library.db"
    assert cfg.acquire.db_path == data_dir / "acquire.db"
    assert cfg.web.stream_key == "personalscraper:events"
    assert not (data_dir / _MARKER).exists()


def test_a_marker_naming_no_environment_fails_naming_the_file(tmp_path: Path) -> None:
    """A marker holding a value that is not an environment fails the load, naming the file."""
    data_dir = _data_dir(tmp_path, "prd")
    with pytest.raises(ValidationError) as excinfo:
        _config(data_dir, tmp_path)
    message = str(excinfo.value)
    assert str(data_dir / _MARKER) in message
    assert "prd" in message
