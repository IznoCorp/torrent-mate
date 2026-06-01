"""Media directory checker for pre-dispatch validation.

Verifies that movie and TV show directories meet quality standards
before being dispatched to storage disks. Checks cover file presence,
naming conventions, NFO validity, artwork, streamdetails, and
genre categorization.

Each check produces a CheckResult with severity (ERROR blocks dispatch,
WARNING is informational) and a fixable flag indicating whether the
issue can be auto-corrected by ``apply_fixes`` (the check's ``fix()`` method).
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_trailer_filename
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.text_utils import _NTFS_ILLEGAL
from personalscraper.verify.checks import registry
from personalscraper.verify.checks.base import CheckContext, CheckResult, CheckStage, Severity

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
        streamdetails, no_empty_dirs, category, no_duplicate_videos.

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            List of CheckResult for each criterion.
        """
        ctx = CheckContext(
            media_dir=movie_dir,
            media_type="movie",
            stage=CheckStage.DISPATCH,
            config=self.config,
            patterns=self.patterns,
        )
        return [r for check in registry.checks_for(CheckStage.DISPATCH, "movie") for r in check.run(ctx)]

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
        ctx = CheckContext(
            media_dir=show_dir,
            media_type="tvshow",
            stage=CheckStage.DISPATCH,
            config=self.config,
            patterns=self.patterns,
        )
        return [r for check in registry.checks_for(CheckStage.DISPATCH, "tvshow") for r in check.run(ctx)]

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

    def _check_no_duplicate_videos(self, movie_dir: Path) -> CheckResult:
        """Verify a movie directory holds at most one video file at its root.

        Movies are flat: a movie folder must contain exactly one feature video
        at its root. More than one root-level video means the same-TMDB merge
        dedup contract was violated (two distinct staged folders resolving to
        the same TMDB id were merged but an orphan video was left behind). If
        that happens, DISPATCH would copy duplicate videos to storage, so this
        check blocks the movie. TV shows are EXEMPT — they hold multi-file
        seasons by design — hence this check is wired into check_movie only.

        The scan is non-recursive (root only): videos inside sub-dirs such as
        ``Extras/`` are legitimate and ignored. The flat Plex movie trailer
        ``{media_name}-trailer.{ext}`` (placed at the movie root by the trailers
        step) is also EXEMPT — it is filtered out before the count so a movie
        with its trailer is not wrongly flagged as holding two feature videos.

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            CheckResult named "no_duplicate_videos" with ERROR severity;
            passed when at most one non-trailer video file lives at the root.
        """
        videos = [f for f in self._find_video_files(movie_dir) if not is_trailer_filename(f.name)]
        passed = len(videos) <= 1
        filenames = sorted(f.name for f in videos)
        return CheckResult(
            name="no_duplicate_videos",
            passed=passed,
            severity=Severity.ERROR,
            message="" if passed else f"Multiple video files at root: {filenames}",
        )

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
