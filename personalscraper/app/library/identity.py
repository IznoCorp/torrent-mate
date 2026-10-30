"""A medium's identity on the wire: a provider and the id it knows the medium by (Q15).

A show is addressed TVDB first, a movie TMDB first; an IMDb id is accepted and
resolved through the index. The pair is parsed once, here, into the engine's
:class:`~personalscraper.core.identity.MediaRef`.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final

from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.core.identity import MediaRef

_NUMERIC_ID: Final[re.Pattern[str]] = re.compile(r"[1-9][0-9]*")
_IMDB_ID: Final[re.Pattern[str]] = re.compile(r"tt[0-9]+")


class Provider(StrEnum):
    """The providers a medium's id is read at."""

    TVDB = "tvdb"
    TMDB = "tmdb"
    IMDB = "imdb"


def parse_media_ref(provider: str, provider_id: str) -> MediaRef:
    """Parse a wire identity into a :class:`MediaRef` carrying that one id.

    Args:
        provider: ``"tvdb"``, ``"tmdb"`` or ``"imdb"``.
        provider_id: The id at that provider: a positive integer for TVDB and TMDB,
            ``tt`` and digits for IMDb.

    Returns:
        The reference, with only the named provider's id set.

    Raises:
        AppBadRequest: ``request.invalid`` naming the field at fault (``provider`` for an
            unknown provider, ``providerId`` for an id that provider cannot hold).
    """
    try:
        known = Provider(provider)
    except ValueError:
        raise AppBadRequest(
            "Unknown provider.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["provider"]}
        ) from None
    if known is Provider.IMDB:
        if _IMDB_ID.fullmatch(provider_id):
            return MediaRef(imdb_id=provider_id)
    elif _NUMERIC_ID.fullmatch(provider_id):
        value = int(provider_id)
        return MediaRef(tvdb_id=value) if known is Provider.TVDB else MediaRef(tmdb_id=value)
    raise AppBadRequest("Malformed provider id.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["providerId"]})


def ref_key(ref: MediaRef) -> tuple[Provider, str]:
    """Name the id a reference is read at: TVDB first, then TMDB, then IMDb.

    Args:
        ref: A reference with at least one id.

    Returns:
        ``(provider, id as text)``.
    """
    if ref.tvdb_id is not None:
        return Provider.TVDB, str(ref.tvdb_id)
    if ref.tmdb_id is not None:
        return Provider.TMDB, str(ref.tmdb_id)
    return Provider.IMDB, str(ref.imdb_id)
