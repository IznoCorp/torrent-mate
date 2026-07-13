"""TV show scraper — canonical write + operator-forced resolve.

Split out of :mod:`personalscraper.scraper.tv_service` to keep both modules
under the 1000-LOC hard ceiling (``scripts/check-module-size.py``). Holds the
canonical show-write (:meth:`TvServiceWriteMixin._write_confirmed_show`) shared
by the automatic scrape and the forced resolve, plus the forced-resolve entry
points (:meth:`scrape_tvshow_forced` / :meth:`_forced_series_lookup`) that let a
manual resolution reuse the SAME complete write as the automatic scrape — folder
rename, episode rename, per-episode NFOs and artwork — instead of the previous
NFO-only write that left episodes unrenamed and ``verify`` blocking dispatch.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from personalscraper.api._contracts import MediaType
from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_sample_path
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.scraper._drift_persistence import DriftIssueStore
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper._tvdb_convert import fetch_show_data
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.rename_service import (
    _cleanup_empty_release_dirs,
    _cleanup_stale_files,
    _merge_dirs,
    _rename_dir_case_safe,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.conf.models.config import Config
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.confidence import MatchResult
    from personalscraper.scraper.nfo_generator import NFOGenerator

log = get_logger("scraper")


class TvServiceWriteMixin:
    """Canonical TV-show write + operator-forced resolve entry points.

    Composed into :class:`~personalscraper.scraper.orchestrator.Scraper`
    alongside the other scraper mixins via multiple inheritance. Declares the
    cross-mixin attributes/methods it consumes so mypy resolves them (the
    established mixin pattern — see :class:`TvServiceMixin`).
    """

    patterns: "NamingPatterns"
    dry_run: bool
    config: "Config | None"
    _registry: "ProviderRegistry"
    _scraper_language: str
    _scraper_fallback_language: str
    _nfo: "NFOGenerator"
    _artwork: "ArtworkDownloader"
    _classify_item: "Callable[..., str | None]"
    _resolve_title: "Callable[..., str]"
    _strip_trailing_year: "Callable[[str], str]"
    _build_episode_map: Any
    _xref_enrichment: Any
    _match_seasons: Any

    def _write_confirmed_show(
        self,
        show_dir: Path,
        match: "MatchResult",
        show_data: dict[str, Any],
        tmdb_id: int | None,
        resolved_title: str,
        title: str,
        year: int | None,
        result: ScrapeResult,
        *,
        drift_rescrape_episode_nfo: bool,
    ) -> ScrapeResult:
        """Apply a confirmed TV-show match to the folder (rename + NFO + episodes + artwork).

        The canonical write shared by the automatic scrape
        (:meth:`~personalscraper.scraper.tv_service.TvServiceMixin.scrape_tvshow`,
        after a confident/selected match) and the operator-forced resolve
        (:meth:`scrape_tvshow_forced`). Renames the folder to ``Show (Year)``,
        classifies the category, writes ``tvshow.nfo``, sweeps episodes into
        ``Saison NN/`` with canonical names + per-episode NFOs, and downloads
        artwork — exactly the shape ``verify`` and dispatch expect. Extracted
        verbatim from ``scrape_tvshow`` so a manual resolution produces an
        identical, complete result instead of a partial NFO-only write.

        Args:
            show_dir: The show's staging directory (pre-rename).
            match: The confirmed :class:`MatchResult` (provider id/title/year/source).
            show_data: Provider show details (legacy TMDB-shaped dict).
            tmdb_id: Cross-referenced TMDB id (``None`` for a TVDB-only show).
            resolved_title: Local/canonical title chosen for the folder name.
            title: Parsed (possibly episode-recovered) folder title.
            year: Parsed/inferred show year (fallback when the API omits one).
            result: The :class:`ScrapeResult` to populate and return.
            drift_rescrape_episode_nfo: When True, ALSO re-sweep episodes already
                in ``Saison NN/`` so per-episode NFOs are regenerated (a forced
                resolve always passes True; ``rename_episodes`` is idempotent).

        Returns:
            The populated :class:`ScrapeResult` (``action="scraped"`` on success).
        """
        # Rename folder to canonical name
        old_dir_name = show_dir.name  # Save before potential rename
        canonical = self.patterns.format(
            "movie_dir",
            Title=resolved_title,
            Year=match.api_year or year or "",
        )
        # NFC-compare: macOS stores filenames in NFD, Python strings are typically
        # NFC; a naive string compare treats them as different and triggers a
        # rename-into-self merge that empties the folder. See
        # ``verify_tvshow_scrape_drift`` for the matching normalization on the
        # read side.
        if unicodedata.normalize("NFC", show_dir.name) != unicodedata.normalize("NFC", canonical):
            new_dir = show_dir.parent / canonical
            if not self.dry_run:
                try:
                    if new_dir.exists():
                        try:
                            is_same_dir = show_dir.samefile(new_dir)
                        except OSError:
                            is_same_dir = False
                        if is_same_dir:
                            _rename_dir_case_safe(show_dir, new_dir)
                            log.info("show_folder_renamed", title=title, dest=canonical)
                        else:
                            moved, merge_failed = _merge_dirs(show_dir, new_dir)
                            log.info("show_folder_merged", title=title, dest=canonical, items=moved)
                            if merge_failed:
                                result.warnings.append(f"Partial merge: {merge_failed} item(s) failed")
                    else:
                        _rename_dir_case_safe(show_dir, new_dir)
                        log.info("show_folder_renamed", title=title, dest=canonical)
                    show_dir = new_dir
                    result.media_path = new_dir
                except OSError as exc:
                    result.error = f"Rename/merge failed: {exc}"
                    log.error("show_folder_rename_failed", title=title, dest=canonical, error=str(exc))
                    return result
                # Non-critical: clean stale files from before rename.
                # TV show artwork uses fixed names (poster.jpg, tvshow.nfo),
                # so this is a no-op for standard shows. Kept as safety net.
                try:
                    _cleanup_stale_files(show_dir, old_dir_name, canonical)
                except OSError as exc:
                    log.warning("stale_cleanup_failed", directory=show_dir.name, error=str(exc))
            else:
                action = "merge into" if new_dir.exists() else "rename"
                log.info("show_folder_would_rename", action=action, title=title, dest=canonical)

        # Classify item — must run before NFO write so the
        # category_id can be embedded in the NFO by nfo_generator.
        # For TV shows matched via TVDB the source TMDB ID may differ from
        # match.api_id — use tmdb_id which was resolved above.
        nfo_path = show_dir / self.patterns.tvshow_nfo
        category_id = self._classify_item(
            media_type=MediaType.TV,
            path=show_dir,
            title=resolved_title,
            api_data=show_data,
            tmdb_id=tmdb_id,
            nfo_path=nfo_path if nfo_path.exists() else None,
        )
        result.category_id = category_id
        if category_id is None and self.config is not None:
            # Config is present but no category matched — skip this item
            result.action = "skipped_no_category"
            return result

        # Generate tvshow.nfo
        try:
            xml = self._nfo.generate_tvshow_nfo(show_data, category_id=category_id)
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
            else:
                log.info("nfo_would_write", filename="tvshow.nfo")
        except Exception as e:
            result.error = f"tvshow.nfo failed: {e}"
            return result

        # Process episodes — rglob to find files nested in release-group subdirs,
        # but skip files already organized in Saison XX/ directories.
        # Trailers/ holds Plex-conformant trailer mp4s, never episodes.
        #
        # Episode processing must run BEFORE artwork so the Saison NN/ dirs
        # exist when ``download_tvshow_artwork`` decides which season posters
        # to fetch: that helper skips seasons whose folder is absent.
        total_renamed = 0

        # On an episode-NFO drift re-scrape, ALSO include files that
        # are already organized in ``Saison NN/`` — otherwise
        # ``_generate_episode_nfos`` never runs and the episode NFOs
        # stay broken (the very condition that triggered drift in the
        # first place, producing an infinite drift→rescrape loop with
        # no fix). ``rename_episodes`` is idempotent (skips files
        # already at their destination), so the wider sweep is safe.
        def _is_in_season_dir(path: Path) -> bool:
            return bool(SEASON_DIR_RE.match(path.parent.name))

        video_files = sorted(
            f
            for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and (drift_rescrape_episode_nfo or not _is_in_season_dir(f))
            and "Trailers" not in f.parts
            and not is_sample_path(f)
        )

        if video_files:
            # Resolve the synthetic-title prefix once per show so in-provider
            # episodes with empty names and post-facto fallbacks share the same
            # user-configurable wording (default "Episode").
            episode_default_name = self.config.scraper.episode_default_name if self.config is not None else "Episode"
            api_episodes = self._build_episode_map(show_dir, match, tmdb_id, episode_default_name)

            # Sequential xref enrichment (phase 5) — backfill the IDs of
            # the non-canonical provider into ``api_episodes`` so the
            # NFO writer can emit ``<uniqueid type=canonical>`` AND
            # ``<uniqueid type=xref>`` on every episode. Fail-soft : a
            # xref provider exception is logged, the canonical scrape
            # carries on with what it already has.
            canonical_provider = match.source
            tvdb_series_id = match.api_id if canonical_provider == "tvdb" else None
            self._xref_enrichment(
                api_episodes,
                canonical_provider=canonical_provider,
                tvdb_id=tvdb_series_id,
                tmdb_id=tmdb_id,
            )

            total_renamed, nfo_warnings = self._match_seasons(
                video_files, api_episodes, show_dir, show_data, episode_default_name
            )
            result.warnings.extend(nfo_warnings)

            # Clean empty release-group subdirectories left after episode moves
            if not self.dry_run:
                try:
                    _cleanup_empty_release_dirs(show_dir)
                except OSError as exc:
                    log.warning("show_clean_release_dirs_failed", show=show_dir.name, error=str(exc))

            # Episodes detected at the show root but none matched/moved into
            # ``Saison NN/`` — file naming and provider season layout diverge.
            # Without this signal the operator gets ``action="scraped"`` and
            # no clue that videos are still loose; verify catches the
            # filesystem shape but the scrape result itself stays opaque.
            if total_renamed == 0:
                loose = [f.name for f in video_files]
                result.warnings.append(
                    f"Episodes unmatched against {match.source} api_id={match.api_id}: {', '.join(loose)}"
                )
                log.warning(
                    "show_episodes_unmatched",
                    provider=match.source,
                    api_id=match.api_id,
                    show=show_dir.name,
                    files=loose,
                )

        # Download artwork (show-level + season posters). Runs after episode
        # processing so newly-created Saison NN/ dirs are visible to the
        # season-poster selection logic in ``download_tvshow_artwork``.
        try:
            downloaded = self._artwork.download_tvshow_artwork(
                show_data,
                show_dir,
                self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except (requests.RequestException, OSError, KeyError, AttributeError) as e:
            log.warning("show_artwork_failed", api_title=match.api_title, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork failed: {e}")

        store = DriftIssueStore.from_config(self.config)
        if store is not None:
            store.clear(show_dir)
        result.episodes_renamed = total_renamed
        result.action = "scraped"
        return result

    def _forced_series_lookup(
        self,
        show_dir: Path,
        source: str,
        provider_id: int,
        result: ScrapeResult,
    ) -> "tuple[MatchResult, dict[str, Any], int | None, str] | None":
        """Build the ``(match, show_data, tmdb_id, resolved_title)`` tuple for a forced id.

        The forced counterpart of
        :meth:`~personalscraper.scraper.tv_service.TvServiceMixin._lookup_series`:
        skips matching entirely (the operator asserted the identity) and fetches
        the chosen provider id directly via the shared
        :func:`~personalscraper.scraper._tvdb_convert.fetch_show_data` helper,
        honouring the TVDB-primary / TMDB-fallback source-of-match invariant.

        Args:
            show_dir: The show's staging directory (title/year fallback source).
            source: Matched provider — ``"tvdb"`` or ``"tmdb"``.
            provider_id: TVDB series id (``source == "tvdb"``) or TMDB id.
            result: ScrapeResult to mark ``error`` on a fetch failure.

        Returns:
            The success tuple, or ``None`` (with ``result.error`` set) on failure.
        """
        from personalscraper.scraper.confidence import MatchResult  # noqa: PLC0415

        title, year = _parse_folder_name(show_dir.name)
        provider_client = self._registry.get(source)
        try:
            show_data, tmdb_id = fetch_show_data(
                source,
                provider_id,
                provider_client,
                preferred_language=self._scraper_language,
                fallback_language=self._scraper_fallback_language,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced as a fail-soft result
            result.error = f"Get details failed: {exc}"
            result.action = "error"
            log.error("forced_show_details_failed", source=source, provider_id=provider_id, error=str(exc))
            return None
        api_title = str(show_data.get("name") or show_data.get("title") or title)
        first_air = str(show_data.get("first_air_date") or "")
        api_year = int(first_air[:4]) if first_air[:4].isdigit() else year
        match = MatchResult(
            api_id=provider_id,
            api_title=api_title,
            api_year=api_year,
            confidence=1.0,
            source=source,
        )
        resolved_title = self._strip_trailing_year(self._resolve_title(match.api_title, show_data, "tvshow"))
        return match, show_data, tmdb_id, resolved_title

    def scrape_tvshow_forced(self, show_dir: Path, source: str, provider_id: int) -> ScrapeResult:
        """Scrape a TV show against an operator-chosen provider id, bypassing matching.

        A manual resolution / re-scrape: fetches the chosen id directly then runs
        the SAME canonical write as the automatic scrape
        (:meth:`_write_confirmed_show`) — folder rename, episode rename into
        ``Saison NN/``, per-episode NFOs and artwork. This is what makes a
        resolved show complete and dispatchable (product-intent §méthode); the
        previous NFO-only resolve left episodes with raw release names, so
        ``verify`` blocked dispatch on "unrenamed episodes / no episode NFO".
        ``drift_rescrape_episode_nfo=True`` forces a full re-sweep so a
        re-scrape of an already-organised show regenerates its episode NFOs.

        Args:
            show_dir: The show's staging directory.
            source: Matched provider — ``"tvdb"`` or ``"tmdb"``.
            provider_id: TVDB series id (``source == "tvdb"``) or TMDB id.

        Returns:
            A :class:`ScrapeResult`; ``action="error"`` with ``result.error`` set
            when the provider fetch fails (fail-soft, never raises).
        """
        title, year = _parse_folder_name(show_dir.name)
        result = ScrapeResult(media_path=show_dir, media_type="tvshow")
        lookup = self._forced_series_lookup(show_dir, source, provider_id, result)
        if lookup is None:
            return result
        match, show_data, tmdb_id, resolved_title = lookup
        return self._write_confirmed_show(
            show_dir,
            match,
            show_data,
            tmdb_id,
            resolved_title,
            title,
            year,
            result,
            drift_rescrape_episode_nfo=True,
        )
