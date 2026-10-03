"""Tests for the ``PERSONALSCRAPER_ENV`` setting that names the stores."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from personalscraper.conf import ids as CID
from personalscraper.conf.environment import (
    ENV_VAR,
    Environment,
    EnvironmentSettingError,
    StoreName,
    current_environment,
    store_filename,
    store_path,
)
from personalscraper.conf.isolation import ENVIRONMENT_MARKER
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.indexer import IndexerConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.models.web import WebConfig
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _config(tmp_path: Path, **extra: object) -> Config:
    """Build the minimal valid Config, with extra top-level fields.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        **extra: Extra ``Config`` fields (e.g. an explicit ``acquire``).

    Returns:
        A loaded ``Config``.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "complete", staging_dir=tmp_path / "staging", data_dir=tmp_path
        ),
        disks=[DiskConfig(id="disk_a", path=tmp_path / "disk_a", categories=list(CID.BUILTIN_CATEGORY_IDS))],
        staging_dirs=CANONICAL_STAGING_DIRS,
        **extra,  # type: ignore[arg-type]
    )


def _mark(tmp_path: Path, env: str) -> None:
    """Mark ``tmp_path`` (the configs' data directory) as owned by ``env``.

    Args:
        tmp_path: Pytest tmp_path fixture value.
        env: The environment name written into the marker.
    """
    (tmp_path / ENVIRONMENT_MARKER).write_text(env, encoding="utf-8")


_STAGING_WEB = WebConfig(stream_key="personalscraper:events:staging")


def test_staging_names_the_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``staging`` suffixes both derived store names."""
    monkeypatch.setenv(ENV_VAR, "staging")
    _mark(tmp_path, "staging")
    cfg = _config(tmp_path, web=_STAGING_WEB)
    assert cfg.acquire.db_path is not None and cfg.acquire.db_path.name == "acquire-staging.db"
    assert cfg.indexer.db_path is not None and cfg.indexer.db_path.name == "library-staging.db"


def test_dev_names_the_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``dev`` suffixes both derived store names."""
    monkeypatch.setenv(ENV_VAR, "dev")
    _mark(tmp_path, "dev")
    cfg = _config(tmp_path)
    assert cfg.acquire.db_path is not None and cfg.acquire.db_path.name == "acquire-dev.db"
    assert cfg.indexer.db_path is not None and cfg.indexer.db_path.name == "library-dev.db"


def test_unset_keeps_the_production_names(tmp_path: Path) -> None:
    """Absent variable means prod: the historical file names, unchanged."""
    cfg = _config(tmp_path)
    assert cfg.acquire.db_path is not None and cfg.acquire.db_path.name == "acquire.db"
    assert cfg.indexer.db_path is not None and cfg.indexer.db_path.name == "library.db"


def test_unknown_value_fails_naming_variable_and_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A value that is not an Environment fails the load, naming the variable and the three values."""
    monkeypatch.setenv(ENV_VAR, "prd")
    with pytest.raises(ValidationError) as excinfo:
        _config(tmp_path)
    message = str(excinfo.value)
    assert ENV_VAR in message
    for value in ("dev", "staging", "prod"):
        assert value in message


def test_current_environment_raises_the_setting_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """``current_environment`` raises ``EnvironmentSettingError`` on an unknown value."""
    monkeypatch.setenv(ENV_VAR, "prd")
    with pytest.raises(EnvironmentSettingError):
        current_environment()


def test_explicit_path_wins_over_the_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit ``db_path`` is never renamed by the variable."""
    monkeypatch.setenv(ENV_VAR, "staging")
    acquire = tmp_path / "acquire.db"
    indexer = tmp_path / "library.db"
    _mark(tmp_path, "staging")
    cfg = _config(
        tmp_path, acquire=AcquireConfig(db_path=acquire), indexer=IndexerConfig(db_path=indexer), web=_STAGING_WEB
    )
    assert cfg.acquire.db_path == acquire
    assert cfg.indexer.db_path == indexer


_EXPECTED = {
    (StoreName.LIBRARY, Environment.PROD): "library.db",
    (StoreName.LIBRARY, Environment.STAGING): "library-staging.db",
    (StoreName.LIBRARY, Environment.DEV): "library-dev.db",
    (StoreName.ACQUIRE, Environment.PROD): "acquire.db",
    (StoreName.ACQUIRE, Environment.STAGING): "acquire-staging.db",
    (StoreName.ACQUIRE, Environment.DEV): "acquire-dev.db",
    (StoreName.APP, Environment.PROD): "app.db",
    (StoreName.APP, Environment.STAGING): "app-staging.db",
    (StoreName.APP, Environment.DEV): "app-dev.db",
}


@pytest.mark.parametrize(("store", "env"), list(_EXPECTED))
def test_store_filename_table(store: StoreName, env: Environment) -> None:
    """3 stores x 3 environments."""
    assert store_filename(store, env) == _EXPECTED[(store, env)]


def test_store_path_joins_data_dir_and_reads_the_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``store_path`` defaults to the current environment and honours an explicit one."""
    assert store_path(tmp_path, StoreName.APP) == tmp_path / "app.db"
    monkeypatch.setenv(ENV_VAR, "dev")
    assert store_path(tmp_path, StoreName.APP) == tmp_path / "app-dev.db"
    assert store_path(tmp_path, StoreName.APP, Environment.STAGING) == tmp_path / "app-staging.db"
