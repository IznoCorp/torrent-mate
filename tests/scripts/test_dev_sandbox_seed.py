"""Tests for scripts/dev-sandbox-seed.py: the guarded copy of chosen titles into the dev sandbox.

Every test builds its own world under ``tmp_path``: a prod disk (``prod/medias``) holding
real files, a fake prod index pointing at them, and a marked dev root. ``tmp_path`` is
never a mount point, so ``is_mounted`` is patched. The Config is built before the
environment is switched to ``dev`` (the suite pins ``prod``). The indexing children are
replaced by a recorder: they are the engine's commands, not this tool's.
"""

from __future__ import annotations

import importlib.util as _util
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf import sandbox_guard
from personalscraper.conf.environment import Environment
from personalscraper.conf.models.config import Config
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.conf.models.paths import PathConfig
from personalscraper.conf.resolver import folder_for
from tests.fixtures.config import CANONICAL_STAGING_DIRS

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "dev-sandbox-seed.py"
_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "personalscraper" / "indexer" / "migrations"

_spec = _util.spec_from_file_location("dev_sandbox_seed", SCRIPT)
assert _spec is not None and _spec.loader is not None, f"Could not load spec from {SCRIPT}"
seed = _util.module_from_spec(_spec)
sys.modules["dev_sandbox_seed"] = seed
_spec.loader.exec_module(seed)

DEV_MARKER = sandbox_guard.root_marker(Environment.DEV)
MOVIE_TMDB_ID = "27205"
MOVIE_FOLDER = "Inception (2010)"
MOVIE_BYTES = b"x" * 4096


def _make_index(tmp_path: Path, prod_disk: Path) -> Path:
    """Build a migrated fake prod index that knows one movie on *prod_disk*.

    Args:
        tmp_path: The test's scratch folder.
        prod_disk: The prod disk's scan root (the indexer's ``disk.mount_path``).

    Returns:
        The index's path.
    """
    from personalscraper.indexer.db import apply_migrations  # noqa: PLC0415

    db_path = tmp_path / "prod-data" / "library.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_migrations(conn, _MIGRATIONS_DIR)
    now = int(time.time())
    disk_id = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted) VALUES ('u3', 'Disk3', ?, ?, 1)",
        (str(prod_disk), now),
    ).lastrowid
    path_id = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)", (disk_id, f"movies/{MOVIE_FOLDER}")
    ).lastrowid
    item_id = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified, "
        "external_ids_json) VALUES ('movie', 'Inception', 'Inception', 'movies', ?, ?, ?)",
        (now, now, json.dumps({"tmdb": {"series_id": MOVIE_TMDB_ID, "episode_id": None}})),
    ).lastrowid
    release_id = conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (item_id,)).lastrowid
    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash, "
        "scan_generation, last_verified_at) VALUES (?, ?, 'Inception.mkv', ?, 0, 'h', 1, ?)",
        (release_id, path_id, len(MOVIE_BYTES), now),
    )
    conn.close()
    return db_path


class World:
    """One test's prod disk, fake prod index, dev root, Config and manifest."""

    def __init__(self, tmp_path: Path) -> None:
        """Lay the world out under *tmp_path*.

        Args:
            tmp_path: The test's scratch folder.
        """
        self.prod_disk = tmp_path / "prod" / "medias"
        self.source = self.prod_disk / "movies" / MOVIE_FOLDER
        self.source.mkdir(parents=True)
        (self.source / "Inception.mkv").write_bytes(MOVIE_BYTES)
        (self.source / "Inception.nfo").write_text("<movie/>", encoding="utf-8")
        self.index = _make_index(tmp_path, self.prod_disk)
        self.dev_root = tmp_path / "vol" / "tm-dev"
        self.dev_root.mkdir(parents=True)
        (self.dev_root / DEV_MARKER).write_text("", encoding="utf-8")
        data_dir = tmp_path / "data-dev"
        data_dir.mkdir()
        self.config = Config(
            paths=PathConfig(
                torrent_complete_dir=tmp_path / "complete", staging_dir=tmp_path / "staging", data_dir=data_dir
            ),
            disks=[DiskConfig(id="disk_3", path=self.dev_root, categories=list(CID.BUILTIN_CATEGORY_IDS))],
            staging_dirs=CANONICAL_STAGING_DIRS,
        )
        self.target = folder_for(self.config, self.config.disks[0], "movies") / MOVIE_FOLDER
        self.manifest = tmp_path / "dev-sandbox.json5"
        self.write_manifest([{"provider": "tmdb", "id": MOVIE_TMDB_ID, "disk": "disk_3"}])
        self.children: list[list[str]] = []

    def write_manifest(self, titles: list[dict[str, str]]) -> None:
        """Write the manifest naming *titles*.

        Args:
            titles: The manifest's ``titles`` entries.
        """
        self.manifest.write_text(json.dumps({"titles": titles}), encoding="utf-8")

    def run(self, *extra: str) -> int:
        """Run the tool's ``main`` against this world.

        Args:
            *extra: Arguments appended after ``--manifest`` and ``--prod-index``.

        Returns:
            The tool's exit code.
        """
        return seed.main(["--manifest", str(self.manifest), "--prod-index", str(self.index), *extra])

    def files_under(self, root: Path) -> list[Path]:
        """List every file under *root* but the marker.

        Args:
            root: The folder to list.

        Returns:
            The files, sorted.
        """
        return sorted(p for p in root.rglob("*") if p.is_file() and p.name != DEV_MARKER)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> World:
    """A mounted world in the dev environment, its Config loaded and its children recorded."""
    built = World(tmp_path)
    monkeypatch.setattr(sandbox_guard, "is_mounted", lambda path: True)
    monkeypatch.setattr(seed, "load_config", lambda: built.config)
    monkeypatch.setattr(seed, "_run_child", built.children.append)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    return built


def test_refused_outside_dev(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside dev (prod or preprod) the tool refuses before reading anything, and copies nothing."""
    for env in ("prod", "staging"):
        monkeypatch.setenv("PERSONALSCRAPER_ENV", env)
        assert world.run() != 0
    assert world.files_under(world.dev_root) == []
    assert world.children == []


def test_target_outside_the_roots_is_refused(world: World, tmp_path: Path) -> None:
    """A dev disk that is no marked sandbox root is refused: the guard judges every target."""
    (world.dev_root / DEV_MARKER).unlink()
    assert world.run() != 0
    assert world.files_under(world.dev_root) == []
    assert world.children == []


def test_root_with_a_medias_child_is_refused(world: World) -> None:
    """A dev root that holds a ``medias`` folder is a volume root, prod's parent: refused."""
    (world.dev_root / "medias").mkdir()
    assert world.run() != 0
    assert world.files_under(world.dev_root) == []
    assert world.children == []


def test_cap_is_refused(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    """A plan above ``--max-gb`` is refused, its total printed, nothing copied."""
    assert world.run("--max-gb", "0.000001") != 0
    assert world.files_under(world.dev_root) == []
    assert world.children == []
    assert "4104" in capsys.readouterr().out  # 4096 bytes of video + 8 of NFO


def test_dry_run_writes_nothing(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    """The dry run prints the plan and its total, and writes nothing nor runs any child."""
    assert world.run("--dry-run") == 0
    assert sorted(p for p in world.dev_root.rglob("*") if p.name != DEV_MARKER) == []
    assert world.children == []
    out = capsys.readouterr().out
    assert str(world.source) in out
    assert str(world.target) in out


def test_title_absent_from_the_index_is_reported_not_guessed(world: World, capsys: pytest.CaptureFixture[str]) -> None:
    """A manifest title the index does not know is named, and the tool copies nothing."""
    world.write_manifest(
        [
            {"provider": "tmdb", "id": MOVIE_TMDB_ID, "disk": "disk_3"},
            {"provider": "tvdb", "id": "999999", "disk": "disk_3"},
        ]
    )
    assert world.run() != 0
    assert world.files_under(world.dev_root) == []
    assert world.children == []
    captured = capsys.readouterr()
    assert "tvdb 999999" in captured.out + captured.err


def test_existing_target_is_not_overwritten(world: World) -> None:
    """A file already in the sandbox is kept as it is; the missing ones are copied, then indexed."""
    world.target.mkdir(parents=True)
    (world.target / "Inception.nfo").write_text("<movie>edited in dev</movie>", encoding="utf-8")
    assert world.run() == 0
    assert (world.target / "Inception.nfo").read_text(encoding="utf-8") == "<movie>edited in dev</movie>"
    assert (world.target / "Inception.mkv").read_bytes() == MOVIE_BYTES
    assert (world.source / "Inception.nfo").read_text(encoding="utf-8") == "<movie/>"
    assert [cmd[-1] for cmd in world.children] == ["library-index", "library-catalogue-refresh"]
