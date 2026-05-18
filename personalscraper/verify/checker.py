"""Media directory checker for pre-dispatch validation.

Verifies that movie and TV show directories meet quality standards
before being dispatched to storage disks. Checks cover file presence,
naming conventions, NFO validity, artwork, streamdetails, and
genre categorization.

Each check produces a CheckResult with severity (ERROR blocks dispatch,
WARNING is informational) and a fixable flag indicating whether the
issue can be auto-corrected by MediaFixer.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from personalscraper.conf.classifier import classify_from_nfo
from personalscraper.conf.models.config import Config
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE, NamingPatterns
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS
from personalscraper.text_utils import _NTFS_ILLEGAL

log = get_logger("verify.checker")

# Minimum file size (bytes) to not be considered a sample
_MIN_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB

# Regex for "Title (Year)" directory format
_DIR_PATTERN = re.compile(r"^.+ \(\d{4}\)$")

# Episode file pattern — accepts both the normal "SxxExx - Title.ext" and the
# title-less fallback "SxxExx.ext" produced when the provider lacks an episode
# (see episode_manager.rename_episodes). The fallback must not trip
# episode_renamed / season_structure checks.
_EPISODE_PATTERN = re.compile(r"^S\d{2}E\d{2}(?: - .+)?\.\w+$")


class Severity(Enum):
    """Check result severity level.

    Attributes:
        ERROR: Blocks dispatch — must be fixed or media is rejected.
        WARNING: Informational — dispatch proceeds but issue is logged.
    """

    ERROR = "error"
    WARNING = "warning"


@dataclass
class CheckResult:
    """Result of a single quality check.

    Attributes:
        name: Check identifier (e.g. "nfo_present", "category").
        passed: Whether the check passed.
        severity: ERROR (blocking) or WARNING (informational).
        message: Human-readable description of the issue.
        fixable: Whether the issue can be auto-corrected.
    """

    name: str
    passed: bool
    severity: Severity
    message: str
    fixable: bool = False


class MediaChecker:
    """Verify media directories meet quality standards.

    Checks naming, NFO validity, artwork presence, streamdetails,
    and genre categorization against NamingPatterns and Config
    (for classifier-backed category resolution).

    Attributes:
        patterns: MediaElch naming patterns reference.
        config: Config used to resolve category IDs from NFO metadata.
    """

    def __init__(self, patterns: NamingPatterns, config: Config):
        """Initialize the checker.

        Args:
            patterns: Naming patterns for file verification.
            config: Config providing category IDs and classifier rules.
        """
        self.patterns = patterns
        self.config = config

    def check_movie(self, movie_dir: Path) -> list[CheckResult]:
        """Run all quality checks on a movie directory.

        Checks: video_present, not_sample, dir_naming, nfo_present,
        nfo_valid, nfo_ids, poster_present, artwork_landscape,
        streamdetails, no_empty_dirs, category.

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            List of CheckResult for each criterion.
        """
        results: list[CheckResult] = []
        title = movie_dir.name

        # video_present
        video_files = self._find_video_files(movie_dir)
        results.append(
            CheckResult(
                name="video_present",
                passed=len(video_files) > 0,
                severity=Severity.ERROR,
                message="" if video_files else "No video file found",
            )
        )

        # not_sample
        if video_files:
            largest = max(f.stat().st_size for f in video_files)
            is_sample = largest < _MIN_VIDEO_SIZE
            results.append(
                CheckResult(
                    name="not_sample",
                    passed=not is_sample,
                    severity=Severity.WARNING,
                    message=f"Largest video is {largest // (1024 * 1024)} MB (possible sample)" if is_sample else "",
                )
            )

        # dir_naming
        results.append(
            CheckResult(
                name="dir_naming",
                passed=bool(_DIR_PATTERN.match(title)),
                severity=Severity.ERROR,
                message=f"Directory name '{title}' doesn't match 'Title (Year)' format"
                if not _DIR_PATTERN.match(title)
                else "",
                fixable=True,
            )
        )

        # Parse title for NamingPatterns lookups
        parsed_title = self._extract_title_from_dir(title)

        # nfo_present
        nfo_name = self.patterns.format("movie_nfo", Title=parsed_title)
        nfo_path = movie_dir / nfo_name
        nfo_exists = nfo_path.exists()
        results.append(
            CheckResult(
                name="nfo_present",
                passed=nfo_exists,
                severity=Severity.ERROR,
                message=f"NFO not found: {nfo_name}" if not nfo_exists else "",
            )
        )

        # Parse NFO for further checks
        nfo_root = self._parse_nfo(nfo_path) if nfo_exists else None

        # nfo_valid
        if nfo_exists:
            has_title = nfo_root is not None and nfo_root.findtext("title")
            has_year = nfo_root is not None and nfo_root.findtext("year")
            nfo_valid = has_title and has_year
            results.append(
                CheckResult(
                    name="nfo_valid",
                    passed=bool(nfo_valid),
                    severity=Severity.ERROR,
                    message="" if nfo_valid else "NFO missing <title> or <year>",
                )
            )

        # nfo_ids — at least one of TMDB or IMDB required (ERROR if neither; WARNING if only one)
        if nfo_root is not None:
            ids = self._extract_ids(nfo_root)
            has_tmdb = bool(ids.get("tmdb"))
            has_imdb = bool(ids.get("imdb"))
            has_both = has_tmdb and has_imdb
            has_any = has_tmdb or has_imdb
            results.append(
                CheckResult(
                    name="nfo_ids",
                    passed=has_both,
                    severity=Severity.ERROR if not has_any else Severity.WARNING,
                    message="" if has_both else f"Missing IDs: tmdb={has_tmdb}, imdb={has_imdb}",
                )
            )

        # poster_present (blocking — dispatch requires poster)
        poster_name = self.patterns.format("movie_poster", Title=parsed_title)
        results.append(
            CheckResult(
                name="poster_present",
                passed=(movie_dir / poster_name).exists(),
                severity=Severity.ERROR,
                message=f"Poster not found: {poster_name}" if not (movie_dir / poster_name).exists() else "",
            )
        )

        # artwork_landscape
        landscape_name = self.patterns.format("movie_landscape", Title=parsed_title)
        results.append(
            CheckResult(
                name="artwork_landscape",
                passed=(movie_dir / landscape_name).exists(),
                severity=Severity.WARNING,
                message=f"Landscape not found: {landscape_name}" if not (movie_dir / landscape_name).exists() else "",
            )
        )

        # streamdetails
        if nfo_root is not None:
            has_sd = nfo_root.find(".//streamdetails") is not None
            results.append(
                CheckResult(
                    name="streamdetails",
                    passed=has_sd,
                    severity=Severity.WARNING,
                    message="" if has_sd else "No <streamdetails> in NFO",
                )
            )

        # no_empty_dirs (check for empty subdirectories)
        empty_dirs = self._find_empty_dirs(movie_dir)
        results.append(
            CheckResult(
                name="no_empty_dirs",
                passed=len(empty_dirs) == 0,
                severity=Severity.ERROR,
                message=f"Empty subdirs: {', '.join(d.name for d in empty_dirs[:3])}" if empty_dirs else "",
                fixable=True,
            )
        )

        # category
        if nfo_exists:
            category, _reason = classify_from_nfo(self.config, nfo_path, "movie")
            results.append(
                CheckResult(
                    name="category",
                    passed=category is not None,
                    severity=Severity.ERROR,
                    message="" if category else "Cannot determine category from genres",
                )
            )

        # ntfs_safe_names
        results.append(self._check_ntfs_safe_names(movie_dir))

        return results

    def check_tvshow(self, show_dir: Path) -> list[CheckResult]:
        """Run all quality checks on a TV show directory.

        Checks: video_present, dir_naming, nfo_present, nfo_valid,
        nfo_ids, poster_present, artwork_landscape, season_structure,
        season_posters, episode_renamed, episode_nfo, no_empty_dirs,
        category.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            List of CheckResult for each criterion.
        """
        results: list[CheckResult] = []
        title = show_dir.name

        # video_present (check recursively in season dirs)
        all_videos = self._find_video_files_recursive(show_dir)
        results.append(
            CheckResult(
                name="video_present",
                passed=len(all_videos) > 0,
                severity=Severity.ERROR,
                message="" if all_videos else "No video files found",
            )
        )

        # dir_naming
        results.append(
            CheckResult(
                name="dir_naming",
                passed=bool(_DIR_PATTERN.match(title)),
                severity=Severity.ERROR,
                message=f"'{title}' doesn't match 'Title (Year)'" if not _DIR_PATTERN.match(title) else "",
                fixable=True,
            )
        )

        # nfo_present (tvshow.nfo)
        nfo_path = show_dir / self.patterns.tvshow_nfo
        nfo_exists = nfo_path.exists()
        results.append(
            CheckResult(
                name="nfo_present",
                passed=nfo_exists,
                severity=Severity.ERROR,
                message="tvshow.nfo not found" if not nfo_exists else "",
            )
        )

        # nfo_valid
        nfo_root = self._parse_nfo(nfo_path) if nfo_exists else None
        if nfo_exists:
            has_title = nfo_root is not None and nfo_root.findtext("title")
            nfo_valid = bool(has_title)
            results.append(
                CheckResult(
                    name="nfo_valid",
                    passed=nfo_valid,
                    severity=Severity.ERROR,
                    message="" if nfo_valid else "tvshow.nfo invalid or missing <title>",
                )
            )

        # nfo_ids (TVDB minimum for TV shows)
        if nfo_root is not None:
            ids = self._extract_ids(nfo_root)
            has_tvdb = bool(ids.get("tvdb")) or bool(ids.get("tmdb"))
            results.append(
                CheckResult(
                    name="nfo_ids",
                    passed=has_tvdb,
                    severity=Severity.ERROR,
                    message="" if has_tvdb else "No TVDB or TMDB uniqueid",
                )
            )

        # poster_present (blocking — dispatch requires poster)
        results.append(
            CheckResult(
                name="poster_present",
                passed=(show_dir / self.patterns.tvshow_poster).exists(),
                severity=Severity.ERROR,
                message="poster.jpg not found" if not (show_dir / self.patterns.tvshow_poster).exists() else "",
            )
        )
        results.append(
            CheckResult(
                name="artwork_landscape",
                passed=(show_dir / self.patterns.tvshow_landscape).exists(),
                severity=Severity.WARNING,
                message="landscape.jpg not found" if not (show_dir / self.patterns.tvshow_landscape).exists() else "",
            )
        )

        # season_structure
        season_dirs = [d for d in show_dir.iterdir() if d.is_dir() and SEASON_DIR_RE.match(d.name)]
        has_episodes_in_seasons = (
            any(any(_EPISODE_PATTERN.match(f.name) for f in sd.iterdir() if f.is_file()) for sd in season_dirs)
            if season_dirs
            else False
        )
        results.append(
            CheckResult(
                name="season_structure",
                passed=has_episodes_in_seasons,
                severity=Severity.ERROR,
                message="" if has_episodes_in_seasons else "No Saison XX/ with properly named episodes",
            )
        )

        # season_posters
        for sd in season_dirs:
            season_num = int(sd.name.split()[-1])
            poster_name = self.patterns.format("season_poster", Season=season_num)
            if not (show_dir / poster_name).exists():
                results.append(
                    CheckResult(
                        name="season_posters",
                        passed=False,
                        severity=Severity.WARNING,
                        message=f"Missing {poster_name}",
                    )
                )
        if not any(r.name == "season_posters" for r in results):
            results.append(
                CheckResult(
                    name="season_posters",
                    passed=True,
                    severity=Severity.WARNING,
                    message="",
                )
            )

        # episode_renamed (all videos in Saison XX/ must match SxxExx pattern)
        unrenamed = self._find_unrenamed_episodes(season_dirs)
        results.append(
            CheckResult(
                name="episode_renamed",
                passed=len(unrenamed) == 0,
                severity=Severity.ERROR,
                message=f"Unrenamed episodes: {', '.join(f.name for f in unrenamed[:3])}" if unrenamed else "",
            )
        )

        # episode_nfo (spot check: at least some episodes have NFOs)
        episode_nfos = list(show_dir.rglob("S??E??*.nfo"))
        results.append(
            CheckResult(
                name="episode_nfo",
                passed=len(episode_nfos) > 0,
                severity=Severity.WARNING,
                message="" if episode_nfos else "No episode NFO files found",
            )
        )

        # no_empty_dirs (recursive check for empty subdirectories)
        empty_dirs = self._find_empty_dirs(show_dir)
        results.append(
            CheckResult(
                name="no_empty_dirs",
                passed=len(empty_dirs) == 0,
                severity=Severity.ERROR,
                message=f"Empty subdirs: {', '.join(d.name for d in empty_dirs[:3])}" if empty_dirs else "",
                fixable=True,
            )
        )

        # category
        if nfo_exists:
            category, _reason = classify_from_nfo(self.config, nfo_path, "tvshow")
            results.append(
                CheckResult(
                    name="category",
                    passed=category is not None,
                    severity=Severity.ERROR,
                    message="" if category else "Cannot determine category from genres",
                )
            )

        # root_video_files — only checked when tvshow.nfo exists (i.e. already scraped).
        # Stray video files at the show root (not inside Saison XX/) mean the scraper
        # repair step did not complete; dispatch must be blocked until they are organized.
        if nfo_exists:
            root_videos = [
                f for f in show_dir.iterdir() if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            ]
            if root_videos:
                names = ", ".join(f.name for f in root_videos[:3])
                suffix = f" (+{len(root_videos) - 3} more)" if len(root_videos) > 3 else ""
                message = f"Unprocessed video files at root: {names}{suffix}"
            else:
                message = ""
            results.append(
                CheckResult(
                    name="root_video_files",
                    passed=len(root_videos) == 0,
                    severity=Severity.ERROR,
                    message=message,
                )
            )

        # provider-ids feature (phase 9) — three new per-episode-NFO checks
        # introduced to bridge the gap between phase 4's drift hardening
        # (which catches missing canonical uniqueid) and the dispatch
        # gate (which needs the same guarantee). Run them only when the
        # show has at least one episode NFO ; otherwise they are no-ops
        # (a freshly scraped show whose episode files have not yet been
        # written has nothing to inspect).
        canonical_family = self._canonical_family_from_nfo(nfo_root) if nfo_root is not None else None
        results.append(self._check_episode_canonical_uniqueid_present(show_dir, canonical_family))
        results.append(self._check_episode_xref_secondary_id_present(show_dir, canonical_family))
        results.append(self._check_episode_xref_imdb_id_present(show_dir))

        # ntfs_safe_names
        results.append(self._check_ntfs_safe_names(show_dir))

        return results

    # --- provider-ids per-episode uniqueid checks (phase 9) -----------

    @staticmethod
    def _canonical_family_from_nfo(root: ET.Element) -> str | None:
        """Return the ``type`` attribute of the ``<uniqueid default="true">`` row.

        Falls back to the first ``<uniqueid>`` ``type`` when no default
        flag is set (legacy NFOs from before the phase-6 canonical
        annotation). ``None`` only when the NFO has no ``<uniqueid>``
        at all — that case is already caught by the ``nfo_ids`` check.
        """
        default = next((u for u in root.findall("uniqueid") if u.get("default") == "true"), None)
        if default is not None:
            kind = (default.get("type") or "").strip().lower()
            return kind or None
        first = root.find("uniqueid")
        if first is not None:
            kind = (first.get("type") or "").strip().lower()
            return kind or None
        return None

    def _episode_nfo_paths(self, show_dir: Path) -> list[Path]:
        """Return every sibling episode NFO under ``show_dir/Saison NN/``."""
        return list(show_dir.rglob("S??E??*.nfo"))

    def _check_episode_canonical_uniqueid_present(
        self,
        show_dir: Path,
        canonical_family: str | None,
    ) -> CheckResult:
        """ERROR check : every episode NFO must carry the canonical ``<uniqueid>``.

        Mirrors the phase-4 drift hardening but lives in the verify
        layer so dispatch (which consumes the verify outcome) refuses
        to ship a show whose episode NFOs would later trigger a
        drift-driven re-scrape.

        The check passes silently when :

        - no episode NFO is on disk yet (nothing to inspect) ;
        - the show's ``tvshow.nfo`` has no canonical family to compare
          against (caught upstream by ``nfo_ids``).
        """
        if canonical_family is None:
            return CheckResult(
                name="episode_canonical_uniqueid_present",
                passed=True,
                severity=Severity.ERROR,
                message="",
            )
        episode_nfos = self._episode_nfo_paths(show_dir)
        if not episode_nfos:
            return CheckResult(
                name="episode_canonical_uniqueid_present",
                passed=True,
                severity=Severity.ERROR,
                message="",
            )
        missing: list[str] = []
        for nfo_path in episode_nfos:
            root = self._parse_nfo(nfo_path)
            if root is None:
                # Unparseable NFO ≡ missing canonical uniqueid for the
                # purpose of dispatch readiness — we cannot ship a show
                # whose episode NFOs would crash a downstream reader.
                missing.append(f"{nfo_path.name} (unparseable)")
                continue
            ids = self._extract_ids(root)
            if not ids.get(canonical_family):
                missing.append(nfo_path.name)
        return CheckResult(
            name="episode_canonical_uniqueid_present",
            passed=not missing,
            severity=Severity.ERROR,
            message=(f'Missing <uniqueid type="{canonical_family}"> on: {", ".join(missing[:3])}' if missing else ""),
        )

    def _check_episode_xref_secondary_id_present(
        self,
        show_dir: Path,
        canonical_family: str | None,
    ) -> CheckResult:
        """WARNING check : episodes should carry the non-canonical xref ID.

        Suggests a ``personalscraper indexer backfill-ids`` re-run when
        the secondary family (TMDb on TVDB-canonical shows, vice versa)
        is missing on episode NFOs. Not blocking — dispatch can proceed
        with canonical-only NFOs, but Plex / Kodi readers benefit from
        the extra row.
        """
        if canonical_family not in ("tvdb", "tmdb"):
            return CheckResult(
                name="episode_xref_secondary_id_present",
                passed=True,
                severity=Severity.WARNING,
                message="",
            )
        secondary = "tmdb" if canonical_family == "tvdb" else "tvdb"
        episode_nfos = self._episode_nfo_paths(show_dir)
        if not episode_nfos:
            return CheckResult(
                name="episode_xref_secondary_id_present",
                passed=True,
                severity=Severity.WARNING,
                message="",
            )
        missing: list[str] = []
        for nfo_path in episode_nfos:
            root = self._parse_nfo(nfo_path)
            if root is None:
                continue
            ids = self._extract_ids(root)
            if not ids.get(secondary):
                missing.append(nfo_path.name)
        return CheckResult(
            name="episode_xref_secondary_id_present",
            passed=not missing,
            severity=Severity.WARNING,
            message=(
                f'Missing xref <uniqueid type="{secondary}"> on: {", ".join(missing[:3])}; '
                "consider 'personalscraper indexer backfill-ids'"
                if missing
                else ""
            ),
        )

    def _check_episode_xref_imdb_id_present(self, show_dir: Path) -> CheckResult:
        """WARNING check : episodes should carry an IMDb ``<uniqueid>``.

        IMDb episode IDs feed the future tracker-search flow ; missing
        them is not blocking but suggests a ``backfill-ids`` re-run.
        """
        episode_nfos = self._episode_nfo_paths(show_dir)
        if not episode_nfos:
            return CheckResult(
                name="episode_xref_imdb_id_present",
                passed=True,
                severity=Severity.WARNING,
                message="",
            )
        missing: list[str] = []
        for nfo_path in episode_nfos:
            root = self._parse_nfo(nfo_path)
            if root is None:
                continue
            ids = self._extract_ids(root)
            if not ids.get("imdb"):
                missing.append(nfo_path.name)
        return CheckResult(
            name="episode_xref_imdb_id_present",
            passed=not missing,
            severity=Severity.WARNING,
            message=(f"Missing IMDb uniqueid on: {', '.join(missing[:3])}" if missing else ""),
        )

    # --- NTFS safety helpers ---

    def _check_ntfs_safe_names(self, media_dir: Path) -> CheckResult:
        r"""Check all filenames for NTFS-illegal characters.

        Scans recursively for files containing <>:"/\\|?* in their names.
        These characters cause rsync failures on NTFS storage disks.

        Args:
            media_dir: Directory to scan.

        Returns:
            CheckResult with list of offending filenames if any.
        """
        illegal_files = []
        for f in media_dir.rglob("*"):
            if f.is_file() and _NTFS_ILLEGAL.search(f.name):
                illegal_files.append(f.name)

        if illegal_files:
            sample = ", ".join(illegal_files[:3])
            suffix = f" (+{len(illegal_files) - 3} more)" if len(illegal_files) > 3 else ""
            message = f"NTFS-illegal filenames: {sample}{suffix}"
        else:
            message = ""

        return CheckResult(
            name="ntfs_safe_names",
            passed=len(illegal_files) == 0,
            severity=Severity.ERROR,
            message=message,
            fixable=True,
        )

    # --- NFO parsing helpers ---

    @staticmethod
    def _parse_nfo(nfo_path: Path) -> ET.Element | None:
        """Parse an NFO XML file.

        Args:
            nfo_path: Path to the NFO file.

        Returns:
            Root Element, or None if parse fails.
        """
        try:
            tree = ET.parse(nfo_path)  # noqa: S314
            return tree.getroot()
        except (ET.ParseError, OSError) as exc:
            log.warning("verify_nfo_parse_failed", nfo=nfo_path.name, exc_info=True, error=str(exc))
            return None

    @staticmethod
    def _extract_ids(root: ET.Element) -> dict[str, str]:
        """Extract uniqueid values by type from NFO root.

        Args:
            root: Parsed NFO root element.

        Returns:
            Dict mapping type to id value (e.g. {"tmdb": "550"}).
        """
        ids: dict[str, str] = {}
        for uid in root.findall("uniqueid"):
            uid_type = uid.get("type", "")
            uid_text = uid.text or ""
            if uid_type and uid_text:
                ids[uid_type] = uid_text
        return ids

    @staticmethod
    def _find_video_files(directory: Path) -> list[Path]:
        """Find video files in a directory (non-recursive).

        Args:
            directory: Directory to search.

        Returns:
            List of video file paths.
        """
        return [f for f in directory.iterdir() if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS]

    @staticmethod
    def _find_video_files_recursive(directory: Path) -> list[Path]:
        """Find video files recursively in a directory tree.

        Args:
            directory: Root directory to search.

        Returns:
            List of video file paths.
        """
        results: list[Path] = []
        for ext in VIDEO_EXTENSIONS:
            results.extend(directory.rglob(f"*.{ext}"))
        return results

    @staticmethod
    def _extract_title_from_dir(dir_name: str) -> str:
        """Extract title from a directory name, stripping (Year) suffix.

        Args:
            dir_name: Directory name, possibly "Title (2024)".

        Returns:
            Title portion, or the full name if no year found.
        """
        m = re.match(r"^(.+?)\s*\(\d{4}\)$", dir_name)
        return m.group(1).strip() if m else dir_name

    @staticmethod
    def _find_empty_dirs(root: Path) -> list[Path]:
        """Find empty subdirectories recursively.

        A directory is considered empty if it contains no files
        (junk files like .DS_Store count as empty).

        Args:
            root: Root directory to scan.

        Returns:
            List of empty directory paths.
        """
        junk = {".DS_Store", "Thumbs.db"}
        empty = []
        for d in root.rglob("*"):
            if not d.is_dir():
                continue
            contents = list(d.iterdir())
            has_real_content = any(item.is_file() and item.name not in junk for item in contents)
            if not has_real_content and not any(item.is_dir() for item in contents):
                empty.append(d)
        return empty

    @staticmethod
    def _find_unrenamed_episodes(season_dirs: list[Path]) -> list[Path]:
        """Find video files in season dirs that don't match episode pattern.

        Args:
            season_dirs: List of 'Saison XX' directories.

        Returns:
            List of video files that don't match S##E## - Title.ext.
        """
        unrenamed = []
        for sd in season_dirs:
            for f in sd.iterdir():
                if not f.is_file():
                    continue
                if f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                    continue
                if not _EPISODE_PATTERN.match(f.name):
                    unrenamed.append(f)
        return unrenamed
