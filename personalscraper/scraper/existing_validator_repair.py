"""Repair helpers extracted from existing_validator.py (Phase 10)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns

if TYPE_CHECKING:
    from personalscraper.api.metadata._base import EpisodeInfo
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.metadata.tvdb import TVDBClient

log = get_logger("scraper")


def _repair_episode_payload(ep: "EpisodeInfo") -> dict[str, Any]:
    """Build a repair-path episode payload, including per-episode provider IDs.

    Mirrors :func:`personalscraper.scraper.tv_service_episodes._episode_payload`:
    the ``{provider}_episode_id`` keys are what reach the NFO writer as the
    episode ``<uniqueid>`` elements. Omitting them (the pre-0.35.1 repair bug)
    produced repaired episode NFOs with no canonical ``<uniqueid>``, which fails
    verify's ``EpisodeCanonicalUniqueidPresent`` check.

    Args:
        ep: Episode parsed from a TMDB / TVDB season response.

    Returns:
        Dict with the display title, the still-path placeholder, and the
        per-provider episode IDs surfaced by the parser.
    """
    payload: dict[str, Any] = {
        "title": ep.title or f"Episode {ep.episode_number}",
        "still_path": "",
    }
    for provider, value in ep.external_ids.items():
        if not value:
            continue
        payload[f"{provider}_episode_id"] = value
    return payload


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
                api_episodes[(s_num, e_num)] = _repair_episode_payload(ep)
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
                api_episodes[(s_num, e_num)] = _repair_episode_payload(ep)
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
