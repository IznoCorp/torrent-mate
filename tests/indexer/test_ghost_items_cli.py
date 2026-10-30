"""Ghost items through the CLI: ``library-index --mode full`` and ``library-retire-ghost-items``.

The scan retires an item whose folder is gone and whose files are all
tombstoned, under the per-disk cap; the command clears a backlog over the cap,
honouring every other guard. Both report and write nothing on a dry run.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.cli import app
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.merkle import DiskMountStatus
from personalscraper.indexer.scanner import ScanRunResult
from tests.conftest import make_cli_runner

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "personalscraper" / "indexer" / "migrations"
_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_SCAN = "personalscraper.indexer.scanner.scan_with"
_PATCH_VERIFY = "personalscraper.indexer.merkle.verify_disk_mounted"

runner = make_cli_runner()


def _make_config(tmp_path: Path, roots: list[Path]) -> Any:
    """Build a Config whose store lives under *tmp_path* and whose disks are *roots*."""
    from personalscraper.conf.models.disks import DiskConfig  # noqa: PLC0415
    from personalscraper.conf.models.indexer import IndexerConfig  # noqa: PLC0415

    cfg = MagicMock()
    cfg.indexer = IndexerConfig(db_path=tmp_path / "library.db")
    cfg.paths.staging_dir = tmp_path / "staging"
    cfg.all_category_ids = frozenset({"movies", "tv_shows"})
    cfg.torrent.active = ""
    cfg.disks = [DiskConfig(id=root.name, path=root, categories=["movies"]) for root in roots]
    return cfg


class _Library:
    """A file-backed store over disk folders built in ``tmp_path``."""

    def __init__(self, tmp_path: Path, labels: list[str]) -> None:
        """Create the store and one disk row per label.

        Args:
            tmp_path: The test's directory.
            labels: Disk labels; each disk's root is ``tmp_path/<label>``.
        """
        self.roots = {label: tmp_path / label for label in labels}
        self.cfg = _make_config(tmp_path, list(self.roots.values()))
        self.conn = sqlite3.connect(str(self.cfg.indexer.db_path), isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        apply_migrations(self.conn, _MIGRATIONS_DIR)
        self.disk_ids = {
            label: int(
                self.conn.execute(  # type: ignore[arg-type]
                    "INSERT INTO disk (uuid, label, mount_path, is_mounted, unreachable_strikes) "
                    "VALUES (?, ?, ?, 1, 0)",
                    (f"{label}-uuid", label, str(root)),
                ).lastrowid
            )
            for label, root in self.roots.items()
        }

    def item(self, label: str, name: str, *, present: bool, file_deleted_at: int | None = 100) -> int:
        """Insert an item on ``<root>/movies/<name>`` with one file.

        Args:
            label: The disk.
            name: The folder name.
            present: Whether the folder exists.
            file_deleted_at: The file's tombstone, ``None`` for a live file.

        Returns:
            The item id.
        """
        folder = self.roots[label] / "movies" / name
        if present:
            folder.mkdir(parents=True)
        item_id = int(
            self.conn.execute(  # type: ignore[arg-type]
                "INSERT INTO media_item (kind, title, title_sort, category_id, date_created, date_modified) "
                "VALUES ('movie', ?, ?, 'movies', 1, 1)",
                (name, name),
            ).lastrowid
        )
        self.conn.execute(
            "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)", (item_id, str(folder))
        )
        release_id = self.conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (item_id,)).lastrowid
        path_id = self.conn.execute(
            "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)", (self.disk_ids[label], f"movies/{name}")
        ).lastrowid
        # Past the strike threshold already, so the scan's own strikes change nothing.
        self.conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
            " last_verified_at, deleted_at, miss_strikes) VALUES (?, ?, 'f.mkv', 1, 1, 'h', 1, 1, ?, 0)",
            (release_id, path_id, file_deleted_at),
        )
        return item_id

    def items(self) -> set[int]:
        """Return the ids of the items left."""
        return {r[0] for r in self.conn.execute("SELECT id FROM media_item")}

    def invoke(
        self, args: list[str], *, unmounted: frozenset[str] = frozenset(), budget_exhausted: bool = False
    ) -> Any:
        """Run the CLI with the store's config, the walk stubbed and mounts answered.

        Args:
            args: CLI arguments.
            unmounted: Labels whose mount check answers ``UNMOUNTED``.
            budget_exhausted: Whether the stubbed walk reports its time budget spent.

        Returns:
            The CliRunner result.
        """

        def _verify(disk: Any) -> DiskMountStatus:
            return DiskMountStatus.UNMOUNTED if disk.label in unmounted else DiskMountStatus.MOUNTED_AND_VERIFIED

        result_stub = ScanRunResult(
            scan_run_id=1,
            files_visited=0,
            dirs_visited=0,
            status="ok",
            disks_skipped=0,
            budget_exhausted=budget_exhausted,
        )
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=self.cfg),
            patch(_PATCH_SCAN, return_value=result_stub),
            patch(_PATCH_VERIFY, side_effect=_verify),
        ):
            return runner.invoke(app, args)


def _summary(result: Any) -> dict[str, Any]:
    """Return the last JSON object of the CLI output."""
    lines = [line for line in re.sub(r"\x1b\[[0-9;]*m", "", result.stdout).splitlines() if line.startswith("{")]
    return json.loads(lines[-1])  # type: ignore[no-any-return]


def _command_payload(result: Any) -> dict[str, Any]:
    """Return the command's indented JSON output."""
    raw = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    return json.loads(raw[raw.find("{") :])  # type: ignore[no-any-return]


def test_a_full_scan_retires_a_ghost_whose_files_are_tombstoned(tmp_path: Path) -> None:
    """The ghost goes and the summary names it; present folders stay.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-index --mode full`` retires the ghost and lists it under
        ``ghost_items``.
    """
    lib = _Library(tmp_path, ["medias1"])
    present = {lib.item("medias1", f"Present {n} (2020)", present=True, file_deleted_at=None) for n in range(10)}
    ghost = lib.item("medias1", "Gone (2020)", present=False)

    result = lib.invoke(["library-index", "--mode", "full"])

    assert result.exit_code == 0, result.output
    assert lib.items() == present, "the ghost item must be retired by a full scan"
    assert [g["item_id"] for g in _summary(result)["ghost_items"]] == [ghost]


def test_a_full_scan_dry_run_reports_the_ghost_and_keeps_it(tmp_path: Path) -> None:
    """``--dry-run`` names the ghost with its reason and deletes nothing.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-index --mode full --dry-run`` lists the ghost and deletes
        nothing.
    """
    lib = _Library(tmp_path, ["medias1"])
    for n in range(10):
        lib.item("medias1", f"Present {n} (2020)", present=True, file_deleted_at=None)
    ghost = lib.item("medias1", "Gone (2020)", present=False)

    result = lib.invoke(["library-index", "--mode", "full", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert ghost in lib.items()
    assert [(g["item_id"], g["reason"]) for g in _summary(result)["ghost_items"]] == [(ghost, "dispatch_path_gone")]


@pytest.mark.parametrize("mode", ["quick", "incremental"])
def test_only_a_full_scan_retires_ghosts(tmp_path: Path, mode: str) -> None:
    """Quick and incremental walk part of a disk: they never judge an item gone.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-index --mode quick`` and ``--mode incremental`` retire
        no ghost and list none.
    """
    lib = _Library(tmp_path, ["medias1"])
    for n in range(10):
        lib.item("medias1", f"Present {n} (2020)", present=True, file_deleted_at=None)
    ghost = lib.item("medias1", "Gone (2020)", present=False)

    result = lib.invoke(["library-index", "--mode", mode])

    assert result.exit_code == 0, result.output
    assert ghost in lib.items()
    assert _summary(result)["ghost_items"] == []


def test_a_full_scan_out_of_budget_retires_no_ghost(tmp_path: Path) -> None:
    """A walk stopped by its time budget did not see every folder: no ghost is judged.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-index --mode full`` whose walk exhausted its budget
        retires no ghost and lists none.
    """
    lib = _Library(tmp_path, ["medias1"])
    for n in range(10):
        lib.item("medias1", f"Present {n} (2020)", present=True, file_deleted_at=None)
    ghost = lib.item("medias1", "Gone (2020)", present=False)

    result = lib.invoke(["library-index", "--mode", "full"], budget_exhausted=True)

    assert result.exit_code == 0, result.output
    assert ghost in lib.items()
    assert _summary(result)["ghost_items"] == []


def test_a_gone_folder_whose_files_are_not_tombstoned_keeps_its_item(tmp_path: Path) -> None:
    """Files retire first, the item after: a live file under a gone folder keeps the item.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-index --mode full`` keeps an item whose folder is gone
        while any of its files is still live.
    """
    lib = _Library(tmp_path, ["medias1"])
    for n in range(10):
        lib.item("medias1", f"Present {n} (2020)", present=True, file_deleted_at=None)
    striking = lib.item("medias1", "Striking (2020)", present=False, file_deleted_at=None)

    result = lib.invoke(["library-index", "--mode", "full"])

    assert result.exit_code == 0, result.output
    assert striking in lib.items()
    assert _summary(result)["ghost_items"] == []


def test_the_scan_cap_holds_and_the_command_clears_the_backlog_with_every_other_guard(tmp_path: Path) -> None:
    """Over the cap the scan retires none; the command retires only the true ghosts.

    Design: docs/production/indexer.md#ghost-items
    Contract: over the cap the scan retires nothing and names the disk under
        ``ghost_items_capped``; ``library-retire-ghost-items`` retires the
        backlog with every other guard and no cap.
    """
    lib = _Library(tmp_path, ["medias1", "medias2"])
    present = lib.item("medias1", "Present (2020)", present=True, file_deleted_at=None)
    ghosts = {lib.item("medias1", f"Gone {n} (2020)", present=False) for n in range(3)}
    live = lib.item("medias1", "Striking (2020)", present=False, file_deleted_at=None)
    repaired = lib.item("medias1", "Repairing (2020)", present=False)
    lib.conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at) VALUES ('item', ?, 'r', 1)", (repaired,)
    )
    unmounted = lib.item("medias2", "Elsewhere (2020)", present=False)
    everything = lib.items()

    scan = lib.invoke(["library-index", "--mode", "full"], unmounted=frozenset({"medias2"}))

    assert scan.exit_code == 0, scan.output
    assert lib.items() == everything, "over the cap the scan retires nothing"
    assert _summary(scan)["ghost_items_capped"] == ["medias1"]

    dry = lib.invoke(["--format", "json", "library-retire-ghost-items", "--dry-run"], unmounted=frozenset({"medias2"}))

    assert dry.exit_code == 0, dry.output
    assert lib.items() == everything
    by_disk = {d["disk"]: d for d in _command_payload(dry)["disks"]}
    assert {g["item_id"] for g in by_disk["medias1"]["ghosts"]} == ghosts
    assert {(k["item_id"], k["reason"]) for k in by_disk["medias1"]["kept"]} == {
        (live, "live_files"),
        (repaired, "pending_repair"),
    }
    assert by_disk["medias2"]["frozen"] is True

    run = lib.invoke(["--format", "json", "library-retire-ghost-items"], unmounted=frozenset({"medias2"}))

    assert run.exit_code == 0, run.output
    assert _command_payload(run)["retired"] == 3
    assert lib.items() == {present, live, repaired, unmounted}


def test_a_failed_ghost_pass_is_named_in_the_summary(tmp_path: Path) -> None:
    """A disk whose ghost pass fails is listed under ``ghost_items_failed``, not only logged.

    Design: docs/production/indexer.md#ghost-items
    Contract: a ghost pass that raises a database error on a disk is rolled
        back, logged with its traceback, and the disk is named under
        ``ghost_items_failed`` in the summary.
    """
    lib = _Library(tmp_path, ["medias1"])
    lib.item("medias1", "Gone (2020)", present=False)

    with patch(
        "personalscraper.indexer.ghost_items.retire_ghost_items", side_effect=sqlite3.OperationalError("locked")
    ):
        result = lib.invoke(["library-index", "--mode", "full"])

    assert result.exit_code == 0, result.output
    assert _summary(result)["ghost_items_failed"] == ["medias1"]


def test_a_dry_run_summary_says_its_ghosts_are_a_lower_bound(tmp_path: Path) -> None:
    """A dry run strikes nothing, so its ghost list is a lower bound, and the summary says so.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-index --mode full --dry-run`` reports
        ``ghost_items_lower_bound: true``; a real run reports ``false``.
    """
    lib = _Library(tmp_path, ["medias1"])
    for n in range(10):
        lib.item("medias1", f"Present {n} (2020)", present=True, file_deleted_at=None)

    dry = lib.invoke(["library-index", "--mode", "full", "--dry-run"])
    real = lib.invoke(["library-index", "--mode", "full"])

    assert _summary(dry)["ghost_items_lower_bound"] is True
    assert _summary(real)["ghost_items_lower_bound"] is False


def test_a_disk_in_the_store_but_not_configured_is_refused(tmp_path: Path) -> None:
    """``--disk`` naming a disk the configuration dropped says so and exits 1, never an empty success.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-retire-ghost-items --disk X`` with ``X`` in the store
        but not in the configuration prints why and exits 1.
    """
    lib = _Library(tmp_path, ["medias1", "old"])
    lib.cfg.disks = [d for d in lib.cfg.disks if d.id == "medias1"]
    ghost = lib.item("old", "Gone (2020)", present=False)

    result = lib.invoke(["--format", "json", "library-retire-ghost-items", "--disk", "old"])

    assert result.exit_code == 1, result.output
    assert "not in the configuration" in result.stderr
    assert ghost in lib.items()


def test_an_error_on_one_disk_reports_the_disks_done_and_exits_1(tmp_path: Path) -> None:
    """Each disk commits on its own: one failing still reports every other, and the run exits 1.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``library-retire-ghost-items`` reports each disk as it completes;
        a disk whose pass fails is named with its error and the command exits 1.
    """
    from personalscraper.indexer import ghost_items  # noqa: PLC0415

    lib = _Library(tmp_path, ["medias1", "medias2"])
    done = lib.item("medias1", "Gone (2020)", present=False)
    kept = lib.item("medias2", "Gone Too (2020)", present=False)
    real = ghost_items.retire_ghost_items

    def _fail_on_medias2(conn: Any, disk: Any, *args: Any, **kwargs: Any) -> Any:
        if disk.label == "medias2":
            raise sqlite3.OperationalError("disk I/O error")
        return real(conn, disk, *args, **kwargs)

    with patch("personalscraper.indexer.ghost_items.retire_ghost_items", side_effect=_fail_on_medias2):
        result = lib.invoke(["--format", "json", "library-retire-ghost-items"])

    assert result.exit_code == 1, result.output
    assert done not in lib.items() and kept in lib.items()
    payload = _command_payload(result)
    assert [d["disk"] for d in payload["disks"]] == ["medias1"]
    assert [f["disk"] for f in payload["failed"]] == ["medias2"]
    assert '"disk": "medias1"' in result.stderr, "the done disk is reported as it completes"
