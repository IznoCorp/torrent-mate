"""Shared NFO file validation utilities.

Provides is_nfo_complete() for checking NFO validity across the
pipeline (scraper, indexer item stage, verify). Moved from
scraper/scraper.py to enable cross-module access.

Also hosts the three NFO helper functions extracted from
``library/scanner.py`` (Phase 1 of the lib-fold refactor):
``parse_title_year``, ``extract_nfo_ids``, and ``extract_nfo_metadata``.
"""

import codecs
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from personalscraper._fs_utils import is_apple_double
from personalscraper.logger import get_logger

log = get_logger("nfo_utils")


# Values that appear in <uniqueid> text but do not identify a real record.
# These come from legacy NFOs written before a53a44f, when missing TMDB/TVDB
# ids were still emitted as "0" or the literal string "None" (from str(None)).
_INVALID_UNIQUEID_VALUES = frozenset({"0", "none"})

# Title (Year) pattern — same as _parse_folder_name in scraper
_TITLE_YEAR_RE = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")

# Inverse map of ``scraper.nfo_generator._NFO_RATING_SOURCE_NAMES`` — the
# NFO writer translates internal source names to Plex/Kodi-compatible
# display names ; the indexer reverses the mapping so ``ratings_json``
# stores the same internal name shape the scraper / backfill produce.
_NFO_RATING_SOURCE_REVERSE: dict[str, str] = {
    "imdb": "imdb",
    "themoviedb": "tmdb",
    "tmdb": "tmdb",
    "rottentomatoes": "rotten_tomatoes",
    "rotten_tomatoes": "rotten_tomatoes",
    "metacritic": "metacritic",
    "trakt": "trakt",
}


def glob_nfo_candidates(base: Path) -> list[Path]:
    """Return ``base/*.nfo`` sorted, skipping macOS AppleDouble metadata files.

    AppleDouble files (``._<name>``) are binary metadata sidecars
    created by macOS on NTFS / SMB volumes. They share the ``.nfo``
    suffix but contain extended-attribute blobs, not XML — feeding
    them to :class:`xml.etree.ElementTree` produces a ``ParseError``
    and masks the legitimate sibling NFO.

    Delegates to :func:`personalscraper._fs_utils.is_apple_double` so the
    AppleDouble convention has a single source of truth across the codebase.

    Args:
        base: Directory to glob (typically a media item's dispatch dir).

    Returns:
        Sorted list of real ``.nfo`` paths (zero or more).
    """
    return sorted(f for f in base.glob("*.nfo") if not is_apple_double(f.name))


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
        tree = ET.parse(nfo_path)
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


_XML_DECLARATION_RE = re.compile(r"^\s*<\?xml[^>]*\?>")
# A DOCTYPE, with or without an internal subset, is as illegal inside the wrapper as the declaration.
_DOCTYPE_RE = re.compile(r"^\s*<!DOCTYPE(?:[^>\[]|\[.*?\])*>", re.DOTALL)
_XML_ENCODING_RE = re.compile(rb"^\s*<\?xml[^>]*?encoding\s*=\s*[\"']([A-Za-z0-9._-]+)[\"']")

# Root element the episode NFO writer produces (NFOGenerator.generate_episode_nfo).
_EPISODE_NFO_ROOT = "episodedetails"

# Fields the writer always emits for an episode; a root lacking any of them is a stub.
# <uniqueid> is NOT required: it is omitted when no provider id is known, and legacy
# NFOs get theirs through the scraper's upgrade-in-place.
_EPISODE_NFO_REQUIRED_FIELDS = ("title", "season", "episode")


def _decode_nfo_bytes(raw: bytes) -> str:
    """Decode NFO bytes with the encoding the XML declaration names.

    With no declaration the content is UTF-8 (BOM dropped), then Latin-1 as a last
    resort: legacy tools wrote accented NFOs in Latin-1, and a well-formed one must
    not be judged unusable (and rewritten) for that. NUL bytes mean binary content
    (AppleDouble sidecar...) which Latin-1 would happily « decode ».

    Args:
        raw: The file content.

    Returns:
        The decoded text, BOM excluded.

    Raises:
        ET.ParseError: Binary content, an unknown declared encoding, or bytes that
            do not decode with the declared one.
    """
    if b"\x00" in raw:
        raise ET.ParseError("binary content (NUL byte)")
    raw = raw.removeprefix(codecs.BOM_UTF8)
    declared = _XML_ENCODING_RE.match(raw)
    if declared is not None:
        encoding = declared.group(1).decode("ascii")
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise ET.ParseError(f"cannot decode as {encoding}: {exc}") from exc
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def read_episode_nfo_roots(nfo_path: Path) -> list[ET.Element]:
    """Parse an episode NFO that may hold several root elements.

    A Kodi multi-episode NFO is a sequence of ``<episodedetails>`` roots, which
    ``ET.parse`` rejects (« junk after document element »). The content is
    wrapped in one synthetic root, after dropping the XML declaration and a leading
    DOCTYPE (both illegal anywhere but the very start), so a single-root file and a multi-root file
    are read the same way.

    Args:
        nfo_path: Path to the episode ``.nfo``.

    Returns:
        The top-level elements, in document order (empty for a blank file).

    Raises:
        ET.ParseError: The content is not well-formed XML (truncated, binary...).
        OSError: The file cannot be read.
    """
    text = _decode_nfo_bytes(nfo_path.read_bytes())
    body = _DOCTYPE_RE.sub("", _XML_DECLARATION_RE.sub("", text, count=1), count=1)
    return list(ET.fromstring(f"<nfo>{body}</nfo>"))


def is_episode_nfo_usable(nfo_path: Path) -> bool:
    """Tell whether an existing episode NFO can be kept as it is.

    The ONE definition shared by the TV scraper (which must not skip a
    non-conformant NFO) and ``library-rescrape`` (which repairs them): the file
    exists, is well-formed XML and every root element is the
    ``<episodedetails>`` the writer produces, carrying a non-empty ``<title>``,
    ``<season>`` and ``<episode>``. A multi-root file is readable and
    carries data for several episodes, so it is conformant.

    Args:
        nfo_path: Path to the episode ``.nfo``.

    Returns:
        True when the NFO is readable and made of ``<episodedetails>`` roots only.
    """
    try:
        roots = read_episode_nfo_roots(nfo_path)
    except (ET.ParseError, OSError) as exc:
        log.debug("episode_nfo_unusable", file=nfo_path.name, error=str(exc))
        return False
    return bool(roots) and all(
        root.tag == _EPISODE_NFO_ROOT
        and all((root.findtext(field) or "").strip() for field in _EPISODE_NFO_REQUIRED_FIELDS)
        for root in roots
    )


def parse_title_year(dirname: str) -> tuple[str, int | None]:
    """Parse 'Title (Year)' from a directory name.

    Args:
        dirname: Directory name (not full path).

    Returns:
        Tuple of (title, year). Year is None if not found.
    """
    m = _TITLE_YEAR_RE.match(dirname)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return dirname, None


def extract_nfo_ids(nfo_path: Path) -> tuple[str | None, str | None]:
    """Extract TMDB and IMDB IDs from a valid NFO file.

    Thin compatibility wrapper around :func:`extract_nfo_metadata`. Kept
    for callers (``trailers/scanner.py``, ``library/rescraper.py``,
    test fixtures) that only need the legacy two-tuple.

    Args:
        nfo_path: Path to .nfo file (must exist and be valid XML).

    Returns:
        Tuple of (tmdb_id, imdb_id). Either can be None.
    """
    meta = extract_nfo_metadata(nfo_path)
    return meta["tmdb_id"], meta["imdb_id"]


def extract_nfo_metadata(nfo_path: Path) -> dict[str, Any]:
    """Extract provider IDs + canonical default + ratings from an NFO.

    Implements the indexer side of the provider-ids contract (DESIGN
    §3 + ACCEPTANCE #4). The legacy ``extract_nfo_ids`` only read
    ``tmdb`` / ``imdb`` uniqueids ; this richer extractor also reads
    ``tvdb``, the ``<uniqueid default="true">`` flag, and the entire
    ``<ratings>`` block so the indexer can populate
    ``media_item.external_ids_json``, ``canonical_provider``, and
    ``ratings_json`` from a single NFO parse.

    Args:
        nfo_path: Path to .nfo file (must exist and be valid XML).

    Returns:
        Dict with keys ``tmdb_id``, ``imdb_id``, ``tvdb_id``,
        ``canonical_provider`` (``"tvdb"`` / ``"tmdb"`` / ``None``),
        and ``ratings`` (list of ``{source, score, votes}``).
        All scalar fields default to ``None`` ; ``ratings`` defaults
        to an empty list. Returned shape is stable even when the
        parser fails — callers can read any key unconditionally.
    """
    blank: dict[str, Any] = {
        "tmdb_id": None,
        "imdb_id": None,
        "tvdb_id": None,
        "canonical_provider": None,
        "ratings": [],
    }
    try:
        root = ET.parse(nfo_path).getroot()  # trusted NFO we wrote
    except (ET.ParseError, OSError) as exc:
        log.debug("library_scan_nfo_ids_parse_error", nfo=str(nfo_path), exc_info=True, error=str(exc))
        return blank

    tmdb_id: str | None = None
    imdb_id: str | None = None
    tvdb_id: str | None = None
    canonical_provider: str | None = None
    for uid in root.iter("uniqueid"):
        uid_type = (uid.get("type") or "").lower().strip()
        text = (uid.text or "").strip()
        if not text:
            continue
        if uid_type == "tmdb":
            tmdb_id = text
        elif uid_type == "imdb":
            imdb_id = text
        elif uid_type == "tvdb":
            tvdb_id = text
        if uid.get("default") == "true" and uid_type in ("tvdb", "tmdb"):
            canonical_provider = uid_type

    ratings: list[dict[str, Any]] = []
    for rating in root.iter("rating"):
        name = (rating.get("name") or "").strip().lower()
        value = (rating.findtext("value") or "").strip()
        votes_raw = (rating.findtext("votes") or "").strip()
        if not name or not value:
            continue
        source = _NFO_RATING_SOURCE_REVERSE.get(name, name)
        votes: int | None = int(votes_raw) if votes_raw.isdigit() else None
        ratings.append({"source": source, "score": value, "votes": votes})

    return {
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "tvdb_id": tvdb_id,
        "canonical_provider": canonical_provider,
        "ratings": ratings,
    }
