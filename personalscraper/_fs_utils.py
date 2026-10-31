"""Shared filesystem helpers — cross-package.

``is_apple_double``: canonical check for macOS AppleDouble metadata files
(``._<name>``) created on NTFS/SMB volumes. Single source of truth for the
7+ filtering sites scattered across ``library/``, ``enforce/``, ``verify/``,
``process/``, ``commands/`` and the scanner exclusions.

``fold_ntfs_question_mark`` / ``name_key`` / ``name_variants``: the one place that
knows a name written on NTFS by macFUSE carries U+F025 where the real name has « ? ».
"""

from __future__ import annotations

import unicodedata
from typing import Literal

#: macFUSE maps the characters NTFS forbids into the private-use block; « ? » (U+003F)
#: becomes U+F025. A name copied off such a disk keeps it on HFS+/APFS.
NTFS_QUESTION_MARK = "\uf025"

_NORMALIZATION_FORMS: tuple[Literal["NFC", "NFD"], ...] = ("NFC", "NFD")


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


def fold_ntfs_question_mark(name: str) -> str:
    """Return *name* with every U+F025 replaced by the « ? » it stands for.

    Args:
        name: Any name or path string.

    Returns:
        The same string with the NTFS/macFUSE private-use character folded to « ? ».
    """
    return name.replace(NTFS_QUESTION_MARK, "?")


def name_key(name: str) -> str:
    """Return the comparison form of *name*: NFC, with U+F025 folded to « ? ».

    Two spellings of one name (macFUSE NFD vs NFC, U+F025 vs « ? ») share a key.
    Case and whitespace are left to the caller.

    Args:
        name: A file/folder name or a path string.

    Returns:
        The NFC-normalised, U+F025-folded string.
    """
    return unicodedata.normalize("NFC", fold_ntfs_question_mark(name))


def name_variants(name: str) -> set[str]:
    """Return every spelling under which *name* may be stored on disk or in the index.

    Used where a stored value must be matched by exact SQL equality: NFC and NFD,
    each with « ? » and with U+F025.

    Args:
        name: A name or relative path string.

    Returns:
        The distinct spellings (always including *name* normalised both ways).
    """
    folded = fold_ntfs_question_mark(name)
    spellings = {name, folded, folded.replace("?", NTFS_QUESTION_MARK)}
    return {unicodedata.normalize(form, spelling) for spelling in spellings for form in _NORMALIZATION_FORMS}
