"""Dispatch package — move staged media to permanent storage disks.

Resolves the destination disk for each item (movies replace, TV shows merge,
new media targets the disk with the most free space) and performs the move
via rsync with idempotent staging (``crash_recovery.DISPATCH_TMP_PREFIX``).
Orphan recovery of interrupted staging is the single-owner
``crash_recovery.sweep_orphans``.
"""
