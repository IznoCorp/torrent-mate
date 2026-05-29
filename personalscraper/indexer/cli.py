"""Public command-function facade for the media indexer sub-system.

The implementation lives in :mod:`personalscraper.indexer.commands.*`; this
module keeps the historic import paths stable for CLI wiring and tests.
"""

from __future__ import annotations

from personalscraper.indexer.commands._bootstrap import (
    _bootstrap_disks_from_config,
    build_fs_type_overrides,
)
from personalscraper.indexer.commands.diagnose import config_migrate_category_command
from personalscraper.indexer.commands.query import (
    library_search_command,
    library_show_command,
    library_status_command,
    library_verify_command,
)
from personalscraper.indexer.commands.repair import library_repair_command
from personalscraper.indexer.commands.scan import library_index_command, library_reconcile_command

__all__ = [
    "_bootstrap_disks_from_config",
    "build_fs_type_overrides",
    "config_migrate_category_command",
    "library_index_command",
    "library_reconcile_command",
    "library_repair_command",
    "library_search_command",
    "library_show_command",
    "library_status_command",
    "library_verify_command",
]
