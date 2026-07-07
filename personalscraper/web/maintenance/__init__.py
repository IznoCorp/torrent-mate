"""Maintenance dashboard backend package (maint-dash feature).

Provides the typed maintenance-action registry consumed by the S3 web UI
panels and the ``POST /api/maintenance/run`` endpoint. Each entry models a
single ``library-*`` CLI command with its risk classification, dry-run
support, targeting options, and French UI labels.

See ``docs/features/maint-dash/DESIGN.md`` §4 for the risk taxonomy and
``docs/features/maint-dash/plan/phase-01-db-registry.md`` §1.2 for the
registry ground truth.
"""

from personalscraper.web.maintenance.registry import REGISTRY, ActionOption, MaintenanceAction, canonical_options_json

__all__ = ["ActionOption", "MaintenanceAction", "REGISTRY", "canonical_options_json"]
