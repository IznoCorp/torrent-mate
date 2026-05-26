#!/usr/bin/env python3
"""One-shot cleanup script for the 8 phantom TV-show rows discovered 2026-05-21.

Runbook
-------
Background
^^^^^^^^^^
``library-reconcile`` (Phase 4.1 / 4.2) detected two classes of phantom shows:

**Class A — deleted filesystem paths (5 shows)**
These directories no longer exist on disk.  The ``path`` rows and their
associated ``media_file`` rows are stale ghosts.  Fix: run
``library-reconcile --scope path_missing --enqueue-repairs`` to push a
``repair_queue`` entry for each phantom path, then drain via
``library-repair`` which calls ``soft_delete_subtree`` on every
``media_file`` belonging to the missing path (BD-D machinery).

Affected shows (directory confirmed gone from FS):

- Bloqués
- Avez-vous déjà...
- Corneil et Bernie
- Star Trek Enterprise
- Star Trek Voyager

**Class B — path exists but media_item row is missing (2 shows)**
The directory is present on disk but no ``media_item`` row exists in the
indexer DB.  Fix: run ``library-index --mode incremental`` to re-create
the ``media_item`` and seed its ``media_file`` rows (Stage A), then
``library-index --mode enrich`` to re-link releases (Stage B).

Affected shows (directory confirmed present on FS):

- Monk
- Squid Game

Idempotence guarantee
^^^^^^^^^^^^^^^^^^^^^
Re-running this script on an already-cleaned DB is safe:

- ``library-reconcile`` will detect 0 missing paths → no new repair rows.
- ``library-index --mode incremental`` skips directories that are already
  indexed (the scanner checks ``scan_generation`` and ``dir_mtime_ns``).
- The partial UNIQUE INDEX on ``repair_queue(scope, scope_id)
  WHERE status='pending'`` (migration 003) deduplicates concurrent enqueues.

Operator procedure
^^^^^^^^^^^^^^^^^^
Execute the steps **in order**.  Each step must succeed (exit 0) before
the next.  Read the JSON output after each command.

Step 1 — soft-delete phantom paths (Class A)::

    personalscraper library-reconcile --scope path_missing --enqueue-repairs

Expected: ``path_missing_count >= 5``, ``enqueued_repairs >= 5``.
If ``path_missing_count == 0`` the paths were already cleaned — skip Step 2.

Step 2 — drain the repair queue (soft-delete subtrees)::

    personalscraper library-repair

Expected: ``succeeded >= 5``, ``failed == 0``.

Step 3 — re-index Class-B shows (Monk, Squid Game)::

    personalscraper library-index --mode incremental

Expected: ``files_walked > 0``.

Step 4 — link releases (Stage B enrich)::

    personalscraper library-index --mode enrich

Expected: finishes without error.

Step 5 — verification::

    personalscraper library-reconcile

Expected: ``path_missing_count == 0``, ``total_findings`` approximately
6655 (sidecars legitimate).  If ``items_without_files_count > 0`` after
re-indexing, run ``library-index --mode enrich`` once more.

Archival
^^^^^^^^
After the operator confirms Step 5 passes, this file can be archived to
``docs/archive/`` or deleted.  It is NOT wired into ``make check`` or CI.

Usage (validation only)
^^^^^^^^^^^^^^^^^^^^^^^^
This script itself contains no executable logic — it is a pure runbook
embedded in a Python module so that:

1. ``python -c "import scripts.cleanup_2026_05_21_orphan_shows"`` (or
   ``python3 scripts/cleanup-2026-05-21-orphan-shows.py``) exits 0,
   confirming the file is syntactically valid.

2. The runbook is version-controlled alongside the code that enables it
   (Phase 4.1 + 4.2 machinery).

3. CI / mypy can type-check it with zero special-casing.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

#: Human-readable label for this cleanup batch.
CLEANUP_LABEL: str = "phantom-shows-2026-05-21"

#: Shows whose FS path was deleted → must be soft-deleted via library-repair.
CLASS_A_DELETED_PATH_SHOWS: tuple[str, ...] = (
    "Bloqués",
    "Avez-vous déjà...",
    "Corneil et Bernie",
    "Star Trek Enterprise",
    "Star Trek Voyager",
)

#: Shows whose FS path exists but media_item is missing → must be re-indexed.
CLASS_B_FS_EXISTS_SHOWS: tuple[str, ...] = (
    "Monk",
    "Squid Game",
)

# ---------------------------------------------------------------------------
# Validation helpers (used by the test suite)
# ---------------------------------------------------------------------------


def describe_cleanup() -> dict[str, object]:
    """Return a structured summary of the cleanup batch for test assertions.

    Returns:
        A dict with keys:
        - ``label``: human-readable cleanup batch identifier.
        - ``class_a``: tuple of show names to soft-delete via repair queue.
        - ``class_b``: tuple of show names to re-index via library-scan.
        - ``total_shows``: total count (class A + class B).
    """
    return {
        "label": CLEANUP_LABEL,
        "class_a": CLASS_A_DELETED_PATH_SHOWS,
        "class_b": CLASS_B_FS_EXISTS_SHOWS,
        "total_shows": len(CLASS_A_DELETED_PATH_SHOWS) + len(CLASS_B_FS_EXISTS_SHOWS),
    }


def build_class_a_runbook_steps() -> list[str]:
    """Return the ordered CLI commands for Class-A phantom-path cleanup.

    Each command must be run in sequence; the next step depends on the
    previous one succeeding (exit 0).

    Returns:
        Ordered list of shell command strings for Class-A soft-delete flow.
    """
    return [
        "personalscraper library-reconcile --scope path_missing --enqueue-repairs",
        "personalscraper library-repair",
    ]


def build_class_b_runbook_steps() -> list[str]:
    """Return the ordered CLI commands for Class-B re-index flow.

    Returns:
        Ordered list of shell command strings for Class-B re-index flow.
    """
    return [
        "personalscraper library-index --mode incremental",
        "personalscraper library-index --mode enrich",
    ]


def build_verification_steps() -> list[str]:
    """Return the verification commands to run after cleanup is complete.

    Returns:
        Ordered list of shell command strings for post-cleanup verification.
    """
    return [
        "personalscraper library-reconcile",
    ]


def assert_reconcile_report_clean(report: dict[str, object]) -> list[str]:
    """Assert that a ``library-reconcile`` JSON report shows a clean state.

    Intended for use in operator scripting or integration tests that call
    ``library-reconcile`` programmatically.  Returns a list of violation
    messages; an empty list means the DB is clean.

    Args:
        report: Parsed JSON dict from ``personalscraper library-reconcile``
            (keys: ``path_missing_count``, ``total_findings``, etc.).

    Returns:
        List of human-readable violation strings.  Empty list = clean.
    """
    violations: list[str] = []

    path_missing = report.get("path_missing_count", -1)
    if path_missing != 0:
        violations.append(f"path_missing_count={path_missing!r} (expected 0 after cleanup)")

    items_without_files = report.get("items_without_files_count", -1)
    if items_without_files != 0:
        violations.append(
            f"items_without_files_count={items_without_files!r} "
            "(expected 0 — re-run 'library-index --mode enrich' if Class-B re-index completed)"
        )

    return violations


# ---------------------------------------------------------------------------
# Entry point (syntax / importability check only)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    # Print the cleanup summary when executed directly — this serves as both
    # a quick sanity check and a human-readable overview for the operator.
    summary = describe_cleanup()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print()
    print("Class-A steps (soft-delete phantom paths):")
    for step in build_class_a_runbook_steps():
        print(f"  {step}")
    print()
    print("Class-B steps (re-index FS-exists shows):")
    for step in build_class_b_runbook_steps():
        print(f"  {step}")
    print()
    print("Verification:")
    for step in build_verification_steps():
        print(f"  {step}")
    sys.exit(0)
