"""Episode NFO generation mixin for the TV scrape flow.

Extracted from :mod:`personalscraper.scraper.tv_service` in Phase 27.2 to bring
the parent module below the 800 non-blank LOC soft ceiling
(``scripts/check-module-size.py``).

Contains the episode-NFO generation methods previously on
:class:`TvServiceMixin`: NFO write, xref augmentation of existing NFOs,
and episode thumbnail download. Behaviour is unchanged — verbatim move.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from personalscraper.logger import get_logger
from personalscraper.scraper.nfo_generator import NFOGenerator

if TYPE_CHECKING:
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper.artwork import ArtworkDownloader

log = get_logger("scraper")


class TvServiceNfoMixin:
    """Episode NFO generation and thumbnail download methods.

    Extracted from :class:`TvServiceMixin` to keep the parent module
    under the 800-LOC soft ceiling. Composed into :class:`Scraper`
    alongside the other mixins via multiple inheritance.
    """

    patterns: "NamingPatterns"
    dry_run: bool
    _nfo: "NFOGenerator"
    _artwork: "ArtworkDownloader"

    def _augment_episode_nfo_with_xref(self, nfo_path: Path, info: dict[str, Any]) -> None:
        """Append missing xref ``<uniqueid>`` rows to an existing episode NFO.

        Thin delegate to
        :func:`personalscraper.scraper._xref.augment_episode_nfo_with_xref`.
        """
        from personalscraper.scraper._xref import augment_episode_nfo_with_xref  # noqa: PLC0415

        augment_episode_nfo_with_xref(nfo_path, info, dry_run=self.dry_run)

    def _download_episode_thumb(
        self,
        still_path: str,
        thumb_path: Path,
        season: int,
        episode: int,
    ) -> None:
        """Download an episode thumbnail from TMDB if available.

        Skips if still_path is empty, thumb already exists, or dry_run.
        Errors are logged and do not interrupt the caller.

        Args:
            still_path: TMDB still image path (e.g. "/abc123.jpg"), empty to skip.
            thumb_path: Local destination path for the thumbnail.
            season: Season number (for log messages).
            episode: Episode number (for log messages).
        """
        if not still_path or thumb_path.exists() or self.dry_run:
            return
        url = f"https://image.tmdb.org/t/p/original{still_path}"
        try:
            self._artwork.download_image(url, thumb_path)
        except requests.exceptions.RequestException:
            log.warning("episode_thumb_failed", season=season, episode=episode)

    def _generate_episode_nfos(
        self,
        matched: dict[Path, dict[str, Any]],
        show_dir: Path,
        show_data: dict[str, Any],
    ) -> list[str]:
        """Generate NFO files and download episode thumbnails.

        For each matched episode, creates an NFO file with metadata and
        downloads the TMDB still image as a thumbnail file. Episodes with
        existing NFOs only get thumbnail recovery (if missing).

        Args:
            matched: Dict from match_episode_files().
            show_dir: Path to the TV show directory.
            show_data: Full TMDB show details.

        Returns:
            List of warning strings for any episode NFO write failures.
        """
        warnings: list[str] = []
        show_title = show_data.get("name", "")
        mpaa = NFOGenerator._extract_fr_rating(show_data, tv=True)
        networks = show_data.get("networks", [])
        studio = networks[0].get("name", "") if networks else ""

        for video_path, info in matched.items():
            season = info["season"]
            episode = info["episode"]
            api_title = info["api_title"]
            still_path = info.get("still_path", "")

            # Fallback entries (no provider record — synthetic "Episode N" title)
            # skip NFO/thumb generation: the file lands as "SxxExx - Episode N.mkv"
            # under its Saison XX/ dir so verify/dispatch don't block, but we refuse
            # to fabricate episode metadata.
            if info.get("fallback"):
                continue

            # Season packs get a Kodi multi-episode NFO (one <episodedetails>
            # per covered episode) named to the SxxE01-Eyy range.
            if info.get("is_season_pack"):
                warnings.extend(self._generate_season_pack_nfo(video_path, info, show_dir, show_title, mpaa, studio))
                continue

            season_dir_name = self.patterns.format("season_dir", Season=season)
            new_stem = self.patterns.format(
                "episode_video",
                Season=season,
                Episode=episode,
                EpisodeTitle=api_title,
            )
            nfo_path = show_dir / season_dir_name / f"{new_stem}.nfo"
            thumb_name = self.patterns.format(
                "episode_thumb",
                Season=season,
                Episode=episode,
                EpisodeTitle=api_title,
            )
            thumb_path = show_dir / season_dir_name / thumb_name

            if nfo_path.exists():
                # Phase 5.4 : upgrade-in-place. An NFO already on disk
                # may have been written by an earlier scrape that did
                # not yet have the xref IDs available — append the
                # ``<uniqueid type=xref>`` rows now without touching
                # the existing canonical (and never overwriting an
                # already-present xref value).
                self._augment_episode_nfo_with_xref(nfo_path, info)
                # Still download thumbnail if NFO exists but thumb doesn't
                self._download_episode_thumb(still_path, thumb_path, season, episode)
                continue

            # Propagate per-episode provider IDs originated by
            # ``_build_episode_map`` and surfaced via
            # ``match_episode_files`` (DEV #2 root cause). Empty values are
            # mapped to ``""`` so the NFO generator's own
            # "omit on blank" logic keeps producing well-formed XML when
            # an upstream provider had nothing to surface.
            episode_data = {
                "name": api_title,
                "showtitle": show_title,
                "id": info.get("tmdb_episode_id", ""),
                "tvdb_id": info.get("tvdb_episode_id", ""),
                "imdb_id": info.get("imdb_episode_id", ""),
                "season_number": season,
                "episode_number": episode,
                "overview": "",
                "mpaa": mpaa,
                "studio": studio,
                "crew": [],
                "still_path": still_path,
            }

            # Stream info from the renamed video
            renamed_video = show_dir / season_dir_name / f"{new_stem}{video_path.suffix}"
            stream_info = None
            if renamed_video.exists():
                from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

                stream_info = scraper_api.extract_stream_info(renamed_video)

            try:
                xml = self._nfo.generate_episode_nfo(episode_data, stream_info)
                if not self.dry_run:
                    nfo_path.parent.mkdir(parents=True, exist_ok=True)
                    self._nfo.write_nfo(xml, nfo_path)
            except Exception as e:
                log.warning("episode_nfo_failed", season=season, episode=episode, error=str(e), exc_info=True)
                warnings.append(f"episode_nfo_failed: season={season} episode={episode} reason={e}")

            # Download episode thumbnail
            self._download_episode_thumb(still_path, thumb_path, season, episode)

        return warnings

    def _generate_season_pack_nfo(
        self,
        video_path: Path,
        info: dict[str, Any],
        show_dir: Path,
        show_title: str,
        mpaa: str,
        studio: str,
    ) -> list[str]:
        """Write a single valid ``<episodedetails>`` NFO for a whole-season file.

        The ``SxxE01-Eyy`` RANGE is carried by the filename (Kodi and Plex read
        the span from there); the NFO holds one well-formed ``<episodedetails>``
        with the season-representative metadata and the canonical ``<uniqueid>``.
        A single root is used deliberately: a multi-``<episodedetails>`` file has
        several XML roots and is unparseable by the strict verify/augment readers
        (``ElementTree``), which would block dispatch. Idempotent: skips when the
        NFO already exists.

        Args:
            video_path: The season-pack video file (pre-rename path).
            info: The season-pack match dict (carries the first episode's ids).
            show_dir: TV show root directory.
            show_title: Series title for the NFO ``showtitle``.
            mpaa: Content rating string.
            studio: Studio/network name.

        Returns:
            Warning strings for any NFO write failure (empty on success).
        """
        warnings: list[str] = []
        season = info["season"]
        ep_start = info["episode"]
        ep_end = info["episode_end"]
        api_title = info["api_title"]
        season_dir_name = self.patterns.format("season_dir", Season=season)
        new_stem = self.patterns.format(
            "episode_video_range",
            Season=season,
            EpisodeStart=ep_start,
            EpisodeEnd=ep_end,
            EpisodeTitle=api_title,
        )
        nfo_path = show_dir / season_dir_name / f"{new_stem}.nfo"
        if nfo_path.exists():
            return warnings

        renamed_video = show_dir / season_dir_name / f"{new_stem}{video_path.suffix}"
        stream_info = None
        if renamed_video.exists():
            from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

            stream_info = scraper_api.extract_stream_info(renamed_video)

        episode_data = {
            "name": api_title,
            "showtitle": show_title,
            "id": info.get("tmdb_episode_id", ""),
            "tvdb_id": info.get("tvdb_episode_id", ""),
            "imdb_id": info.get("imdb_episode_id", ""),
            "season_number": season,
            "episode_number": ep_start,
            "overview": "",
            "mpaa": mpaa,
            "studio": studio,
            "crew": [],
            "still_path": info.get("still_path", ""),
        }
        try:
            xml = self._nfo.generate_episode_nfo(episode_data, stream_info)
            if not self.dry_run:
                nfo_path.parent.mkdir(parents=True, exist_ok=True)
                self._nfo.write_nfo(xml, nfo_path)
        except Exception as e:  # noqa: BLE001 - fail-soft
            log.warning("episode_nfo_failed", season=season, episode=ep_start, error=str(e), exc_info=True)
            warnings.append(f"episode_nfo_failed: season={season} episode={ep_start} reason={e}")

        thumb_name = self.patterns.format(
            "episode_thumb_range",
            Season=season,
            EpisodeStart=ep_start,
            EpisodeEnd=ep_end,
            EpisodeTitle=api_title,
        )
        self._download_episode_thumb(
            info.get("still_path", ""), show_dir / season_dir_name / thumb_name, season, ep_start
        )
        return warnings
