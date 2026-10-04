"""The ``media`` tag's bodies, written from the contract's ``MediaSheet``, the seasons answer and ``RescrapeQueued``.

A property the contract leaves out of its required set and does not make nullable
(the show-only ``episodes``, ``seasons`` and ``tmdbTelevisionId``; an episode's
``duration``) is never assigned on a film, and the routes serialise with
``response_model_exclude_unset``: a film's sheet carries no show block at all,
while every required property, null included, is always assigned.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import Field, WithJsonSchema

from personalscraper.app.library.facts import (
    CastFact,
    EpisodeFact,
    GenreId,
    MediaSheetFacts,
    MediaStatus,
    SeasonSummaryFact,
)
from personalscraper.app.library.service import RescrapeAccepted, SeasonFacts, SeasonsFacts
from personalscraper.http_v1.contract import ContractModel

#: One provider id: an integer (TVDB, TMDB) or a string (IMDb). The contract's ``ProviderIds``
#: writes the union as a ``oneOf`` — the two are disjoint — where pydantic writes an ``anyOf``.
ProviderIdValue = Annotated[int | str, WithJsonSchema({"oneOf": [{"type": "integer"}, {"type": "string"}]})]


class CastMemberModel(ContractModel):
    """The contract's ``CastMember``.

    Attributes:
        name: The actor's name.
        role: The character played.
    """

    name: str
    role: str

    @classmethod
    def from_fact(cls, fact: CastFact) -> CastMemberModel:
        """Map one cast fact.

        Args:
            fact: The service's fact.

        Returns:
            The body.
        """
        return cls(name=fact.name, role=fact.role)


class TrailerModel(ContractModel):
    """The contract's ``Trailer``: a trailer's key beside its name.

    Attributes:
        key: The YouTube key.
        name: The trailer's title.
        language: Its language code, as the provider gives it.
    """

    key: str
    name: str
    language: str


class EpisodeModel(ContractModel):
    """The contract's ``Episode``: one catalogued episode.

    Attributes:
        number: The episode number.
        title: Its title; ``None`` when the catalogue gives none.
        air_date: Its air date, or ``None``.
        duration: Minutes, where known; never assigned (the catalogue holds none).
    """

    number: int
    title: str | None
    air_date: date | None = None
    duration: int | None = None

    @classmethod
    def from_fact(cls, fact: EpisodeFact) -> EpisodeModel:
        """Map one episode fact.

        Args:
            fact: The service's fact.

        Returns:
            The body.
        """
        return cls(number=fact.number, title=fact.title, air_date=fact.air_date)


class SeasonSummaryModel(ContractModel):
    """The contract's ``SeasonSummary``: a season as the provider knows it.

    Attributes:
        number: The season number.
        episodes: How many episodes the provider counts, or ``None``.
        air_date: The season's first air date, or ``None``.
    """

    number: int
    episodes: int | None = None
    air_date: date | None = None

    @classmethod
    def from_fact(cls, fact: SeasonSummaryFact) -> SeasonSummaryModel:
        """Map one season summary.

        Args:
            fact: The service's fact.

        Returns:
            The body.
        """
        return cls(number=fact.number, episodes=fact.episodes, air_date=fact.air_date)


class MediaSheet(ContractModel):
    """The contract's ``MediaSheet``: one medium's sheet, film or show.

    Attributes:
        title: The title the sheet is filed under.
        kind: ``movie`` or ``show``.
        year: The year, or ``None``.
        rating: The provider's average, or ``None``.
        genres: The genre tokens, in the provider's order.
        runtime: Minutes, or ``None``.
        overview: The synopsis, or ``None``.
        director: The director, or ``None``.
        creator: A show's creator, or ``None``.
        cast: The cast, in the provider's order.
        cast_portraits: The cast's portrait URLs, keyed by name.
        trailer: The trailer's title (the provider's first trailer), or ``None``.
        trailer_video: The trailer's key and name, or ``None`` unless all three are known.
        ids: Every provider id known.
        status: Where the medium stands at its provider, or ``None``.
        owned: Whether the library holds it.
        episodes: A show's catalogue by season number; unassigned on a film.
        seasons: A show's seasons as the provider knows them; unassigned on a film.
        tmdb_television_id: A show's TMDB id; unassigned on a film and on a show without one.
        poster: The poster's provider URL, or ``None``.
        poster_high_definition: The poster at gallery definition, or ``None``.
        hero: The wide visual's URL, or ``None``.
        metadata_refreshed_at: When the library last read the provider data, or ``None``.
    """

    title: str
    kind: str
    year: int | None
    rating: float | None
    genres: list[GenreId]
    runtime: int | None
    overview: str | None
    director: str | None
    creator: str | None
    cast: list[CastMemberModel]
    cast_portraits: dict[str, str] = Field(default_factory=dict)
    trailer: str | None
    trailer_video: TrailerModel | None = None
    ids: dict[str, ProviderIdValue]
    status: MediaStatus | None
    owned: bool
    episodes: dict[int, list[EpisodeModel]] | None = None
    seasons: list[SeasonSummaryModel] | None = None
    tmdb_television_id: str | None = None
    poster: str | None = None
    poster_high_definition: str | None = None
    hero: str | None = None
    metadata_refreshed_at: datetime | None = None

    @classmethod
    def from_facts(cls, facts: MediaSheetFacts) -> MediaSheet:
        """Map a sheet's facts; a film's sheet leaves the show-only properties unassigned.

        A poster the library folder alone holds (``local_poster``) has no URL to serve yet:
        ``poster`` is ``None`` until an image route answers it.

        Args:
            facts: The service's facts.

        Returns:
            The body.
        """
        has_trailer = facts.trailer_key is not None and facts.trailer_name is not None
        has_trailer = has_trailer and facts.trailer_language is not None
        trailer_video = (
            TrailerModel(key=facts.trailer_key, name=facts.trailer_name, language=facts.trailer_language)  # type: ignore[arg-type]
            if has_trailer
            else None
        )
        show_block: dict[str, object] = {}
        if facts.episodes is not None:
            show_block["episodes"] = {
                season: [EpisodeModel.from_fact(episode) for episode in episodes]
                for season, episodes in facts.episodes.items()
            }
        if facts.seasons is not None:
            show_block["seasons"] = [SeasonSummaryModel.from_fact(season) for season in facts.seasons]
        if facts.tmdb_television_id is not None:
            show_block["tmdb_television_id"] = facts.tmdb_television_id
        return cls(
            title=facts.title,
            kind=facts.kind,
            year=facts.year,
            rating=facts.rating,
            genres=list(facts.genres),
            runtime=facts.runtime,
            overview=facts.overview,
            director=facts.director,
            creator=facts.creator,
            cast=[CastMemberModel.from_fact(member) for member in facts.cast],
            cast_portraits=dict(facts.cast_portraits),
            trailer=facts.trailer_name,
            trailer_video=trailer_video,
            ids=dict(facts.ids),
            status=facts.status,
            owned=facts.owned,
            poster=facts.poster_url,
            poster_high_definition=facts.poster_high_definition_url,
            hero=facts.hero_url,
            metadata_refreshed_at=facts.metadata_refreshed_at,
            **show_block,  # type: ignore[arg-type]
        )


class SeasonModel(ContractModel):
    """The contract's ``Season``: one season, as the catalogue and the library know it.

    Attributes:
        number: The season number.
        episodes: How many episodes the catalogue lists, or ``None``.
        air_date: The season's first air date, or ``None``.
        off_catalogue: The held episode numbers above the catalogue's last, ascending.
    """

    number: int
    episodes: int | None
    air_date: date | None = None
    off_catalogue: list[int]

    @classmethod
    def from_fact(cls, fact: SeasonFacts) -> SeasonModel:
        """Map one season's facts.

        Args:
            fact: The service's fact.

        Returns:
            The body.
        """
        return cls(
            number=fact.number, episodes=fact.episodes, air_date=fact.air_date, off_catalogue=list(fact.off_catalogue)
        )


class MediaSeasons(ContractModel):
    """``readMediaSeasons``'s answer: the seasons, the held episodes, the aired counts.

    Attributes:
        seasons: The catalogued and held seasons, by number.
        owned: The held episode numbers, keyed by season number.
        aired: How many episodes of each season have aired, keyed by season number.
    """

    seasons: list[SeasonModel]
    owned: dict[int, list[int]]
    aired: dict[int, int | None]

    @classmethod
    def from_facts(cls, facts: SeasonsFacts) -> MediaSeasons:
        """Map a show's seasons facts.

        Args:
            facts: The service's facts.

        Returns:
            The body.
        """
        return cls(
            seasons=[SeasonModel.from_fact(season) for season in facts.seasons],
            owned={season: list(numbers) for season, numbers in facts.owned.items()},
            aired=dict(facts.aired),
        )


class RescrapeQueued(ContractModel):
    """``rescrapeMedia``'s 202: the ask accepted, running or visibly in file.

    Attributes:
        provider: The provider the medium was named at.
        provider_id: Its id there.
        queued: Whether the ask waits on the pipeline rather than running now.
        run_uid: The run to follow, or ``None``.
    """

    provider: str
    provider_id: str
    queued: bool
    run_uid: str | None

    @classmethod
    def from_acceptance(cls, accepted: RescrapeAccepted) -> RescrapeQueued:
        """Map the service's acceptance.

        Args:
            accepted: The acceptance.

        Returns:
            The body.
        """
        return cls(
            provider=accepted.provider.value,
            provider_id=accepted.provider_id,
            queued=accepted.queued,
            run_uid=accepted.run_uid,
        )
