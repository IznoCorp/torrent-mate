"""Existing-scrape validation and repair services."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE, NamingPatterns

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.metadata.tvdb import TVDBClient
    from personalscraper.scraper.artwork import ArtworkDownloader

# DIRECT-mode capabilities (IDValidator, IDCrossRef) use ``registry.get("name")``
# (DESIGN §5.2) — this is the public API for ``Mode.DIRECT``. The return type is
# ``Named`` Protocol, so ``cast(...)`` unwraps either to a capability Protocol
# (preferred) or to the concrete client when the caller needs provider-specific
# methods outside the capability Protocol.
#
# Sub-phase 7.4 audit + sub-phase 17.3 migration (registry feature): every
# ``cast(...)`` site in this module is intentionally direct-dispatch — see the
# per-site rationale comments. All remaining sites fall into a single family:
# ID-bound canonical-provider refetch where the ID was minted by a specific
# provider (recorded in the NFO at scrape time) and any chain fallback would
# silently switch the canonical data source.
#
# The remaining sites are the Multi-method provider-specific sequences
# (``_repair_episode_files``, ``_repair_artwork``): they combine ``get_series``
# / ``get_tv`` with ``get_tv_season`` / ``get_series_episodes`` and helpers that
# consume the concrete client (``_fetch_season_episodes_tvdb``,
# ``_tvdb_series_to_show_data``). The Protocols in ``_contracts.py`` do not
# cover these methods → 4 sites keep ``cast("TMDBClient"|"TVDBClient", ...)``.
# These are the expected residual per DESIGN §5.2 (``Mode.DIRECT`` for methods
# without a capability Protocol).
#
# The single-call artwork refetch (``_recover_movie_artwork`` /
# ``_recover_tvshow_artwork``) was folded (P4.4, SCRAPER-09) into the ONE
# canonical-family helper ``_writeback.recover_artwork`` — resolving the
# provider from the item's canonical family (TVDB-primary for TV) rather than
# the TMDB-hardwired path — so those two cast sites now live there.

from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_sample_path
from personalscraper.nfo_utils import extract_nfo_metadata
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper._writeback import recover_artwork
from personalscraper.scraper.episode_manager import (
    _extract_season_episode,
    create_season_dirs,
    match_episode_files,
    rename_episodes,
)
from personalscraper.scraper.existing_validator_drift import (
    _episode_nfo_has_canonical_uniqueid,
    _infer_year_from_child_names,
    _local_show_seasons,
    _read_canonical_provider,
    verify_tvshow_scrape_drift,
)
from personalscraper.scraper.existing_validator_repair import (
    _build_root_moved_map,
    _dedup_and_move_root_episode,
    _fetch_season_episodes,
    _fetch_season_episodes_tvdb,
)
from personalscraper.scraper.rename_service import _cleanup_empty_release_dirs
from personalscraper.text_utils import sanitize_filename

log = get_logger("scraper")

_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)


def _coerce_numeric_nfo_id(raw: str | None, nfo_path: Path, family: str) -> int | None:
    """Coerce an NFO id string (from ``extract_nfo_metadata``) to ``int``.

    Shared by the TMDB/TVDB repair-id readers so the NFO is parsed through the
    single canonical parser (:func:`personalscraper.nfo_utils.extract_nfo_metadata`,
    SCRAPER-09) rather than a third bespoke ``ElementTree`` walk.

    Args:
        raw: Provider id text read from the NFO, or ``None`` when absent.
        nfo_path: Source NFO path (for the non-numeric warning log).
        family: Provider family label (``"tmdb"`` / ``"tvdb"``) for the log.

    Returns:
        The id as ``int``, or ``None`` when absent or non-numeric.
    """
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        log.warning("nfo_id_non_numeric", family=family, value=raw, path=str(nfo_path))
        return None


# Re-exports for backward compatibility (Phase 10 extraction).
__all__ = [
    "ExistingValidatorMixin",
    "_build_root_moved_map",
    "_dedup_and_move_root_episode",
    "_episode_nfo_has_canonical_uniqueid",
    "_fetch_season_episodes",
    "_fetch_season_episodes_tvdb",
    "_infer_year_from_child_names",
    "_local_show_seasons",
    "_read_canonical_provider",
    "verify_tvshow_scrape_drift",
]


class ExistingValidatorMixin:
    """Existing scrape validation and repair helper methods."""

    patterns: "NamingPatterns"
    dry_run: bool
    _registry: "ProviderRegistry"
    _artwork: "ArtworkDownloader"
    _generate_episode_nfos: Any  # from TvServiceNfoMixin (Phase 27.2 S3 extraction)

    def _repair_season_dir(self, show_dir: Path) -> tuple[set[tuple[int, int]], bool]:
        """Collect organised episodes and replace them when a new root duplicate exists.

        Iterates ``Saison XX/`` directories to build the ``organized`` mapping of
        already-organised ``(season, episode)`` tuples, then for every root-level
        video file that targets an already-organised episode, deletes the OLDER
        organised file and removes its key from ``organized`` so the caller's
        ``_repair_episode_files`` can move/rename the fresher root file into the
        season directory.

        Design contract (operator-confirmed 2026-05-21): the latest download
        ALWAYS supersedes a previously-organised file. A fresh root download is
        a deliberate operator action — typically a re-fetch to repair a corrupt
        or unreadable previous copy — so the root file is preserved and the
        organised file is the one removed. Earlier revisions of this method had
        the opposite semantics (root duplicate deleted) which silently lost the
        newer copy.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            Tuple of ``(organized_set, repaired_flag)``. The set contains the
            ``(season, episode)`` tuples STILL organised after replacement
            (i.e. without keys whose organised file was just removed in favour
            of a root duplicate). The flag is ``True`` when at least one
            organised file was removed to make room for a fresher root copy.
        """
        organized_files: dict[tuple[int, int], Path] = {}
        for season_dir in show_dir.iterdir():
            if season_dir.is_dir() and SEASON_DIR_RE.match(season_dir.name):
                for f in season_dir.iterdir():
                    if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
                        m = _SXXEXX_RE.search(f.stem)
                        if m:
                            organized_files[(int(m.group(1)), int(m.group(2)))] = f

        repaired = False
        if organized_files:
            for f in list(show_dir.iterdir()):
                if not f.is_file() or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                    continue
                if is_sample_path(f):
                    continue
                m = _SXXEXX_RE.search(f.stem)
                if not m:
                    continue
                key = (int(m.group(1)), int(m.group(2)))
                if key not in organized_files:
                    continue
                old_file = organized_files[key]
                if not self.dry_run:
                    try:
                        old_file.unlink()
                        log.info(
                            "repair_root_duplicate_replaced",
                            new=f.name,
                            removed=str(old_file.relative_to(show_dir)),
                        )
                    except OSError as exc:
                        log.warning(
                            "repair_root_duplicate_replace_failed",
                            old_file=old_file.name,
                            error=str(exc),
                        )
                        continue
                else:
                    log.info(
                        "repair_root_duplicate_would_replace",
                        new=f.name,
                        removed=str(old_file.relative_to(show_dir)),
                    )
                del organized_files[key]
                repaired = True

        return set(organized_files.keys()), repaired

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
            if is_sample_path(f):
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
                from personalscraper.scraper.models import ScraperExternalIds  # noqa: PLC0415
                from personalscraper.scraper.tv_service import _tvdb_series_to_show_data  # noqa: PLC0415

                # Direct-dispatch (sub-phase 7.4 audit): the NFO-stored TVDB id was
                # minted by TVDB, and this sequence calls ``get_series`` +
                # ``_fetch_season_episodes_tvdb`` (uses ``get_series_episodes``) which
                # are TVDB-specific and not covered by any capability Protocol in
                # ``_contracts.py``. Chain fallback would silently swap the canonical
                # data source — forbidden for ID-bound refetch.
                tvdb_client = cast("TVDBClient", self._registry.get("tvdb"))
                tvdb_data = tvdb_client.get_series(tvdb_id)
                external_ids = tvdb_data.external_ids if hasattr(tvdb_data, "external_ids") else {}
                imdb_id = external_ids.get("imdb") or ""
                show_data = _tvdb_series_to_show_data(
                    tvdb_data,
                    tvdb_id,
                    tvdb_client,
                    preferred_language="fr-FR",
                    fallback_language="en-US",
                    external_ids=ScraperExternalIds(tmdb_id=tmdb_id, imdb_id=imdb_id),
                )
                root_api_episodes = _fetch_season_episodes_tvdb(tvdb_client, tvdb_id, season_nums)
            else:
                assert tmdb_id is not None
                from personalscraper.scraper._movie_convert import _coerce_to_show_data

                # Direct-dispatch (sub-phase 7.4 audit): the NFO-stored TMDB id was
                # minted by TMDB, and ``_fetch_season_episodes`` calls TMDB-specific
                # ``get_tv_season`` — not in any capability Protocol. ID-bound
                # canonical refetch, chain fallback forbidden.
                tmdb_client = cast("TMDBClient", self._registry.get("tmdb"))
                show_data = _coerce_to_show_data(tmdb_client.get_tv(tmdb_id))
                root_api_episodes = _fetch_season_episodes(tmdb_client, tmdb_id, season_nums)

            _cfg = getattr(self, "config", None)
            allow_synthetic_rename = (
                _cfg is None or _cfg.metadata.episode_scraping_policy.allow_synthetic_rename_on_unmatched
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
            and not is_sample_path(f)
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
                from personalscraper.scraper.models import ScraperExternalIds  # noqa: PLC0415
                from personalscraper.scraper.tv_service import _tvdb_series_to_show_data  # noqa: PLC0415

                # Direct-dispatch (sub-phase 7.4 audit): mirror of
                # ``_repair_episode_files`` TVDB branch — TVDB-specific
                # ``get_series`` + ``_fetch_season_episodes_tvdb``
                # (``get_series_episodes``) not covered by any Protocol.
                # ID-bound canonical refetch, chain fallback forbidden.
                tvdb_client = cast("TVDBClient", self._registry.get("tvdb"))
                tvdb_data = tvdb_client.get_series(tvdb_id)
                external_ids = tvdb_data.external_ids if hasattr(tvdb_data, "external_ids") else {}
                imdb_id = external_ids.get("imdb") or ""
                show_data = _tvdb_series_to_show_data(
                    tvdb_data,
                    tvdb_id,
                    tvdb_client,
                    preferred_language="fr-FR",
                    fallback_language="en-US",
                    external_ids=ScraperExternalIds(tmdb_id=tmdb_id, imdb_id=imdb_id),
                )
                api_episodes = _fetch_season_episodes_tvdb(tvdb_client, tvdb_id, season_nums)
            else:
                assert tmdb_id is not None
                from personalscraper.scraper._movie_convert import _coerce_to_show_data

                # Direct-dispatch (sub-phase 7.4 audit): mirror of
                # ``_repair_episode_files`` TMDB branch — TMDB-specific
                # ``get_tv_season`` via ``_fetch_season_episodes`` not covered
                # by any Protocol. ID-bound canonical refetch, chain
                # fallback forbidden.
                tmdb_client = cast("TMDBClient", self._registry.get("tmdb"))
                show_data = _coerce_to_show_data(tmdb_client.get_tv(tmdb_id))
                api_episodes = _fetch_season_episodes(tmdb_client, tmdb_id, season_nums)

            if not api_episodes:
                return False

            # Honour the unmatched-episode policy in the repair path too —
            # otherwise the contract is enforced only on full scrapes and
            # bypassed on the (faster) repair path, leaving the Top Chef Le
            # Concours Parallèle S17 case mis-renamed.
            _cfg = getattr(self, "config", None)
            allow_synthetic_rename = (
                _cfg is None or _cfg.metadata.episode_scraping_policy.allow_synthetic_rename_on_unmatched
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
        """Extract the TMDB id from a valid NFO file.

        Reads the ``<uniqueid type="tmdb">`` value through the single canonical
        NFO parser (:func:`personalscraper.nfo_utils.extract_nfo_metadata`) and
        coerces it to ``int`` — no third bespoke parser (SCRAPER-09).

        Args:
            nfo_path: Path to the NFO file.

        Returns:
            TMDB id as ``int``, or ``None`` if absent or non-numeric.
        """
        raw = extract_nfo_metadata(nfo_path).get("tmdb_id")
        return _coerce_numeric_nfo_id(raw, nfo_path, "tmdb")

    @staticmethod
    def _extract_tvdb_id_from_nfo(nfo_path: Path) -> int | None:
        """Extract the TVDB id from a valid NFO file.

        TVDB is the primary scraper for TV shows (per ``metadata.json5``
        ``series_scraping`` priority), so the repair pass reads the TVDB
        ``<uniqueid>`` first and only falls back to TMDB when absent. Reads
        through the single canonical NFO parser
        (:func:`personalscraper.nfo_utils.extract_nfo_metadata`, SCRAPER-09).

        Args:
            nfo_path: Path to the NFO file.

        Returns:
            TVDB id as ``int``, or ``None`` if absent or non-numeric.
        """
        raw = extract_nfo_metadata(nfo_path).get("tvdb_id")
        return _coerce_numeric_nfo_id(raw, nfo_path, "tvdb")

    def _recover_movie_artwork(
        self,
        nfo_path: Path,
        movie_dir: Path,
        result: ScrapeResult,
    ) -> None:
        """Re-download missing movie artwork via the canonical (TMDB) family.

        Thin delegate to :func:`personalscraper.scraper._writeback.recover_artwork`
        — the single canonical-family recovery folded out of the two hand-synced
        copies (SCRAPER-09). Movies are always TMDB-canonical.

        Args:
            nfo_path: Path to the valid NFO file.
            movie_dir: Path to the movie directory.
            result: ScrapeResult to update with recovery info.
        """
        recover_artwork(
            nfo_path,
            movie_dir,
            result,
            kind="movie",
            registry=self._registry,
            artwork=self._artwork,
            patterns=self.patterns,
        )

    def _recover_tvshow_artwork(
        self,
        nfo_path: Path,
        show_dir: Path,
        result: ScrapeResult,
    ) -> None:
        """Re-download missing TV-show artwork from the item's canonical family.

        Thin delegate to :func:`personalscraper.scraper._writeback.recover_artwork`.
        Resolves the provider from the canonical family — TVDB-primary when the
        NFO carries a TVDB id, else TMDB — which is the F7 fix: a TVDB-only show
        (no TMDB id) now recovers its artwork instead of short-circuiting.

        Args:
            nfo_path: Path to the valid tvshow.nfo file.
            show_dir: Path to the TV show directory.
            result: ScrapeResult to update with recovery info.
        """
        recover_artwork(
            nfo_path,
            show_dir,
            result,
            kind="tvshow",
            registry=self._registry,
            artwork=self._artwork,
            patterns=self.patterns,
        )

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
