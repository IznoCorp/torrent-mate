"""Existing-scrape validation and repair services."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any

from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE, NamingPatterns

if TYPE_CHECKING:
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.metadata.tvdb import TVDBClient
    from personalscraper.scraper.artwork import ArtworkDownloader

from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.episode_manager import (
    _extract_season_episode,
    create_season_dirs,
    match_episode_files,
    rename_episodes,
)
from personalscraper.scraper.rename_service import _cleanup_empty_release_dirs
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS
from personalscraper.text_utils import media_processor, sanitize_filename

log = get_logger("scraper")

_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
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


def _fetch_season_episodes(
    tmdb: "TMDBClient",
    tmdb_id: int,
    season_numbers: list[int],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Fetch TMDB episode data for one or more seasons.

    Args:
        tmdb: TMDBClient instance.
        tmdb_id: TMDB series ID.
        season_numbers: List of season numbers to fetch.

    Returns:
        Dict mapping ``(season, episode)`` to ``{"title", "still_path"}``.
        May be empty when all seasons failed to fetch or had no episodes.
    """
    api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
    for s_num in season_numbers:
        if s_num == 0:
            continue
        try:
            s_detail = tmdb.get_tv_season(tmdb_id, s_num)
            for ep in s_detail.episodes:
                e_num = ep.episode_number
                api_episodes[(s_num, e_num)] = {
                    "title": ep.title or f"Episode {e_num}",
                    "still_path": "",
                }
        except (OSError, ConnectionError, TimeoutError) as e:
            log.warning("repair_season_fetch_failed", season=s_num, error=str(e))
    return api_episodes


def _fetch_season_episodes_tvdb(
    tvdb: "TVDBClient",
    tvdb_id: int,
    season_numbers: list[int],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Fetch TVDB episode data for one or more seasons.

    TVDB-primary mirror of :func:`_fetch_season_episodes`. Used by the repair
    pass when a show was scraped via TVDB-only (no TMDB id in NFO).

    Args:
        tvdb: TVDBClient instance.
        tvdb_id: TVDB series ID.
        season_numbers: List of season numbers to fetch.

    Returns:
        Dict mapping ``(season, episode)`` to ``{"title", "still_path"}``.
    """
    api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
    for s_num in season_numbers:
        if s_num == 0:
            continue
        try:
            s_detail = tvdb.get_series_episodes(tvdb_id, s_num)
            for ep in s_detail.episodes:
                e_num = ep.episode_number
                api_episodes[(s_num, e_num)] = {
                    "title": ep.title or f"Episode {e_num}",
                    "still_path": "",
                }
        except (OSError, ConnectionError, TimeoutError) as e:
            log.warning("repair_season_fetch_failed_tvdb", season=s_num, error=str(e))
    return api_episodes


def _dedup_and_move_root_episode(
    show_dir: Path,
    s_num: int,
    e_num: int,
    candidates: list[Path],
    root_api_episodes: dict[tuple[int, int], dict[str, Any]],
    patterns: NamingPatterns,
    dry_run: bool,
    allow_synthetic_rename: bool = True,
) -> bool:
    """Deduplicate and move a root-level episode into its season directory.

    When multiple files match the same ``(season, episode)``, keeps the
    newest by mtime and deletes the rest. The keeper is then renamed using
    the naming patterns and moved into ``Saison XX/``.

    Args:
        show_dir: Path to the TV show directory.
        s_num: Season number.
        e_num: Episode number.
        candidates: List of file paths matching this (s_num, e_num).
        root_api_episodes: Dict from ``_fetch_season_episodes()``.
        patterns: NamingPatterns for file and directory naming.
        dry_run: If True, log actions without making changes.
        allow_synthetic_rename: When ``False`` (default contract per
            ``metadata.episode_scraping_policy.allow_synthetic_rename_on_unmatched``)
            AND the provider has no record for ``(s_num, e_num)``, the
            file is LEFT at the show root with its raw filename
            instead of being moved with a synthetic ``"Episode N"``
            title. Pinned by the Top Chef Le Concours Parallèle S17
            integration case.

    Returns:
        True if any repair was applied (file deleted or moved).
    """
    # Unmatched-episode policy gate (DESIGN scraping.md §Unmatched
    # Episode Policy). When the provider catalog has no entry for this
    # (season, episode) AND synthetic rename is disabled, leave the
    # file at the root and log for observability.
    if not allow_synthetic_rename and (s_num, e_num) not in root_api_episodes:
        log.warning(
            "episode_unmatched_no_rename",
            filename=candidates[0].name,
            season=s_num,
            episode=e_num,
            available_seasons=sorted({s for s, _ in root_api_episodes}),
        )
        return False

    repaired = False

    # Dedup: keep newest by mtime, delete older ones
    if len(candidates) > 1:
        candidates_sorted = sorted(
            candidates,
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        to_delete = candidates_sorted[1:]
        keeper = candidates_sorted[0]
        for old_f in to_delete:
            if not dry_run:
                try:
                    old_f.unlink()
                    log.info("repair_duplicate_deleted", deleted=old_f.name, kept=keeper.name)
                    repaired = True
                except OSError as exc:
                    log.warning("repair_duplicate_delete_failed", filename=old_f.name, error=str(exc))
            else:
                log.info("repair_duplicate_would_delete", deleted=old_f.name, kept=keeper.name)
                repaired = True
    else:
        keeper = candidates[0]

    # Rename and move keeper to Saison XX/
    ep_info = root_api_episodes.get((s_num, e_num))
    ep_title = ep_info["title"] if ep_info else f"Episode {e_num}"
    season_dir_name = patterns.format("season_dir", Season=s_num)
    new_stem = patterns.format("episode_video", Season=s_num, Episode=e_num, EpisodeTitle=ep_title)
    season_dir = show_dir / season_dir_name
    dest = season_dir / f"{new_stem}{keeper.suffix}"
    if not dry_run:
        season_dir.mkdir(parents=True, exist_ok=True)
        try:
            keeper.rename(dest)
            log.info("repair_episode_moved", source=keeper.name, season_dir=season_dir_name, dest=dest.name)
            repaired = True
        except OSError as exc:
            log.warning("repair_episode_move_failed", filename=keeper.name, error=str(exc))
    else:
        log.info("repair_episode_would_move", source=keeper.name, season_dir=season_dir_name, dest=dest.name)
        repaired = True

    return repaired


def _build_root_moved_map(
    root_new: dict[tuple[int, int], list[Path]],
    root_api_episodes: dict[tuple[int, int], dict[str, Any]],
    show_dir: Path,
    patterns: NamingPatterns,
) -> dict[Path, dict[str, Any]]:
    """Build a map of destination paths to episode info for NFO generation.

    Constructs a dict compatible with ``_generate_episode_nfos()`` from the
    root-new dictionary and API episode data.

    Args:
        root_new: Dict mapping ``(season, episode)`` to candidate file list.
        root_api_episodes: Dict from ``_fetch_season_episodes()``.
        show_dir: Path to the TV show directory.
        patterns: NamingPatterns for file naming.

    Returns:
        Dict mapping destination ``Path`` to episode info dict, or empty
        when no API episode data is available for any entry.
    """
    root_moved: dict[Path, dict[str, Any]] = {}
    for (s_num, e_num), candidates in root_new.items():
        ep_info = root_api_episodes.get((s_num, e_num))
        if ep_info is None:
            continue
        ep_title = ep_info["title"]
        season_dir_name = patterns.format("season_dir", Season=s_num)
        new_stem = patterns.format("episode_video", Season=s_num, Episode=e_num, EpisodeTitle=ep_title)
        suffix = candidates[0].suffix
        dest = show_dir / season_dir_name / f"{new_stem}{suffix}"
        root_moved[dest] = {
            "season": s_num,
            "episode": e_num,
            "api_title": ep_title,
            "still_path": ep_info.get("still_path", ""),
        }
    return root_moved


class ExistingValidatorMixin:
    """Existing scrape validation and repair helper methods."""

    patterns: "NamingPatterns"
    dry_run: bool
    _tmdb: "TMDBClient"
    _tvdb: "TVDBClient"
    _artwork: "ArtworkDownloader"
    _generate_episode_nfos: Any  # from TvServiceMixin

    def _repair_season_dir(self, show_dir: Path) -> tuple[set[tuple[int, int]], bool]:
        """Collect organised episodes and remove root duplicates.

        Iterates ``Saison XX/`` directories to build a set of already-organised
        ``(season, episode)`` tuples, then deletes (or logs deletion of) root-level
        video files that duplicate an already-organised episode.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            Tuple of ``(organized_set, repaired_flag)``. The set contains
            ``(season, episode)`` for every episode already inside a season
            directory. The flag is ``True`` when at least one root duplicate
            was removed.
        """
        organized: set[tuple[int, int]] = set()
        for season_dir in show_dir.iterdir():
            if season_dir.is_dir() and SEASON_DIR_RE.match(season_dir.name):
                for f in season_dir.iterdir():
                    if f.is_file():
                        m = _SXXEXX_RE.search(f.stem)
                        if m:
                            organized.add((int(m.group(1)), int(m.group(2))))

        repaired = False
        if organized:
            for f in list(show_dir.iterdir()):
                if not f.is_file() or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                    continue
                m = _SXXEXX_RE.search(f.stem)
                if m and (int(m.group(1)), int(m.group(2))) in organized:
                    if not self.dry_run:
                        try:
                            f.unlink()
                            log.info("repair_root_duplicate_removed", filename=f.name)
                            repaired = True
                        except OSError as exc:
                            log.warning("repair_root_duplicate_delete_failed", filename=f.name, error=str(exc))
                    else:
                        log.info("repair_root_duplicate_would_remove", filename=f.name)
                        repaired = True

        return organized, repaired

    def _repair_episode_files(
        self,
        show_dir: Path,
        organized: set[tuple[int, int]],
    ) -> bool:
        """Organise new root-level video files into season directories.

        Finds video files at the show root that parse as ``SxxExx`` but are
        not yet in any ``Saison XX/`` directory, fetches TMDB episode data,
        deduplicates, renames, and moves them into place. Generates episode
        NFOs for moved files.

        Args:
            show_dir: Path to the TV show directory.
            organized: Set of already-organised ``(season, episode)`` tuples.

        Returns:
            True if any repair was applied.
        """
        root_new: dict[tuple[int, int], list[Path]] = {}
        for f in list(show_dir.iterdir()):
            if not f.is_file() or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                continue
            m = _SXXEXX_RE.search(f.stem)
            if not m:
                continue
            key = (int(m.group(1)), int(m.group(2)))
            if key in organized:
                continue
            root_new.setdefault(key, []).append(f)

        if not root_new:
            return False

        nfo_path = show_dir / "tvshow.nfo"
        # TV-show repair must read TVDB id first (primary scraper for series per
        # series_scraping priority); TMDB is the fallback when the NFO carries
        # no TVDB id. Bailing out on a missing TMDB id alone would block every
        # TVDB-only show from being repaired.
        tvdb_id = self._extract_tvdb_id_from_nfo(nfo_path)
        tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
        if not tvdb_id and not tmdb_id:
            log.warning("repair_root_episodes_no_id", show=show_dir.name)
            return False

        repaired = False
        try:
            season_nums = sorted({s for s, _ in root_new if s > 0})
            if tvdb_id:
                # Lazy import: tv_service imports from this module, so a top-level
                # import would be circular. The conversion is needed because
                # ``_generate_episode_nfos`` consumes show_data as a dict.
                from personalscraper.scraper.tv_service import _tvdb_series_to_show_data

                tvdb_data = self._tvdb.get_series(tvdb_id)
                external_ids = tvdb_data.external_ids if hasattr(tvdb_data, "external_ids") else {}
                imdb_id = external_ids.get("imdb") or ""
                show_data = _tvdb_series_to_show_data(
                    tvdb_data,
                    tvdb_id,
                    self._tvdb,
                    tmdb_id=tmdb_id or 0,
                    imdb_id=imdb_id,
                    preferred_language="fr-FR",
                    fallback_language="en-US",
                )
                root_api_episodes = _fetch_season_episodes_tvdb(self._tvdb, tvdb_id, season_nums)
            else:
                assert tmdb_id is not None
                from personalscraper.scraper.movie_service import _coerce_to_show_data

                show_data = _coerce_to_show_data(self._tmdb.get_tv(tmdb_id))
                root_api_episodes = _fetch_season_episodes(self._tmdb, tmdb_id, season_nums)

            allow_synthetic_rename = (
                getattr(self, "config", None) is None
                or self.config.metadata.episode_scraping_policy.allow_synthetic_rename_on_unmatched
            )
            for (s_num, e_num), candidates in root_new.items():
                if _dedup_and_move_root_episode(
                    show_dir,
                    s_num,
                    e_num,
                    candidates,
                    root_api_episodes,
                    self.patterns,
                    self.dry_run,
                    allow_synthetic_rename=allow_synthetic_rename,
                ):
                    repaired = True

            root_moved = _build_root_moved_map(root_new, root_api_episodes, show_dir, self.patterns)
            if root_moved and not self.dry_run:
                self._generate_episode_nfos(root_moved, show_dir, show_data)
        except (OSError, ConnectionError, TimeoutError, ValueError, KeyError) as e:
            log.warning("repair_root_episodes_failed", show=show_dir.name, exc_info=True, error=str(e))

        return repaired

    def _repair_artwork(self, show_dir: Path) -> bool:
        """Organise unstructured episodes from non-season subdirectories.

        Finds video files in non-season subdirectories (raw torrent dirs),
        fetches TMDB episode data, matches local files to episodes, renames
        and moves them into proper season directories, and generates per-episode
        NFO files.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            True if any repair was applied.
        """
        unorganized = sorted(
            f
            for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not SEASON_DIR_RE.match(f.parent.name)
            and f.parent != show_dir
            and ".actors" not in f.parts
            and "Trailers" not in f.parts
        )

        if not unorganized:
            return False

        nfo_path = show_dir / "tvshow.nfo"
        # TVDB-primary repair (see ``_repair_episode_files`` for the rationale).
        tvdb_id = self._extract_tvdb_id_from_nfo(nfo_path)
        tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
        if not tvdb_id and not tmdb_id:
            log.warning("repair_organize_episodes_no_id", show=show_dir.name)
            return False

        try:
            # Discover season numbers from the local filesystem. Saison NN/ dirs
            # are the canonical source; when the show is still in raw torrent
            # layout (no Saison NN/ yet), infer seasons from SxxEyy patterns in
            # the unorganized files so the repair can bootstrap the structure.
            season_nums = sorted(
                {
                    int(m.group(1))
                    for d in show_dir.iterdir()
                    if d.is_dir() and (m := SEASON_DIR_RE.match(d.name))
                    if int(m.group(1)) > 0
                }
            )
            if not season_nums:
                season_nums = sorted(
                    {s for s in (_extract_season_episode(f.name)[0] for f in unorganized) if s is not None and s > 0}
                )
            if tvdb_id:
                from personalscraper.scraper.tv_service import _tvdb_series_to_show_data

                tvdb_data = self._tvdb.get_series(tvdb_id)
                external_ids = tvdb_data.external_ids if hasattr(tvdb_data, "external_ids") else {}
                imdb_id = external_ids.get("imdb") or ""
                show_data = _tvdb_series_to_show_data(
                    tvdb_data,
                    tvdb_id,
                    self._tvdb,
                    tmdb_id=tmdb_id or 0,
                    imdb_id=imdb_id,
                    preferred_language="fr-FR",
                    fallback_language="en-US",
                )
                api_episodes = _fetch_season_episodes_tvdb(self._tvdb, tvdb_id, season_nums)
            else:
                assert tmdb_id is not None
                from personalscraper.scraper.movie_service import _coerce_to_show_data

                show_data = _coerce_to_show_data(self._tmdb.get_tv(tmdb_id))
                api_episodes = _fetch_season_episodes(self._tmdb, tmdb_id, season_nums)

            if not api_episodes:
                return False

            # Honour the unmatched-episode policy in the repair path too —
            # otherwise the contract is enforced only on full scrapes and
            # bypassed on the (faster) repair path, leaving the Top Chef Le
            # Concours Parallèle S17 case mis-renamed.
            allow_synthetic_rename = (
                getattr(self, "config", None) is None
                or self.config.metadata.episode_scraping_policy.allow_synthetic_rename_on_unmatched
            )
            matched = match_episode_files(
                unorganized,
                api_episodes,
                allow_synthetic_rename=allow_synthetic_rename,
            )
            if not matched:
                return False

            needed_seasons = sorted({info["season"] for info in matched.values()})
            ep_list = [{"season_number": s, "episode_number": 0} for s in needed_seasons]
            create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
            count = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
            if count > 0:
                log.info("repair_episodes_organized", count=count, show=show_dir.name)
            self._generate_episode_nfos(matched, show_dir, show_data)
            return count > 0
        except (OSError, ConnectionError, TimeoutError, ValueError, KeyError) as e:
            log.warning("repair_organize_episodes_failed", show=show_dir.name, exc_info=True, error=str(e))
            return False

    def _check_missing_movie_artwork(self, movie_dir: Path, title: str) -> list[str]:
        """List missing essential artwork for a movie directory.

        Checks poster and landscape only (the two files required by
        the fast-skip gate in _has_unscraped_items).

        Args:
            movie_dir: Path to the movie directory.
            title: Movie title for filename patterns.

        Returns:
            List of missing artwork filenames. Empty if both present.
        """
        missing = []
        poster = self.patterns.format("movie_poster", Title=title)
        if not (movie_dir / poster).exists():
            missing.append(poster)
        landscape = self.patterns.format("movie_landscape", Title=title)
        if not (movie_dir / landscape).exists():
            missing.append(landscape)
        return missing

    def _check_missing_tvshow_artwork(self, show_dir: Path) -> list[str]:
        """List missing essential artwork for a TV show directory.

        Checks show-level poster/landscape and season posters for seasons
        already present on disk.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            List of missing artwork filenames. Empty if both present.
        """
        missing = []
        if not (show_dir / self.patterns.tvshow_poster).exists():
            missing.append(self.patterns.tvshow_poster)
        if not (show_dir / self.patterns.tvshow_landscape).exists():
            missing.append(self.patterns.tvshow_landscape)
        for season_dir in show_dir.iterdir():
            if not season_dir.is_dir() or not SEASON_DIR_RE.match(season_dir.name):
                continue
            season_num = int(season_dir.name.split()[-1])
            poster_name = self.patterns.format("season_poster", Season=season_num)
            if not (show_dir / poster_name).exists():
                missing.append(poster_name)
        return missing

    @staticmethod
    def _extract_tmdb_id_from_nfo(nfo_path: Path) -> int | None:
        """Extract TMDB ID from a valid NFO file.

        Parses the NFO XML and finds the first <uniqueid type="tmdb">
        element with a numeric value.

        Args:
            nfo_path: Path to the NFO file (must exist and be valid XML).

        Returns:
            TMDB ID as int, or None if not found or not numeric.
        """
        try:
            root = ET.parse(nfo_path).getroot()  # noqa: S314
        except (ET.ParseError, OSError) as exc:
            log.warning("nfo_parse_failed", filename=nfo_path.name, error=str(exc))
            return None
        for uid in root.findall("uniqueid"):
            if uid.get("type") == "tmdb" and uid.text:
                try:
                    return int(uid.text)
                except ValueError:
                    log.warning("nfo_tmdb_id_non_numeric", tmdb_id=uid.text, path=str(nfo_path))
                    return None
        log.debug("nfo_no_tmdb_id", path=str(nfo_path))
        return None

    @staticmethod
    def _extract_tvdb_id_from_nfo(nfo_path: Path) -> int | None:
        """Extract TVDB ID from a valid NFO file.

        TVDB is the primary scraper for TV shows (per ``metadata.json5``
        ``series_scraping`` priority), so the repair pass must read the TVDB
        ``<uniqueid>`` first and only fall back to TMDB when absent.

        Args:
            nfo_path: Path to the NFO file (must exist and be valid XML).

        Returns:
            TVDB ID as int, or None if not found or not numeric.
        """
        try:
            root = ET.parse(nfo_path).getroot()  # noqa: S314
        except (ET.ParseError, OSError) as exc:
            log.warning("nfo_parse_failed", filename=nfo_path.name, error=str(exc))
            return None
        for uid in root.findall("uniqueid"):
            if uid.get("type") == "tvdb" and uid.text:
                try:
                    return int(uid.text)
                except ValueError:
                    log.warning("nfo_tvdb_id_non_numeric", tvdb_id=uid.text, path=str(nfo_path))
                    return None
        log.debug("nfo_no_tvdb_id", path=str(nfo_path))
        return None

    def _recover_movie_artwork(
        self,
        nfo_path: Path,
        movie_dir: Path,
        result: ScrapeResult,
    ) -> None:
        """Re-download missing artwork using TMDB ID from existing NFO.

        Extracts the TMDB ID, fetches movie data, and downloads artwork
        (existing files are automatically skipped by the downloader).

        Args:
            nfo_path: Path to the valid NFO file.
            movie_dir: Path to the movie directory.
            result: ScrapeResult to update with recovery info.
        """
        tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
        if not tmdb_id:
            return
        # Broad catch: get_movie() can raise ApiError, CircuitOpenError, or requests
        # exceptions; download_movie_artwork() adds OSError. CircuitOpenError needs
        # a lazy import — narrowing this mixed path is not worthwhile here.
        try:
            from personalscraper.scraper.movie_service import _coerce_to_movie_data

            movie_data = self._tmdb.get_movie(tmdb_id)
            downloaded = self._artwork.download_movie_artwork(
                _coerce_to_movie_data(movie_data),
                movie_dir,
                self.patterns,
            )
            if downloaded:
                result.action = "artwork_recovered"
                result.artwork_downloaded = [p.name for p in downloaded]
                log.info("artwork_recovered", count=len(downloaded), directory=movie_dir.name)
        except Exception as e:  # noqa: BLE001 — see block comment above
            log.warning("artwork_recovery_failed", directory=movie_dir.name, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork recovery failed: {e}")

    def _recover_tvshow_artwork(
        self,
        nfo_path: Path,
        show_dir: Path,
        result: ScrapeResult,
    ) -> None:
        """Re-download missing artwork for a TV show using NFO TMDB ID.

        Extracts the TMDB ID, fetches show data, and downloads artwork
        (existing files are automatically skipped by the downloader).

        Args:
            nfo_path: Path to the valid tvshow.nfo file.
            show_dir: Path to the TV show directory.
            result: ScrapeResult to update with recovery info.
        """
        tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
        if not tmdb_id:
            return
        # Broad catch: get_tv() can raise ApiError, CircuitOpenError, or requests
        # exceptions; download_tvshow_artwork() adds OSError. CircuitOpenError needs
        # a lazy import — narrowing this mixed path is not worthwhile here.
        try:
            from personalscraper.scraper.movie_service import _coerce_to_show_data

            show_data = self._tmdb.get_tv(tmdb_id)
            downloaded = self._artwork.download_tvshow_artwork(
                _coerce_to_show_data(show_data),
                show_dir,
                self.patterns,
            )
            if downloaded:
                result.action = "artwork_recovered"
                result.artwork_downloaded = [p.name for p in downloaded]
                log.info("artwork_recovered", count=len(downloaded), directory=show_dir.name)
        except Exception as e:  # noqa: BLE001 — mixed API+IO path; see comment above
            log.warning("artwork_recovery_failed", directory=show_dir.name, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork recovery failed: {e}")

    def _repair_movie_dir(self, movie_dir: Path, title: str) -> bool:
        """Repair a movie directory with valid NFO.

        Removes residual NFOs (keeps only {sanitized_title}.nfo).
        Does not re-scrape or re-match.

        Args:
            movie_dir: Path to the movie directory.
            title: Parsed movie title from folder name.

        Returns:
            True if any repair was applied.
        """
        repaired = False
        expected_nfo = sanitize_filename(title) + ".nfo"

        for nfo in movie_dir.glob("*.nfo"):
            if nfo.name != expected_nfo:
                if not self.dry_run:
                    try:
                        nfo.unlink()
                        log.info("repair_residual_nfo_removed", filename=nfo.name)
                        repaired = True
                    except OSError as exc:
                        log.warning("repair_residual_nfo_delete_failed", filename=nfo.name, error=str(exc))
                else:
                    log.info("repair_residual_nfo_would_remove", filename=nfo.name)
                    repaired = True

        return repaired

    def _verify_existing_scrape(self, show_dir: Path, nfo_path: Path) -> tuple[bool, str]:
        """Thin wrapper over ``verify_tvshow_scrape_drift``.

        Kept as an instance method so existing call sites keep threading
        ``self.patterns`` through the class.

        Args:
            show_dir: Path to the TV show directory.
            nfo_path: Path to ``tvshow.nfo``.

        Returns:
            ``(is_valid, reason)`` — see ``verify_tvshow_scrape_drift``.
        """
        return verify_tvshow_scrape_drift(show_dir, nfo_path, self.patterns)

    def _repair_tvshow_dir(self, show_dir: Path) -> bool:
        """Repair a TV show directory with valid NFO.

        1. Remove residual NFOs at root (keep only tvshow.nfo).
        2. Remove root MKV duplicates (same SxxExx in Saison XX/).
        3. Organize new root episodes not yet in Saison XX/ (if TMDB ID available).
           Dedup rule: when multiple root files match the same SxxExx, keep the
           newest by mtime and delete the others before organizing.
        4. Organize unstructured episodes from non-season subdirs (if TMDB ID available).

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            True if any repair was applied.
        """
        repaired = False

        # 1. Remove residual NFOs at root (keep tvshow.nfo)
        for nfo in show_dir.glob("*.nfo"):
            if nfo.name != "tvshow.nfo":
                if not self.dry_run:
                    try:
                        nfo.unlink()
                        log.info("repair_residual_nfo_removed", filename=nfo.name, show=show_dir.name)
                        repaired = True
                    except OSError as exc:
                        log.warning("repair_residual_nfo_delete_failed", filename=nfo.name, error=str(exc))
                else:
                    log.info("repair_residual_nfo_would_remove", filename=nfo.name)
                    repaired = True

        # 2 + 3. Collect organised episodes from season dirs + remove root duplicates
        organized, season_repaired = self._repair_season_dir(show_dir)
        if season_repaired:
            repaired = True

        # 3b. Organise new root video files into season dirs
        if self._repair_episode_files(show_dir, organized):
            repaired = True

        # 4. Organise unstructured episodes from non-season subdirs
        if self._repair_artwork(show_dir):
            repaired = True

        # Always clean residual torrent dirs (even if no unorganized episodes)
        if not self.dry_run:
            try:
                cleaned = _cleanup_empty_release_dirs(show_dir)
                if cleaned > 0:
                    repaired = True
            except OSError as exc:
                log.warning("repair_clean_release_dirs_failed", show=show_dir.name, error=str(exc))

        return repaired
