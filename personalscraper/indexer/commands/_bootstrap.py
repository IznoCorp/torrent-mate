"""Shared indexer CLI bootstrap helpers."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Sequence

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.indexer.merkle import _resolve_volume_root
from personalscraper.logger import get_logger

log = get_logger("indexer.cli")


def _bootstrap_disks_from_config(
    conn: sqlite3.Connection,
    cfg_disks: Sequence[DiskConfig],
) -> int:
    """Populate the ``disk`` table from ``Config.disks`` entries on first run.

    Called when the ``disk`` table is empty and ``Config.disks`` is non-empty.
    For each :class:`~personalscraper.conf.models.DiskConfig`, this function:

    1. Resolves the volume mount root via :func:`_resolve_volume_root`.
    2. Calls ``diskutil`` via
       :func:`~personalscraper.indexer.merkle.bootstrap_disk_identity` to
       obtain the volume UUID and write the sentinel file.
    3. INSERTs the disk row with ``is_mounted=1`` and ``last_seen_at=now``.

    If ``bootstrap_disk_identity`` raises :class:`~personalscraper.indexer.merkle.BootstrapError`
    (e.g. disk offline or not a macOS system), the disk is skipped with a
    warning so that offline disks do not block the bootstrap entirely.

    Args:
        conn: Open :class:`sqlite3.Connection` with migrations applied.
        cfg_disks: Sequence of :class:`~personalscraper.conf.models.DiskConfig`
            objects from the loaded config.

    Returns:
        Number of disk rows successfully inserted.
    """
    from personalscraper.indexer.merkle import BootstrapError, bootstrap_disk_identity  # noqa: PLC0415

    registered = 0
    now = int(time.time())

    for disk_cfg in cfg_disks:
        mount_root = _resolve_volume_root(disk_cfg.path)
        try:
            uuid = bootstrap_disk_identity(mount_root)
        except BootstrapError as exc:
            log.warning(
                "indexer.bootstrap.disk_skipped",
                disk_id=disk_cfg.id,
                mount_root=str(mount_root),
                reason=str(exc),
            )
            continue

        conn.execute(
            "INSERT OR IGNORE INTO disk "
            "(uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
            "VALUES (?, ?, ?, ?, NULL, 1, 0)",
            (uuid, disk_cfg.id, str(disk_cfg.path), now),
        )
        log.info(
            "indexer.bootstrap.disk_registered",
            disk_id=disk_cfg.id,
            uuid=uuid,
            mount_path=str(disk_cfg.path),
        )
        registered += 1

    return registered


def build_fs_type_overrides(cfg_disks: Sequence[DiskConfig]) -> dict[str, str]:
    """Build the scanner ``fs_type_overrides`` map keyed on the STABLE disk id.

    The override map links an operator ``DiskConfig.fs_type`` to the disk it
    applies to.  The link MUST use a stable identity, not the mutable
    ``DiskRow.mount_path`` (which is rewritten by
    :func:`~personalscraper.indexer.repos.disk_repo.update_mount_path` and set
    to ``NULL`` on unmount).  :func:`_bootstrap_disks_from_config` persists
    ``DiskConfig.id`` into the immutable ``DiskRow.label`` column, so the label
    is the durable join key between a config disk and its DB row.

    Keying on ``DiskConfig.id`` (== ``DiskRow.label``) therefore guarantees the
    scanner resolves the SAME capability the transfer layer resolves for that
    disk — the two can never diverge after a remount.  The scanner looks the
    map up by ``DiskRow.label`` in
    :func:`~personalscraper.indexer.scanner._scan_orchestrator._scan_one_disk`.

    Args:
        cfg_disks: Sequence of :class:`~personalscraper.conf.models.DiskConfig`
            objects from the loaded config.

    Returns:
        Mapping ``{DiskConfig.id: DiskConfig.fs_type}`` for every disk that
        carries an explicit ``fs_type`` override.  Disks with ``fs_type=None``
        are omitted (pure auto-detection on the scan side).
    """
    return {disk.id: disk.fs_type for disk in cfg_disks if disk.fs_type is not None}


# ---------------------------------------------------------------------------
# library-status
# ---------------------------------------------------------------------------
