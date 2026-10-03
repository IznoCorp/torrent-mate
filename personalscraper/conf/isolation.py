"""The isolation guard: a data directory names the environment that owns it.

A file ``.tm-environment`` in ``paths.data_dir`` holds one environment name. At config
load, a process whose environment differs from the marker refuses to start, so a
mistyped variable can never point production at a preprod data directory, nor the
reverse. A data directory with no marker is production's, as it always was: production
sets nothing and writes nothing. Every other environment must find its own marker and
keep every store it resolves inside that directory; ``staging`` must also publish on a
stream key of its own. The marker is written by hand, never by the code.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from personalscraper.conf.environment import Environment, current_environment

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

ENVIRONMENT_MARKER: Final[str] = ".tm-environment"
PROD_STREAM_KEY: Final[str] = "personalscraper:events"  # the WebConfig default, conf/models/web.py


class EnvironmentIsolationError(ValueError):
    """A process was pointed at another environment's data directory, or preprod shares prod's stream key."""


def read_marker(data_dir: Path) -> Environment | None:
    """Read the environment that owns ``data_dir``.

    Args:
        data_dir: The data directory.

    Returns:
        The environment named by ``data_dir/.tm-environment``; ``None`` when the file
        is absent (or ``data_dir`` is not a directory).

    Raises:
        EnvironmentIsolationError: The file names no Environment, or exists but cannot
            be read (a directory, no permission, not UTF-8) — fail closed, never untyped.
    """
    marker = data_dir / ENVIRONMENT_MARKER
    try:
        raw = marker.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, NotADirectoryError):
        # No marker: the data directory is prod's, as it was before the guard existed.
        return None
    except (OSError, UnicodeDecodeError) as exc:
        # The marker may name another environment: an unreadable one is never read as absent.
        raise EnvironmentIsolationError(f"{marker} cannot be read: {exc}") from exc
    try:
        return Environment(raw)
    except ValueError:
        allowed = ", ".join(repr(e.value) for e in Environment)
        raise EnvironmentIsolationError(
            f"{marker} holds {raw!r}, which is not an environment; expected one of {allowed}"
        ) from None


def _store_paths(config: Config) -> list[Path]:
    """List the store paths a config resolves (``Config._resolve_derived_paths``).

    Args:
        config: The configuration, its store paths already resolved.

    Returns:
        The library store, the acquire store and the trailers state file.
    """
    paths = [config.indexer.db_path, config.acquire.db_path, config.trailers.state_file]
    return [Path(p) for p in paths if p is not None]


def assert_isolated(config: Config, env: Environment | None = None) -> None:
    """Refuse a config whose data directory, stores or stream key belong to another environment.

    Args:
        config: The configuration, its store paths already resolved.
        env: The process's environment; ``None`` reads ``PERSONALSCRAPER_ENV``.

    Raises:
        EnvironmentIsolationError: The marker names another environment or cannot be
            read; the data directory is unmarked outside prod; a store path sits outside
            the data directory outside prod; or ``staging`` uses prod's stream key.
        EnvironmentSettingError: ``env`` is ``None`` and the variable is invalid.
    """
    env = env if env is not None else current_environment()
    data_dir = config.paths.data_dir
    owner = read_marker(data_dir)
    if owner is None:
        if env is not Environment.PROD:
            raise EnvironmentIsolationError(
                f"this process runs in {env.value!r} but {data_dir} has no {ENVIRONMENT_MARKER}; "
                f"only prod runs on an unmarked data directory"
            )
    elif owner is not env:
        raise EnvironmentIsolationError(
            f"this process runs in {env.value!r} but {data_dir / ENVIRONMENT_MARKER} names {owner.value!r}"
        )
    if env is not Environment.PROD:
        # A marked data directory proves nothing if a store path points into another one.
        root = data_dir.resolve()
        for path in _store_paths(config):
            if not path.resolve().is_relative_to(root):
                raise EnvironmentIsolationError(
                    f"this process runs in {env.value!r} but its store {path} lies outside {data_dir}; "
                    f"outside prod every store lives in the environment's own data directory"
                )
    if env is Environment.STAGING and config.web.stream_key == PROD_STREAM_KEY:
        raise EnvironmentIsolationError(
            f"staging must set web.stream_key to a key of its own, not prod's {PROD_STREAM_KEY!r}"
        )
