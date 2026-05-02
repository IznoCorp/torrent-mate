"""Dispatch package — move staged media to permanent storage disks.

Resolves the destination disk for each item (movies replace, TV shows merge,
new media targets the disk with the most free space) and performs the move
via rsync with idempotent ``_tmp_dispatch_*`` staging.
"""
