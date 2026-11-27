"""``Suggestions``: the deck of titles worth following, minus what the reader already holds (K3 P11c).

A refresh (``personalscraper acquisition-suggestions-refresh``,
:mod:`personalscraper.acquire.suggestions_refresh`) stores the deck in ``acquire.db``;
:meth:`Suggestions.read` serves it a page at a time. A title leaves a reader's page when

* the library OWNS it: a film a live file holds, a show with any live episode file (the indexer's
  ownership read, as the search's ``owned``);
* a standing FOLLOW holds its id: a ``followed_series`` row of scope ``follow`` that is not removed
  (a paused follow counts, a request row and a removed follow do not, as the search's ``followed``);
* the reader REJECTED it, through the :class:`RejectionFilter` seam.

Owned and followed are told by provider id, never by title. A title is known by its own id when
that is a TVDB, TMDB or IMDb id, and by the ids its provider gave beside it (``external_ids``:
Trakt names a title by a slug and gives its IMDb, TMDB and TVDB ids alongside). A title with no
such id (a slug and nothing else) cannot be asked of the library and always stays: no title guess
stands in for an id.

The per-account rejection store (``suggestion_rejection`` in ``app.db``, and the writes that fill
it) waits the operator's ruling O-9: the seam is here, the store is not. Until it lands nothing is
rejected.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from personalscraper.app.accounts.authorise import requires
from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.core.identity import MediaRef

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import FollowKind, SuggestionReason, SuggestionRow
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.acquisition.completeness import OwnershipReader

__all__ = [
    "DEFAULT_LIMIT",
    "RejectionFilter",
    "SuggestedMedium",
    "SuggestionKey",
    "SuggestionPage",
    "Suggestions",
    "media_ref_of",
]

#: Cards a page carries when the caller names no limit.
DEFAULT_LIMIT: Final[int] = 20

#: Rows read from the deck at a time while a page is being filled.
_BATCH: Final[int] = 50

#: A title's identity in a deck and in a rejection: ``(provider, provider_id, kind)``.
type SuggestionKey = tuple[str, str, str]

_IMDB_ID = re.compile(r"tt\d+")
_CURSOR = re.compile(r"[0-9]{1,18}")


class RejectionFilter(Protocol):
    """Where a reader's own rejections are told: the seam the rejection store plugs into (O-9)."""

    def rejected(self, actor: Actor, keys: Sequence[SuggestionKey]) -> Collection[SuggestionKey]:
        """Name which of ``keys`` the actor's own account rejected.

        Args:
            actor: The reader; another account's rejection never counts.
            keys: The titles to check.

        Returns:
            The keys among ``keys`` the account rejected.
        """
        ...


class _NoRejections:
    """The filter until the rejection store lands: nothing is rejected."""

    def rejected(self, actor: Actor, keys: Sequence[SuggestionKey]) -> Collection[SuggestionKey]:
        """Name no key.

        Args:
            actor: The reader.
            keys: The titles to check.

        Returns:
            Nothing.
        """
        return ()


@dataclass(frozen=True)
class SuggestedMedium:
    """One title of a reader's page.

    Attributes:
        provider: The provider that recommended it.
        provider_id: Its id at that provider: a number, an IMDb id or a slug.
        kind: ``"movie"`` or ``"show"``.
        title: The provider's title.
        year: The release or first-air year, or ``None``.
        rating: The provider's rating, or ``None`` when none came with it.
        poster: The poster's address, or ``None`` when none came with it.
        reason: Why it is suggested, as a code the interface words.
        seed_key: The title whose recommendation this is (``"tmdb:603"``).
        cursor: The ``after`` that continues the deck past this card.
    """

    provider: str
    provider_id: str
    kind: FollowKind
    title: str
    year: int | None
    rating: float | None
    poster: str | None
    reason: SuggestionReason
    seed_key: str
    cursor: str


@dataclass(frozen=True)
class SuggestionPage:
    """One page of the deck.

    Attributes:
        items: The cards, in deck order.
        after: The ``after`` that continues the deck, or ``None`` when this page ends it.
    """

    items: tuple[SuggestedMedium, ...]
    after: str | None


def media_ref_of(provider: str, provider_id: str, external_ids: Mapping[str, str] | None = None) -> MediaRef | None:
    """Return the ids a title is known by, as the library and the follows key them.

    Args:
        provider: The provider that recommended the title.
        provider_id: Its id at that provider.
        external_ids: The other ids the provider gave beside ``provider_id`` (``"imdb"`` /
            ``"tmdb"`` / ``"tvdb"``); one that is not a well-formed id is left out.

    Returns:
        The ref holding every id that is one: the ids beside ``provider_id``, and ``provider_id``
        itself when it is an IMDb id (``tt…``, whatever the provider) or a TMDB or TVDB number
        (that provider's own). ``None`` when none is: a bare Trakt slug or number names no id the
        library knows.
    """
    imdb: str | None = None
    tmdb: int | None = None
    tvdb: int | None = None
    candidates = dict(external_ids or {})
    if _IMDB_ID.fullmatch(provider_id):
        candidates.setdefault("imdb", provider_id)
    elif provider in ("tmdb", "tvdb"):
        candidates.setdefault(provider, provider_id)
    if _IMDB_ID.fullmatch(candidates.get("imdb", "")):
        imdb = candidates["imdb"]
    if _is_number(candidates.get("tmdb", "")):
        tmdb = int(candidates["tmdb"])
    if _is_number(candidates.get("tvdb", "")):
        tvdb = int(candidates["tvdb"])
    if imdb is None and tmdb is None and tvdb is None:
        return None
    return MediaRef(tvdb_id=tvdb, tmdb_id=tmdb, imdb_id=imdb)


def _is_number(value: str) -> bool:
    """Whether ``value`` is a plain number, as a provider's numeric id is.

    Args:
        value: The text to check.

    Returns:
        ``True`` for ASCII digits only.
    """
    return value.isascii() and value.isdigit()


def _cursor_of(after: str | None) -> int | None:
    """Read the deck key a caller continues from.

    Args:
        after: The ``after`` a previous page gave, or ``None`` to start at the head.

    Returns:
        The key, or ``None`` for the head.

    Raises:
        AppBadRequest: ``request.invalid`` when ``after`` is not a cursor this deck gives.
    """
    if after is None:
        return None
    if not _CURSOR.fullmatch(after):
        raise AppBadRequest(
            "The cursor is not one the deck gave.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["after"]}
        )
    return int(after)


def _key_of(row: SuggestionRow) -> SuggestionKey:
    """Return a row's identity.

    Args:
        row: A deck row.

    Returns:
        ``(provider, provider_id, kind)``.
    """
    return (row.provider, row.provider_id, row.kind)


class Suggestions:
    """Read the suggestions deck for one account."""

    def __init__(
        self,
        *,
        open_store: Callable[[], AcquireStore],
        open_ownership: Callable[[], OwnershipReader],
        rejections: RejectionFilter | None = None,
    ) -> None:
        """Hold the seams; nothing is opened yet.

        Args:
            open_store: Opens the acquire store for one call (closed after it).
            open_ownership: Opens the library's ownership reader for one call (closed after it).
            rejections: Names the titles a reader rejected; ``None`` until the rejection store
                (O-9) lands, when nothing is rejected.
        """
        self._open_store = open_store
        self._open_ownership = open_ownership
        self._rejections: RejectionFilter = rejections if rejections is not None else _NoRejections()

    @requires("readSuggestions")
    def read(self, actor: Actor, after: str | None, *, limit: int = DEFAULT_LIMIT) -> SuggestionPage:
        """Read one page of the deck: what the reader neither owns, follows nor rejected.

        The page is filled from the rows that survive, in deck order: a title left out costs the
        page no card. ``after`` is the cursor of a card (the previous page's last, or any card of
        it); a cursor of a deck since replaced starts the new deck at its head.

        Args:
            actor: Who reads; authorised by ``@requires`` (``acquisition.request``).
            after: The ``after`` of the previous page, ``None`` for the first.
            limit: The most cards the page carries.

        Returns:
            The page; its ``after`` is ``None`` when the deck has no more to read.

        Raises:
            AppBadRequest: ``request.invalid`` when ``after`` is not a cursor the deck gave.
        """
        cursor = _cursor_of(after)
        items: list[SuggestedMedium] = []
        with closing(self._open_store()) as store, closing(self._open_ownership()) as ownership:
            while len(items) < limit:
                rows = store.suggestions.after(cursor, _BATCH)
                if not rows:
                    return SuggestionPage(items=tuple(items), after=None)
                rejected = set(self._rejections.rejected(actor, [_key_of(r) for r in rows]))
                for row in rows:
                    cursor = row.id
                    if _key_of(row) in rejected or _is_followed(store, row) or _is_owned(ownership, row):
                        continue
                    items.append(_medium_of(row))
                    if len(items) == limit:
                        break
        return SuggestionPage(items=tuple(items), after=items[-1].cursor if items else None)


def _is_followed(store: AcquireStore, row: SuggestionRow) -> bool:
    """Whether a standing follow holds the title's provider id.

    The lookup is within the title's kind (TMDB numbers films and shows apart). A row stands when
    its scope is ``follow`` and it is not removed; a paused follow stands.

    Args:
        store: The acquire store.
        row: The deck row.

    Returns:
        ``True`` when at least one matching follow stands; ``False`` for an id no follow can hold.
    """
    ref = media_ref_of(row.provider, row.provider_id, row.external_ids)
    if ref is None:
        return False
    return any(f.scope == "follow" and f.removed_at is None for f in store.follow.find_all_by_ref(ref, kind=row.kind))


def _is_owned(ownership: OwnershipReader, row: SuggestionRow) -> bool:
    """Whether the library holds the title, by its provider id, live files only.

    Args:
        ownership: The library's ownership reader.
        row: The deck row.

    Returns:
        ``True`` for a film a live file holds, or a show with any live episode file; ``False``
        for an id the library cannot be asked by.
    """
    ref = media_ref_of(row.provider, row.provider_id, row.external_ids)
    if ref is None:
        return False
    return ownership.owns(ref, kind="movie") if row.kind == "movie" else len(ownership.owned_pairs(ref)) > 0


def _medium_of(row: SuggestionRow) -> SuggestedMedium:
    """Map a deck row to a card.

    Args:
        row: The deck row, its key set.

    Returns:
        The card; its cursor is the row's key.
    """
    return SuggestedMedium(
        provider=row.provider,
        provider_id=row.provider_id,
        kind=row.kind,
        title=row.title,
        year=row.year,
        rating=row.rating,
        poster=row.poster,
        reason=row.reason,
        seed_key=row.seed_key,
        cursor=str(row.id),
    )
