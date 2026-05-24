"""Shared NFO file validation utilities.

Provides is_nfo_complete() for checking NFO validity across the
pipeline (scraper, library scanner, verify). Moved from
scraper/scraper.py to enable cross-module access.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.logger import get_logger

log = get_logger("nfo_utils")


# Values that appear in <uniqueid> text but do not identify a real record.
# These come from legacy NFOs written before a53a44f, when missing TMDB/TVDB
# ids were still emitted as "0" or the literal string "None" (from str(None)).
_INVALID_UNIQUEID_VALUES = frozenset({"0", "none"})


def glob_nfo_candidates(base: Path) -> list[Path]:
    """Return ``base/*.nfo`` sorted, skipping macOS AppleDouble metadata files.

    AppleDouble files (``._<name>``) are binary metadata sidecars
    created by macOS on NTFS / SMB volumes. They share the ``.nfo``
    suffix but contain extended-attribute blobs, not XML — feeding
    them to :class:`xml.etree.ElementTree` produces a ``ParseError``
    and masks the legitimate sibling NFO.

    Args:
        base: Directory to glob (typically a media item's dispatch dir).

    Returns:
        Sorted list of real ``.nfo`` paths (zero or more).
    """
    return sorted(f for f in base.glob("*.nfo") if not f.name.startswith("._"))


def is_nfo_complete(nfo_path: Path) -> bool:
    """Check if an NFO file is complete and valid.

    A complete NFO must:
    1. Exist on disk
    2. Be parsable as XML
    3. Contain at least one <uniqueid> element with a non-empty,
       non-placeholder text value (``"0"`` and ``"None"`` are rejected —
       they indicate a provider miss that should trigger a re-scrape).

    Used to distinguish valid NFOs from crash-truncated or incomplete
    ones that should be re-scraped.

    Args:
        nfo_path: Path to the .nfo file.

    Returns:
        True if the NFO is complete and valid.
    """
    if not nfo_path.exists():
        return False
    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        root = tree.getroot()
        for uid in root.findall("uniqueid"):
            if uid.text and uid.text.strip().lower() not in _INVALID_UNIQUEID_VALUES and uid.text.strip():
                return True
        return False
    except ET.ParseError:
        log.debug("nfo_not_parsable", file=nfo_path.name)
        return False
    except OSError as exc:
        log.warning("nfo_read_failed", path=str(nfo_path), error=str(exc))
        return False
