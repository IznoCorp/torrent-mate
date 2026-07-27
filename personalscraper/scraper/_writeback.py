"""Shared scraper write-back helpers — canonical-family artwork recovery.

Home of the ONE artwork-recovery helper (:func:`recover_artwork`) folded out of
the two hand-synchronised, TMDB-hardwired copies that used to live in
:mod:`personalscraper.scraper.existing_validator`
(``_recover_movie_artwork`` / ``_recover_tvshow_artwork``, SCRAPER-09).

Cohesion rationale (P4.4): this is a *provider-dispatch + download* concern —
resolve the item's canonical family from its NFO ids, refetch from that family
and re-pull the missing images. That is a different axis from the filesystem
move mechanics in :mod:`personalscraper.scraper.rename_service` (which owns
``apply_canonical_dir_rename`` / ``_merge_dirs`` / ``_rename_dir_case_safe``),
so it earns its own module rather than being wedged into the rename service.

Provider-separation invariant (unchanged, only the *dispatch* is fixed): the
canonical family is TVDB-primary for TV shows when a TVDB id is present, TMDB
otherwise — movies are always TMDB-canonical (IMDB is info-only). The refetch
goes through the shared :func:`personalscraper.scraper._tvdb_convert.fetch_show_data`
kernel so the TVDB-primary / TMDB-fallback discipline lives in ONE place.

F7 fix: a TVDB-only show (NFO carrying a ``tvdb`` id but no ``tmdb`` id) now
recovers its artwork from TVDB instead of silently short-circuiting on the
missing TMDB id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from personalscraper.logger import get_logger
from personalscraper.nfo_utils import extract_nfo_metadata

if TYPE_CHECKING:
    from pathlib import Path

    from personalscraper.api.metadata._contracts import MovieDetailsProvider
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper._shared import ScrapeResult
    from personalscraper.scraper.artwork import ArtworkDownloader

log = get_logger("scraper")

# Languages for the TVDB → show_data conversion during recovery. Mirrors the
# sibling repair path (``existing_validator._repair_artwork``); the value only
# affects the show name/overview in the converted payload — image selection is
# driven by the downloader's own language priority, so recovery is insensitive
# to it in practice.
_RECOVERY_PREFERRED_LANGUAGE = "fr-FR"
_RECOVERY_FALLBACK_LANGUAGE = "en-US"


def _coerce_id(raw: str | int | None) -> int | None:
    """Coerce an NFO id (string as parsed by ``extract_nfo_metadata``) to int.

    Args:
        raw: The raw id value (``str`` / ``int`` / ``None``).

    Returns:
        The id as ``int``, or ``None`` when absent or non-numeric.
    """
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def recover_artwork(
    nfo_path: "Path",
    media_dir: "Path",
    result: "ScrapeResult",
    *,
    kind: str,
    registry: "ProviderRegistry",
    artwork: "ArtworkDownloader",
    patterns: "NamingPatterns",
) -> None:
    """Re-download missing artwork, resolving the provider from the canonical family.

    Reads the provider ids from the existing NFO **once** via
    :func:`~personalscraper.nfo_utils.extract_nfo_metadata`, resolves the item's
    canonical family (TVDB-primary for a TV show when a TVDB id is present, TMDB
    otherwise; movies are always TMDB-canonical), refetches from that family and
    downloads the missing images (already-present files are skipped by the
    downloader). On success, sets ``result.action = "artwork_recovered"`` and
    records the downloaded filenames.

    Fixes F7 (SCRAPER-09): a TVDB-only show previously never recovered artwork
    because the path read only the TMDB uniqueid and returned early.

    Args:
        nfo_path: Path to the existing, valid NFO file.
        media_dir: Path to the movie / show directory.
        result: :class:`ScrapeResult` to update with recovery info.
        kind: ``"movie"`` or ``"tvshow"``.
        registry: Provider registry (``get(name)`` resolves the family client).
        artwork: The artwork downloader.
        patterns: Naming patterns for the downloaded filenames.
    """
    # Lazy import (matches the codebase convention for scraper cross-imports and
    # keeps the registry error type off the module import graph).
    from personalscraper.api.metadata.registry._errors import UnknownProviderError  # noqa: PLC0415

    meta = extract_nfo_metadata(nfo_path)
    tmdb_id = _coerce_id(meta.get("tmdb_id"))
    tvdb_id = _coerce_id(meta.get("tvdb_id"))

    # Canonical family: TVDB-primary for TV when present, else TMDB. Movies never
    # take the TVDB branch — TMDB is the movie canonical source.
    if kind == "tvshow" and tvdb_id is not None:
        family, api_id = "tvdb", tvdb_id
    elif tmdb_id is not None:
        family, api_id = "tmdb", tmdb_id
    else:
        # No id in the canonical family → nothing to recover (unchanged
        # early-return: a movie/tmdb-only show with no tmdb id, or a bare NFO).
        return

    # Pre-check (I4): ``registry.get(family)`` raises ``UnknownProviderError``
    # when the family is not configured. Detect it explicitly so the operator
    # sees a structured debug anchor instead of a generic "recovery failed"
    # warning swallowed by the broad ``except`` below.
    try:
        provider = registry.get(family)
    except UnknownProviderError:
        log.debug("artwork_recovery_skipped_no_provider", family=family, directory=media_dir.name)
        return

    # Broad catch: the provider fetch (ApiError / CircuitOpenError / requests)
    # plus the download (OSError) span a mixed API+IO surface not worth
    # narrowing here — every failure is a non-fatal recovery warning.
    try:
        if kind == "movie":
            from personalscraper.scraper._movie_convert import _coerce_to_movie_data  # noqa: PLC0415

            # Direct-dispatch cast (mirrors the old ``_recover_movie_artwork``):
            # ``registry.get`` returns the ``Named`` protocol; the TMDB id was
            # minted by TMDB so artwork is re-pulled from the same canonical
            # source (chain fallback would silently switch the provider).
            movie_data = cast("MovieDetailsProvider", provider).get_movie(api_id)
            downloaded = artwork.download_movie_artwork(_coerce_to_movie_data(movie_data), media_dir, patterns)
        else:
            # Reuse the single TVDB-primary / TMDB-fallback fetch kernel via the
            # module (never the bound name) so the patch/observation point stays
            # ``_tvdb_convert.fetch_show_data``.
            from personalscraper.scraper import _tvdb_convert  # noqa: PLC0415

            show_data, _tmdb_xref = _tvdb_convert.fetch_show_data(
                family,
                api_id,
                provider,
                preferred_language=_RECOVERY_PREFERRED_LANGUAGE,
                fallback_language=_RECOVERY_FALLBACK_LANGUAGE,
            )
            downloaded = artwork.download_tvshow_artwork(show_data, media_dir, patterns)

        if downloaded:
            result.action = "artwork_recovered"
            result.artwork_downloaded = [p.name for p in downloaded]
            log.info("artwork_recovered", count=len(downloaded), directory=media_dir.name, family=family)
    except Exception as e:  # noqa: BLE001 — mixed API+IO path; see comment above
        log.warning("artwork_recovery_failed", directory=media_dir.name, exc_info=True, error=str(e))
        result.warnings.append(f"Artwork recovery failed: {e}")
