"""Tests for the isolation guard: a data directory names its environment.

A ``.tm-environment`` file in ``paths.data_dir`` names the environment that owns it.
A process of another environment refuses to load its config; ``staging`` refuses an
unmarked data directory and the production stream key. Production with no marker
loads exactly as before.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from personalscraper.conf import ids as CID
from personalscraper.conf.environment import Environment
from personalscraper.conf.isolation import (
    ENVIRONMENT_MARKER,
    PROD_STREAM_KEY,
    EnvironmentIsolationError,
    assert_isolated,
    read_marker,
)
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.indexer import IndexerConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.trailers import TrailersConfig
from personalscraper.conf.models.web import WebConfig
from tests.fixtures.config import CANONICAL_STAGING_DIRS

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
        (data_dir / ENVIRONMENT_MARKER).write_text(marker, encoding="utf-8")
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
    cause = excinfo.value.errors()[0]["ctx"]["error"]
    assert isinstance(cause, EnvironmentIsolationError)
    message = str(cause)
    assert str(data_dir / ENVIRONMENT_MARKER) in message
    assert "runs in 'prod'" in message
    assert "names 'staging'" in message


def test_staging_refuses_an_unmarked_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``staging`` never runs on a data directory nobody marked as its own."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    data_dir = _data_dir(tmp_path)
    with pytest.raises(ValidationError) as excinfo:
        _config(data_dir, tmp_path, web=WebConfig(stream_key=_STAGING_KEY))
    assert ENVIRONMENT_MARKER in str(excinfo.value)


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
    assert cfg.web.stream_key == PROD_STREAM_KEY
    assert not (data_dir / ENVIRONMENT_MARKER).exists()


def test_a_marker_naming_no_environment_fails_naming_the_file(tmp_path: Path) -> None:
    """A marker holding a value that is not an environment fails the load, naming the file."""
    data_dir = _data_dir(tmp_path, "prd")
    with pytest.raises(ValidationError) as excinfo:
        _config(data_dir, tmp_path)
    message = str(excinfo.value)
    assert str(data_dir / ENVIRONMENT_MARKER) in message
    assert "prd" in message


def test_prod_stream_key_is_the_web_default() -> None:
    """The key ``staging`` may not use is the one production gets by default."""
    assert WebConfig().stream_key == PROD_STREAM_KEY


@pytest.mark.parametrize("env", ["dev", "staging", "prod"])
def test_read_marker_names_each_environment(tmp_path: Path, env: str) -> None:
    """``read_marker`` reads each environment's name, surrounding whitespace ignored."""
    assert read_marker(_data_dir(tmp_path, f" {env}\n")) is Environment(env)


def test_read_marker_absent_is_none(tmp_path: Path) -> None:
    """No marker, and no data directory at all, both read as ``None``."""
    assert read_marker(_data_dir(tmp_path)) is None
    assert read_marker(tmp_path / "missing") is None


@pytest.mark.parametrize("raw", ["", "prd", "STAGING"])
def test_read_marker_refuses_an_unknown_name(tmp_path: Path, raw: str) -> None:
    """An empty marker or one naming no environment raises ``EnvironmentIsolationError``."""
    with pytest.raises(EnvironmentIsolationError):
        read_marker(_data_dir(tmp_path, raw))


def test_assert_isolated_takes_an_explicit_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit ``env`` wins over the variable: with ``dev`` set, an explicit PROD accepts an unmarked directory."""
    cfg = _config(_data_dir(tmp_path), tmp_path)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    with pytest.raises(EnvironmentIsolationError):
        assert_isolated(cfg)
    assert_isolated(cfg, Environment.PROD)


def test_assert_isolated_explicit_staging_refuses_an_unmarked_data_dir(tmp_path: Path) -> None:
    """An explicit STAGING, the variable unset, refuses the unmarked directory a prod load accepted."""
    cfg = _config(_data_dir(tmp_path), tmp_path)
    with pytest.raises(EnvironmentIsolationError, match=ENVIRONMENT_MARKER):
        assert_isolated(cfg, Environment.STAGING)


def test_dev_loads_on_its_own_marker_with_the_default_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The stream-key rule is ``staging``'s alone: ``dev`` on a ``dev`` marker loads with the default key."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    data_dir = _data_dir(tmp_path, "dev")
    assert _config(data_dir, tmp_path).indexer.db_path == data_dir / "library-dev.db"


def test_staging_refuses_a_prod_marked_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The reverse direction: ``staging`` refuses a data directory marked ``prod``."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    data_dir = _data_dir(tmp_path, "prod")
    with pytest.raises(ValidationError):
        _config(data_dir, tmp_path, web=WebConfig(stream_key=_STAGING_KEY))


def test_a_marker_that_is_a_directory_fails_naming_the_file(tmp_path: Path) -> None:
    """A marker path that is a directory cannot be read: the load fails typed, naming the file."""
    data_dir = _data_dir(tmp_path)
    (data_dir / ENVIRONMENT_MARKER).mkdir()
    with pytest.raises(EnvironmentIsolationError, match=str(data_dir / ENVIRONMENT_MARKER)):
        read_marker(data_dir)
    with pytest.raises(ValidationError):
        _config(data_dir, tmp_path)


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="root reads a mode-000 file")
def test_an_unreadable_marker_fails_naming_the_file(tmp_path: Path) -> None:
    """A marker with mode 000 fails typed, naming the file (fail closed, never untyped)."""
    data_dir = _data_dir(tmp_path, "prod")
    marker = data_dir / ENVIRONMENT_MARKER
    marker.chmod(0)
    try:
        with pytest.raises(EnvironmentIsolationError, match=str(marker)):
            read_marker(data_dir)
        with pytest.raises(ValidationError):
            _config(data_dir, tmp_path)
    finally:
        marker.chmod(0o644)


def test_a_marker_not_in_utf8_fails_naming_the_file(tmp_path: Path) -> None:
    """A marker whose bytes are not UTF-8 fails typed, naming the file."""
    data_dir = _data_dir(tmp_path)
    marker = data_dir / ENVIRONMENT_MARKER
    marker.write_bytes(b"\xffprod")
    with pytest.raises(EnvironmentIsolationError, match=str(marker)):
        read_marker(data_dir)
    with pytest.raises(ValidationError):
        _config(data_dir, tmp_path)


def test_a_data_dir_that_is_a_file_reads_as_unmarked_and_loads_under_prod(tmp_path: Path) -> None:
    """``data_dir`` naming a file reads as no marker (NotADirectoryError), so prod loads as before."""
    data_file = tmp_path / "data"
    data_file.write_text("", encoding="utf-8")
    assert read_marker(data_file) is None
    cfg = _config(data_file, tmp_path)
    assert cfg.indexer.db_path == data_file / "library.db"


def test_staging_refuses_a_store_outside_its_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Under staging, a store path outside the marked data directory is refused, naming the path."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
    data_dir = _data_dir(tmp_path, "staging")
    elsewhere = tmp_path / "prod-data" / "library.db"
    elsewhere.parent.mkdir()
    with pytest.raises(ValidationError) as excinfo:
        _config(
            data_dir,
            tmp_path,
            web=WebConfig(stream_key=_STAGING_KEY),
            indexer=IndexerConfig(db_path=elsewhere),
        )
    cause = excinfo.value.errors()[0]["ctx"]["error"]
    assert isinstance(cause, EnvironmentIsolationError)
    assert str(elsewhere) in str(cause)


@pytest.mark.parametrize("field", ["acquire", "trailers"])
def test_dev_refuses_each_store_outside_its_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    """The rule holds for every resolved store, and for every environment but prod."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    data_dir = _data_dir(tmp_path, "dev")
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    extra = (
        {"acquire": AcquireConfig(db_path=outside / "acquire.db")}
        if field == "acquire"
        else {"trailers": TrailersConfig(state_file=str(outside / "trailers_state.json"))}
    )
    with pytest.raises(ValidationError, match="elsewhere"):
        _config(data_dir, tmp_path, **extra)


def test_prod_loads_with_a_store_outside_its_data_dir(tmp_path: Path) -> None:
    """Prod is unchanged: an explicit store path outside ``data_dir`` still loads."""
    data_dir = _data_dir(tmp_path)
    elsewhere = tmp_path / "elsewhere" / "library.db"
    elsewhere.parent.mkdir()
    cfg = _config(data_dir, tmp_path, indexer=IndexerConfig(db_path=elsewhere))
    assert cfg.indexer.db_path == elsewhere.resolve()
