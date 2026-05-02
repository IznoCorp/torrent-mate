"""Per-disk scan mode drivers.

Package replacement for the former monolithic ``_modes.py`` module.
"""

from __future__ import annotations

import time

from personalscraper.indexer.scanner._db_writes import _flush_insert_buffer
from personalscraper.indexer.scanner._index_ddl import _drop_secondary_indexes

from .backfill import _scan_disk_enrich_backfill
from .enrich import (
    MediaInfoWrapper,
    _check_nfo_status,
    _enrich_one_file,
    _inventory_artwork,
    _purge_non_video_stream_rows,
    _resolve_item_root_dir,
    _scan_disk_enrich,
    os,
)
from .full import _scan_disk_full
from .incremental import _scan_disk_incremental, _walk_dir_incremental
from .quick import _run_paranoia_branch, _scan_disk_quick
from .verify import _scan_disk_verify

__all__ = [
    "MediaInfoWrapper",
    "os",
    "time",
    "_check_nfo_status",
    "_drop_secondary_indexes",
    "_enrich_one_file",
    "_flush_insert_buffer",
    "_inventory_artwork",
    "_purge_non_video_stream_rows",
    "_resolve_item_root_dir",
    "_run_paranoia_branch",
    "_scan_disk_enrich",
    "_scan_disk_enrich_backfill",
    "_scan_disk_full",
    "_scan_disk_incremental",
    "_scan_disk_quick",
    "_scan_disk_verify",
    "_walk_dir_incremental",
]
