"""Media sheet endpoint - GET /api/media/{provider}/{provider_id} (media-sheet feature).

Implements DESIGN D1-D9: live provider call with an in-memory cache,
library ownership crossing via the existing IndexerOwnershipChecker,
and a French degraded_reason on provider failure - never a 500 or an
empty screen.

Routes are mounted behind the single guarded_api perimeter in app.py,
inheriting Depends(require_session).  Read-only - no require_not_staging
and no pipeline.lock.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from personalscraper.api._contracts import ProviderName
from personalscraper.core._contracts import ApiError, CircuitOpenError
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.logger import get_logger
from personalscraper.web.models.media import (
    MediaSheetResponse,
    OwnershipBlock,
    SeasonOwnership,
)

router = APIRouter(prefix="/api/media", tags=["media"])
log = get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory LRU cache (DESIGN D6) — bounded, TTL-expiring OrderedDict.
# Keyed on (provider, provider_id); value is (response_dict, expiry_ts).
# Oldest entry evicted when len(_cache) > _CACHE_MAX.
# ---------------------------------------------------------------------------
_CACHE_TTL = 300  # seconds
_CACHE_MAX = 256
_cache: OrderedDict[tuple[str, str], tuple[dict[str, Any], float]] = OrderedDict()


def _build_tmdb_client(api_key: str) -> Any:
    """Build a TMDB client with minimal retry for web-request deadlines (D1)."""
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.transport._http import HttpTransport
    from personalscraper.api.transport._policy import RetryPolicy

    retry = RetryPolicy(max_attempts=1)
    policy = TMDBClient.policy(api_key, retry=retry)
    transport = HttpTransport(policy, event_bus=EventBus())
    return TMDBClient(transport, language="fr-FR")


def _build_tvdb_client(api_key: str) -> Any:
    """Build a TVDB client with minimal retry for web-request deadlines (D1)."""
    from personalscraper.api.metadata.tvdb import TVDBClient
    from personalscraper.api.transport._policy import RetryPolicy

    retry = RetryPolicy(max_attempts=1)
    return TVDBClient(api_key, language="fr-FR", retry=retry, event_bus=EventBus())


def _provider_from_name(name: str, api_key: str) -> Any:
    """Build the metadata provider client for *name*.

    Args:
        name: Provider name ("tmdb" or "tvdb").
        api_key: The provider API key from Settings.

    Returns:
        A provider client instance with get_movie / get_tv methods.

    Raises:
        HTTPException: 400 if the provider name is unknown.
    """
    if name == ProviderName.TMDB:
        return _build_tmdb_client(api_key)
    if name == ProviderName.TVDB:
        return _build_tvdb_client(api_key)
    raise HTTPException(status_code=400, detail=f"Fournisseur inconnu : {name}")


def _safe_int(value: str) -> int | None:
    """Parse *value* as an int, returning None on failure.

    Args:
        value: String to parse.

    Returns:
        The parsed int, or None.
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_media_ref(details: Any, provider: str, provider_id: str) -> MediaRef | None:
    """Build a MediaRef from provider details for ownership lookup.

    Args:
        details: A MediaDetails instance.
        provider: Provider name ("tmdb" or "tvdb").
        provider_id: The raw provider id string.

    Returns:
        A MediaRef with as many IDs as available, or None when no usable
        identifier can be extracted.
    """
    tvdb_id: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None

    external_ids: dict[str, str] = getattr(details, "external_ids", {}) or {}

    # TMDB external_ids dict carries tvdb_id + imdb_id as strings
    if provider == "tmdb":
        tmdb_id = _safe_int(provider_id)
        raw_tvdb = external_ids.get("tvdb", "").strip()
        if raw_tvdb and raw_tvdb != "0":
            tvdb_id = _safe_int(raw_tvdb)
        raw_imdb = external_ids.get("imdb", "").strip()
        if raw_imdb:
            imdb_id = raw_imdb

    # TVDB external_ids dict carries tmdb_id + imdb_id
    if provider == "tvdb":
        tvdb_id = _safe_int(provider_id)
        raw_tmdb = external_ids.get("tmdb", "").strip()
        if raw_tmdb and raw_tmdb != "0":
            tmdb_id = _safe_int(raw_tmdb)
        raw_imdb = external_ids.get("imdb", "").strip()
        if raw_imdb:
            imdb_id = raw_imdb

    if tvdb_id is None and tmdb_id is None and imdb_id is None:
        return None

    try:
        return MediaRef(tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)
    except ValueError:
        return None


def _build_seasons_list(details: Any) -> list[dict[str, Any]]:
    """Build the seasons list from provider details.

    Args:
        details: A MediaDetails whose seasons attribute is a list of
            SeasonInfo dataclass instances.

    Returns:
        A list of dicts with season_number and episode_count keys.
    """
    seasons_attr = getattr(details, "seasons", None) or []
    return [{"season_number": s.season_number, "episode_count": s.episode_count} for s in seasons_attr]


def _build_ownership_block(
    details: Any,
    request: Request,
    provider: str,
    provider_id: str,
) -> OwnershipBlock | None:
    """Cross the library for ownership info, returning None on any failure (fail-soft).

    Args:
        details: A MediaDetails from the provider.
        request: The incoming FastAPI request (for app.state.config).
        provider: Provider name.
        provider_id: Provider-specific id.

    Returns:
        An OwnershipBlock when the library is reachable, or None.
    """
    from personalscraper.indexer.ownership import IndexerOwnershipChecker

    config = request.app.state.config
    db_path = config.indexer.db_path
    if db_path is None or not db_path.exists():
        return None

    media_ref = _build_media_ref(details, provider, provider_id)
    if media_ref is None:
        return None

    seasons_catalog = getattr(details, "seasons", None) or []
    has_seasons = len(seasons_catalog) > 0

    checker = IndexerOwnershipChecker(Path(db_path))
    try:
        if has_seasons:
            # TV show: use owned_pairs for per-season breakdown.
            owned_pairs = checker.owned_pairs(media_ref)
            owned = len(owned_pairs) > 0
            # Group owned pairs by season.
            owned_by_season: dict[int, int] = {}
            for season_num, _ep_num in owned_pairs:
                owned_by_season[season_num] = owned_by_season.get(season_num, 0) + 1
            # Build per-season ownership blocks.
            season_blocks: list[SeasonOwnership] = []
            for si in seasons_catalog:
                sn = si.season_number
                ec = si.episode_count
                season_blocks.append(
                    SeasonOwnership(
                        season_number=sn,
                        episode_count=ec,
                        owned_count=owned_by_season.get(sn, 0),
                        aired_count=ec,
                    )
                )
            return OwnershipBlock(owned=owned, seasons=season_blocks)
        else:
            # Movie: simple owns() check.
            owned = checker.owns(media_ref, kind="movie")
            return OwnershipBlock(owned=owned, seasons=[])
    finally:
        checker.close()


def _maybe_evict_cache() -> None:
    """Evict oldest entry when the cache exceeds _CACHE_MAX."""
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


def _is_not_found(exc: ApiError) -> bool:
    """Return True when *exc* is a genuine 404.

    Args:
        exc: An ApiError instance.

    Returns:
        True when ``http_status`` is 404.
    """
    return exc.http_status == 404


def _is_blocking_error(exc: BaseException) -> bool:
    """Return True when *exc* must NOT trigger a fallback call.

    CircuitOpenError: the provider is unavailable — a second call doubles the
    damage. Auth errors (401/403 ApiError): credentials are wrong — a second
    call to the same provider fails the same way.

    Args:
        exc: The exception caught during the first provider call.

    Returns:
        True when the caller must degrade immediately rather than try a fallback.
    """
    if isinstance(exc, CircuitOpenError):
        return True
    if isinstance(exc, ApiError) and exc.http_status in (401, 403):
        return True
    return False


@router.get("/{provider}/{provider_id}", response_model=MediaSheetResponse)
def get_media_sheet(
    provider: str,
    provider_id: str,
    request: Request,
    kind: Literal["movie", "tv"] | None = Query(None, description="Media kind hint to skip wasted probing"),
) -> MediaSheetResponse:
    """Return a full media sheet for a provider-identified media item.

    Fetches metadata from the live provider API (with a short in-memory cache),
    crosses the local library for ownership, and returns typed data.  When the
    provider is unreachable, the response carries a French degraded_reason
    rather than a 500 - the identity fields are always present (DESIGN D9).

    Args:
        provider: Provider name - "tmdb" or "tvdb".
        provider_id: Provider-specific media identifier.
        request: The incoming FastAPI request.
        kind: Optional media kind hint (``"movie"`` or ``"tv"``).  When supplied,
            only the matching provider method is called — no probing, no wasted
            provider round-trip and quota token for a doomed cross-kind lookup.
            Callers always know the kind (search results, followed rows,
            decision candidates); this parameter exists so a read-only detail
            page avoids unnecessary API calls and keeps the degraded reason
            pointing at the real first failure.  Omit for hand-typed URLs
            (no-hint fallback).

    Returns:
        A MediaSheetResponse.

    Raises:
        HTTPException: 400 when *provider* is not "tmdb" / "tvdb".
    """
    # Step 1: Validate provider
    if provider not in (ProviderName.TMDB, ProviderName.TVDB):
        raise HTTPException(
            status_code=400,
            detail=f"Fournisseur inconnu : {provider}. Utilisez 'tmdb' ou 'tvdb'.",
        )

    # Step 2: Check cache
    cache_key = (provider, provider_id)
    now = time.monotonic()
    if cache_key in _cache:
        cached_data, expiry = _cache[cache_key]
        if now < expiry:
            log.debug("media_sheet_cache_hit", provider=provider, provider_id=provider_id)
            # Move to end to preserve LRU order on hit.
            _cache.move_to_end(cache_key)
            return MediaSheetResponse(**cached_data)

    # Step 3: Build provider client
    settings = request.app.state.settings
    api_key = settings.tmdb_api_key if provider == ProviderName.TMDB else settings.tvdb_api_key
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=f"Le fournisseur {provider} n'est pas configure (cle API absente).",
        )

    # Step 4: Fetch from provider.
    # When *kind* is supplied the caller knows the media type — call only the
    # matching method.  A doomed cross-kind lookup (e.g. get_tv for a movie)
    # wastes a provider round-trip and a quota token; it does NOT record a
    # circuit failure — 4xx responses are explicitly excluded from the
    # failure count (see CircuitBreaker._is_circuit_error).  The no-hint
    # fallback probes TV first, but restricts the fallback: only a genuine
    # 404 justifies trying get_movie; any blocking error (circuit open, auth
    # failure) degrades immediately.
    degraded_reason: str | None = None
    details: Any = None
    is_tv: bool | None = None

    try:
        client = _provider_from_name(provider, api_key)

        if kind is not None:
            # Directed lookup — no probing, no doomed call.  A single method
            # call; if it fails the whole request degrades (D9).
            if kind == "tv":
                details = client.get_tv(provider_id)
                is_tv = True
            else:
                details = client.get_movie(provider_id)
                is_tv = False
        else:
            # No-hint fallback: probe TV first, then movie on genuine 404 only.
            # CAUTION: the TV probe wastes a provider round-trip and quota
            # token on a doomed lookup — this is why callers pass *kind*.
            # (A 404 does not record a circuit failure — 4xx errors are
            # excluded per CircuitBreaker._is_circuit_error.)  Blocking
            # errors (circuit open, 401/403) must NOT trigger a fallback call.
            try:
                details = client.get_tv(provider_id)
                is_tv = True
            except CircuitOpenError:
                raise  # re-raised → caught by outer except → degraded response
            except ApiError as exc:
                if _is_not_found(exc):
                    # Genuine 404 — this is a movie, not TV.  Try get_movie.
                    details = client.get_movie(provider_id)
                    is_tv = False
                elif _is_blocking_error(exc):
                    raise  # auth error — degrade, don't double-call
                else:
                    raise  # unexpected API error — degrade
            except Exception:
                # Non-API error (network, timeout, etc.) — try movie.
                details = client.get_movie(provider_id)
                is_tv = False
    except Exception as exc:
        # Provider fully unreachable -> partial response with degraded_reason.
        degraded_reason = f"{provider.upper()} n'a pas repondu : {exc}"
        log.warning("media_sheet_provider_failed", provider=provider, provider_id=provider_id, error=str(exc))
        return MediaSheetResponse(
            provider=provider,
            provider_id=provider_id,
            title=provider_id,  # best-effort title
            year=None,
            poster_url="",
            overview="",
            director=None,
            genres=[],
            trailer_url=None,
            series_status=None,
            seasons=[],
            ownership=None,
            degraded_reason=degraded_reason,
        )

    # Step 5: Cross library ownership
    ownership = _build_ownership_block(details, request, provider, provider_id)

    # Step 6: Build response
    seasons_list = _build_seasons_list(details)
    series_status = getattr(details, "series_status", None) if is_tv else None

    # Determine poster URL: use the first poster from images.
    poster_url = ""
    images = getattr(details, "images", None) or []
    for img in images:
        if getattr(img, "type", "") == "poster" and getattr(img, "url", ""):
            poster_url = img.url
            break

    response = MediaSheetResponse(
        provider=provider,
        provider_id=provider_id,
        title=getattr(details, "title", "") or provider_id,
        year=getattr(details, "year", None),
        poster_url=poster_url,
        overview=getattr(details, "overview", "") or "",
        director=getattr(details, "director", None),
        genres=getattr(details, "genres", None) or [],
        trailer_url=getattr(details, "trailer_url", None),
        series_status=series_status,
        seasons=seasons_list,
        ownership=ownership,
        degraded_reason=degraded_reason,
    )

    # Cache (LRU eviction) and return
    _cache[cache_key] = (response.model_dump(), now + _CACHE_TTL)
    _maybe_evict_cache()
    # Move to end so recently-inserted entries don't get evicted prematurely.
    _cache.move_to_end(cache_key)
    return response
