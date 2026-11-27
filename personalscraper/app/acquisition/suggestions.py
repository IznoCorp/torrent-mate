"""``Suggestions``: the deck of titles worth following, minus what the reader already holds (K3 P11c).

A refresh (``personalscraper acquisition-suggestions-refresh``,
:mod:`personalscraper.acquire.suggestions_refresh`) stores the deck in ``acquire.db``;
:meth:`Suggestions.read` serves it a page at a time. A title leaves a reader's page when

* the library OWNS it: a film a live file holds, a show with any live episode file (the indexer's
  ownership read, as the search's ``owned``);
* a standing FOLLOW holds its id: a ``followed_series`` row of scope ``follow`` that is not removed
  (a paused follow counts, a request row and a removed follow do not, as the search's ``followed``);
* the reader REJECTED it: the rejection is the rejecting account's alone (O-9 A, K3-G7), held in
  ``app.db`` and reached through the :class:`RejectionStore` seam; :meth:`Suggestions.reject` and
  :meth:`Suggestions.undo_rejection` write it.

Owned and followed are told by provider id, never by title. A title is known by its own id when
that is a TVDB, TMDB or IMDb id, and by the ids its provider gave beside it (``external_ids``:
Trakt names a title by a slug and gives its IMDb, TMDB and TVDB ids alongside). A title with no
such id (a slug and nothing else) cannot be asked of the library and always stays: no title guess
stands in for an id.

A card is addressed by its suggestion id, ``<kind>:<provider>:<providerId>``: a title's identity,
which a refresh of the deck keeps. The wire carries it opaque.

A card's reason names the title whose recommendation it is, read where that title lives: a follow's
own title, or the library's through the index. A title neither holds any more is not named.

A cursor is the key of the card a page continues past, sealed under a key the environment keeps
(:func:`cursor_key_path`): only a cursor the server issued is read, and it stays readable across a
restart (K3-G13).
"""

from __future__ import annotations

import hmac
import re
from collections.abc import Callable, Collection, Mapping, Sequence
from contextlib import AbstractContextManager, closing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol

from personalscraper.app.accounts.authorise import requires
from personalscraper.app.errors import AppBadRequest, AppNotFound, RefusalCode
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import IndexUnavailable
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.domain import FollowKind, SuggestionReason, SuggestionRow
    from personalscraper.app.accounts.actor import Actor
    from personalscraper.app.acquisition.completeness import OwnershipReader
    from personalscraper.indexer.library_view import IndexItem

log = get_logger("app.acquisition.suggestions")

__all__ = [
    "DEFAULT_LIMIT",
    "RejectionFilter",
    "RejectionStore",
    "SuggestedMedium",
    "SuggestionKey",
    "SuggestionPage",
    "Suggestions",
    "cursor_key_path",
    "media_ref_of",
]

#: Cards a page carries when the caller names no limit.
DEFAULT_LIMIT: Final[int] = 20

#: Rows read from the deck at a time while a page is being filled.
_BATCH: Final[int] = 50

#: A title's identity in a deck and in a rejection: ``(provider, provider_id, kind)``.
type SuggestionKey = tuple[str, str, str]

#: A card's seed as its reason reads it: ``(reason, seed_key, kind)``.
type _Seed = tuple[SuggestionReason, str, FollowKind]

_IMDB_ID = re.compile(r"tt\d+")
#: A suggestion id: the title's kind, the provider that recommended it, and its id there.
_SUGGESTION_ID = re.compile(r"(?P<kind>movie|show):(?P<provider>[^:]+):(?P<provider_id>.+)")
#: A cursor: the key of the card it continues past, then the server's seal on that key.
_CURSOR = re.compile(r"([0-9]{1,18})\.([0-9a-f]{32})")

#: What the seal covers ahead of the card's key.
_SEALED: Final = b"suggestions-cursor:"


def cursor_key_path(app_db: Path) -> Path:
    """Where an environment's cursor key file lives: beside its ``app.db``, never in it.

    Args:
        app_db: The environment's ``app`` store file.

    Returns:
        ``<data_dir>/<app store stem>.cursor.key``.
    """
    return app_db.with_name(f"{app_db.stem}.cursor.key")


def _cursor_to(card: str, key: bytes) -> str:
    """Issue the cursor that continues the deck past a card.

    Args:
        card: The card's key in the deck.
        key: The environment's cursor key.

    Returns:
        The card's key and the server's seal on it.
    """
    return f"{card}.{hmac.new(key, _SEALED + card.encode(), 'sha256').hexdigest()[:32]}"


class RejectionFilter(Protocol):
    """Where a reader's own rejections are told (O-9 A)."""

    def rejected(self, actor: Actor, keys: Sequence[SuggestionKey]) -> Collection[SuggestionKey]:
        """Name which of ``keys`` the actor's own account rejected.

        Args:
            actor: The reader; another account's rejection never counts.
            keys: The titles to check.

        Returns:
            The keys among ``keys`` the account rejected.
        """
        ...


class RejectionStore(RejectionFilter, Protocol):
    """The rejections, read and written for the actor's own account."""

    def reject(self, actor: Actor, key: SuggestionKey) -> None:
        """Record that the actor's account rejected a title; one already rejected stays so.

        Args:
            actor: Whose rejection it is.
            key: The title.
        """
        ...

    def undo(self, actor: Actor, key: SuggestionKey) -> bool:
        """Forget the actor's account's rejection of a title.

        Args:
            actor: Whose rejection it is.
            key: The title.

        Returns:
            Whether the account had rejected it.
        """
        ...


class _IndexReader(Protocol):
    """What is read of the library index to name a seed."""

    def holders(self, provider: str, provider_id: str) -> list[IndexItem]:
        """Read every row bearing one provider id."""
        ...


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
        suggestion_id: The card's handle, which a rejection and its undo address it by.
        reason: Why it is suggested, as a code the interface words.
        seed_key: The title whose recommendation this is (``"tmdb:603"``).
        reason_titles: The titles the reason names: the seed's, or none when nothing holds it.
        cursor: The ``after`` that continues the deck past this card.
        ids: The ids the library and the follows know the title by (:func:`media_ref_of`), or
            ``None`` when it has none.
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
    suggestion_id: str
    reason_titles: tuple[str, ...] = ()
    ids: MediaRef | None = None


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


def _cursor_of(after: str | None, key: bytes) -> int | None:
    """Read the deck key a caller continues from.

    Args:
        after: The ``after`` a previous page gave, or ``None`` to start at the head.
        key: The environment's cursor key.

    Returns:
        The key, or ``None`` for the head.

    Raises:
        AppBadRequest: ``request.invalid`` when ``after`` is not a cursor the server issued.
    """
    if after is None:
        return None
    read = _CURSOR.fullmatch(after)
    if read is None or not hmac.compare_digest(after, _cursor_to(read[1], key)):
        raise AppBadRequest(
            "The cursor is not one the deck gave.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["cursor"]}
        )
    return int(read[1])


def _key_of(row: SuggestionRow) -> SuggestionKey:
    """Return a row's identity.

    Args:
        row: A deck row.

    Returns:
        ``(provider, provider_id, kind)``.
    """
    return (row.provider, row.provider_id, row.kind)


def _suggestion_id(key: SuggestionKey) -> str:
    """Return the handle a card is addressed by.

    Args:
        key: The title's identity.

    Returns:
        ``<kind>:<provider>:<providerId>``.
    """
    provider, provider_id, kind = key
    return f"{kind}:{provider}:{provider_id}"


def _keyed_by(suggestion_id: str) -> SuggestionKey:
    """Read the title a suggestion id names.

    Args:
        suggestion_id: The handle a card carried.

    Returns:
        ``(provider, provider_id, kind)``.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``suggestionId`` when it is no card's handle.
    """
    read = _SUGGESTION_ID.fullmatch(suggestion_id)
    if read is None:
        raise AppBadRequest(
            "The id is not a suggestion's.", code=RefusalCode.REQUEST_INVALID, params={"fields": ["suggestionId"]}
        )
    return (read["provider"], read["provider_id"], read["kind"])


class Suggestions:
    """Read the suggestions deck for one account, and keep what it rejects."""

    def __init__(
        self,
        *,
        open_store: Callable[[], AcquireStore],
        open_ownership: Callable[[], OwnershipReader],
        open_index: Callable[[], AbstractContextManager[_IndexReader]],
        cursor_key: Callable[[], bytes],
        rejections: RejectionStore,
    ) -> None:
        """Hold the seams; nothing is opened yet.

        Args:
            open_store: Opens the acquire store for one call (closed after it).
            open_ownership: Opens the library's ownership reader for one call (closed after it).
            open_index: Opens a reader of the library index for one call; raises
                ``IndexUnavailable`` when the index cannot be read.
            cursor_key: Reads the key the cursors are sealed under, the same across restarts.
            rejections: The titles each account rejected.
        """
        self._open_store = open_store
        self._open_ownership = open_ownership
        self._open_index = open_index
        self._cursor_key = cursor_key
        self._rejections = rejections

    @requires("readSuggestions")
    def read(self, actor: Actor, after: str | None, *, limit: int = DEFAULT_LIMIT) -> SuggestionPage:
        """Read one page of the deck: what the reader neither owns, follows nor rejected.

        The page is filled from the rows that survive, in deck order: a title left out costs the
        page no card. ``after`` is the cursor of a card (the previous page's last, or any card of
        it); a cursor of a deck since replaced starts the new deck at its head. The wire carries it
        opaque, as ``cursor`` going in and ``nextCursor`` coming out (K3-G13).

        Args:
            actor: Who reads; authorised by ``@requires`` (``acquisition.request``).
            after: The ``after`` of the previous page, ``None`` for the first.
            limit: The most cards the page carries.

        Returns:
            The page; its ``after`` is ``None`` when the deck has no more to read.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``cursor`` when ``after`` is not a cursor the deck gave.
        """
        key = self._cursor_key()
        cursor = _cursor_of(after, key)
        kept: list[SuggestionRow] = []
        with closing(self._open_store()) as store, closing(self._open_ownership()) as ownership:
            while len(kept) < limit:
                rows = store.suggestions.after(cursor, _BATCH)
                if not rows:
                    break
                rejected = set(self._rejections.rejected(actor, [_key_of(r) for r in rows]))
                for row in rows:
                    cursor = row.id
                    if _key_of(row) in rejected or _is_followed(store, row) or _is_owned(ownership, row):
                        continue
                    kept.append(row)
                    if len(kept) == limit:
                        break
            titles = self._seed_titles(store, kept)
        items = tuple(_medium_of(row, key, titles.get((row.reason, row.seed_key, row.kind))) for row in kept)
        # A page short of its limit read the deck to its end: nothing follows it.
        return SuggestionPage(items=items, after=items[-1].cursor if len(items) == limit else None)

    @requires("rejectSuggestion")
    def reject(self, actor: Actor, suggestion_id: str) -> None:
        """Reject a card for the actor's account alone (O-9 A): its deck no longer holds the title.

        A title the account already rejected stays rejected.

        Args:
            actor: Whose rejection it is; authorised by ``@requires`` (``acquisition.request``).
            suggestion_id: The card's handle.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``suggestionId`` when it is no card's handle.
            AppNotFound: ``suggestion.not_found`` when no card of the deck bears it.
        """
        title = _keyed_by(suggestion_id)
        with closing(self._open_store()) as store:
            if not store.suggestions.holds(*title):
                raise AppNotFound("No card of the deck bears this id.", code=RefusalCode.SUGGESTION_NOT_FOUND)
        self._rejections.reject(actor, title)

    @requires("undoSuggestionRejection")
    def undo_rejection(self, actor: Actor, suggestion_id: str) -> None:
        """Undo the actor's account's rejection of a card.

        The account's rejections are read, never the deck: a title a later deck dropped is undone too.

        Args:
            actor: Whose rejection it is; authorised by ``@requires`` (``acquisition.request``).
            suggestion_id: The card's handle.

        Raises:
            AppBadRequest: ``request.invalid`` naming ``suggestionId`` when it is no card's handle.
            AppNotFound: ``suggestion.not_found`` when the account holds no rejection of it.
        """
        if not self._rejections.undo(actor, _keyed_by(suggestion_id)):
            raise AppNotFound("This account rejected no suggestion of this id.", code=RefusalCode.SUGGESTION_NOT_FOUND)

    def _seed_titles(self, store: AcquireStore, rows: Sequence[SuggestionRow]) -> dict[_Seed, str]:
        """Name the seeds of a page's cards by their titles, each seed read once.

        A followed seed's title is its follow's; an owned one's is the library's, read through the
        index (opened only when a card asks it).

        Args:
            store: The acquire store (the follows).
            rows: The page's rows.

        Returns:
            ``(reason, seed_key, kind)`` → the title, for the seeds something still holds; the
            owned ones are all absent when the index cannot be read.
        """
        titles: dict[_Seed, str] = {}
        seeds = dict.fromkeys((r.reason, r.seed_key, r.kind) for r in rows)
        for reason, seed_key, kind in seeds:
            if reason != "similar_to_followed":
                continue
            ref = media_ref_of(*_split_seed(seed_key))
            follows = [] if ref is None else store.follow.find_all_by_ref(ref, kind=kind)
            title = next((f.title for f in follows if f.title), None)
            if title is not None:
                titles[(reason, seed_key, kind)] = title
        owned = [seed for seed in seeds if seed[0] == "similar_to_owned"]
        if not owned:
            return titles
        try:
            with self._open_index() as index:
                for reason, seed_key, kind in owned:
                    held = index.holders(*_split_seed(seed_key))
                    title = next((item.title for item in held if item.kind == kind and item.title), None)
                    if title is not None:
                        titles[(reason, seed_key, kind)] = title
        except IndexUnavailable:
            log.warning("app.acquisition.suggestions.index_unavailable")
        return titles


def _split_seed(seed_key: str) -> tuple[str, str]:
    """Split a seed's name in the deck (``"tvdb:81189"``) into its provider and id.

    Args:
        seed_key: The name.

    Returns:
        ``(provider, provider_id)``.
    """
    provider, _, provider_id = seed_key.partition(":")
    return provider, provider_id


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


def _medium_of(row: SuggestionRow, key: bytes, seed_title: str | None) -> SuggestedMedium:
    """Map a deck row to a card.

    Args:
        row: The deck row, its key set.
        key: The environment's cursor key.
        seed_title: The title of the row's seed, ``None`` when nothing holds it.

    Returns:
        The card; its cursor continues the deck past the row.
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
        cursor=_cursor_to(str(row.id), key),
        suggestion_id=_suggestion_id(_key_of(row)),
        reason_titles=() if seed_title is None else (seed_title,),
        ids=media_ref_of(row.provider, row.provider_id, row.external_ids),
    )
