"""The environment a process runs in, and the store file names it derives.

One setting, ``PERSONALSCRAPER_ENV``, names the environment (``dev``, ``staging`` or
``prod``). Each store file (library, acquire, app) takes its name from it; ``prod`` keeps
the historical file names. The variable must be set: absent or empty is refused, never read
as prod, so a process that names no environment cannot open prod's stores by default — prod
(its PM2 apps) sets ``prod``, and a dev command that wants prod's stores asks for them by
setting ``prod`` itself. The names alone do not isolate: every
environment but prod needs a ``data_dir`` of its own, marked with its name, and the
isolation guard (``conf/isolation.py``) refuses one that is unmarked or marked for
another environment.
"""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path
from typing import Final

ENV_VAR: Final[str] = "PERSONALSCRAPER_ENV"


class Environment(StrEnum):
    """The environments a process can run in."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class StoreName(StrEnum):
    """The SQLite stores that live in ``paths.data_dir``."""

    LIBRARY = "library"
    ACQUIRE = "acquire"
    APP = "app"


class EnvironmentSettingError(ValueError):
    """PERSONALSCRAPER_ENV is unset, or holds a value that is not an Environment."""


def current_environment() -> Environment:
    """Read the environment from ``PERSONALSCRAPER_ENV``.

    Returns:
        The named environment.

    Raises:
        EnvironmentSettingError: The variable is absent or empty (fail closed: it never
            defaults to prod), or holds a value that is not an Environment.
    """
    allowed = ", ".join(repr(e.value) for e in Environment)
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        raise EnvironmentSettingError(
            f"{ENV_VAR} is not set; set it to one of {allowed} (prod's stores open only under an explicit 'prod')"
        )
    try:
        return Environment(raw)
    except ValueError:
        raise EnvironmentSettingError(f"{ENV_VAR}={raw!r} is not an environment; expected one of {allowed}") from None


def is_sandboxed(env: Environment | None = None) -> bool:
    """Tell whether an environment is a sandbox, held off prod's folders and data.

    Every environment but prod is one: its writes stay inside its own marked roots
    (``conf/sandbox_guard.py``), it publishes on a stream key of its own and never
    tells prod's Plex.

    Args:
        env: The environment; ``None`` reads ``PERSONALSCRAPER_ENV``.

    Returns:
        ``True`` for every environment but prod.

    Raises:
        EnvironmentSettingError: ``env`` is ``None`` and the variable is invalid.
    """
    return (env if env is not None else current_environment()) is not Environment.PROD


def store_filename(store: StoreName, env: Environment) -> str:
    """Name a store's file in an environment.

    Args:
        store: The store.
        env: The environment; ``prod`` keeps the bare historical name.

    Returns:
        ``<store>.db`` for prod, ``<store>-<env>.db`` otherwise.
    """
    if env is Environment.PROD:
        return f"{store.value}.db"
    return f"{store.value}-{env.value}.db"


def store_path(data_dir: Path, store: StoreName, env: Environment | None = None) -> Path:
    """Locate a store's file in ``data_dir``.

    Args:
        data_dir: The data directory.
        store: The store.
        env: The environment; ``None`` reads ``PERSONALSCRAPER_ENV``.

    Returns:
        ``data_dir`` joined with the store's file name.

    Raises:
        EnvironmentSettingError: ``env`` is ``None`` and the variable is invalid.
    """
    return data_dir / store_filename(store, env if env is not None else current_environment())
