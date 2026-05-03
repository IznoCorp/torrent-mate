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
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.tmdb_client import TMDBClient

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
            if not sibling_nfo.exists() and not _EPISODE_FALLBACK_RE.match(ep_file.name):
                return False, f"episode_nfo_missing:{sibling_nfo.name}"

    return True, "ok"


class ExistingValidatorMixin:
    """Existing scrape validation and repair helper methods."""

    patterns: "NamingPatterns"
    dry_run: bool
    _tmdb: "TMDBClient"
    _artwork: "ArtworkDownloader"
    _generate_episode_nfos: Any  # from TvServiceMixin

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
        # Broad catch: get_movie() can raise TMDBError, CircuitOpenError, or requests
        # exceptions; download_movie_artwork() adds OSError. CircuitOpenError needs
        # a lazy import — narrowing this mixed path is not worthwhile here.
        try:
            movie_data = self._tmdb.get_movie(tmdb_id)
            downloaded = self._artwork.download_movie_artwork(
                movie_data,
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
        # Broad catch: get_tv() can raise TMDBError, CircuitOpenError, or requests
        # exceptions; download_tvshow_artwork() adds OSError. CircuitOpenError needs
        # a lazy import — narrowing this mixed path is not worthwhile here.
        try:
            show_data = self._tmdb.get_tv(tmdb_id)
            downloaded = self._artwork.download_tvshow_artwork(
                show_data,
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

        # 2. Collect organized episodes (SxxExx → set of (season, episode))
        organized: set[tuple[int, int]] = set()
        for season_dir in show_dir.iterdir():
            if season_dir.is_dir() and SEASON_DIR_RE.match(season_dir.name):
                for f in season_dir.iterdir():
                    if f.is_file():
                        m = _SXXEXX_RE.search(f.stem)
                        if m:
                            organized.add((int(m.group(1)), int(m.group(2))))

        # 3. Remove root MKV duplicates that match organized episodes
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

        # 3b. Organize new root video files for episodes NOT yet in any Saison XX/.
        # Collect all root video files that parse as SxxExx and are not duplicates.
        root_new: dict[tuple[int, int], list[Path]] = {}
        for f in list(show_dir.iterdir()):
            if not f.is_file() or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                continue
            m = _SXXEXX_RE.search(f.stem)
            if not m:
                continue
            key = (int(m.group(1)), int(m.group(2)))
            if key in organized:
                continue  # Already handled as duplicate in step 3
            root_new.setdefault(key, []).append(f)

        if root_new:
            nfo_path = show_dir / "tvshow.nfo"
            tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
            if not tmdb_id:
                log.warning("repair_root_episodes_no_tmdb_id", show=show_dir.name)
            else:
                try:
                    show_data = self._tmdb.get_tv(tmdb_id)
                    root_api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
                    for season in show_data.get("seasons", []):
                        s_num = season.get("season_number", 0)
                        if s_num == 0:
                            continue
                        # Only fetch seasons that have new root files
                        if not any(s == s_num for s, _ in root_new):
                            continue
                        try:
                            s_detail = self._tmdb.get_tv_season(tmdb_id, s_num)
                            for ep in s_detail.get("episodes", []):
                                e_num = ep.get("episode_number", 0)
                                root_api_episodes[(s_num, e_num)] = {
                                    "title": ep.get("name", f"Episode {e_num}"),
                                    "still_path": ep.get("still_path", ""),
                                }
                        except (OSError, ConnectionError, TimeoutError) as e:
                            log.warning("repair_season_fetch_failed", season=s_num, error=str(e))

                    for (s_num, e_num), candidates in root_new.items():
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
                                if not self.dry_run:
                                    try:
                                        old_f.unlink()
                                        log.info(
                                            "repair_duplicate_deleted",
                                            deleted=old_f.name,
                                            kept=keeper.name,
                                        )
                                        repaired = True
                                    except OSError as exc:
                                        log.warning(
                                            "repair_duplicate_delete_failed",
                                            filename=old_f.name,
                                            error=str(exc),
                                        )
                                else:
                                    log.info(
                                        "repair_duplicate_would_delete",
                                        deleted=old_f.name,
                                        kept=keeper.name,
                                    )
                                    repaired = True
                        else:
                            keeper = candidates[0]

                        # Rename and move keeper to Saison XX/
                        ep_info = root_api_episodes.get((s_num, e_num))
                        ep_title = ep_info["title"] if ep_info else f"Episode {e_num}"
                        season_dir_name = self.patterns.format("season_dir", Season=s_num)
                        new_stem = self.patterns.format(
                            "episode_video",
                            Season=s_num,
                            Episode=e_num,
                            EpisodeTitle=ep_title,
                        )
                        season_dir = show_dir / season_dir_name
                        dest = season_dir / f"{new_stem}{keeper.suffix}"
                        if not self.dry_run:
                            season_dir.mkdir(parents=True, exist_ok=True)
                            try:
                                keeper.rename(dest)
                                log.info(
                                    "repair_episode_moved",
                                    source=keeper.name,
                                    season_dir=season_dir_name,
                                    dest=dest.name,
                                )
                                repaired = True
                            except OSError as exc:
                                log.warning("repair_episode_move_failed", filename=keeper.name, error=str(exc))
                        else:
                            log.info(
                                "repair_episode_would_move",
                                source=keeper.name,
                                season_dir=season_dir_name,
                                dest=dest.name,
                            )
                            repaired = True

                    # Generate episode NFOs for moved files
                    root_moved: dict[Path, dict[str, Any]] = {}
                    for (s_num, e_num), candidates in root_new.items():
                        ep_info = root_api_episodes.get((s_num, e_num))
                        if ep_info is None:
                            continue
                        ep_title = ep_info["title"]
                        season_dir_name = self.patterns.format("season_dir", Season=s_num)
                        new_stem = self.patterns.format(
                            "episode_video",
                            Season=s_num,
                            Episode=e_num,
                            EpisodeTitle=ep_title,
                        )
                        suffix = candidates[0].suffix
                        dest = show_dir / season_dir_name / f"{new_stem}{suffix}"
                        root_moved[dest] = {
                            "season": s_num,
                            "episode": e_num,
                            "api_title": ep_title,
                            "still_path": ep_info.get("still_path", ""),
                        }
                    if root_moved and not self.dry_run:
                        self._generate_episode_nfos(root_moved, show_dir, show_data)

                except (OSError, ConnectionError, TimeoutError, ValueError, KeyError) as e:
                    log.warning("repair_root_episodes_failed", show=show_dir.name, exc_info=True, error=str(e))

        # 4. Organize unstructured episodes (from raw torrent dirs)
        # Finds video files in non-season subdirs (not root, not .actors)
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

        if unorganized:
            nfo_path = show_dir / "tvshow.nfo"
            tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
            if tmdb_id:
                try:
                    show_data = self._tmdb.get_tv(tmdb_id)
                    api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
                    for season in show_data.get("seasons", []):
                        s_num = season.get("season_number", 0)
                        if s_num == 0:
                            continue
                        try:
                            s_detail = self._tmdb.get_tv_season(
                                tmdb_id,
                                s_num,
                            )
                            for ep in s_detail.get("episodes", []):
                                e_num = ep.get("episode_number", 0)
                                api_episodes[(s_num, e_num)] = {
                                    "title": ep.get("name", f"Episode {e_num}"),
                                    "still_path": ep.get("still_path", ""),
                                }
                        except (OSError, ConnectionError, TimeoutError) as e:
                            log.warning("repair_season_fetch_failed", exc_info=True, season=s_num, error=str(e))

                    if api_episodes:
                        # Match local files to TMDB episodes BEFORE creating
                        # season directories so we only mkdir the seasons
                        # that actually receive a file.  Without this guard
                        # the scraper used to create every Saison NN that
                        # TMDB knew about (e.g. 16 dirs for Top Chef) only
                        # for the cleanup step to delete them all back
                        # immediately — wasted I/O + log noise on every
                        # incremental ingest of a long-running show.
                        matched = match_episode_files(
                            unorganized,
                            api_episodes,
                        )
                        if matched:
                            needed_seasons = sorted({info["season"] for info in matched.values()})
                            ep_list = [{"season_number": s, "episode_number": 0} for s in needed_seasons]
                            create_season_dirs(
                                show_dir,
                                ep_list,
                                self.patterns,
                                self.dry_run,
                            )
                            count = rename_episodes(
                                matched,
                                show_dir,
                                self.patterns,
                                self.dry_run,
                            )
                            if count > 0:
                                repaired = True
                                log.info("repair_episodes_organized", count=count, show=show_dir.name)
                            self._generate_episode_nfos(
                                matched,
                                show_dir,
                                show_data,
                            )

                except (OSError, ConnectionError, TimeoutError, ValueError, KeyError) as e:
                    log.warning("repair_organize_episodes_failed", show=show_dir.name, exc_info=True, error=str(e))
            else:
                log.warning("repair_organize_episodes_no_tmdb_id", show=show_dir.name)

        # Always clean residual torrent dirs (even if no unorganized episodes)
        if not self.dry_run:
            try:
                cleaned = _cleanup_empty_release_dirs(show_dir)
                if cleaned > 0:
                    repaired = True
            except OSError as exc:
                log.warning("repair_clean_release_dirs_failed", show=show_dir.name, error=str(exc))

        return repaired
