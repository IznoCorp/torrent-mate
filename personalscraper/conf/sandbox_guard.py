"""The sandbox mount-point guard: a sandbox writes and purges only inside its own roots.

A sandbox is every environment but prod (:func:`~personalscraper.conf.environment.is_sandboxed`):
preprod (``staging``) and the dev environment tm-design serves. A sandbox shares nothing
with prod but the torrent client. Its disks are folders (siblings of prod's ``medias``,
never under them), each holding the sandbox's own marker file (:data:`ROOT_MARKERS`). In a
sandbox a write or purge must land under the real path of one such root, and that root must
be on a mounted volume and hold its marker: a disk that dropped off the bus leaves an empty
folder on the system disk, and an unmarked folder is not one an operator declared as that
sandbox's. Each sandbox has its own marker, so a dev process refuses a preprod root and a
preprod process refuses a dev root.

In prod the guard is a no-op by construction (the environment check is the first thing
:func:`assert_within_sandbox` does), so prod behaves as before.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

from personalscraper.conf.environment import Environment, current_environment, is_sandboxed
from personalscraper.conf.models.config import Config
from personalscraper.core.sqlite._fs_probe import is_mounted

ROOT_MARKERS: Final[Mapping[Environment, str]] = MappingProxyType(
    {Environment.STAGING: ".tm-preprod-root", Environment.DEV: ".tm-dev-root"}
)


class SandboxGuardError(RuntimeError):
    """A sandbox write or purge aimed outside the sandbox's own marked, mounted roots."""


def root_marker(env: Environment) -> str:
    """Name the marker file that declares a folder one of *env*'s roots.

    Args:
        env: A sandboxed environment.

    Returns:
        The marker's file name.

    Raises:
        SandboxGuardError: *env* is prod, which has no sandbox roots.
    """
    marker = ROOT_MARKERS.get(env)
    if marker is None:
        raise SandboxGuardError(f"{env.value!r} is not a sandbox: it has no root marker")
    return marker


def sandbox_roots(config: Config) -> tuple[Path, ...]:
    """List the roots a sandboxed process may write under.

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


def assert_sandbox_root(root: Path, env: Environment | None = None) -> None:
    """Raise unless *root* is on a mounted volume and holds *env*'s marker.

    Args:
        root: A candidate sandbox root.
        env: The sandbox judging it; the process's own when ``None``.

    Raises:
        SandboxGuardError: The root is not on a mounted volume, or has no marker file
            of *env*'s own (a symlink named like the marker does not count), or *env*
            is prod.
    """
    marker_name = root_marker(env if env is not None else current_environment())
    if not is_mounted(root):
        raise SandboxGuardError(f"sandbox root {root} is not on a mounted volume")
    marker = root / marker_name
    if marker.is_symlink() or not marker.is_file():
        raise SandboxGuardError(f"sandbox root {root} has no {marker_name} marker")


def assert_within_sandbox(config: Config, path: Path, env: Environment | None = None) -> None:
    """Raise unless *path* is under one of the sandbox's marked, mounted roots (a no-op in prod).

    A no-op unless *env* (default :func:`current_environment`) is sandboxed. The real
    path of *path* is judged, so a symlink inside a root that points out of it is
    refused.

    Args:
        config: The loaded configuration, naming the roots.
        path: The path about to be written to or purged.
        env: The environment to judge for; the process's own when ``None``.

    Raises:
        SandboxGuardError: In a sandbox, *path* is outside every root, or the root
            holding it fails :func:`assert_sandbox_root`.
    """
    env = env if env is not None else current_environment()
    if not is_sandboxed(env):
        return
    real = Path(os.path.realpath(path))
    for root in sandbox_roots(config):
        real_root = Path(os.path.realpath(root))
        if real == real_root or real.is_relative_to(real_root):
            assert_sandbox_root(real_root, env)
            return
    raise SandboxGuardError(f"{path} is outside every sandbox root")


def assert_all_within_sandbox(config: Config, *paths: Path, env: Environment | None = None) -> None:
    """Raise unless every one of *paths* is under a marked, mounted sandbox root (a no-op in prod).

    The step-level form of :func:`assert_within_sandbox`: a pipeline step names the
    directories it is about to write to or purge, once, before it touches any of them.

    Args:
        config: The loaded configuration, naming the roots.
        *paths: The directories (or files) the caller is about to write to or purge.
        env: The environment to judge for; the process's own when ``None``.

    Raises:
        SandboxGuardError: In a sandbox, any of *paths* fails
            :func:`assert_within_sandbox`. A no-op in prod.
    """
    for path in paths:
        assert_within_sandbox(config, path, env)
