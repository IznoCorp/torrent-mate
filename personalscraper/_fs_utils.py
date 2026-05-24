"""Shared filesystem helpers — cross-package.

``is_apple_double``: canonical check for macOS AppleDouble metadata files
(``._<name>``) created on NTFS/SMB volumes. Single source of truth for the
7+ filtering sites scattered across ``library/``, ``enforce/``, ``verify/``,
``process/``, ``commands/`` and the scanner exclusions.
"""

from __future__ import annotations


def is_apple_double(name: str) -> bool:
    """Return True if *name* is a macOS AppleDouble metadata sidecar.

    AppleDouble files start with the literal prefix ``._``. They are
    binary extended-attribute blobs created by macOS on filesystems
    that don't natively support extended attributes (NTFS via macFUSE,
    SMB shares). They are noise from our pipeline's perspective and
    must be filtered out everywhere we enumerate files.

    Args:
        name: The bare entry name (no directory component).

    Returns:
        True if *name* starts with ``._``; False otherwise.
    """
    return name.startswith("._")
