"""Maintenance dashboard backend package (maint-dash feature).

Provides the typed maintenance-action registry consumed by the S3 web UI
panels and the ``POST /api/maintenance/run`` endpoint. Each entry models a
single ``library-*`` CLI command with its risk classification, dry-run
support, targeting options, and French UI labels.

Exports the Pydantic response models for the three monitoring-panel
endpoints (disks, locks, index-health) defined in
``docs/features/maint-dash/plan/phase-02-panels-backend.md`` §2.1.

See ``docs/features/maint-dash/DESIGN.md`` §4 for the risk taxonomy and
``docs/features/maint-dash/plan/phase-01-db-registry.md`` §1.2 for the
registry ground truth.
"""

from personalscraper.web.maintenance.models import (  # noqa: F401
    DiskInfo,
    DisksResponse,
    IndexHealthResponse,
    LocksResponse,
    LockState,
    NfoStats,
    Sentinels,
    TmpOrphan,
)
from personalscraper.web.maintenance.registry import REGISTRY, ActionOption, MaintenanceAction, canonical_options_json

__all__ = [
    "ActionOption",
    "DiskInfo",
    "DisksResponse",
    "IndexHealthResponse",
    "LockState",
    "LocksResponse",
    "MaintenanceAction",
    "NfoStats",
    "REGISTRY",
    "Sentinels",
    "TmpOrphan",
    "canonical_options_json",
]
