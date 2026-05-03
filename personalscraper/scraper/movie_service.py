"""Extracted scraper service module."""

from __future__ import annotations

import re
from pathlib import Path

import requests

from personalscraper.logger import get_logger
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper._shared import ScrapeResult, _find_video_file
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.confidence import LOW_CONFIDENCE
from personalscraper.scraper.rename_service import _cleanup_stale_files, _merge_dirs
from personalscraper.text_utils import sanitize_filename

log = get_logger("scraper")

_TVDB_LANG_MAP: dict[str, str] = {
    "fr": "fra",
    "en": "eng",
    "es": "spa",
    "de": "deu",
    "it": "ita",
    "ja": "jpn",
    "ko": "kor",
    "pt": "por",
    "ru": "rus",
    "zh": "zho",
    "ar": "ara",
    "nl": "nld",
}

_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


class MovieServiceMixin:
    """Movie scrape service methods."""

    def scrape_movie(self, movie_dir: Path) -> ScrapeResult:
        """Scrape a single movie: match → NFO → artwork.

        Flow:
        1. Parse title + year from folder name
        2. If valid NFO exists: recover missing artwork if needed, then skip
        3. If corrupt NFO exists: delete it and re-scrape
        4. Match against TMDB
        5. Get full movie details + resolve local title
        6. Rename folder to canonical format
        7. Extract stream info from video file
        8. Generate and write NFO
        9. Download artwork (poster + landscape)

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            ScrapeResult with action and details.
        """
        title, year = _parse_folder_name(movie_dir.name)
        result = ScrapeResult(media_path=movie_dir, media_type="movie")

        # Check for existing valid NFO
        nfo_name = self.patterns.format("movie_nfo", Title=title)
        nfo_path = movie_dir / nfo_name
        if _is_nfo_complete(nfo_path):
            # Check for missing artwork — recover without re-scraping
            missing = self._check_missing_movie_artwork(movie_dir, title)
            if missing and not self.dry_run:
                self._recover_movie_artwork(nfo_path, movie_dir, result)
            # Set action: artwork_recovered if recovery succeeded, else skipped
            # Repair pass: remove residual NFOs
            repaired = self._repair_movie_dir(movie_dir, title)
            if repaired and result.action != "artwork_recovered":
                result.action = "repaired"
            elif result.action != "artwork_recovered":
                result.action = "skipped_already_done"
            log.info("nfo_valid", action=result.action, directory=movie_dir.name)
            return result

        # Corrupt NFO: delete before re-scrape.  Honor dry_run — without
        # this guard a dry-run pass that detected drift would still
        # unlink the file, leaving the next real run thinking the NFO is
        # missing from the start (and downstream verify reports it as
        # blocked).  In dry_run mode we log the would-be deletion and
        # leave the file in place so the staging area is unchanged.
        if nfo_path.exists():
            if self.dry_run:
                log.info("nfo_corrupt_rescrape_would_delete", filename=nfo_path.name)
            else:
                log.warning("nfo_corrupt_rescrape", filename=nfo_path.name)
                try:
                    nfo_path.unlink()
                except OSError as exc:
                    result.error = f"Cannot delete corrupt NFO: {exc}"
                    log.error("nfo_corrupt_delete_failed", path=str(nfo_path), error=str(exc))
                    return result

        # Match against TMDB
        try:
            from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

            match = scraper_api.match_movie(self._tmdb, title, year)
        except Exception as e:
            result.error = f"Match failed: {e}"
            log.error("movie_match_failed", title=title, error=str(e), exc_info=True)
            return result

        if match is None or match.confidence < LOW_CONFIDENCE:
            result.action = "skipped_low_confidence"
            log.warning(
                "movie_no_confident_match",
                title=title,
                year=year,
                score=round(match.confidence if match else 0.0, 2),
            )
            return result

        result.match = match
        log.info(
            "movie_matched",
            title=title,
            api_title=match.api_title,
            source=match.source,
            confidence=round(match.confidence, 2),
        )

        # Get full movie details (needed for local title resolution)
        try:
            movie_data = self._tmdb.get_movie(match.api_id)
        except Exception as e:
            result.error = f"Get details failed: {e}"
            log.error("movie_details_failed", api_title=match.api_title, error=str(e), exc_info=True)
            return result

        # Resolve title: use local FR title if preferred and available
        resolved_title = self._strip_trailing_year(self._resolve_title(match.api_title, movie_data, "movie"))
        api_year = match.api_year or year
        # Folder name is filesystem-safe (sanitize_filename strips ``:``, ``?``,
        # ``"`` etc. for NTFS compatibility) while the NFO ``<title>`` keeps
        # the original punctuation for Plex/Kodi display. The two values are
        # *intentionally* allowed to diverge — same item ``Some Show: Subtitle``
        # ends up as folder ``Some Show Subtitle`` and NFO title
        # ``Some Show: Subtitle``. Verified items downstream (verify/run.py)
        # compare on NFC-normalised, NTFS-sanitised forms so this asymmetry
        # does not cause false-positive drift.
        clean_name = sanitize_filename(f"{resolved_title} ({api_year})" if api_year else resolved_title)

        # Save old title before rename for stale file cleanup
        old_title = title

        # Rename folder to clean format if it doesn't match
        if movie_dir.name != clean_name:
            new_path = movie_dir.parent / clean_name
            if not self.dry_run:
                try:
                    if new_path.exists():
                        moved, merge_failed = _merge_dirs(movie_dir, new_path)
                        log.info("movie_folder_merged", source=movie_dir.name, dest=clean_name, items=moved)
                        if merge_failed:
                            result.warnings.append(f"Partial merge: {merge_failed} item(s) failed")
                    else:
                        movie_dir.rename(new_path)
                        log.info("movie_folder_renamed", source=movie_dir.name, dest=clean_name)
                    movie_dir = new_path
                    result.media_path = new_path
                    title = resolved_title
                    nfo_name = self.patterns.format("movie_nfo", Title=title)
                    nfo_path = movie_dir / nfo_name
                except OSError as exc:
                    result.error = f"Rename/merge failed: {exc}"
                    log.error("movie_folder_rename_failed", source=movie_dir.name, dest=clean_name, error=str(exc))
                    return result
                # Non-critical: clean stale artwork/NFO from before rename
                try:
                    _cleanup_stale_files(movie_dir, old_title, resolved_title)
                except OSError as exc:
                    log.warning("stale_cleanup_failed", directory=movie_dir.name, error=str(exc))
            else:
                action = "merge into" if new_path.exists() else "rename"
                log.info("movie_folder_would_rename", action=action, source=movie_dir.name, dest=clean_name)

        # Rename video file to clean title and extract stream info
        video_file = _find_video_file(movie_dir)
        stream_info = None
        if video_file:
            clean_video_name = (
                self.patterns.format(
                    "movie_video",
                    Title=title,
                )
                + video_file.suffix
            )
            if video_file.name != clean_video_name:
                new_video = movie_dir / clean_video_name
                if not self.dry_run:
                    try:
                        video_file.rename(new_video)
                        log.info("movie_video_renamed", source=video_file.name, dest=clean_video_name)
                        video_file = new_video
                    except OSError as exc:
                        log.warning(
                            "movie_video_rename_failed",
                            source=video_file.name,
                            dest=clean_video_name,
                            directory=movie_dir.name,
                            error=str(exc),
                        )
                        result.warnings.append(f"Video rename failed: {video_file.name}: {exc}")
                else:
                    log.info("movie_video_would_rename", source=video_file.name, dest=clean_video_name)
            from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

            stream_info = scraper_api.extract_stream_info(video_file)

        # Classify item — must run before NFO write so the
        # category_id can be embedded in the NFO by nfo_generator.
        category_id = self._classify_item(
            media_type="movie",
            path=movie_dir,
            title=title,
            api_data=movie_data,
            tmdb_id=match.api_id,
            nfo_path=nfo_path if nfo_path.exists() else None,
        )
        result.category_id = category_id
        if category_id is None and self.config is not None:
            # Config is present but no category matched — skip this item
            result.action = "skipped_no_category"
            return result

        # Generate and write NFO
        try:
            xml = self._nfo.generate_movie_nfo(movie_data, stream_info, category_id=category_id)
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
                log.info("nfo_written", filename=nfo_path.name)
            else:
                log.info("nfo_would_write", filename=nfo_path.name)
        except Exception as e:
            result.error = f"NFO generation failed: {e}"
            log.error("nfo_generation_failed", title=title, error=str(e), exc_info=True)
            return result

        # Download artwork
        try:
            downloaded = self._artwork.download_movie_artwork(
                movie_data,
                movie_dir,
                self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except (requests.RequestException, OSError, KeyError, AttributeError) as e:
            log.warning("movie_artwork_failed", title=title, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork failed: {e}")

        result.action = "scraped"
        return result
