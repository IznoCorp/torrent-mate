#!/usr/bin/env python3
"""Seed the dev sandbox: copy a chosen set of prod titles into the dev roots, then index them.

The dev environment tm-design serves needs a starting library of real media folders. This
tool copies the titles a manifest names from prod's disks into the dev sandbox roots, one
title at a time, then runs the engine's own indexing so the dev stores describe them.

Manifest (default ``~/.torrentmate/dev-sandbox.json5``, machine data outside the repo)::

    {titles: [{provider: "tmdb", id: "27205", disk: "disk_3"}, ...]}

``provider`` is ``tmdb`` or ``tvdb``; ``disk`` is the id of a disk in the dev config, which
receives the title under its category folder.

Each title's folder is found in prod's index (``library.db``), opened read-only
(``mode=ro``); a title the index does not know, or knows in more than one folder, is
reported and nothing is copied. The tool refuses to run:

- unless ``PERSONALSCRAPER_ENV`` is ``dev``;
- when a target is outside the dev sandbox's marked, mounted roots (the sandbox guard);
- when a dev disk root has a ``medias`` child (a volume root, the parent of prod's media);
- when the titles weigh more than ``--max-gb`` (sizes are read with ``stat`` only).

The copy is ``rsync -a --ignore-existing``: a file already in the sandbox is never
overwritten, prod's folders are only read, and nothing is ever deleted. A re-run restores
what a dev operation removed. ``personalscraper library-index`` and
``personalscraper library-catalogue-refresh`` then run as children with the same
environment.

Usage:
    python scripts/dev-sandbox-seed.py --dry-run              # print the plan and its total
    python scripts/dev-sandbox-seed.py                        # copy, then index
    python scripts/dev-sandbox-seed.py --manifest PATH --prod-index PATH --max-gb 120

Exit codes:
    0 — the plan was printed (dry run) or copied and indexed.
    1 — refused, or a title could not be resolved; nothing was copied.
    2 — usage error (unreadable manifest, config or index), or a copy or child failed.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import json5

from personalscraper.conf.environment import (
    Environment,
    EnvironmentSettingError,
    StoreName,
    current_environment,
    store_filename,
)
from personalscraper.conf.loader import load_config
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.resolver import folder_for
from personalscraper.conf.sandbox_guard import SandboxGuardError, assert_within_sandbox

DEFAULT_MANIFEST = Path("~/.torrentmate/dev-sandbox.json5")
#: Prod's config overlay, read only for ``paths.data_dir`` when ``--prod-index`` is not given.
PROD_PATHS_CONFIG = Path("~/.torrentmate/config/paths.json5")
DEFAULT_MAX_GB = 120.0
#: Decimal gigabytes, as disk capacities are sold and ``df -H`` prints them.
BYTES_PER_GB = 10**9
PROVIDERS = ("tmdb", "tvdb")
#: The folder that holds prod's media on each volume; a dev root never holds one.
PROD_MEDIA_FOLDER = "medias"

#: Live files of an item matched by provider id, through a movie release or an episode release.
#: ``{provider}`` is one of :data:`PROVIDERS`, never user text.
_TITLE_FILES_SQL = """
    SELECT m.id, m.category_id, d.mount_path, p.rel_path
      FROM media_item m
      JOIN media_release r ON r.item_id = m.id
      JOIN media_file f ON f.release_id = r.id
      JOIN path p ON p.id = f.path_id
      JOIN disk d ON d.id = p.disk_id
     WHERE json_extract(m.external_ids_json, '$.{provider}.series_id') = CAST(? AS TEXT)
       AND f.deleted_at IS NULL
    UNION
    SELECT m.id, m.category_id, d.mount_path, p.rel_path
      FROM media_item m
      JOIN season s ON s.item_id = m.id
      JOIN episode e ON e.season_id = s.id
      JOIN media_release r ON r.episode_id = e.id
      JOIN media_file f ON f.release_id = r.id
      JOIN path p ON p.id = f.path_id
      JOIN disk d ON d.id = p.disk_id
     WHERE json_extract(m.external_ids_json, '$.{provider}.series_id') = CAST(? AS TEXT)
       AND f.deleted_at IS NULL
"""


class SeedRefused(Exception):
    """The seed would leave the sandbox, break a cap, or run outside dev: nothing is copied."""


class UsageError(Exception):
    """The manifest, the config or the prod index cannot be read as given."""


@dataclass(frozen=True)
class Title:
    """One manifest entry.

    Attributes:
        provider: ``tmdb`` or ``tvdb``.
        id: The provider's series or movie id, as text.
        disk: The id of the dev config disk that receives the title.
    """

    provider: str
    id: str
    disk: str

    def label(self) -> str:
        """Name the title as the manifest does, for the report."""
        return f"{self.provider} {self.id}"


@dataclass(frozen=True)
class Copy:
    """One title's planned copy.

    Attributes:
        title: The manifest entry.
        source: The title's folder on prod's disk (only ever read).
        target: The folder it lands in, inside a dev root.
        disk: The dev config disk holding *target*.
        size_bytes: The bytes under *source*, read with ``stat``.
    """

    title: Title
    source: Path
    target: Path
    disk: DiskConfig
    size_bytes: int


def load_manifest(path: Path) -> list[Title]:
    """Read and check the manifest.

    Args:
        path: The manifest file.

    Returns:
        The titles, in manifest order.

    Raises:
        UsageError: The file is unreadable, or an entry is not ``{provider, id, disk}``
            with a known provider.
    """
    try:
        data = json5.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read the manifest {path}: {exc}") from exc
    entries = data.get("titles") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise UsageError(f"the manifest {path} has no 'titles' list")
    titles = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"provider", "id", "disk"}:
            raise UsageError(f"titles[{index}] must hold exactly provider, id and disk")
        if entry["provider"] not in PROVIDERS:
            raise UsageError(f"titles[{index}].provider must be one of {', '.join(PROVIDERS)}")
        titles.append(Title(provider=entry["provider"], id=str(entry["id"]), disk=str(entry["disk"])))
    return titles


def default_prod_index() -> Path:
    """Locate prod's ``library.db`` from prod's ``paths.json5``.

    Returns:
        ``<paths.data_dir>/library.db`` as prod's config names it.

    Raises:
        UsageError: The file is unreadable or its ``data_dir`` is missing or relative.
    """
    config_file = PROD_PATHS_CONFIG.expanduser()
    try:
        data = json5.loads(config_file.read_text(encoding="utf-8"))
        data_dir = Path(data["paths"]["data_dir"]).expanduser()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise UsageError(f"cannot read paths.data_dir from {config_file}: {exc}; pass --prod-index") from exc
    if not data_dir.is_absolute():
        raise UsageError(f"{config_file} names a relative data_dir ({data_dir}); pass --prod-index")
    return data_dir / store_filename(StoreName.LIBRARY, Environment.PROD)


def open_prod_index(path: Path) -> sqlite3.Connection:
    """Open prod's index read-only: SQLite itself refuses any write on this connection.

    Args:
        path: Prod's ``library.db``.

    Returns:
        The read-only connection.

    Raises:
        UsageError: The file is absent or is not a readable index.
    """
    try:
        conn = sqlite3.connect(f"{path.expanduser().resolve().as_uri()}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM media_item LIMIT 1")
    except sqlite3.Error as exc:
        raise UsageError(f"cannot open the prod index {path} read-only: {exc}") from exc
    return conn


def find_title_folder(conn: sqlite3.Connection, title: Title) -> tuple[Path, str] | str:
    """Find the one folder on prod's disks that holds a title's live files.

    The folder is ``<disk scan root>/<category folder>/<title folder>``: the first two
    components of the files' indexed directory under the disk's scan root.

    Args:
        conn: Prod's index, read-only.
        title: The manifest entry.

    Returns:
        ``(folder, category_id)`` when the index names exactly one existing folder;
        otherwise the reason it cannot, as text. Nothing is guessed.
    """
    rows = conn.execute(_TITLE_FILES_SQL.format(provider=title.provider), (title.id, title.id)).fetchall()
    if not rows:
        return "not in the prod index (no item with live files)"
    if len({row[0] for row in rows}) > 1:
        return "matches more than one item in the prod index"
    folders = set()
    for _item_id, _category, mount_path, rel_path in rows:
        parts = Path(rel_path).parts
        if mount_path is None:
            return "its disk is not mounted, according to the prod index"
        if len(parts) < 2:
            return f"its files sit outside a title folder ({rel_path!r})"
        folders.add(Path(mount_path, *parts[:2]))
    if len(folders) > 1:
        return f"its files span {len(folders)} folders: {', '.join(sorted(map(str, folders)))}"
    folder = folders.pop()
    if not folder.is_dir():
        return f"its folder {folder} does not exist"
    return folder, rows[0][1]


def folder_size(folder: Path) -> int:
    """Sum the sizes under a folder with ``stat`` only, never reading a file nor following a link.

    Args:
        folder: The folder.

    Returns:
        The total, in bytes.
    """
    total = 0
    for dirpath, _dirnames, filenames in os.walk(folder):
        for name in filenames:
            total += os.lstat(os.path.join(dirpath, name)).st_size
    return total


def check_target(config: Config, disk: DiskConfig, target: Path) -> None:
    """Refuse a target the sandbox does not own.

    Args:
        config: The dev config, naming the sandbox roots.
        disk: The dev disk receiving the target.
        target: The folder about to be written.

    Raises:
        SeedRefused: The disk root holds a ``medias`` child, or the target is outside the
            dev sandbox's marked, mounted roots.
    """
    if (disk.path / PROD_MEDIA_FOLDER).exists():
        raise SeedRefused(
            f"disk {disk.id} root {disk.path} has a '{PROD_MEDIA_FOLDER}' child: it is a volume root, not a sandbox root"
        )
    try:
        assert_within_sandbox(config, target, Environment.DEV)
    except SandboxGuardError as exc:
        raise SeedRefused(str(exc)) from exc


def plan(config: Config, conn: sqlite3.Connection, titles: list[Title]) -> list[Copy]:
    """Resolve and check every title before anything is copied.

    Args:
        config: The dev config.
        conn: Prod's index, read-only.
        titles: The manifest's titles.

    Returns:
        One copy per title, in manifest order.

    Raises:
        SeedRefused: A title cannot be resolved (each one is named), or a target fails
            :func:`check_target`.
        UsageError: A title names a disk the dev config does not have.
    """
    disks = {disk.id: disk for disk in config.disks}
    unresolved = []
    copies = []
    for title in titles:
        disk = disks.get(title.disk)
        if disk is None:
            raise UsageError(f"{title.label()}: the dev config has no disk {title.disk!r}")
        found = find_title_folder(conn, title)
        if isinstance(found, str):
            unresolved.append(f"{title.label()}: {found}")
            continue
        source, category_id = found
        target = folder_for(config, disk, category_id) / source.name
        check_target(config, disk, target)
        copies.append(Copy(title=title, source=source, target=target, disk=disk, size_bytes=folder_size(source)))
    if unresolved:
        raise SeedRefused("titles not resolved, nothing copied:\n  " + "\n  ".join(unresolved))
    return copies


def print_plan(copies: list[Copy]) -> int:
    """Print the plan and its total.

    Args:
        copies: The planned copies.

    Returns:
        The total size, in bytes.
    """
    total = sum(copy.size_bytes for copy in copies)
    for copy in copies:
        print(f"{copy.title.label():16} {copy.size_bytes / BYTES_PER_GB:8.2f} GB  {copy.source}  ->  {copy.target}")
    print(f"Total: {total} bytes ({total / BYTES_PER_GB:.2f} GB) in {len(copies)} title(s).")
    return total


def _run_child(cmd: list[str]) -> None:
    """Run one command in the foreground, with this process's environment.

    Args:
        cmd: The command.

    Raises:
        subprocess.CalledProcessError: The command failed.
    """
    subprocess.run(cmd, check=True)


def copy_title(config: Config, copy: Copy) -> None:
    """Copy one title into the sandbox, never overwriting nor deleting.

    The target is judged again right before the copy: a disk may have dropped off the
    bus since the plan.

    Args:
        config: The dev config.
        copy: The planned copy.

    Raises:
        SeedRefused: The target no longer passes :func:`check_target`.
        subprocess.CalledProcessError: rsync failed.
    """
    check_target(config, copy.disk, copy.target)
    copy.target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", "--ignore-existing", f"{copy.source}/", f"{copy.target}/"], check=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: The arguments, ``sys.argv[1:]`` when ``None``.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Copy a chosen set of prod titles into the dev sandbox, then index them."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help=f"default: {DEFAULT_MANIFEST}")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and its total, write nothing")
    parser.add_argument(
        "--max-gb", type=float, default=DEFAULT_MAX_GB, help=f"refuse above this total (default {DEFAULT_MAX_GB:g})"
    )
    parser.add_argument(
        "--prod-index",
        type=Path,
        default=None,
        help=f"prod's library.db (default: paths.data_dir in {PROD_PATHS_CONFIG})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Plan, check and copy the manifest's titles, then index the sandbox.

    Args:
        argv: The arguments, ``sys.argv[1:]`` when ``None``.

    Returns:
        The exit code (see the module docstring).
    """
    args = _parse_args(argv)
    try:
        env = current_environment()
    except EnvironmentSettingError as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1
    if env is not Environment.DEV:
        print(f"Refused: PERSONALSCRAPER_ENV is {env.value!r}; the seed runs only in 'dev'.", file=sys.stderr)
        return 1

    try:
        titles = load_manifest(args.manifest.expanduser())
        config = load_config()
        conn = open_prod_index(args.prod_index if args.prod_index is not None else default_prod_index())
        try:
            copies = plan(config, conn, titles)
        finally:
            conn.close()
    except SeedRefused as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    total = print_plan(copies)
    if total > args.max_gb * BYTES_PER_GB:
        print(f"Refused: {total} bytes is above --max-gb {args.max_gb:g}; nothing copied.", file=sys.stderr)
        return 1
    if args.dry_run:
        print("Dry run: nothing copied.")
        return 0

    try:
        for copy in copies:
            print(f"Copying {copy.title.label()}: {copy.source} -> {copy.target}", flush=True)
            copy_title(config, copy)
        for command in ("library-index", "library-catalogue-refresh"):
            print(f"Running personalscraper {command}", flush=True)
            _run_child([sys.executable, "-m", "personalscraper", command])
    except SeedRefused as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Error: {' '.join(map(str, exc.cmd))} exited {exc.returncode}", file=sys.stderr)
        return 2
    print(f"[OK] {len(copies)} title(s) seeded and indexed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
