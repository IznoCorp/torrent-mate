"""The acquisition reads' bodies: the release picker, the provider search, the deck and the ranking preview.

Written from the contract's ``Release``, ``SearchResults``, ``Suggestion`` and ``RankingPreview`` (and the
``RankingConfig`` the preview is asked with). The contract fixes what the wire says; two of its places
say more than the services hold, and the mapping is deliberate:

* a string the contract requires and the engine may not know (a release's ``resolution``, ``source`` and
  ``language``, a result's ``overview``) is ``""``, never ``null``;
* ``Suggestion`` is the contract as it stands, before K3-G7 corrects it: ``year`` is a string, ``rating`` a
  number, and ``why`` the run of pieces the interface words itself, here the reason's code (the contract
  forbids the server its own words).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, WithJsonSchema

from personalscraper.app.acquisition.ranking import PreviewedRelease
from personalscraper.app.acquisition.releases import ReleaseOffer
from personalscraper.app.acquisition.search import SearchedMedium, SearchPage
from personalscraper.app.acquisition.suggestions import SuggestedMedium, SuggestionPage
from personalscraper.conf.models._ranking import RankingBonuses, RankingConfig, RankingCriterion, ThresholdEntry
from personalscraper.core.identity import MediaRef
from personalscraper.http_v1.contract import ContractModel
from personalscraper.http_v1.models.media import ProviderIdValue

#: Bytes in the decimal gigabyte a release's size is told in, as the preview's samples are written.
_BYTES_PER_GIGABYTE = 1_000_000_000

#: The contract's nullable ``ProviderIds``: a map of ids, each an integer or a string, or ``null``.
ProviderIdsOrNull = Annotated[
    dict[str, ProviderIdValue] | None,
    WithJsonSchema(
        {
            "oneOf": [
                {"type": "object", "additionalProperties": {"oneOf": [{"type": "integer"}, {"type": "string"}]}},
                {"type": "null"},
            ]
        }
    ),
]

#: The wire names of a criterion's field, as the contract spells them, and the engine's own.
_ENGINE_FIELD = {"sizeBytes": "size", "trackerRatioState": "tracker_ratio_state"}

#: The members of ``trackerRatioState`` the contract declares (its ``unknown`` is never served: see ``RatioStanding``).
_RatioState = Annotated[
    Literal["under_floor", "under_target", "comfortable", "unknown"] | None,
    WithJsonSchema(
        {"type": ["string", "null"], "enum": ["under_floor", "under_target", "comfortable", "unknown", None]}
    ),
]


#: The contract's ``SuggestionReason``: a piece of text, or a figure the interface emphasises.
ReasonPiece = Annotated[
    "str | EmphasisPiece",
    WithJsonSchema(
        {
            "oneOf": [
                {"type": "string"},
                {"type": "object", "properties": {"emphasis": {"type": "string"}}, "required": ["emphasis"]},
            ]
        }
    ),
]

#: A criterion's ``prefer``, with the ``null`` the contract lists among its enum members.
_Prefer = Annotated[
    Literal["higher", "lower"] | None,
    WithJsonSchema({"type": ["string", "null"], "enum": ["higher", "lower", None]}),
]


def ids_of(ref: MediaRef | None) -> dict[str, ProviderIdValue] | None:
    """Spell a medium's ids as the contract's ``ProviderIds``.

    Args:
        ref: The ids a medium is known by, or ``None`` for none.

    Returns:
        ``{"tvdb": 81189, "tmdb": 1396, "imdb": "tt0903747"}`` for the ids held; ``None`` when none is.
    """
    if ref is None:
        return None
    ids: dict[str, ProviderIdValue] = {}
    if ref.tvdb_id is not None:
        ids["tvdb"] = ref.tvdb_id
    if ref.tmdb_id is not None:
        ids["tmdb"] = ref.tmdb_id
    if ref.imdb_id is not None:
        ids["imdb"] = ref.imdb_id
    return ids or None


class ReleaseModel(ContractModel):
    """The contract's ``Release``: one candidate the picker offers.

    Attributes:
        id: The candidate's handle, which a grab chooses it by.
        name: The release name, as the tracker publishes it.
        resolution: Its resolution, ``""`` when unknown.
        source: Its source, ``""`` when unknown.
        language: Its language tag, ``""`` when unknown.
        seeders: Its seeders when searched.
        size_gigabytes: Its size in decimal gigabytes.
        score: The ranking score.
        season: The season it numbers, ``None`` for a film.
        episode: The episode it numbers, ``None`` for a season and for a film.
    """

    id: str
    name: str
    resolution: str
    source: str
    language: str
    seeders: int
    size_gigabytes: float
    score: int
    season: int | None
    episode: int | None

    @classmethod
    def from_offer(cls, offer: ReleaseOffer) -> ReleaseModel:
        """Map one offer.

        Args:
            offer: The candidate and the wanted row it was found for.

        Returns:
            The body.
        """
        candidate = offer.candidate
        return cls(
            id=offer.handle,
            name=candidate.title,
            resolution=candidate.resolution or "",
            source=candidate.source or "",
            language=candidate.language or "",
            seeders=candidate.seeders,
            size_gigabytes=candidate.size_bytes / _BYTES_PER_GIGABYTE,
            score=candidate.score,
            season=candidate.season,
            episode=candidate.episode,
        )


class SearchResultModel(ContractModel):
    """The contract's ``SearchResult``: one medium a provider knows.

    Attributes:
        title: The provider's title.
        year: The release or first-air year, ``None`` when the provider gives none.
        kind: ``movie`` or ``show``.
        overview: The synopsis, ``""`` when none.
        owned: Whether the library holds it.
        followed: Whether a standing follow holds it.
        ids: Its provider identity, ``None`` when no sheet identifies it.
        poster: The poster's address, ``None`` when none is known.
    """

    title: str
    year: int | None
    kind: Literal["movie", "show"]
    overview: str
    owned: bool
    followed: bool
    ids: ProviderIdsOrNull
    poster: str | None

    @classmethod
    def from_medium(cls, medium: SearchedMedium) -> SearchResultModel:
        """Map one result.

        Args:
            medium: The service's result.

        Returns:
            The body; a result whose provider id is not a number has no ``ids``.
        """
        ref = None
        if medium.provider_id > 0:
            ref = (
                MediaRef(tmdb_id=medium.provider_id)
                if medium.provider == "tmdb"
                else MediaRef(tvdb_id=medium.provider_id)
            )
        return cls(
            title=medium.title,
            year=medium.year,
            kind="movie" if medium.kind == "movie" else "show",
            overview=medium.overview or "",
            owned=medium.owned,
            followed=medium.followed,
            ids=ids_of(ref),
            poster=medium.poster_url,
        )


class SearchResults(ContractModel):
    """The contract's ``SearchResults``: one page of a search, or the media found by an identifier.

    Attributes:
        total: How many the provider has.
        shown: How many this page carries.
        results: The page, best first.
    """

    total: int
    shown: int
    results: list[SearchResultModel]

    @classmethod
    def from_page(cls, page: SearchPage) -> SearchResults:
        """Map one page of a search.

        Args:
            page: The service's page.

        Returns:
            The body.
        """
        results = [SearchResultModel.from_medium(medium) for medium in page.results]
        return cls(total=page.total, shown=len(results), results=results)

    @classmethod
    def from_media(cls, media: tuple[SearchedMedium, ...]) -> SearchResults:
        """Map the media an identifier resolved to.

        Args:
            media: The media found, possibly none.

        Returns:
            The body; its total is what was found.
        """
        results = [SearchResultModel.from_medium(medium) for medium in media]
        return cls(total=len(results), shown=len(results), results=results)

    @classmethod
    def empty(cls) -> SearchResults:
        """The answer to a search with nothing to search for, or an identifier no source knows.

        Returns:
            No result.
        """
        return cls(total=0, shown=0, results=[])


class EmphasisPiece(ContractModel):
    """A piece of a ``why`` the interface emphasises.

    Attributes:
        emphasis: The emphasised text.
    """

    emphasis: str


class SuggestionModel(ContractModel):
    """The contract's ``Suggestion``, as it stands before K3-G7 corrects it.

    Attributes:
        title: The provider's title.
        year: The year as text, ``""`` when none.
        kind: ``movie`` or ``show``.
        rating: The provider's rating, ``0`` when none came with the title.
        why: The reason's code, which the interface words (the contract forbids the server its own words).
        ids: Its provider identity, ``None`` when it has none the library knows.
        poster: The poster's address, ``None`` when none is known.
        poster_high_definition: The full-screen poster, ``None``: the deck keeps none.
    """

    title: str
    year: str
    kind: str
    rating: float
    why: list[ReasonPiece]
    ids: ProviderIdsOrNull
    poster: str | None
    poster_high_definition: str | None

    @classmethod
    def from_card(cls, card: SuggestedMedium) -> SuggestionModel:
        """Map one card of the deck.

        Args:
            card: The service's card.

        Returns:
            The body.
        """
        return cls(
            title=card.title,
            year="" if card.year is None else str(card.year),
            kind=card.kind,
            rating=card.rating if card.rating is not None else 0.0,
            why=[card.reason],
            ids=ids_of(card.ids),
            poster=card.poster,
            poster_high_definition=None,
        )


class SuggestionPageModel(ContractModel):
    """The contract's ``SuggestionPage``: one page of the suggestions deck.

    Attributes:
        suggestions: The page's cards, in deck order.
        next_cursor: The ``cursor`` the next page is asked with, ``None`` once the deck has no more.
    """

    suggestions: list[SuggestionModel]
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: SuggestionPage) -> SuggestionPageModel:
        """Map one page of the deck.

        Args:
            page: The service's page.

        Returns:
            The body.
        """
        return cls(
            suggestions=[SuggestionModel.from_card(card) for card in page.items],
            next_cursor=page.after,
        )


class RankingThresholdBody(ContractModel):
    """The contract's ``RankingThreshold``.

    Attributes:
        at: The threshold: bytes for a size, a count for seeders.
        score: The score awarded when the field meets it.
    """

    at: float
    score: int


class RankingCriterionBody(ContractModel):
    """The contract's ``RankingCriterion``.

    Attributes:
        field: The release field it scores.
        weight: The multiplier applied to its score.
        values: A score per value, for a categorical field.
        thresholds: Ordered thresholds, for a numeric field.
        prefer: For thresholds, whether higher or lower is better.
    """

    field: str
    weight: float
    values: dict[str, int] | None = None
    thresholds: list[RankingThresholdBody] | None = None
    prefer: _Prefer = None

    def to_engine(self) -> RankingCriterion:
        """Translate the criterion to the engine's, field name included.

        The contract spells a field the way the API does (``sizeBytes``, ``trackerRatioState``); the engine
        reads the attribute of ``TrackerResult`` (``size``, ``tracker_ratio_state``). Any other name is the
        engine's own and passes as written.

        Returns:
            The engine's criterion.
        """
        return RankingCriterion(
            field=_ENGINE_FIELD.get(self.field, self.field),
            weight=self.weight,
            values=self.values,
            thresholds=None
            if self.thresholds is None
            else [ThresholdEntry(at=int(t.at), score=t.score) for t in self.thresholds],
            prefer=self.prefer,
        )


class RankingBonusesBody(ContractModel):
    """The contract's ``RankingBonuses``.

    Attributes:
        freeleech: Added to a freeleech release.
        silverleech: Added to a silverleech release.
    """

    freeleech: int
    silverleech: int


class RankingConfigBody(ContractModel):
    """The contract's ``RankingConfig``: the ranking the preview scores the samples under.

    Attributes:
        criteria: Every criterion, in order.
        min_seeders: A release with fewer seeders is excluded.
        bonuses: The bonuses.
    """

    criteria: list[RankingCriterionBody]
    min_seeders: int
    bonuses: RankingBonusesBody

    def to_engine(self) -> RankingConfig:
        """Translate the ranking to the engine's.

        Returns:
            The engine's ranking.
        """
        return RankingConfig(
            criteria=[criterion.to_engine() for criterion in self.criteria],
            bonuses=RankingBonuses(freeleech=self.bonuses.freeleech, silverleech=self.bonuses.silverleech),
            min_seeders=self.min_seeders,
        )


class RankingPreviewReleaseModel(ContractModel):
    """The contract's ``RankingPreviewRelease``: one sample scored under the ranking asked for.

    Attributes:
        title: The release's title.
        provider: The tracker it stands for.
        size_bytes: Its size.
        seeders: Its seeders.
        leechers: Its leechers.
        freeleech: Whether it is freeleech.
        resolution: Its resolution token.
        codec: Its video codec token.
        source: Its media source token.
        language: Its language marker.
        score: Its score under that ranking.
        excluded: Whether it has fewer seeders than ``minSeeders``.
        tracker_ratio_state: Where its tracker's ratio stands against that tracker's own economy.
    """

    title: str
    provider: str
    size_bytes: int
    seeders: int
    leechers: int
    freeleech: bool
    resolution: str | None
    codec: str | None
    source: str | None
    language: str | None
    score: int
    excluded: bool
    tracker_ratio_state: _RatioState

    @classmethod
    def from_preview(cls, release: PreviewedRelease) -> RankingPreviewReleaseModel:
        """Map one scored sample.

        Args:
            release: The service's scored sample.

        Returns:
            The body.
        """
        return cls(
            title=release.title,
            provider=release.provider,
            size_bytes=release.size_bytes,
            seeders=release.seeders,
            leechers=release.leechers,
            freeleech=release.freeleech,
            resolution=release.resolution,
            codec=release.codec,
            source=release.source,
            language=release.language,
            score=release.score,
            excluded=release.excluded,
            tracker_ratio_state=release.tracker_ratio_state,  # type: ignore[arg-type]  # a standing the service validated
        )


class RankingPreviewModel(ContractModel):
    """The contract's ``RankingPreview``: the sample set, scored and ordered.

    Attributes:
        ranked: Every sample, scored, in the order the ranking puts them.
        known_trackers: The configured trackers, the values a tracker-keyed criterion is offered.
    """

    ranked: Annotated[list[RankingPreviewReleaseModel], Field(description="every sample, scored")]
    known_trackers: list[str]
