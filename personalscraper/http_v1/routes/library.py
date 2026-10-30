"""The library routes: the listing, its categories, the recents, the incomplete shows, one membership and the deletion.

The contract files them under its ``library`` tag. Each route makes ONE
library service call; a medium is named by its provider identity, parsed with
:func:`~personalscraper.app.library.identity.parse_media_ref`.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Query

from personalscraper.app.accounts.actor import Actor
from personalscraper.app.library.identity import Provider, parse_media_ref
from personalscraper.app.library.listing import LibrarySort
from personalscraper.app.services import AppServices
from personalscraper.http_v1.contract import PROBLEM_RESPONSES
from personalscraper.http_v1.deps import actor, services
from personalscraper.http_v1.models.library import (
    DeleteLibraryItemsBody,
    DeleteLibraryItemsResult,
    IncompleteShow,
    LibraryCategory,
    LibraryItemsPage,
    LibraryMembership,
    LibraryRow,
)

router = APIRouter()

#: ``deleteLibraryItems``'s refusals: 404 for an id no row holds, beside the 409s
#: (an id two rows hold, the pipeline's lock).
_DELETE_RESPONSES = {**PROBLEM_RESPONSES, 404: PROBLEM_RESPONSES[400]}

#: The orders ``sort`` names on the wire; absent, the most recently added first.
_WireSort = Literal["az", "missing"]


@router.get(
    "/library/items",
    operation_id="readLibraryItems",
    response_model=LibraryItemsPage,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_library_items(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
    category: Annotated[list[str] | None, Query(description="the engine leaf category ids to keep")] = None,
    sort: Annotated[_WireSort | None, Query(description="the order; absent, the most recent first")] = None,
    reversed_: Annotated[Literal["1"] | None, Query(alias="reversed", description="the other way round")] = None,
    query: Annotated[str | None, Query(description="the search text")] = None,
    page: Annotated[int, Query(description="the page, zero based")] = 0,
) -> LibraryItemsPage:
    """One page of the library listing.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.
        category: The leaf categories to keep, repeated; absent, every one.
        sort: ``az`` or ``missing``; absent, the most recently added first.
        reversed_: ``"1"`` to run the order the other way.
        query: The search text.
        page: The page, zero based.

    Returns:
        The page and its three counts.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``page`` for a negative page.
        AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
    """
    return LibraryItemsPage.from_page(
        app_services.library.read_items(
            signed_in,
            category=category,
            sort=LibrarySort(sort) if sort is not None else LibrarySort.RECENT,
            reversed_=reversed_ is not None,
            query=query,
            page=page,
        )
    )


@router.delete(
    "/library/items",
    operation_id="deleteLibraryItems",
    response_model=DeleteLibraryItemsResult,
    status_code=200,
    responses=_DELETE_RESPONSES,
)
def delete_library_items(
    body: Annotated[DeleteLibraryItemsBody, Body()],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> DeleteLibraryItemsResult:
    """Delete media from the disks, the index and Plex, each named by its provider identity.

    Args:
        body: The media to delete.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        What the deletion did, per medium: deleted, or kept and why (operator ruling R2).

    Raises:
        AppBadRequest: ``request.invalid`` naming the field at fault (``provider`` or
            ``providerId``), before anything is read.
        AppNotFound: ``media.not_found`` when no library row holds an id; nothing deleted.
        AppConflict: ``media.ambiguous`` when an id is held twice, ``library.locked`` while
            the pipeline holds its lock; nothing deleted.
        AppUnavailable: ``library.obligations_unreadable`` when the seed obligations cannot
            be read (operator ruling R1), ``library.unavailable`` when ``library.db`` cannot
            be read; nothing deleted.
    """
    refs = [parse_media_ref(medium.provider.value, medium.provider_id) for medium in body.media]
    return DeleteLibraryItemsResult.from_report(app_services.deletion.delete_media(signed_in, refs))


@router.get(
    "/library/categories",
    operation_id="readLibraryCategories",
    response_model=list[LibraryCategory],
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_library_categories(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> list[LibraryCategory]:
    """The engine's leaf categories and their live media.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        One count per leaf holding a medium.

    Raises:
        AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
    """
    return [LibraryCategory.from_count(count) for count in app_services.library.read_categories(signed_in)]


@router.get(
    "/library/recent",
    operation_id="readLibraryRecent",
    response_model=list[LibraryRow],
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_library_recent(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> list[LibraryRow]:
    """The most recently added media.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The newest rows, newest first.

    Raises:
        AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
    """
    return [LibraryRow.from_entry(entry) for entry in app_services.library.read_recent(signed_in)]


@router.get(
    "/library/incomplete",
    operation_id="readLibraryIncomplete",
    response_model=list[IncompleteShow],
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_library_incomplete(
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> list[IncompleteShow]:
    """The shows missing aired episodes.

    Args:
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The incomplete shows, most missing first, each with its episodes owned and aired:
        the client derives how many are missing.

    Raises:
        AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
    """
    return [IncompleteShow.from_incomplete(show) for show in app_services.library.read_incomplete(signed_in)]


@router.get(
    "/library/membership",
    operation_id="readLibraryMembership",
    response_model=LibraryMembership,
    status_code=200,
    responses=PROBLEM_RESPONSES,
)
def read_library_membership(
    provider: Annotated[Provider, Query(description="the provider the id is read at")],
    provider_id: Annotated[str, Query(alias="providerId", description="the medium's id at that provider")],
    signed_in: Annotated[Actor, Depends(actor)],
    app_services: Annotated[AppServices, Depends(services)],
) -> LibraryMembership:
    """What the library holds of one medium, named by its provider identity.

    Args:
        provider: The provider the id belongs to.
        provider_id: The id at that provider.
        signed_in: The signed-in actor.
        app_services: The application services.

    Returns:
        The membership, read from the whole library.

    Raises:
        AppBadRequest: ``request.invalid`` naming ``providerId`` for an id its provider
            cannot hold, before anything is read.
        AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
    """
    ref = parse_media_ref(provider.value, provider_id)
    return LibraryMembership.from_membership(app_services.library.read_membership(signed_in, ref))
