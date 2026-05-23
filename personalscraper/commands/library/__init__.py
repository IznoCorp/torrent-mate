"""Library CLI commands package.

Re-exports all 16 Typer command functions from the domain submodules.
"""

from personalscraper.commands.library.analyze import (
    library_analyze,
    library_recommend,
    library_report,
    library_rescrape,
)
from personalscraper.commands.library.audit import library_ghost_audit, library_reconcile, library_relink
from personalscraper.commands.library.gc import library_gc
from personalscraper.commands.library.maintenance import library_clean, library_repair, library_validate, library_verify
from personalscraper.commands.library.query import library_search, library_show, library_status
from personalscraper.commands.library.scan import library_index, library_init_canonical

__all__ = [
    "library_analyze",
    "library_clean",
    "library_gc",
    "library_ghost_audit",
    "library_index",
    "library_init_canonical",
    "library_recommend",
    "library_reconcile",
    "library_relink",
    "library_repair",
    "library_report",
    "library_rescrape",
    "library_search",
    "library_show",
    "library_status",
    "library_validate",
    "library_verify",
]
