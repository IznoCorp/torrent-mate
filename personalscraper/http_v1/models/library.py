"""The ``library`` tag's bodies, written from the contract's library schemas and the deletion's request and answer.

The contract's ``LibraryItem``, ``LibraryRow``, ``LibraryCategory``, ``IncompleteShow``,
``LibraryMembership`` and ``MediaRef``, and the inline answers of ``readLibraryItems`` and
``deleteLibraryItems``.

Every entry carries its provider identity (``LibraryIds``) and a poster: the provider's
URL, else ``readMediaPoster``'s URL when only the library folder holds one, else null.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Final, Literal

from pydantic import Field, WithJsonSchema

from personalscraper.app.library.deletion import DeletionReport, KeptReason, MediaDeletion
from personalscraper.app.library.identity import Provider, ref_key
from personalscraper.app.library.reads import CategoryCount, IncompleteEntry, LibraryEntry, LibraryPage, Membership
from personalscraper.http_v1.contract import ContractModel
from personalscraper.http_v1.models.media import ProviderIdValue, poster_route_url

#: The contract's ``LibraryIds``: its ``ProviderIds`` (a map of ids, each an integer or a
#: string) with at least one id, written as the contract writes it, a one-member ``allOf``.
LibraryIds = Annotated[
    dict[str, ProviderIdValue],
    WithJsonSchema(
        {
            "allOf": [{"type": "object", "additionalProperties": {"oneOf": [{"type": "integer"}, {"type": "string"}]}}],
            "minProperties": 1,
        }
    ),
]


#: The order a film's ids name it, as the interface's ``MOVIE_ORDER`` does: TMDB first.
_MOVIE_ORDER: Final[tuple[Provider, ...]] = (Provider.TMDB, Provider.TVDB, Provider.IMDB)

#: The order a show's ids name it: TVDB first.
_SHOW_ORDER: Final[tuple[Provider, ...]] = (Provider.TVDB, Provider.TMDB, Provider.IMDB)


def _poster(entry: LibraryEntry) -> str | None:
    """The poster an entry is shown with: the provider's, else the folder's through ``readMediaPoster``.

    Args:
        entry: The service's entry.

    Returns:
        The provider URL; else, when only the folder holds a poster, ``readMediaPoster``'s
        URL at the entry's first id as the interface names the medium (a film TMDB first,
        then TVDB; a show TVDB first, then TMDB; IMDb last); else ``None``.
    """
    if entry.poster_url is not None or not entry.local_poster:
        return entry.poster_url
    order = _MOVIE_ORDER if entry.kind == "movie" else _SHOW_ORDER
    provider = next(known for known in order if known.value in entry.ids)
    return poster_route_url(provider, str(entry.ids[provider.value]))


def _ids(ids: Mapping[str, int | str]) -> dict[str, int | str]:
    """Copy an entry's provider ids for the wire.

    Args:
        ids: The service's ids.

    Returns:
        A plain dict, in the service's order.
    """
    return dict(ids)


class LibraryRow(ContractModel):
    """The contract's ``LibraryRow``: a row as a listing shows it, facts only.

    Attributes:
        title: The title the library files it under.
        ids: Its provider ids, at least one.
        poster: Its poster's address, or ``None``.
        year: Its year, or ``None``.
        kind: ``movie`` or ``show``.
    """

    title: str
    ids: LibraryIds
    poster: str | None
    year: int | None
    kind: Literal["movie", "show"]

    @classmethod
    def from_entry(cls, entry: LibraryEntry) -> LibraryRow:
        """Map one library entry.

        Args:
            entry: The service's entry.

        Returns:
            The body.
        """
        return cls(title=entry.title, ids=_ids(entry.ids), poster=_poster(entry), year=entry.year, kind=entry.kind)


class LibraryItem(ContractModel):
    """The contract's ``LibraryItem``: a listing row with its category and its synopsis.

    Attributes:
        title: The title the library files it under.
        category: The engine leaf category it is filed under.
        overview: The NFO's synopsis, or ``None``.
        ids: Its provider ids, at least one.
        poster: Its poster's address, or ``None``.
        year: Its year, or ``None``.
        kind: ``movie`` or ``show``.
    """

    title: str
    category: str
    overview: str | None = None
    ids: LibraryIds
    poster: str | None
    year: int | None
    kind: Literal["movie", "show"]

    @classmethod
    def from_entry(cls, entry: LibraryEntry) -> LibraryItem:
        """Map one library entry.

        Args:
            entry: The service's entry.

        Returns:
            The body.
        """
        return cls(
            title=entry.title,
            category=entry.category_id,
            overview=entry.overview,
            ids=_ids(entry.ids),
            poster=_poster(entry),
            year=entry.year,
            kind=entry.kind,
        )


class LibraryItemsPage(ContractModel):
    """``readLibraryItems``'s answer: one page and its three counts.

    Attributes:
        total: The library's count when nothing filters, else ``matching``.
        matching: How many entries the question matches.
        loaded: How many entries the library holds, whatever is filtered.
        items: The page's entries.
    """

    total: int
    matching: int
    loaded: int
    items: list[LibraryItem]

    @classmethod
    def from_page(cls, page: LibraryPage) -> LibraryItemsPage:
        """Map one page of the listing.

        Args:
            page: The service's page.

        Returns:
            The body.
        """
        return cls(
            total=page.total,
            matching=page.matching,
            loaded=page.loaded,
            items=[LibraryItem.from_entry(entry) for entry in page.items],
        )


class LibraryCategory(ContractModel):
    """The contract's ``LibraryCategory``: one engine leaf and its live media.

    Attributes:
        id: The leaf category id.
        count: Its live media.
    """

    id: str
    count: int

    @classmethod
    def from_count(cls, count: CategoryCount) -> LibraryCategory:
        """Map one leaf's count.

        Args:
            count: The service's count.

        Returns:
            The body.
        """
        return cls(id=count.category_id, count=count.count)


class IncompleteShow(ContractModel):
    """The contract's ``IncompleteShow``: a show missing aired episodes.

    Attributes:
        title: The title the library files it under.
        owned: Its aired episodes held.
        aired: Its aired episodes.
        year: Its year, or ``None`` when nothing states one.
        ids: Its provider ids, at least one.
        poster: Its poster's address, or ``None``.
        category: The engine leaf category it is stored under.
        kind: Always ``show``.
    """

    title: str
    owned: int
    aired: int
    year: int | None
    ids: LibraryIds
    poster: str | None
    category: str
    kind: Literal["show"]

    @classmethod
    def from_incomplete(cls, incomplete: IncompleteEntry) -> IncompleteShow:
        """Map one incomplete show.

        Args:
            incomplete: The service's entry.

        Returns:
            The body.
        """
        entry = incomplete.entry
        return cls(
            title=entry.title,
            owned=incomplete.owned,
            aired=incomplete.aired,
            year=entry.year,
            ids=_ids(entry.ids),
            poster=_poster(entry),
            category=entry.category_id,
            kind="show",
        )


class LibraryMembership(ContractModel):
    """The contract's ``LibraryMembership``: what the library holds of one medium.

    Attributes:
        in_library: Whether some live row holds the id.
        rows: How many holdings the id names; two or more is a duplicate.
        incomplete: Whether it is a show held with aired episodes missing.
        ids: The held row's provider ids, or ``None`` when not held.
        kind: The held row's kind, or ``None`` when not held.
    """

    in_library: bool
    rows: int
    incomplete: bool
    ids: LibraryIds | None
    kind: Literal["movie", "show"] | None

    @classmethod
    def from_membership(cls, membership: Membership) -> LibraryMembership:
        """Map one membership.

        Args:
            membership: The service's membership.

        Returns:
            The body.
        """
        return cls(
            in_library=membership.in_library,
            rows=membership.rows,
            incomplete=membership.incomplete,
            ids=_ids(membership.ids) if membership.ids is not None else None,
            kind=membership.kind,
        )


class MediaRefModel(ContractModel):
    """The contract's ``MediaRef``: a medium named by its provider identity.

    Attributes:
        provider: The provider the id belongs to.
        provider_id: The id at that provider.
    """

    provider: Provider
    provider_id: str


class DeleteLibraryItemsBody(ContractModel):
    """``deleteLibraryItems``'s request: the media to delete, by provider identity.

    Attributes:
        media: The media, one at least.
    """

    media: list[MediaRefModel] = Field(min_length=1)


#: When a kept medium's seeding is met: epoch seconds, declared a ``number`` as the
#: contract declares its epochs, served as the integer the authority computes.
_EpochSeconds = Annotated[int | None, WithJsonSchema({"anyOf": [{"type": "number"}, {"type": "null"}]})]


#: Why a medium was kept, or null: written as the contract writes a nullable enum, null a member.
_KeptReasonOrNone = Annotated[
    KeptReason | None,
    WithJsonSchema({"type": ["string", "null"], "enum": [*(reason.value for reason in KeptReason), None]}),
]


class LibraryDeletion(ContractModel):
    """The contract's ``LibraryDeletion``: what the deletion did to one medium (operator ruling R2).

    Attributes:
        ref: The medium, as the request named it.
        outcome: ``deleted`` when it went, ``kept`` when it is still in the library.
        reason: Why a kept medium was kept, ``None`` when it went.
        owed_until: On ``seed_owed``, when the seeding is met, epoch seconds, ``None`` when
            the authority does not know it; ``None`` for any other reason.
    """

    ref: MediaRefModel
    outcome: Literal["deleted", "kept"]
    reason: _KeptReasonOrNone
    owed_until: _EpochSeconds

    @classmethod
    def from_deletion(cls, deletion: MediaDeletion) -> LibraryDeletion:
        """Map one medium's deletion.

        Args:
            deletion: The service's deletion of one medium.

        Returns:
            The body.
        """
        provider, provider_id = ref_key(deletion.ref)
        reason = deletion.kept_reason
        return cls(
            ref=MediaRefModel(provider=provider, provider_id=provider_id),
            outcome="kept" if reason is not None else "deleted",
            reason=reason,
            owed_until=deletion.owed_until if reason is KeptReason.SEED_OWED else None,
        )


class DeleteLibraryItemsResult(ContractModel):
    """``deleteLibraryItems``'s answer: what the deletion did, per medium.

    Attributes:
        media: Each medium deleted or kept, in request order.
    """

    media: list[LibraryDeletion]

    @classmethod
    def from_report(cls, report: DeletionReport) -> DeleteLibraryItemsResult:
        """Map a deletion's report.

        Args:
            report: The service's report.

        Returns:
            The body.
        """
        return cls(media=[LibraryDeletion.from_deletion(deletion) for deletion in report.media])
