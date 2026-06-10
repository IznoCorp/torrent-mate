"""Re-export shim — real implementation moved to core/sqlite/_fs_probe.py (RP3).

All existing importers (conf/models/indexer.py, conf/models/disks.py,
indexer/_fs_capability.py, indexer/scanner/__init__.py,
indexer/scanner/_spotlight.py, indexer/db.py) continue to import from this
module and get the same symbols without modification.
"""

from __future__ import annotations

from personalscraper.core.sqlite._fs_probe import (  # noqa: F401
    MountInfo,
    _build_mount_table,
    _run_mount,
    canonical_fs_type,
    probe_mount,
)

__all__ = ["MountInfo", "_build_mount_table", "_run_mount", "canonical_fs_type", "probe_mount"]
