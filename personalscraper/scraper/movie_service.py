"""Extracted scraper service module."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import requests

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.metadata._base import MediaDetails, Notations
from personalscraper.api.metadata._contracts import MovieDetailsProvider
from personalscraper.api.metadata.registry import AttemptOutcome, RegistryProviderName
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_trailer_filename
from personalscraper.logger import get_logger
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper._movie_convert import _coerce_to_movie_data
from personalscraper.scraper._shared import ScrapeResult, _find_video_file
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.decision_triage import apply_decision_to_result, classify_decision_trigger
from personalscraper.scraper.rename_service import _cleanup_stale_files, _merge_dirs
from personalscraper.text_utils import sanitize_filename

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.conf.models.config import Config
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.confidence import MatchResult
    from personalscraper.scraper.decision_candidate import DecisionCandidate
    from personalscraper.scraper.nfo_generator import NFOGenerator

log = get_logger("scraper")


@dataclass(frozen=True)
class RestoreOutcome:
    """Base for the ``_restore_from_db`` outcome sum type."""

    pass


@dataclass(frozen=True)
class Restored(RestoreOutcome):
    """Restore succeeded — caller sets ``result.action = 'restored_from_db'``."""

    files_copied: int
    nfo_path: Path


@dataclass(frozen=True)
class NoDb(RestoreOutcome):
    """Restoration unavailable — config/db_path missing or non-file."""

    reason: str  # e.g. "config_is_none" | "db_path_is_none" | "db_path_not_path" | "db_file_missing" | "connect_failed"


@dataclass(frozen=True)
class NoMatch(RestoreOutcome):
    """No ``media_item`` row matches the staging title."""

    title: str


@dataclass(frozen=True)
class NoDispatchPath(RestoreOutcome):
    """Matched item has no ``dispatch_path`` attribute or it points to a missing dir."""

    item_id: int


@dataclass(frozen=True)
class NoNfoAtDispatch(RestoreOutcome):
    """Dispatch directory exists but contains no NFO files."""

    item_id: int
    dispatch_path: str


@dataclass(frozen=True)
class AmbiguousNfo(RestoreOutcome):
    """Multiple NFO candidates at dispatch — manual review required."""

    item_id: int
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class CopyFailed(RestoreOutcome):
    """Filesystem copy failed mid-way; rollback executed."""

    files_rolled_back: int
    error: str


def _restore_from_db(
    config: "Config | None",
    dry_run: bool,
    movie_dir: Path,
    title: str,
    year: int | None,
) -> RestoreOutcome:
    """Restore NFO and artwork from BDD when a re-ingested movie has a valid DB entry.

    When a movie in staging produces no confident TMDB match but already
    has a valid ``media_item`` row (from a previous successful
    scrape+dispatch), this copies the NFO and artwork files back from
    the original dispatch location to the staging directory.

    Fail-soft — every early return produces a typed ``RestoreOutcome``
    variant instead of mutating a ``ScrapeResult``.

    Args:
        config: Application config (may be None or test stub).
        dry_run: If True, log what would be copied without copying.
        movie_dir: Path to the staging movie directory.
        title: Parsed movie title for the DB lookup.
        year: Optional release year (informational for logging).

    Returns:
        A ``RestoreOutcome`` variant (``Restored`` on success, or a
        skip/failure variant describing why restoration didn't happen).
    """
    # 1. Guard: no config or no db_path
    if config is None:
        return NoDb(reason="config_is_none")
    db_path = config.indexer.db_path
    if db_path is None:
        return NoDb(reason="db_path_is_none")
    if isinstance(db_path, str):
        db_path = Path(db_path)
    if not isinstance(db_path, Path):
        log.info(
            "movie_db_restore_skipped_db_path_not_path",
            reason="config.indexer.db_path is not a string or Path (likely MagicMock test stub)",
            type=type(db_path).__name__,
        )
        return NoDb(reason="db_path_not_path")

    db_file = db_path.expanduser()
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file
    if not db_file.is_file():
        return NoDb(reason="db_file_missing")

    # 2. Open connection with canonical PRAGMA
    try:
        from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

        conn = sqlite3.connect(str(db_file))
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
    except Exception:
        log.warning("movie_db_restore_connect_failed", db_path=str(db_file), exc_info=True)
        return NoDb(reason="connect_failed")

    copied_files: list[Path] = []
    try:
        # 3. Look up a valid BDD entry by title
        row = conn.execute(
            "SELECT mi.id, mi.year AS media_year, ia.value AS dispatch_path "
            "FROM media_item mi "
            "LEFT JOIN item_attribute ia ON ia.item_id = mi.id AND ia.key = 'dispatch_path' "
            "WHERE mi.kind = 'movie' AND mi.title = ? AND mi.nfo_status = 'valid' "
            "ORDER BY mi.date_modified DESC LIMIT 1",
            (title,),
        ).fetchone()

        if row is None:
            log.info("movie_db_restore_skipped_no_match", title=title, year=year)
            return NoMatch(title=title)

        item_id = row["id"]
        dispatch_path_str = row["dispatch_path"]

        if dispatch_path_str is None:
            log.info("movie_db_restore_skipped_no_dispatch_path", title=title, item_id=item_id)
            return NoDispatchPath(item_id=item_id)

        dispatch_dir = Path(dispatch_path_str)
        if not dispatch_dir.is_dir():
            log.info(
                "movie_db_restore_skipped_dispatch_path_missing",
                title=title,
                dispatch_path=str(dispatch_dir),
            )
            return NoDispatchPath(item_id=item_id)

        # 4. Locate NFO file at dispatch location
        from personalscraper.nfo_utils import glob_nfo_candidates  # noqa: PLC0415

        nfo_files = glob_nfo_candidates(dispatch_dir)
        if not nfo_files:
            log.info(
                "movie_db_restore_skipped_no_nfo_at_dispatch",
                title=title,
                dispatch_path=str(dispatch_dir),
            )
            return NoNfoAtDispatch(item_id=item_id, dispatch_path=str(dispatch_dir))
        if len(nfo_files) > 1:
            log.info(
                "movie_db_restore_skipped_ambiguous_nfo",
                title=title,
                dispatch_path=str(dispatch_dir),
                candidates=[f.name for f in nfo_files],
            )
            return AmbiguousNfo(
                item_id=item_id,
                candidates=tuple(f.name for f in nfo_files),
            )

        dispatch_nfo = nfo_files[0]
        dest_nfo = movie_dir / dispatch_nfo.name

        # 5. Locate artwork files (any image at the dispatch root)
        artwork_files: list[Path] = []
        for ext in (".jpg", ".png", ".jpeg"):
            artwork_files.extend(sorted(dispatch_dir.glob(f"*{ext}")))

        # 6. Copy (or log in dry-run mode)
        if dry_run:
            log.info(
                "movie_db_restore_would_copy",
                title=title,
                item_id=item_id,
                dispatch_path=str(dispatch_dir),
                nfo=dispatch_nfo.name,
                artwork=[f.name for f in artwork_files],
            )
            return Restored(files_copied=0, nfo_path=dest_nfo)

        import shutil

        shutil.copy2(dispatch_nfo, dest_nfo)
        copied_files.append(dest_nfo)
        log.info(
            "movie_db_restore_copied_nfo",
            src=str(dispatch_nfo),
            dst=str(dest_nfo),
        )

        for art_file in artwork_files:
            dest_art = movie_dir / art_file.name
            shutil.copy2(art_file, dest_art)
            copied_files.append(dest_art)
            log.info(
                "movie_db_restore_copied_artwork",
                src=str(art_file),
                dst=str(dest_art),
            )

        log.info(
            "movie_db_restore_success",
            title=title,
            item_id=item_id,
            dispatch_path=str(dispatch_dir),
            files_copied=len(copied_files),
        )
        return Restored(files_copied=len(copied_files), nfo_path=dest_nfo)

    except Exception as exc:
        log.warning(
            "movie_db_restore_failed",
            title=title,
            files_to_rollback=len(copied_files),
            exc_info=True,
        )
        for f in copied_files:
            try:
                f.unlink(missing_ok=True)
            except OSError as unlink_exc:
                log.warning(
                    "movie_db_restore_rollback_failed",
                    path=str(f),
                    error=str(unlink_exc),
                )
        return CopyFailed(files_rolled_back=len(copied_files), error=str(exc))
    finally:
        try:
            conn.close()
        except Exception:
            pass


_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2}(?:-E\d{2,})? - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


class MovieServiceMixin:
    """Movie scrape service methods.

    Provider access goes through ``self._registry`` (DESIGN §5.2). Phase 1 uses
    ``self._registry.get("tmdb")`` / ``get("tvdb")`` as transitional direct
    access; Phase 2 will migrate Movie/TV matching to ``registry.chain()`` and
    Artwork/Keyword/Video to ``registry.locked()`` (identity-locked semantics).
    """

    patterns: "NamingPatterns"
    dry_run: bool
    _registry: "ProviderRegistry"
    _artwork: "ArtworkDownloader"
    config: "Config | None"
    _nfo: "NFOGenerator"
    _classify_item: "Callable[..., str | None]"
    _resolve_title: "Callable[..., str]"
    _strip_trailing_year: "Callable[[str], str]"
    _check_missing_movie_artwork: "Callable[..., list[str]]"
    _recover_movie_artwork: "Callable[..., None]"
    _repair_movie_dir: "Callable[..., bool]"

    def _resolve_external_ids(
        self,
        canonical_provider: str,
        movie_ids: dict[str, str],
        expected_title: str,
        expected_year: int | None,
    ) -> tuple[dict[str, str], list["Notations"]]:
        """Resolve trusted cross-provider IDs + ratings for a movie (Q5=B).

        Thin delegate to
        :func:`personalscraper.scraper._xref.resolve_external_ids` —
        the TV and movie services share one implementation. Movies
        differ only in that there is no per-episode ``_xref_enrichment``
        companion step.
        """
        from personalscraper.scraper._xref import resolve_external_ids as _resolve  # noqa: PLC0415

        return _resolve(
            canonical_provider=canonical_provider,
            ids=movie_ids,
            expected_title=expected_title,
            expected_year=expected_year,
            family_to_client=self._family_to_client,
            imdb_client=getattr(self, "_imdb", None),
            rt_client=getattr(self, "_rotten_tomatoes", None),
        )

    def _family_to_client(self, family: str) -> Any | None:
        """Map a provider family to the wired client / façade (or ``None``).

        Transitional access via the registry (Phase 1 — DESIGN §5.2). The
        registry raises ``UnknownProviderError`` for names it does not know;
        we treat that as ``None`` to preserve the legacy fail-soft contract
        of this helper (xref enrichment and ratings resolution both consume
        the ``None`` branch).
        """
        from personalscraper.api.metadata.registry._errors import UnknownProviderError  # noqa: PLC0415

        # ``imdb`` / ``rotten_tomatoes`` remain optional companion façades
        # injected by other call sites; the registry currently only owns the
        # canonical "tmdb"/"tvdb" providers (Phase 1 scope).
        if family in {"tmdb", "tvdb"}:
            try:
                return self._registry.get(family)
            except UnknownProviderError as e:
                # If boot validation passed but we reach here, this is a runtime
                # contract violation worth a forensic anchor (the registry's
                # config should already have caught an unwired family).
                log.warning(
                    "xref_family_unwired",
                    family=family,
                    exc_type=type(e).__name__,
                )
                return None
        mapping: dict[str, Any] = {
            "imdb": getattr(self, "_imdb", None),
        }
        return mapping.get(family)

    def _match_movie_candidates(
        self,
        title: str,
        year: int | None,
        result: ScrapeResult,
    ) -> tuple[MatchResult | None, list[DecisionCandidate]]:
        """Search the configured movie chain for candidates matching title + year.

        Iterates ``self._registry.chain(MovieDetailsProvider)`` per DESIGN §6.2
        and tries each eligible provider in priority order. Per-provider
        failures emit :class:`ProviderFallbackTriggered`; full chain
        exhaustion (every attempt errored) emits
        :class:`ProviderExhaustedEvent` **and raises**
        :class:`ProviderExhausted` (DESIGN §6.2 line 79, restored in
        Phase 16). The immediate caller (:meth:`scrape_movie`) catches
        and surfaces a legacy fail-soft ``result.error`` containing the
        original exception's message — the ACC-13 contract
        (``"API down" in result.error``) is preserved because
        :attr:`ProviderExhausted.last_exception` carries the underlying
        :class:`ApiError` / :class:`OSError`.

        Branch semantics (closed list — DESIGN §6.2):

        - ``circuit_open`` — :class:`CircuitOpenError` raised by the
          provider; record outcome, emit fallback, continue.
        - ``network`` — :class:`ApiError`, :class:`requests.RequestException`,
          or :class:`OSError` (including :class:`ConnectionError`); record
          outcome with ``exc_type``, emit fallback, continue.
        - ``empty_result`` — provider returned ``None`` (no candidates);
          emit fallback, continue.
        - Any other exception — set ``result.error``, log, return ``None``
          (preserves the legacy fail-soft contract used by orchestrator).

        Returns the **first** provider's MatchResult and scored candidate list
        (even if low-confidence — the confidence threshold is the caller's
        responsibility, see ``_select_best_candidate``).

        Args:
            title: Movie title to search for.
            year: Optional release year to narrow the search.
            result: ScrapeResult for error tracking.

        Returns:
            Tuple of (MatchResult, top-5 DecisionCandidate list) on the first
            successful provider call, or ``(None, [])`` when
            ``result.error`` was populated (unclassified exception)
            or every chain provider returned an empty result (legacy
            ``skipped_low_confidence`` path).

        Raises:
            ProviderExhausted: When at least one chain provider raised
                a classified failure (``circuit_open`` / ``network``) and
                no provider returned a match. The caller is responsible
                for catching and surfacing the error in ``result.error``.
        """
        from personalscraper.scraper.confidence import match_movie_detailed  # noqa: PLC0415

        item_context: dict[str, Any] = {"title": title, "year": year, "media_type": "movie"}
        providers = self._registry.chain(MovieDetailsProvider)  # type: ignore[type-abstract]
        attempted: list[AttemptOutcome] = []
        last_exception: Exception | None = None
        all_candidates: list[DecisionCandidate] = []

        for provider in providers:
            provider_name = getattr(provider, "provider_name", "?")
            try:
                best, candidates = match_movie_detailed(provider, title, year)
                all_candidates = candidates
            except CircuitOpenError as exc:
                last_exception = exc
                attempted.append(AttemptOutcome(provider=RegistryProviderName(provider_name), reason="circuit_open"))
                log.debug(
                    "registry_provider_skip",
                    provider=provider_name,
                    capability="MovieDetailsProvider",
                    reason="circuit_open",
                )
                self._registry.emit_provider_fallback(
                    capability="MovieDetailsProvider",
                    from_provider=provider_name,
                    reason="circuit_open",
                    item=item_context,
                )
                continue
            except (ApiError, requests.RequestException, OSError) as exc:
                last_exception = exc
                attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(provider_name),
                        reason="network",
                        detail=type(exc).__name__,
                    )
                )
                log.warning(
                    "registry_provider_fail",
                    provider=provider_name,
                    capability="MovieDetailsProvider",
                    exc_type=type(exc).__name__,
                )
                self._registry.emit_provider_fallback(
                    capability="MovieDetailsProvider",
                    from_provider=provider_name,
                    reason="network",
                    exc_type=type(exc).__name__,
                    item=item_context,
                )
                continue
            except Exception as exc:  # noqa: BLE001 — DESIGN §6.2 fallback on unclassified
                # Unclassified provider failure — DESIGN §6.2 promises chain
                # fallback ("first provider that returns a usable result wins"),
                # so we record the attempt, emit a ``reason="other"`` fallback
                # event for observers, and continue to the next provider.
                # Phase 21 (C2): restored chain semantics that previous code
                # broke by short-circuiting here with ``result.error`` /
                # ``return None``.
                last_exception = exc
                attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(provider_name),
                        reason="other",
                        detail=type(exc).__name__,
                    )
                )
                log.warning(
                    "registry_provider_fail",
                    provider=provider_name,
                    capability="MovieDetailsProvider",
                    exc_type=type(exc).__name__,
                )
                self._registry.emit_provider_fallback(
                    capability="MovieDetailsProvider",
                    from_provider=provider_name,
                    reason="other",
                    exc_type=type(exc).__name__,
                    item=item_context,
                )
                continue

            if best is None:
                attempted.append(AttemptOutcome(provider=RegistryProviderName(provider_name), reason="empty_result"))
                log.debug(
                    "registry_provider_skip",
                    provider=provider_name,
                    capability="MovieDetailsProvider",
                    reason="empty_result",
                )
                self._registry.emit_provider_fallback(
                    capability="MovieDetailsProvider",
                    from_provider=provider_name,
                    reason="empty_result",
                    item=item_context,
                )
                continue

            return best, all_candidates

        # All providers attempted and none produced a match.
        if attempted and any(a.reason in {"circuit_open", "network", "other"} for a in attempted):
            # At least one attempt errored (chain actually broken). Emit
            # the exhausted event for observers, then RAISE
            # ``ProviderExhausted`` per DESIGN §6.2. The caller
            # (:meth:`scrape_movie`) catches and surfaces a
            # legacy-shape ``result.error`` carrying the original
            # exception's detail (ACC-13 contract).
            self._registry.emit_provider_exhausted(
                capability="MovieDetailsProvider",
                attempted=attempted,
                item=item_context,
            )
            log.error(
                "registry_chain_exhausted",
                capability="MovieDetailsProvider",
                attempted=[(a.provider, a.reason) for a in attempted],
                item=item_context,
            )
            raise ProviderExhausted(
                capability=MovieDetailsProvider,
                attempted=attempted,
                item_context=item_context,
                last_exception=last_exception,
            )
        # Empty chain or all empty_result → legacy "no confident match"
        # path (caller branches on the None return to set
        # ``skipped_low_confidence`` and try ``_restore_from_db``).
        return None, []

    def _select_best_candidate(
        self,
        match: MatchResult | None,
        title: str,
        year: int | None,
        result: ScrapeResult,
        candidates: list[DecisionCandidate] | None = None,
    ) -> bool:
        """Route a match through the three-tier decision logic (DESIGN §4).

        Delegates to :mod:`~personalscraper.scraper.decision_triage`.

        Returns:
            True for clean auto-accept, False otherwise.
        """
        trigger = classify_decision_trigger(match, candidates)
        if trigger is not None:
            apply_decision_to_result(result, match, candidates, trigger)
            if trigger == "below_threshold":
                log.warning(
                    "movie_no_confident_match",
                    title=title,
                    year=year,
                    score=round(match.confidence if match else 0.0, 2),
                )
            else:
                assert match is not None  # narrowed by classify_decision_trigger
                log.info(
                    "movie_queued_for_decision",
                    title=title,
                    api_title=match.api_title,
                    source=match.source,
                    confidence=round(match.confidence, 2),
                    trigger=trigger,
                    runner_up_score=(round(candidates[1].score, 2) if trigger == "ambiguous" and candidates else None),
                )
            return False
        assert match is not None  # narrowed by classify_decision_trigger
        result.match = match
        log.info(
            "movie_matched",
            title=title,
            api_title=match.api_title,
            source=match.source,
            confidence=round(match.confidence, 2),
        )
        return True

    def scrape_movie(self, movie_dir: Path) -> ScrapeResult:
        """Scrape a single movie: match -> NFO -> artwork.

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
            # Check for missing artwork -- recover without re-scraping
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

        # Corrupt/drifted NFO: do NOT delete it up front.  A confident
        # re-scrape overwrites it atomically (``write_nfo`` → ``atomic_write_text``)
        # further down, so the pre-emptive unlink was unnecessary there — and
        # harmful when the re-match turns out AMBIGUOUS: that path returns early
        # (``queued_for_decision``) WITHOUT writing a fresh NFO, so unlinking here
        # left the folder with no NFO at all while a decision waited (webui-overhaul
        # #3 — 'resolved but unscraped'). Keeping the drifted NFO means the item is
        # never worse off than before the re-scrape: the confident path replaces it,
        # every early-return path preserves it.
        if nfo_path.exists() and not _is_nfo_complete(nfo_path):
            log.warning("nfo_drift_detected", filename=nfo_path.name)

        # Match against TMDB. The chain raises ``ProviderExhausted`` when
        # every eligible provider failed with a classified error
        # (``circuit_open`` / ``network``) — DESIGN §6.2 line 79. Catch
        # and surface the original exception detail in ``result.error``
        # to preserve the ACC-13 legacy contract.
        try:
            match, candidates = self._match_movie_candidates(title, year, result)
        except ProviderExhausted as exc:
            detail = exc.last_exception if exc.last_exception is not None else exc
            result.error = f"Match failed: {detail}"
            result.action = "error"
            return result
        if result.error:
            return result
        if not self._select_best_candidate(match, title, year, result, candidates):
            # queued_for_decision items (mid_band, ambiguous) return early —
            # no db restore, no NFO/artwork. The item stays in staging until
            # the operator resolves the decision.
            if result.action == "queued_for_decision":
                return result
            # below_threshold → try db restore (existing behavior), then
            # additively set decision_candidates so the item lands in the
            # decision queue even when restoration fails.
            outcome = _restore_from_db(self.config, self.dry_run, movie_dir, title, year)
            if isinstance(outcome, Restored):
                result.action = "restored_from_db"
                # A successful restore recovered a valid NFO (identity already
                # known, item healthy + dispatchable) — it needs no operator
                # decision.  Clear the additive decision fields set above so the
                # enqueue path in run_scrape does not create a spurious pending
                # row for it (F10/F17: restored items are not queued).
                result.decision_candidates = None
                result.decision_trigger = None
            else:
                result.action = "skipped_low_confidence"
            return result
        assert match is not None  # narrowed by _select_best_candidate returning True

        # Get full movie details via chain iteration (DESIGN §6.2). Iterate
        # ``registry.chain(MovieDetailsProvider)`` and try each provider that
        # owns the match's source id (others would need cross_ref translation
        # — out of scope until sub-phase 7.4). Per-provider failures emit
        # ``ProviderFallbackTriggered``; total chain exhaustion emits
        # ``ProviderExhaustedEvent`` and populates ``result.error``.
        details_item_context: dict[str, Any] = {
            "title": match.api_title,
            "year": match.api_year,
            "media_type": "movie",
            "provider_id": match.api_id,
        }
        movie_data: MediaDetails | dict[str, Any] | None = None
        details_attempted: list[AttemptOutcome] = []
        details_providers = self._registry.chain(MovieDetailsProvider)  # type: ignore[type-abstract]
        for provider in details_providers:
            provider_name = getattr(provider, "provider_name", "?")
            # Honour the source-of-match invariant: only consult the provider
            # that produced the MatchResult. Cross-provider translation (e.g.
            # TMDB id → TVDB id) is owned by ``registry.cross_ref`` and lands
            # in sub-phase 7.4 (existing_validator) — out of scope for 7.1.
            if provider_name != match.source:
                continue
            # Runtime isinstance + narrow: the chain overload returns a
            # union type for type-checkers (Searchable | MovieDetailsProvider
            # | TvDetailsProvider | EpisodeFetcher); the guard restores
            # the MovieDetailsProvider Protocol shape for ``get_movie``.
            if not isinstance(provider, MovieDetailsProvider):
                continue
            try:
                movie_data = provider.get_movie(str(match.api_id))
                break
            except CircuitOpenError:
                details_attempted.append(
                    AttemptOutcome(provider=RegistryProviderName(provider_name), reason="circuit_open")
                )
                self._registry.emit_provider_fallback(
                    capability="MovieDetailsProvider",
                    from_provider=provider_name,
                    reason="circuit_open",
                    item=details_item_context,
                )
                continue
            except (ApiError, requests.RequestException, OSError) as exc:
                details_attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(provider_name),
                        reason="network",
                        detail=type(exc).__name__,
                    )
                )
                self._registry.emit_provider_fallback(
                    capability="MovieDetailsProvider",
                    from_provider=provider_name,
                    reason="network",
                    exc_type=type(exc).__name__,
                    item=details_item_context,
                )
                continue
            except Exception as exc:  # noqa: BLE001 — DESIGN §6.2 fallback on unclassified
                # Unclassified failure — Phase 21 (C2) restores DESIGN §6.2
                # fallback semantics: record the attempt with reason="other",
                # emit ProviderFallbackTriggered for observers, and continue
                # to the next eligible provider in the chain. If every
                # candidate fails the post-loop exhausted branch surfaces
                # ``result.error`` (ACC-13 legacy shape).
                details_attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(provider_name),
                        reason="other",
                        detail=type(exc).__name__,
                    )
                )
                self._registry.emit_provider_fallback(
                    capability="MovieDetailsProvider",
                    from_provider=provider_name,
                    reason="other",
                    exc_type=type(exc).__name__,
                    item=details_item_context,
                )
                log.warning(
                    "movie_details_failed",
                    api_title=match.api_title,
                    provider=provider_name,
                    exc_type=type(exc).__name__,
                    error=str(exc),
                )
                continue

        if movie_data is None:
            # Either no provider matched ``match.source`` or every attempt
            # in that subset failed. Emit the exhausted event and surface
            # the legacy ``result.error`` path so the orchestrator records
            # ``action="error"``.
            if details_attempted:
                self._registry.emit_provider_exhausted(
                    capability="MovieDetailsProvider",
                    attempted=details_attempted,
                    item=details_item_context,
                )
                log.error(
                    "registry_chain_exhausted",
                    capability="MovieDetailsProvider",
                    attempted=[(a.provider, a.reason) for a in details_attempted],
                    item=details_item_context,
                )
                result.error = f"Get details failed: all providers exhausted for {MovieDetailsProvider.__name__}"
            else:
                result.error = f"Get details failed: no provider available for source={match.source!r}"
                log.error("movie_details_no_provider", api_title=match.api_title, source=match.source)
            return result

        return self._write_confirmed_movie(movie_dir, match, movie_data, title, year, result)

    def _write_confirmed_movie(
        self,
        movie_dir: Path,
        match: MatchResult,
        movie_data: MediaDetails | dict[str, Any],
        title: str,
        year: int | None,
        result: ScrapeResult,
    ) -> ScrapeResult:
        """Apply a confirmed movie match to the folder (rename + NFO + artwork).

        The canonical write shared by the automatic scrape (:meth:`scrape_movie`,
        after a confident/selected match) and the operator-forced resolve
        (:meth:`scrape_movie_forced`). Renames the folder to ``Title (Year)``,
        renames the video to the canonical ``Title.<ext>``, removes orphan root
        videos, classifies the category, writes the NFO and downloads artwork —
        exactly the shape the ``verify`` step and dispatch expect. Extracted
        verbatim from ``scrape_movie`` so a manual resolution produces an
        identical, complete result instead of a partial NFO-only write.

        Args:
            movie_dir: The movie's staging directory (pre-rename).
            match: The confirmed :class:`MatchResult` (provider id/title/year).
            movie_data: Provider details (typed ``MediaDetails`` or legacy dict).
            title: Parsed folder title (year stripped).
            year: Parsed folder year (fallback when the API omits one).
            result: The :class:`ScrapeResult` to populate and return.

        Returns:
            The populated :class:`ScrapeResult` (``action="scraped"`` on success).
        """
        nfo_name = self.patterns.format("movie_nfo", Title=title)
        nfo_path = movie_dir / nfo_name

        # Resolve title: use local FR title if preferred and available
        resolved_title = self._strip_trailing_year(self._resolve_title(match.api_title, movie_data, "movie"))
        api_year = match.api_year or year
        # Folder name is filesystem-safe (sanitize_filename strips ``:``, ``?``,
        # ``"`` etc. for NTFS compatibility) while the NFO ``<title>`` keeps
        # the original punctuation for Plex/Kodi display. The two values are
        # *intentionally* allowed to diverge -- same item ``Some Show: Subtitle``
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

            # Remove non-canonical video files left at the movie root. When two
            # distinct staged folders resolve to the same TMDB id, _merge_dirs
            # folds both into one folder, so several video files can coexist at
            # the root. _find_video_file picked the most-recently-modified one as
            # canonical (above); every other root-level video is an orphan from
            # the merged source and must go. Iterate non-recursively so videos in
            # Trailers/ or Extras/ sub-folders are never touched (movies are flat
            # at the root).
            #
            # Scope-consistency guard: _find_video_file selects RECURSIVELY
            # (rglob), so the canonical may legitimately live in a sub-dir (e.g.
            # an Extras/ video that was the newest). The cleanup below is
            # root-only and skips by-name comparison against the canonical; if
            # the canonical is NOT itself at the root, that name-based skip
            # cannot protect it and the loop would delete every root video.
            # Only run the cleanup when selection and cleanup share the same
            # scope — i.e. the canonical sits at the movie root. Otherwise skip;
            # VERIFY's no_duplicate_videos check still backstops residual roots.
            if video_file.parent == movie_dir:
                for entry in sorted(movie_dir.iterdir()):
                    if not entry.is_file() or entry.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                        continue
                    # A flat movie trailer ({name}-trailer.{ext}) legitimately lives
                    # at the movie root (Plex Local Media Assets) — never unlink it.
                    if is_trailer_filename(entry.name):
                        continue
                    if entry.name == video_file.name:
                        continue
                    if self.dry_run:
                        log.info("movie_video_orphan_would_remove", filename=entry.name, parent=movie_dir.name)
                        continue
                    try:
                        entry.unlink()
                        log.info("movie_video_orphan_removed", filename=entry.name, parent=movie_dir.name)
                    except OSError as exc:
                        log.warning(
                            "movie_video_orphan_remove_failed",
                            filename=entry.name,
                            parent=movie_dir.name,
                            error=str(exc),
                        )
                        # Surface the residual duplicate so the scrape result does
                        # not self-report clean success while an orphan persists
                        # (mirrors the rename-failure branch above). Fail-soft: the
                        # ``continue`` semantics are preserved — one failing orphan
                        # must not abort cleanup of the others.
                        result.warnings.append(f"Orphan video not removed: {entry.name}: {exc}")

            from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

            stream_info = scraper_api.extract_stream_info(video_file)

        # Classify item -- must run before NFO write so the
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
            # Config is present but no category matched -- skip this item
            result.action = "skipped_no_category"
            return result

        # api-unify phase 27: movie_data arrives as MediaDetails from
        # ``self._registry.get("tmdb").get_movie``. Adapt to the legacy raw-dict shape the
        # NFO generator + artwork downloader still consume. Once those two
        # consumers migrate to MediaDetails, this conversion can be deleted.
        movie_data_dict = _coerce_to_movie_data(movie_data)

        # Generate and write NFO
        try:
            xml = self._nfo.generate_movie_nfo(movie_data_dict, stream_info, category_id=category_id)
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
                movie_data_dict,
                movie_dir,
                self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except (requests.RequestException, OSError, KeyError, AttributeError) as e:
            log.warning("movie_artwork_failed", title=title, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork failed: {e}")

        result.action = "scraped"
        return result

    def scrape_movie_forced(self, movie_dir: Path, provider_id: int) -> ScrapeResult:
        """Scrape a movie against an operator-chosen TMDB id, bypassing matching.

        A manual resolution / re-scrape: the operator has already asserted the
        identity, so this skips confidence matching entirely and fetches the
        chosen TMDB id directly, then runs the SAME canonical write as the
        automatic scrape (:meth:`_write_confirmed_movie`) — folder rename, video
        rename, NFO and artwork. This is what makes a resolved item complete and
        dispatchable (webui-overhaul / product-intent §méthode); the previous
        NFO-only resolve left the folder + video unrenamed, so ``verify`` blocked
        dispatch on a poster-name mismatch.

        Args:
            movie_dir: The movie's staging directory.
            provider_id: The operator-chosen TMDB movie id (movies are TMDB-only).

        Returns:
            A :class:`ScrapeResult`; ``action="error"`` with ``result.error`` set
            when the provider fetch fails (fail-soft, never raises).
        """
        from personalscraper.scraper.confidence import MatchResult  # noqa: PLC0415

        title, year = _parse_folder_name(movie_dir.name)
        result = ScrapeResult(media_path=movie_dir, media_type="movie")
        # Movies are TMDB-only; cast to the details protocol for the direct fetch
        # (the automatic path reaches the same call via a chain + isinstance guard).
        provider = cast("MovieDetailsProvider", self._registry.get("tmdb"))
        try:
            movie_data = provider.get_movie(str(provider_id))
        except Exception as exc:  # noqa: BLE001 — surfaced as a fail-soft result
            result.error = f"Get details failed: {exc}"
            result.action = "error"
            log.error("forced_movie_details_failed", provider_id=provider_id, error=str(exc))
            return result
        # Build the forced match from the fetched details so ``_resolve_title``
        # has the provider's canonical title even when ``prefer_local_title`` is
        # off (it falls back to ``match.api_title``). Year comes from the coerced
        # ``release_date`` (the dict shape has no ``year`` key).
        coerced = _coerce_to_movie_data(movie_data)
        api_title = str(coerced.get("title") or title)
        release_date = str(coerced.get("release_date") or "")
        api_year = int(release_date[:4]) if release_date[:4].isdigit() else year
        match = MatchResult(
            api_id=provider_id,
            api_title=api_title,
            api_year=api_year,
            confidence=1.0,
            source="tmdb",
        )
        return self._write_confirmed_movie(movie_dir, match, movie_data, title, year, result)
