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
    is_sandboxed,
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
_DEV_WEB = WebConfig(stream_key="personalscraper:events:dev")


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
    cfg = _config(tmp_path, web=_DEV_WEB)
    assert cfg.acquire.db_path is not None and cfg.acquire.db_path.name == "acquire-dev.db"
    assert cfg.indexer.db_path is not None and cfg.indexer.db_path.name == "library-dev.db"


def test_explicit_prod_keeps_the_production_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``prod``, named explicitly, keeps the historical file names, unchanged."""
    monkeypatch.setenv(ENV_VAR, "prod")
    cfg = _config(tmp_path)
    assert cfg.acquire.db_path is not None and cfg.acquire.db_path.name == "acquire.db"
    assert cfg.indexer.db_path is not None and cfg.indexer.db_path.name == "library.db"


@pytest.mark.parametrize("unset", [None, "", "  "], ids=["absent", "empty", "blank"])
def test_an_unset_variable_is_refused(unset: str | None, monkeypatch: pytest.MonkeyPatch) -> None:
    """No environment named is no environment: ``current_environment`` fails instead of reading prod.

    Args:
        unset: The variable's value; ``None`` removes it.
        monkeypatch: Pytest monkeypatch fixture.
    """
    if unset is None:
        monkeypatch.delenv(ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(ENV_VAR, unset)
    with pytest.raises(EnvironmentSettingError) as excinfo:
        current_environment()
    message = str(excinfo.value)
    assert ENV_VAR in message
    for value in ("dev", "staging", "prod"):
        assert value in message


def test_an_unset_variable_fails_the_config_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A config load with no environment fails before any store path is derived."""
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(ValidationError) as excinfo:
        _config(tmp_path)
    assert ENV_VAR in str(excinfo.value)


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


@pytest.mark.parametrize(
    ("env", "sandboxed"), [(Environment.PROD, False), (Environment.STAGING, True), (Environment.DEV, True)]
)
def test_is_sandboxed_is_every_environment_but_prod(env: Environment, sandboxed: bool) -> None:
    """Prod is the one environment that is not a sandbox."""
    assert is_sandboxed(env) is sandboxed


def test_is_sandboxed_reads_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """``None`` reads ``PERSONALSCRAPER_ENV``: ``prod`` is not a sandbox, ``dev`` is one."""
    monkeypatch.setenv(ENV_VAR, "prod")
    assert is_sandboxed() is False
    monkeypatch.setenv(ENV_VAR, "dev")
    assert is_sandboxed() is True
