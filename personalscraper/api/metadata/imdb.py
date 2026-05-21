"""IMDb façade backed by the internal :class:`OMDbAdapter`.

The scraper layer never talks to OMDb directly (DESIGN §4). It
composes :class:`IMDbClient` and
:class:`~personalscraper.api.metadata.rotten_tomatoes.RottenTomatoesClient`,
which expose the business semantics — ``validate_id``, ``get_rating``,
``get_cross_refs`` — while sharing one :class:`OMDbAdapter` instance so
the rate-limit and circuit-breaker budgets stay consolidated.

This façade composes three atomic capability protocols from
:mod:`personalscraper.api.metadata._contracts` :
:class:`~personalscraper.api.metadata._contracts.IDValidator`,
:class:`~personalscraper.api.metadata._contracts.RatingProvider`,
:class:`~personalscraper.api.metadata._contracts.IDCrossRef`.

OMDb does not surface TVDB / TMDB identifiers when queried by IMDb ID,
so :meth:`IMDbClient.get_cross_refs` always returns an empty mapping.
Cross-reference enrichment happens in phase 5 via the TVDB ↔ TMDB
loop. Keeping the capability on the façade preserves the symmetric
contract — every façade declares the same shape and the consumer
treats an empty result as "no cross-refs from this provider", which is
already the standard convention (DESIGN §4 helpers).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api._helpers import ProviderFeatureUnavailable
from personalscraper.api.metadata._base import MediaDetails, Notations
from personalscraper.api.metadata._contracts import IDCrossRef, IDValidator, RatingProvider

if TYPE_CHECKING:
    from personalscraper.api.metadata.omdb import OMDbAdapter


def _normalize_title(value: str) -> str:
    """Lowercase + strip surrounding whitespace + collapse internal whitespace.

    Used by :meth:`IMDbClient.validate_id` to compare an OMDb-reported
    title against the scraper's expected title. Both sides go through
    the same normaliser so trivial differences (trailing whitespace,
    double spaces, casing) do not poison the validation.

    Args:
        value: Raw title string from either side of the comparison.

    Returns:
        Normalised title — lowercased, whitespace-collapsed, stripped.
    """
    return " ".join(value.lower().split())


class IMDbClient(IDValidator, RatingProvider, IDCrossRef):
    """IMDb business façade — validates IMDb IDs, fetches IMDb ratings.

    Composes :class:`IDValidator`, :class:`RatingProvider`,
    :class:`IDCrossRef` (DESIGN §4). All methods delegate to a shared
    :class:`OMDbAdapter` instance — the OMDb HTTP backend is the
    *only* path to IMDb data (no separate IMDb API key is required).

    Attributes:
        provider_name: Lowercase provider identifier, ``"imdb"``.
    """

    provider_name: ClassVar[str] = "imdb"

    def __init__(self, backend: OMDbAdapter) -> None:
        """Wire the façade onto an existing :class:`OMDbAdapter`.

        Args:
            backend: Shared OMDb HTTP backend. The same instance can
                also back :class:`RottenTomatoesClient` so both façades
                share one rate-limit / circuit-breaker budget.
        """
        self._backend = backend

    # -- IDValidator capability ---------------------------------------------

    def validate_id(
        self,
        provider_id: str,
        expected_title: str,
        expected_year: int | None,
    ) -> bool:
        """Re-validate an IMDb ID against an expected title / year tuple (Q5=B).

        Returns ``True`` when the OMDb-side payload for ``provider_id``
        carries a title that matches ``expected_title`` after
        case- and whitespace-normalisation, *and* (when
        ``expected_year`` is provided) a year that matches exactly.
        ``False`` covers every other case — wrong ID, OMDb hard error,
        title mismatch, year mismatch.

        Args:
            provider_id: IMDb identifier of the form ``"ttNNNNNNN"``.
            expected_title: Title the scraper believes ``provider_id``
                points at.
            expected_year: Release year to compare, or ``None`` to skip
                the year check.

        Returns:
            ``True`` iff the OMDb payload matches both inputs.
        """
        try:
            details = self._backend.get_details(provider_id)
        except ApiError:
            return False
        if _normalize_title(details.title) != _normalize_title(expected_title):
            return False
        if expected_year is not None and details.year is not None and details.year != expected_year:
            return False
        return True

    # -- RatingProvider capability ------------------------------------------

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        """Fetch the IMDb rating entry for ``provider_id``.

        Filters the OMDb ``Ratings[]`` array down to its ``imdb`` source
        rows. Returns ``None`` when OMDb reports no rating at all and
        when the payload carries ratings but none for IMDb (e.g. a
        movie too obscure for an aggregate score). Raises
        :exc:`ProviderFeatureUnavailable` on a hard transport / OMDb
        failure so the consumer can swallow it and continue with the
        other providers (DESIGN §4).

        Args:
            provider_id: IMDb identifier (e.g. ``"tt0944947"``).

        Returns:
            Non-empty ``list[Notations]`` carrying only IMDb entries,
            or ``None`` when no IMDb rating is available.

        Raises:
            ProviderFeatureUnavailable: OMDb returned an
                :class:`ApiError`.
        """
        try:
            notations = self._backend.get_notations(provider_id)
        except ApiError as exc:
            raise ProviderFeatureUnavailable("imdb", "get_rating", str(exc)) from exc
        if not notations:
            return None
        imdb_only = [n for n in notations if n.source == "imdb"]
        return imdb_only or None

    # -- IDCrossRef capability ----------------------------------------------

    def get_cross_refs(self, provider_id: str) -> dict[str, str]:
        """Return cross-provider IDs reachable from an IMDb starting point.

        Always returns ``{}`` — OMDb does not expose TVDB / TMDB IDs
        when queried by IMDb ID. The capability is preserved on the
        façade for contract symmetry (every metadata façade exposes
        :class:`IDCrossRef`) ; consumers iterate cross-refs and
        treat empty dicts as "this provider has nothing to add"
        (DESIGN §4 helpers).

        Args:
            provider_id: IMDb identifier, ignored.

        Returns:
            Empty dict.
        """
        return {}

    # -- Extra helper: full payload access ----------------------------------

    def get_by_id(
        self,
        provider_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> MediaDetails:
        """Fetch the full OMDb-side :class:`MediaDetails` for an IMDb ID.

        Exposed so callers that already paid for a backend round-trip
        in :meth:`validate_id` can reuse the same data instead of
        re-fetching. The return value is the un-filtered OMDb payload
        adapter form — it is *not* an IMDb-specific projection.

        Args:
            provider_id: IMDb identifier.
            media_type: Media type hint forwarded to the OMDb adapter.

        Returns:
            Populated :class:`MediaDetails`.

        Raises:
            ApiError: Underlying OMDb failure (propagated unchanged).
        """
        return self._backend.get_details(provider_id, media_type=media_type)


__all__ = ["IMDbClient"]
