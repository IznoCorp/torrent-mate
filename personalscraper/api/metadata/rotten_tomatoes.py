"""Rotten Tomatoes façade backed by the internal :class:`OMDbAdapter`.

OMDb is the only practical way to obtain a Rotten Tomatoes score
without dealing with the upstream's authenticated APIs ; it returns a
Rotten-Tomatoes-source row in the ``Ratings[]`` array of every movie
detail response. :class:`RottenTomatoesClient` projects that row down
to the :class:`RatingProvider` capability protocol.

The façade *only* composes :class:`RatingProvider` (DESIGN §4) —
unlike :class:`~personalscraper.api.metadata.imdb.IMDbClient`, OMDb
gives us no Rotten-Tomatoes-side identifier to validate or cross-ref,
so no :class:`IDValidator` and no :class:`IDCrossRef` are implemented
here. Consumers detect this via :func:`isinstance` (the helpers in
:mod:`personalscraper.api._helpers` already filter on capability).

When OMDb returns a payload that does not contain a Rotten Tomatoes
entry — a frequent case for niche or non-US releases —
:meth:`RottenTomatoesClient.get_rating` returns ``None``. When the
OMDb call itself fails (hard ``ApiError`` on the transport / 5xx),
the façade raises :exc:`ProviderFeatureUnavailable` so the helper
functions can swallow it and continue with the remaining providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from personalscraper.api._contracts import ApiError
from personalscraper.api._helpers import ProviderFeatureUnavailable
from personalscraper.api.metadata._base import Notations
from personalscraper.api.metadata._contracts import RatingProvider
from personalscraper.api.metadata.omdb import OmdbQuotaExhausted

if TYPE_CHECKING:
    from personalscraper.api.metadata.omdb import OMDbAdapter


class RottenTomatoesClient(RatingProvider):
    """Rotten Tomatoes business façade — extracts the RT row from OMDb payloads.

    Composes :class:`RatingProvider` (DESIGN §4). The lookup is
    keyed by **IMDb identifier** — OMDb does not surface a separate
    Rotten Tomatoes ID, so the caller queries by the canonical IMDb ID
    and the façade returns whatever Rotten Tomatoes row OMDb embeds
    in the response.

    Attributes:
        provider_name: Lowercase provider identifier,
            ``"rotten_tomatoes"``.
    """

    provider_name: ClassVar[str] = "rotten_tomatoes"

    def __init__(self, backend: OMDbAdapter) -> None:
        """Wire the façade onto an existing :class:`OMDbAdapter`.

        Args:
            backend: Shared OMDb HTTP backend (typically the same
                instance that backs :class:`IMDbClient` so both façades
                draw from a single rate-limit / circuit-breaker
                budget).
        """
        self._backend = backend

    # -- RatingProvider capability ------------------------------------------

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        """Return the Rotten Tomatoes rating row for an IMDb ID.

        Filters the OMDb ``Ratings[]`` array down to its
        ``rotten_tomatoes`` source rows. Returns ``None`` in two
        distinct "no rating available" cases :

        - OMDb has no rating data at all for this ID.
        - OMDb has ratings but none from Rotten Tomatoes.

        Raises :exc:`ProviderFeatureUnavailable` only when the
        underlying OMDb call hard-fails (transport error,
        :class:`ApiError`). That is the structural-unavailability
        case (DESIGN §4) — distinct from the soft ``None`` outcome.

        Args:
            provider_id: IMDb identifier (e.g. ``"tt0468569"``).
                OMDb is queried by this key.

        Returns:
            Non-empty ``list[Notations]`` carrying only Rotten Tomatoes
            entries, or ``None`` when no RT rating is available.

        Raises:
            OmdbQuotaExhausted: OMDb daily quota exhausted (pre-call or
                runtime). Propagated so the consumer can stop the
                rating pass rather than treat quota-gone as "no
                Rotten Tomatoes data available".
            ProviderFeatureUnavailable: OMDb returned an
                :class:`ApiError` (non-quota transport failure).
        """
        try:
            notations = self._backend.get_notations(provider_id)
        except OmdbQuotaExhausted:
            raise
        except ApiError as exc:
            raise ProviderFeatureUnavailable(
                "rotten_tomatoes",
                "get_rating",
                str(exc),
            ) from exc
        if not notations:
            return None
        rt_only = [n for n in notations if n.source == "rotten_tomatoes"]
        return rt_only or None


__all__ = ["RottenTomatoesClient"]
