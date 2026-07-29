"""Anti-split provenance: resolve a followed series' TVDB id for a staging show.

When a followed series' episodes are grabbed and ingested, the scrape must land
them under the SAME TVDB id as the follow — not a duplicate TVDB entry the free
match might pick (the Rooster incident: tvdb 452575 "ニワトリ・ファイター" vs the
follow's 457770 "Rooster", which split the show and broke the acquisition
reconcile). This module reverse-looks-up the follow's tvdb from the grabbed
``wanted`` queue by matching the folder's episodes, guarded by a title check so a
coincidental ``S01E06`` on a different follow can never force the wrong id.

Pure (folder name + child filenames + the passed-in queue snapshot, no I/O), so
it is golden-testable. Fail-soft: any internal error yields ``None`` — the caller
then falls back to the free match, never blocking the scrape.

See ``[[project_tvdb_duplicate_split_reconcile_break]]``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from personalscraper.acquire.domain import WantedItem

logger = get_logger(__name__)

#: ``SxxEyy`` episode marker (case-insensitive) — the scene standard on the files.
_SXXEYY_RE: re.Pattern[str] = re.compile(r"(?i)\bS(\d{1,2})E(\d{1,3})\b")

#: Minimum rapidfuzz token-set score between the folder title and the follow
#: title for the provenance to be trusted (anti-collision guard).
_TITLE_MATCH_THRESHOLD = 80


def _folder_episodes(show_dir: Path) -> set[tuple[int, int]]:
    """Return the ``(season, episode)`` set parsed from a folder's filenames."""
    found: set[tuple[int, int]] = set()
    try:
        children = list(show_dir.iterdir())
    except OSError:
        return found
    for child in children:
        match = _SXXEYY_RE.search(child.name)
        if match is not None:
            found.add((int(match.group(1)), int(match.group(2))))
    return found


def _title_matches(folder_name: str, follow_title: str) -> bool:
    """Whether the folder title is similar enough to the follow title.

    Uses rapidfuzz ``token_set_ratio`` (subset-tolerant: "Rooster Fighter" vs
    "Rooster" scores high). Fail-soft: any error → ``False`` (abstain).
    """
    try:
        from rapidfuzz import fuzz  # noqa: PLC0415 — local import keeps module load light

        return fuzz.token_set_ratio(folder_name, follow_title) >= _TITLE_MATCH_THRESHOLD
    except Exception:  # noqa: BLE001 — fail-soft: a fuzzy error must not force an id
        return False


def resolve_followed_tvdb(
    show_dir: Path,
    grabbed: list[WantedItem],
    follow_titles: dict[int, str],
) -> int | None:
    """Resolve the follow's TVDB id for a staging show folder, or ``None``.

    Returns an id ONLY when exactly one followed series' grabbed episodes cover
    the folder's episodes AND its title matches the folder (precision-first). Any
    ambiguity, mismatch, or error yields ``None`` — the caller free-matches.

    Args:
        show_dir: The staging show directory (its child filenames carry ``SxxEyy``).
        grabbed: Snapshot of ``grabbed`` wanted rows (episode kind, provider ids).
        follow_titles: Map ``followed_id -> title`` for the title guard.

    Returns:
        The follow's TVDB series id, or ``None`` when it cannot be asserted.
    """
    try:
        episodes = _folder_episodes(show_dir)
        if not episodes:
            return None

        # Group the tvdb ids of grabbed episodes that COVER this folder and whose
        # follow title matches. A distinct id set of size 1 is an unambiguous win.
        matched_tvdb: set[int] = set()
        for item in grabbed:
            if item.kind != "episode" or item.season is None or item.episode is None:
                continue
            tvdb = item.media_ref.tvdb_id
            if tvdb is None:
                continue
            if (item.season, item.episode) not in episodes:
                continue
            follow_title = follow_titles.get(item.followed_id) if item.followed_id is not None else None
            if not follow_title or not _title_matches(show_dir.name, follow_title):
                continue
            matched_tvdb.add(tvdb)

        if len(matched_tvdb) == 1:
            return next(iter(matched_tvdb))
        return None
    except Exception as exc:  # noqa: BLE001 — fail-soft: never block the scrape
        logger.warning("scrape_follow_tvdb_resolve_failed", error=str(exc))
        return None
