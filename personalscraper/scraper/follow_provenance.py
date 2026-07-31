"""Anti-split provenance: resolve a followed series' TVDB id for a staging show.

When a followed series' episodes are grabbed and ingested, the scrape must land
them under the SAME TVDB id as the follow — not a duplicate TVDB entry the free
match might pick (the Rooster incident: tvdb 452575 "ニワトリ・ファイター" vs the
follow's 457770 "Rooster", which split the show and broke the acquisition
reconcile). This module reverse-looks-up the follow's tvdb from the grabbed
``wanted`` queue by matching the folder's episodes.

**Precision-first** (a wrong force writes the wrong show, so the bar is high). An
id is asserted ONLY when a single followed series:

1. **covers ALL** the folder's episodes with its grabbed wanted (not just one —
   a coincidental shared ``S01E06`` cannot force), and
2. its **title matches** the folder (rapidfuzz token-set guard), and
3. its **year agrees** with the folder's year when the folder carries one (so a
   different-year remake — ``Doctor Who (1963)`` vs a followed ``Doctor Who``
   2005 — cannot force).

Any ambiguity (two follows qualify), partial coverage, title/year mismatch, or
error yields ``None`` — the caller then free-matches, never blocked. Pure (folder
name + child filenames + the passed-in queue snapshot), so it is golden-testable.

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

#: ``SxxEyy`` episode marker(s) — the scene standard. Captures a run of episodes
#: (``S01E06``, ``S01E06E07``) so a multi-episode file contributes each episode.
_SXXEYY_RE: re.Pattern[str] = re.compile(r"(?i)\bS(\d{1,2})((?:E\d{1,3})+)\b")
_EP_RE: re.Pattern[str] = re.compile(r"(?i)E(\d{1,3})")

#: Trailing ``(YYYY)`` or bare ``YYYY`` year in a folder name (1900-2099).
_YEAR_RE: re.Pattern[str] = re.compile(r"\b(19|20)\d{2}\b")

#: Minimum rapidfuzz token-set score between the folder title and the follow
#: title for the provenance to be trusted (anti-collision guard).
_TITLE_MATCH_THRESHOLD = 80


def _folder_episodes(show_dir: Path) -> set[tuple[int, int]]:
    """Return the ``(season, episode)`` set parsed from a folder's file tree.

    Recursive (one level of ``Saison NN/`` nesting is common on a re-scrape) and
    multi-episode aware (``S01E06E07`` yields both ``(1,6)`` and ``(1,7)``).
    """
    found: set[tuple[int, int]] = set()
    try:
        walk = list(show_dir.rglob("*"))
    except OSError:
        return found
    for child in walk:
        match = _SXXEYY_RE.search(child.name)
        if match is None:
            continue
        season = int(match.group(1))
        for ep in _EP_RE.findall(match.group(2)):
            found.add((season, int(ep)))
    return found


def _folder_year(folder_name: str) -> int | None:
    """Return the year embedded in a folder name, or ``None``."""
    match = _YEAR_RE.search(folder_name)
    return int(match.group(0)) if match is not None else None


def _title_tokens(text: str) -> set[str]:
    """Lowercased alphanumeric word tokens of a title (punctuation stripped)."""
    return {tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if tok}


def _title_matches(folder_name: str, follow_title: str) -> bool:
    """Whether the folder title is similar enough to the follow title.

    Two ways to match (either suffices):

    1. rapidfuzz ``token_set_ratio`` ≥ threshold — the general fuzzy guard.
    2. **Subset (#29)**: every token of the folder name is contained in the
       follow title. A generic release folder (``"Star Trek"``) is a
       less-specific name of a longer followed title (``"Star Trek: Strange New
       Worlds"``) — a strong, non-coincidental match that ``token_set_ratio``
       scores LOW (61.5) because the follow's extra words dilute it. Accepting
       the subset is safe: ``resolve_followed_tvdb`` still requires ONE follow to
       cover ALL the folder's episodes (coverage-all uniqueness is the real
       anti-collision guard), so a folder matching several Star Trek follows by
       title still only forces the one that grabbed exactly these episodes.

    Fail-soft: any error → ``False`` (abstain).
    """
    try:
        from rapidfuzz import fuzz  # noqa: PLC0415 — local import keeps module load light

        if fuzz.token_set_ratio(folder_name, follow_title) >= _TITLE_MATCH_THRESHOLD:
            return True
        folder_tokens = _title_tokens(folder_name)
        follow_tokens = _title_tokens(follow_title)
        return bool(folder_tokens) and folder_tokens <= follow_tokens
    except Exception:  # noqa: BLE001 — fail-soft: a fuzzy error must not force an id
        return False


def resolve_followed_tvdb(
    show_dir: Path,
    grabbed: list[WantedItem],
    follow_titles: dict[int, str],
    follow_years: dict[int, int | None] | None = None,
) -> int | None:
    """Resolve the follow's TVDB id for a staging show folder, or ``None``.

    Returns an id ONLY when exactly one followed series covers ALL the folder's
    episodes with grabbed wanted, matches the folder title, and (if the folder
    carries a year) agrees on the year. Any ambiguity, gap, mismatch, or error
    yields ``None`` — the caller free-matches (precision-first, fail-soft).

    Args:
        show_dir: The staging show directory (its files carry ``SxxEyy``).
        grabbed: Snapshot of ``grabbed`` wanted rows (episode kind, provider ids).
        follow_titles: Map ``followed_id -> title`` for the title guard.
        follow_years: Map ``followed_id -> year | None`` for the year guard
            (optional — absent/None disables the year check for that follow).

    Returns:
        The follow's TVDB series id, or ``None`` when it cannot be asserted.
    """
    years = follow_years or {}
    try:
        episodes = _folder_episodes(show_dir)
        if not episodes:
            return None
        folder_year = _folder_year(show_dir.name)

        # Group each followed series' grabbed (season, episode) set, keyed by its
        # tvdb id, keeping only follows whose title (and year, when present) match.
        by_tvdb: dict[int, set[tuple[int, int]]] = {}
        for item in grabbed:
            if item.kind != "episode" or item.season is None or item.episode is None:
                continue
            tvdb = item.media_ref.tvdb_id
            if tvdb is None or item.followed_id is None:
                continue
            title = follow_titles.get(item.followed_id)
            if not title or not _title_matches(show_dir.name, title):
                continue
            follow_year = years.get(item.followed_id)
            if folder_year is not None and follow_year is not None and folder_year != follow_year:
                continue  # different-year remake — not this show
            by_tvdb.setdefault(tvdb, set()).add((item.season, item.episode))

        # A follow QUALIFIES only if it covers EVERY episode in the folder — a
        # coincidental single shared episode cannot force the wrong show.
        qualifying = [tvdb for tvdb, eps in by_tvdb.items() if episodes <= eps]
        if len(qualifying) == 1:
            return qualifying[0]
        return None
    except Exception as exc:  # noqa: BLE001 — fail-soft: never block the scrape
        logger.warning("scrape_follow_tvdb_resolve_failed", error=str(exc))
        return None
