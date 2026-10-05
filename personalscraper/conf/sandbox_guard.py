"""The preprod mount-point guard: preprod writes and purges only inside its own roots.

Preprod shares nothing with prod but the torrent client. Its disks are folders (siblings
of prod's ``medias``, never under them), each holding a marker file
:data:`PREPROD_ROOT_MARKER`. Under ``PERSONALSCRAPER_ENV=staging`` a write or purge must
land under the real path of one such root, and that root must be on a mounted volume and
hold its marker: a disk that dropped off the bus leaves an empty folder on the system
disk, and an unmarked folder is not one an operator declared as preprod's.

In every other environment the guard is a no-op by construction (the environment check
is the first thing :func:`assert_within_sandbox` does), so prod behaves as before.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from personalscraper.conf.environment import Environment, current_environment
from personalscraper.conf.models.config import Config
from personalscraper.core.sqlite._fs_probe import is_mounted

PREPROD_ROOT_MARKER: Final[str] = ".tm-preprod-root"


class SandboxGuardError(RuntimeError):
    """A preprod write or purge aimed outside preprod's own marked, mounted roots."""


def sandbox_roots(config: Config) -> tuple[Path, ...]:
    """List the roots a staging process may write under.

    Args:
        config: The loaded configuration.

    Returns:
        Every configured storage disk path, ``config.paths.staging_dir``, and the
        download root of each torrent client scope that sets one, in that order and
        without duplicates.
    """
    roots = [disk.path for disk in config.disks]
    roots.append(config.paths.staging_dir)
    roots.extend(entry.scope.download_root for entry in config.torrent.clients.values() if entry.scope is not None)
    return tuple(dict.fromkeys(roots))


def assert_sandbox_root(root: Path) -> None:
    """Raise unless *root* is on a mounted volume and holds the preprod marker.

    Args:
        root: A candidate preprod root.

    Raises:
        SandboxGuardError: The root is not on a mounted volume, or has no marker file
            of its own (a symlink named like the marker does not count).
    """
    if not is_mounted(root):
        raise SandboxGuardError(f"preprod root {root} is not on a mounted volume")
    marker = root / PREPROD_ROOT_MARKER
    if marker.is_symlink() or not marker.is_file():
        raise SandboxGuardError(f"preprod root {root} has no {PREPROD_ROOT_MARKER} marker")


def assert_within_sandbox(config: Config, path: Path, env: Environment | None = None) -> None:
    """Raise unless *path* is under one marked, mounted preprod root (``staging`` only).

    A no-op unless *env* (default :func:`current_environment`) is ``staging``. The
    real path of *path* is judged, so a symlink inside a root that points out of it is
    refused.

    Args:
        config: The loaded configuration, naming the roots.
        path: The path about to be written to or purged.
        env: The environment to judge for; the process's own when ``None``.

    Raises:
        SandboxGuardError: Under ``staging``, *path* is outside every root, or the root
            holding it fails :func:`assert_sandbox_root`.
    """
    if (env if env is not None else current_environment()) is not Environment.STAGING:
        return
    real = Path(os.path.realpath(path))
    for root in sandbox_roots(config):
        real_root = Path(os.path.realpath(root))
        if real == real_root or real.is_relative_to(real_root):
            assert_sandbox_root(real_root)
            return
    raise SandboxGuardError(f"{path} is outside every preprod root")


def assert_all_within_sandbox(config: Config, *paths: Path, env: Environment | None = None) -> None:
    """Raise unless every one of *paths* is under a marked, mounted preprod root (``staging`` only).

    The step-level form of :func:`assert_within_sandbox`: a pipeline step names the
    directories it is about to write to or purge, once, before it touches any of them.

    Args:
        config: The loaded configuration, naming the roots.
        *paths: The directories (or files) the caller is about to write to or purge.
        env: The environment to judge for; the process's own when ``None``.

    Raises:
        SandboxGuardError: Under ``staging``, any of *paths* fails
            :func:`assert_within_sandbox`. A no-op in every other environment.
    """
    for path in paths:
        assert_within_sandbox(config, path, env)
