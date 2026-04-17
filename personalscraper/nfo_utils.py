"""Shared NFO file validation utilities.

Provides is_nfo_complete() for checking NFO validity across the
pipeline (scraper, library scanner, verify). Moved from
scraper/scraper.py to enable cross-module access.
"""

import logging
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


def is_nfo_complete(nfo_path: Path) -> bool:
    """Check if an NFO file is complete and valid.

    A complete NFO must:
    1. Exist on disk
    2. Be parsable as XML
    3. Contain at least one <uniqueid> element with non-empty text

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
            if uid.text and uid.text.strip():
                return True
        return False
    except ET.ParseError:
        logger.debug("NFO not parsable as XML: %s", nfo_path.name)
        return False
    except OSError as exc:
        logger.warning("Cannot read NFO file %s: %s", nfo_path, exc)
        return False
