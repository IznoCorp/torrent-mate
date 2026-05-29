"""Drift detection helpers extracted from existing_validator.py (Phase 10)."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from personalscraper.core.media_types import VIDEO_EXTENSIONS
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE, NamingPatterns
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.episode_manager import _extract_season_episode
from personalscraper.text_utils import media_processor

log = get_logger("scraper")

# Local regex copies — kept here to avoid a circular re-import from
# ``existing_validator`` (which re-exports the helpers below).
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


def _local_show_seasons(show_dir: Path) -> set[int]:
    """Extract the set of seasons present in a TV show folder.

    Walks the folder recursively and parses S/E from each video filename.
    Feeds content-aware candidate disambiguation in ``match_tvshow_tvdb``:
    a candidate whose TVDB catalog does not cover the observed seasons is
    very likely the wrong show (e.g. a same-keyword spin-off).

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        Set of season numbers (> 0). Empty when no parseable S/E found.
    """
    seasons: set[int] = set()
    for f in show_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
            continue
        season, _ = _extract_season_episode(f.name)
        if season and season > 0:
            seasons.add(season)
    return seasons


def _infer_year_from_child_names(show_dir: Path, title: str) -> int | None:
    """Infer a show year from release subfolders or video files.

    Some staging folders use a clean localized parent name without a year,
    while the release directory below still carries the original year token.
    Only accept years from child names whose cleaned title matches the parent
    closely enough to avoid leaking an episode title or unrelated extra.
    """
    expected_title = media_processor(title)
    if not expected_title:
        return None

    candidates = list(show_dir.iterdir())
    candidates.extend(
        f for f in show_dir.rglob("*") if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
    )

    for child in candidates:
        name = child.stem if child.is_file() else child.name
        child_title, child_year = _parse_folder_name(name)
        if child_year is None:
            continue
        parsed_title = media_processor(child_title)
        if parsed_title == expected_title or expected_title in parsed_title:
            log.info("show_year_inferred_from_child", directory=show_dir.name, child=name, year=child_year)
            return child_year

    return None


def _read_canonical_provider(tvshow_nfo_root: ET.Element) -> str | None:
    """Return the canonical provider family declared on a parsed ``tvshow.nfo``.

    The canonical family is the ``type`` attribute of the
    ``<uniqueid default="true">`` element. When no default is set,
    falls back to the first ``<uniqueid>`` element's ``type`` (legacy
    NFOs from before the ``provider-ids`` feature did not always mark
    a default).

    Args:
        tvshow_nfo_root: Parsed root element of ``tvshow.nfo``.

    Returns:
        Provider name (``"tvdb"`` / ``"tmdb"`` / …) or ``None`` when
        the NFO has no ``<uniqueid>`` at all.
    """
    default_unique = next(
        (u for u in tvshow_nfo_root.findall("uniqueid") if u.get("default") == "true"),
        None,
    )
    if default_unique is not None:
        kind = (default_unique.get("type") or "").strip()
        return kind or None
    first = tvshow_nfo_root.find("uniqueid")
    if first is not None:
        kind = (first.get("type") or "").strip()
        return kind or None
    return None


def _episode_nfo_has_canonical_uniqueid(nfo_path: Path, canonical_family: str) -> bool:
    """Check whether an episode NFO carries a non-empty canonical ``<uniqueid>``.

    Returns ``True`` only when the NFO parses, contains at least one
    ``<uniqueid type=canonical_family>`` tag (case-insensitive match),
    and the tag's text is non-empty after stripping.

    Args:
        nfo_path: Path to the sibling ``.nfo`` file.
        canonical_family: Family that the show's ``tvshow.nfo``
            declared canonical (``"tvdb"`` / ``"tmdb"``).

    Returns:
        ``True`` iff the canonical uniqueid is present and populated.
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314 — trusted NFO we just wrote
    except (ET.ParseError, OSError):
        return False
    expected = canonical_family.lower()
    for unique in root.findall("uniqueid"):
        kind = (unique.get("type") or "").strip().lower()
        text = (unique.text or "").strip()
        if kind == expected and text:
            return True
    return False


def verify_tvshow_scrape_drift(
    show_dir: Path,
    nfo_path: Path,
    patterns: NamingPatterns,
) -> tuple[bool, str]:
    r"""Verify a previously-scraped TV show directory still matches current scraper output.

    Purely filesystem + NFO parsing — no external API calls. Drift found
    here triggers a full re-scrape upstream (caller deletes the NFO and
    falls through).

    Checks, all must pass:

    1. ``tvshow.nfo`` parses and exposes non-empty ``<title>``, ``<year>``,
       and at least one non-empty ``<uniqueid>``.
    2. Folder name equals the canonical ``sanitize("{title} ({year})")``
       — catches previous scrapes whose API-sourced folder name drifted
       from the current policy (e.g. "Top Chef (France) (2010)" vs the
       TVDB canonical "Top Chef (2010)").
    3. Every video file under ``Saison XX/`` matches
       ``S\d{2}E\d{2} - .+\.ext`` — a title segment is required. A bare
       ``SxxExx.ext`` indicates a legacy title-less fallback that must be
       upgraded to the synthetic-title form.
    4. Every episode video has a sibling ``.nfo`` with the same stem.
    5. ``poster.jpg`` and ``landscape.jpg`` are present.

    Args:
        show_dir: Path to the TV show directory.
        nfo_path: Path to ``tvshow.nfo`` (existence already confirmed).
        patterns: Naming patterns used to compute the canonical folder
            name and artwork filenames.

    Returns:
        Tuple ``(is_valid, reason)``. ``reason`` is a short slug suitable
        for a log field; ``"ok"`` on success.
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314 — trusted NFO we just wrote
    except (ET.ParseError, OSError) as exc:
        return False, f"nfo_parse_failed:{exc}"

    # 1. Mandatory NFO fields.
    nfo_title = (root.findtext("title") or "").strip()
    nfo_year = (root.findtext("year") or "").strip()
    if not nfo_title:
        return False, "nfo_missing_title"
    if not nfo_year:
        return False, "nfo_missing_year"
    has_uniqueid = any((u.text or "").strip() for u in root.findall("uniqueid"))
    if not has_uniqueid:
        return False, "nfo_missing_uniqueid"
    # Strict canonical check (DESIGN §3 Q6) — at least one
    # ``<uniqueid default="true" type="...">`` with non-empty text and
    # a non-empty ``type`` attribute. Pre-existing NFOs that ship a
    # uniqueid without the default attribute (or without a type) trip
    # this branch and get re-scraped, which is intentional under the
    # provider-ids feature (no retro-compat before 1.x).
    # ``_read_canonical_provider`` keeps its tolerant first-uniqueid
    # fallback for downstream consumers that have already passed
    # this gate.
    has_default_uniqueid = any(
        u.get("default") == "true" and (u.get("type") or "").strip() and (u.text or "").strip()
        for u in root.findall("uniqueid")
    )
    if not has_default_uniqueid:
        return False, "nfo_missing_canonical_uniqueid"
    canonical_family = _read_canonical_provider(root)
    if canonical_family is None:
        # Defensive: with the strict ``type`` requirement above the
        # tolerant reader cannot return None on the happy path. Kept
        # as a safety net should the reader be hardened later.
        return False, "nfo_missing_canonical_uniqueid"
    trailing_year_pattern = f" ({nfo_year})"
    if nfo_title.endswith(trailing_year_pattern):
        return False, "nfo_title_contains_year"

    # 2. Canonical folder name. Compare under NFC normalization so macOS's
    # NFD-stored filenames don't trip the check (the two strings can look
    # identical in logs but differ in codepoints — "è" as U+00E8 vs
    # "e" + U+0300). Without this, the drift check falsely fires and the
    # subsequent rename-into-itself corrupts the folder.
    #
    canonical = patterns.format("movie_dir", Title=nfo_title, Year=nfo_year)
    if unicodedata.normalize("NFC", show_dir.name) != unicodedata.normalize("NFC", canonical):
        return False, f"folder_name_drift:{show_dir.name}!={canonical}"

    # 5. Show-level artwork.
    if not (show_dir / patterns.tvshow_poster).exists():
        return False, "poster_missing"
    if not (show_dir / patterns.tvshow_landscape).exists():
        return False, "landscape_missing"

    # 3 + 4. Episode naming + sibling NFO.
    for season_dir in show_dir.iterdir():
        if not (season_dir.is_dir() and SEASON_DIR_RE.match(season_dir.name)):
            continue
        for ep_file in season_dir.iterdir():
            if not ep_file.is_file():
                continue
            if ep_file.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                continue
            # Strict: require "SxxExx - Title.ext". A bare "SxxExx.ext" is a
            # legacy fallback name that must be upgraded.
            if not _EPISODE_STRICT_RE.match(ep_file.name):
                return False, f"episode_naming_drift:{ep_file.name}"
            # Synthetic-title fallbacks (e.g. "S17E09 - Episode 9.mkv") are
            # NFO-less by design (TMDB had no record at scrape time and the
            # scraper refuses to fabricate metadata).  Treat the missing
            # sibling NFO as expected so we don't trigger an endless
            # rescrape-drift loop on every dry-run.  A subsequent real
            # scrape will pick up the new TMDB data and rename the file.
            sibling_nfo = ep_file.with_suffix(".nfo")
            is_fallback = bool(_EPISODE_FALLBACK_RE.match(ep_file.name))
            if not sibling_nfo.exists():
                if not is_fallback:
                    return False, f"episode_nfo_missing:{sibling_nfo.name}"
                continue
            # Drift hardening (provider-ids feature, phase 4) : the sibling
            # NFO must carry the canonical ``<uniqueid type=...>`` matching
            # the show's ``tvshow.nfo`` default. Without this, layer-5
            # drift (NFOs without ``<uniqueid>``) would slip through and
            # ``scrape_fast_skip`` would perpetuate the broken state.
            if not _episode_nfo_has_canonical_uniqueid(sibling_nfo, canonical_family):
                return False, f"episode_nfo_missing_canonical_uniqueid:{sibling_nfo.name}"

    return True, "ok"
