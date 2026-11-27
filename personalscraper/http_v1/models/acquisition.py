"""The ``acquisition`` tag's follow bodies, from the contract's ``Follow``, ``FollowCompleteness`` and the writes.

A property the contract leaves out of its required set and does not make nullable (a show's ``aired`` and
``owned``) is never assigned on a film, nor on a show whose count is unknown, and the routes serialise a
``Follow`` with ``response_model_exclude_unset``: a film's follow carries no show counts at all, while every
required property, null included, is always assigned.

The follow is named on the wire by the medium's key, ``<provider>:<providerId>`` (O-1 A), parsed by
:meth:`~personalscraper.app.acquisition.model.AcquisitionKey.parse`; no body here carries a title as an identity.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field, WithJsonSchema

from personalscraper.app.acquisition.completeness import (
    Completeness,
    EpisodeCompleteness,
    SeasonCompleteness,
)
from personalscraper.app.acquisition.follows import AccountRef, FollowView
from personalscraper.app.acquisition.model import QualityFloor
from personalscraper.app.acquisition.states import EpisodeState, FollowStatus
from personalscraper.core.identity import MediaRef
from personalscraper.http_v1.contract import ContractModel
from personalscraper.http_v1.models.media import ProviderIdValue

#: How long a follow is « fresh » after it was made: the interface marks it and sorts it first
#: (``Follow.fresh``, « added recently enough to be marked as such »). One day: a follow made today. The
#: value is PROVISIONAL, no ruling gives it (an open contract question): the tests pin both sides of it.
FRESH_WINDOW_SECONDS: Final = 24 * 60 * 60

#: The wire's names of the quality floors the contract's profile enum lists.
QualityProfile = Literal["720p", "1080p", "2160p"]

#: The contract's ``setAcquisitionQuality`` profile: a floor, or ``null`` for the default — ``null`` is a MEMBER
#: of its enum, which pydantic writes as a second branch.
ProfileOrDefault = Annotated[
    QualityProfile | None,
    WithJsonSchema({"type": ["string", "null"], "enum": ["720p", "1080p", "2160p", None]}),
]


def floor_of(profile: QualityProfile | None) -> QualityFloor | None:
    """The floor a wire profile names.

    Args:
        profile: ``"720p"``, ``"1080p"``, ``"2160p"`` or ``None`` (the default profile).

    Returns:
        The floor, ``None`` for the default.
    """
    return None if profile is None else QualityFloor(int(profile.removesuffix("p")))


def profile_of(floor: QualityFloor | None) -> QualityProfile | None:
    """The wire profile a floor is served as.

    Args:
        floor: The floor, or ``None``.

    Returns:
        ``"720p"``, ``"1080p"``, ``"2160p"`` or ``None``.
    """
    if floor is None:
        return None
    profile: QualityProfile = f"{int(floor)}p"  # type: ignore[assignment]  # the enum holds exactly 720, 1080, 2160
    return profile


def _ids(ref: MediaRef) -> dict[str, int | str]:
    """A medium's provider ids as the wire carries them: TVDB and TMDB integers, IMDb text.

    Args:
        ref: The follow's ids, at least one set.

    Returns:
        The ids that are set.
    """
    ids: dict[str, int | str] = {}
    if ref.tvdb_id is not None:
        ids["tvdb"] = ref.tvdb_id
    if ref.tmdb_id is not None:
        ids["tmdb"] = ref.tmdb_id
    if ref.imdb_id is not None:
        ids["imdb"] = ref.imdb_id
    return ids


class AccountRefModel(ContractModel):
    """The contract's ``AccountRef``: an account named by another answer, a requester.

    Attributes:
        id: The account's key.
        name: Its display name.
    """

    id: str
    name: str

    @classmethod
    def from_ref(cls, ref: AccountRef) -> AccountRefModel:
        """Map a requester.

        Args:
            ref: The service's requester.

        Returns:
            The body.
        """
        return cls(id=ref.id, name=ref.name)


class FollowModel(ContractModel):
    """The contract's ``Follow``: a medium followed, as the signed-in account reads it.

    Attributes:
        title: The title.
        kind: ``movie`` or ``show``.
        year: The year, ``None`` when unknown. The contract also lets a string through (the maquette's own
            mocks hold one); the service serves an integer or ``None``.
        status: The acquisition status token.
        show_status: Whether the show is still running, ``None`` for a film.
        added_at: Unix-epoch seconds the follow was made.
        next_air_date: ISO date of the next release, ``None`` when none is known.
        searches: How many searches have run for it.
        owned: A show's episodes held; unassigned on a film.
        aired: A show's episodes aired; unassigned on a film.
        fresh: Made recently enough to be marked as such.
        ids: The medium's provider ids.
        poster: The poster's address, ``None`` when none is known.
        requesters: Who asked for it.
        own_quality: The floor the caller set, ``None`` when none.
        quality: The floor in force, ``None`` when none is set.
        own_paused: Whether the caller asked for a pause.
        paused: Whether the follow is paused in force.
    """

    title: str
    kind: str
    year: int | str | None
    status: FollowStatus
    show_status: str | None
    added_at: float
    next_air_date: str | None
    searches: int
    owned: int | None = None
    aired: int | None = None
    fresh: bool | None = None
    ids: dict[str, ProviderIdValue]
    poster: str | None
    requesters: list[AccountRefModel] | None = None
    own_quality: str | None = None
    quality: str | None = None
    own_paused: bool | None = None
    paused: bool | None = None

    @classmethod
    def from_view(cls, view: FollowView, now: float) -> FollowModel:
        """Map a follow as its reader sees it; a film's show counts stay unassigned.

        Args:
            view: The service's view.
            now: The epoch the answer is made at, which ``fresh`` is read against.

        Returns:
            The body.
        """
        # Integers in the contract: a count the service does not know (no aired catalogue cached) is left unassigned.
        counts = {"owned": view.owned, "aired": view.aired} if view.kind == "show" else {}
        shows_only = {name: count for name, count in counts.items() if count is not None}
        return cls(
            title=view.title,
            kind=view.kind,
            year=view.year,
            status=view.status,  # type: ignore[arg-type]  # the single derivation's tokens, the contract's enum
            show_status=view.show_status,
            added_at=view.added_at,
            next_air_date=view.next_air_date,
            searches=view.searches,
            fresh=now - view.added_at < FRESH_WINDOW_SECONDS,
            ids=_ids(view.ids),
            poster=view.poster,
            requesters=[AccountRefModel.from_ref(one) for one in view.requesters],
            own_quality=profile_of(view.own_quality),
            quality=profile_of(view.quality),
            own_paused=view.own_paused,
            paused=view.paused,
            **shows_only,
        )


class CreateFollowBody(ContractModel):
    """The contract's ``createFollow`` body: the medium to follow, identified by one provider pair.

    The pair is optional on the wire and required here in fact: a follow with no identity has no sheet
    to open, so the route refuses a body that names none.

    Attributes:
        title: The title, for a new follow.
        kind: ``movie`` or ``show``.
        year: The year, for a new follow.
        provider: The provider the id belongs to.
        provider_id: The id at that provider.
    """

    title: str
    kind: str
    year: int | None = None
    provider: str | None = None
    provider_id: int | None = None


class UpdateFollowBody(ContractModel):
    """The contract's ``updateFollow`` body.

    Attributes:
        status: ``disabled`` pauses the follow; ``pending`` resumes a film and ``up_to_date`` a show.
    """

    status: Literal["disabled", "pending", "up_to_date"]


class SetQualityBody(ContractModel):
    """The contract's ``setAcquisitionQuality`` body.

    Attributes:
        profile: The resolution floor the caller sets, ``None`` to follow the default.
    """

    profile: ProfileOrDefault


class SetPauseBody(ContractModel):
    """The contract's ``setAcquisitionPause`` body.

    Attributes:
        paused: Whether the caller pauses its own ask.
    """

    paused: bool


class Acknowledgement(ContractModel):
    """The contract's ``deleteFollow`` answer.

    Attributes:
        ok: Always true: it is gone.
    """

    ok: bool


class ReassignBody(ContractModel):
    """The contract's ``reassignRequester`` body.

    Attributes:
        kind: A follow, or a card of the queue.
        acquisition: The acquisition's key, ``<provider>:<providerId>``.
        source: The requester moved off, by its account id (``from`` on the wire).
        target: The account moved on, by its account id (``to`` on the wire).
    """

    kind: Literal["follow", "card"]
    acquisition: str
    source: str = Field(alias="from")
    target: str = Field(alias="to")


class Requesters(ContractModel):
    """The contract's ``reassignRequester`` answer: the acquisition's requesters after the move.

    Attributes:
        requesters: Who asked for the acquisition now.
    """

    requesters: list[AccountRefModel]

    @classmethod
    def from_refs(cls, refs: tuple[AccountRef, ...]) -> Requesters:
        """Map the requesters.

        Args:
            refs: The service's requesters.

        Returns:
            The body.
        """
        return cls(requesters=[AccountRefModel.from_ref(one) for one in refs])


class EpisodeCompletenessModel(ContractModel):
    """The contract's ``EpisodeCompleteness``.

    Attributes:
        episode: Its number within the season.
        title: Its title, ``None`` when the provider gave none.
        air_date: ISO ``YYYY-MM-DD``, ``None`` when unknown.
        state: The single derivation's reading.
        last_search_outcome: The verdict of the governing search, ``None`` when none ran.
    """

    episode: int
    title: str | None = None
    air_date: str | None = None
    state: EpisodeState
    last_search_outcome: str | None = None

    @classmethod
    def from_fact(cls, fact: EpisodeCompleteness) -> EpisodeCompletenessModel:
        """Map one episode.

        Args:
            fact: The service's fact.

        Returns:
            The body.
        """
        return cls(
            episode=fact.episode,
            title=fact.title,
            air_date=fact.air_date,
            state=fact.state,
            last_search_outcome=fact.last_search_outcome,
        )


class SeasonCompletenessModel(ContractModel):
    """The contract's ``SeasonCompleteness``.

    Attributes:
        season: Its number.
        total: Aired episodes.
        owned: Of those, the ones in the library.
        queued: Of those, the ones wanted and not yet held.
        announced: Episodes announced and not yet aired.
        episodes: Its episodes, by number.
    """

    season: int
    total: int
    owned: int
    queued: int
    announced: int
    episodes: list[EpisodeCompletenessModel]

    @classmethod
    def from_fact(cls, fact: SeasonCompleteness) -> SeasonCompletenessModel:
        """Map one season.

        Args:
            fact: The service's fact.

        Returns:
            The body.
        """
        return cls(
            season=fact.season,
            total=fact.total,
            owned=fact.owned,
            queued=fact.queued,
            announced=fact.announced,
            episodes=[EpisodeCompletenessModel.from_fact(one) for one in fact.episodes],
        )


class FollowCompletenessModel(ContractModel):
    """The contract's ``FollowCompleteness``: what has aired against what the library holds, per season.

    Attributes:
        followed_id: The follow's row, the integer the contract declares (the medium's key names it on the path).
        title: Its title.
        kind: ``show`` or ``movie`` (a film has no seasons).
        seasons: Its seasons, newest first; empty for a film or with no cached catalogue.
        source: ``cache``, or ``unknown`` when no aired catalogue is cached.
        provider_catalog_empty: Reserved for a detect-confirmed empty catalogue: never set today.
        catalog_refreshed_at: Epoch seconds of the detect pass that wrote the cache, ``None`` without one.
    """

    followed_id: int
    title: str
    kind: str
    seasons: list[SeasonCompletenessModel]
    source: Literal["cache", "unknown"]
    provider_catalog_empty: bool
    catalog_refreshed_at: float | None = None

    @classmethod
    def from_completeness(cls, fact: Completeness) -> FollowCompletenessModel:
        """Map a follow's completeness.

        Args:
            fact: The service's fact.

        Returns:
            The body.
        """
        return cls(
            followed_id=fact.follow_id,
            title=fact.title,
            kind=fact.kind,
            seasons=[SeasonCompletenessModel.from_fact(one) for one in fact.seasons],
            source=fact.source,
            provider_catalog_empty=False,
            catalog_refreshed_at=fact.catalog_refreshed_at,
        )
