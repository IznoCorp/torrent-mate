"""The suggestions deck's refresh: recommendations over the follows' and the library's ids (K3 P11c).

``personalscraper acquisition-suggestions-refresh`` is the deck's only writer. It seeds the
providers' recommendations with the titles an account follows (first: an explicit signal) and the
titles the library holds, then replaces the deck in one transaction. The library's titles come in
through a callable: ``acquire/`` never imports the indexer, and the application layer reads the
library THROUGH THE INDEXER (``app.acquisition.held_titles``), never ``library.db`` by SQL.

Politeness, as ``library-catalogue-refresh``'s: a deck refreshed within
:data:`DEFAULT_MIN_INTERVAL_S` is not asked again (unless forced), and at most ``max_seeds`` seeds
are asked per run. The seeds rotate: the store remembers when each was asked
(``suggestion_seed``) and a run takes the seeds least recently asked first, the follows before the
library among equals, so the seeds a run left over are the next run's first. A provider failure on
one seed is counted and the run goes on (that seed is not marked asked, and is retried first); a
run in which no provider answered leaves the previous deck and its date untouched, so an outage
neither empties the deck nor makes it look fresh. A title that two seeds recommend is stored once,
for the first seed asked.

Each provider is asked by the id it numbers titles with (TMDB's, TVDB's; IMDb's for Trakt and the
rest): a seed holding no such id costs the provider no call and the run no slot.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from personalscraper.acquire.domain import FollowKind, SuggestionReason, SuggestionRow
from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import Recommendation
from personalscraper.core.identity import MediaRef
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore

log = get_logger("acquire.suggestions_refresh")

__all__ = [
    "DEFAULT_MAX_SEEDS",
    "DEFAULT_MIN_INTERVAL_S",
    "HeldTitle",
    "Recommender",
    "SuggestionsRefreshReport",
    "refresh_suggestions",
]

#: A deck refreshed less than this long ago is not asked again. Six days, not a week: the weekly
#: cron's runs start a few seconds apart from one week to the next, and a gate of exactly the cron's
#: period would skip a run that starts a second earlier than the last.
DEFAULT_MIN_INTERVAL_S: Final[int] = 6 * 86400

#: Seeds asked in one run unless the operator says otherwise (each costs one call per provider).
DEFAULT_MAX_SEEDS: Final[int] = 25

#: The ``MediaRef`` field a provider numbers titles with; every other provider is asked by IMDb id.
_NATIVE_ID: Final[dict[str, str]] = {"tmdb": "tmdb_id", "tvdb": "tvdb_id"}


class Recommender(Protocol):
    """A provider that recommends: the registry's ``RecommendationProvider``, with its name."""

    provider_name: str

    def get_recommendations(self, media_id: str, media_type: MediaType) -> list[Recommendation]:
        """Fetch the titles related to ``media_id``.

        Args:
            media_id: The seed's id in the provider's own numbering.
            media_type: ``"movie"`` or ``"tv"``.

        Returns:
            The recommendations, possibly none.
        """
        ...


#: A title the library holds: its provider ids and its kind.
type HeldTitle = tuple[MediaRef, FollowKind]


@dataclass(frozen=True)
class SuggestionsRefreshReport:
    """What one refresh run did.

    Attributes:
        asked: Provider calls that answered.
        failed: Provider calls that failed (the run went on).
        stored: Titles the new deck holds; ``0`` when the deck was left as it was.
        remaining: Seeds not asked in this run because ``max_seeds`` was reached (they come first
            in the next run).
        fresh: Whether the run asked nobody because the deck is younger than the interval.
    """

    asked: int = 0
    failed: int = 0
    stored: int = 0
    remaining: int = 0
    fresh: bool = False


@dataclass(frozen=True)
class _Seed:
    """One title the providers are asked for recommendations of.

    Attributes:
        ref: Its provider ids.
        kind: ``"movie"`` or ``"show"``.
        reason: The code its recommendations carry.
        key: Its name in the deck (``"tvdb:81189"``).
    """

    ref: MediaRef
    kind: FollowKind
    reason: SuggestionReason
    key: str


def _identity(ref: MediaRef, kind: FollowKind) -> set[tuple[str, ...]]:
    """Return the tokens by which two sources of one title are recognised.

    TMDB and TVDB number films and shows apart, so their ids are tokens within a kind; an IMDb
    id numbers both together.

    Args:
        ref: The title's provider ids.
        kind: Its kind.

    Returns:
        One token per id the ref holds.
    """
    tokens: set[tuple[str, ...]] = set()
    if ref.tvdb_id is not None:
        tokens.add((kind, "tvdb", str(ref.tvdb_id)))
    if ref.tmdb_id is not None:
        tokens.add((kind, "tmdb", str(ref.tmdb_id)))
    if ref.imdb_id is not None:
        tokens.add(("imdb", ref.imdb_id))
    return tokens


def _key_of(ref: MediaRef) -> str:
    """Name a title by its first id: TVDB, TMDB, then IMDb.

    Args:
        ref: The title's provider ids (at least one set).

    Returns:
        ``"tvdb:81189"``, ``"tmdb:603"`` or ``"imdb:tt0133093"``.
    """
    if ref.tvdb_id is not None:
        return f"tvdb:{ref.tvdb_id}"
    if ref.tmdb_id is not None:
        return f"tmdb:{ref.tmdb_id}"
    return f"imdb:{ref.imdb_id}"


def _seeds(store: AcquireStore, library_titles: Callable[[], Iterable[HeldTitle]]) -> list[_Seed]:
    """Gather the seeds: the standing active follows, then the library's live titles.

    A title both followed and held is one seed, the follow's.

    Args:
        store: The acquire store (the follows).
        library_titles: Reads the titles the library holds, most recently added first.

    Returns:
        The seeds, the follows first, the library most recently added first (the order of the
        seeds no run has asked yet; :func:`refresh_suggestions` reorders the others by their age).
    """
    seeds: list[_Seed] = []
    seen: set[tuple[str, ...]] = set()

    def add(ref: MediaRef, kind: FollowKind, reason: SuggestionReason) -> None:
        tokens = _identity(ref, kind)
        if tokens & seen:
            return
        seen.update(tokens)
        seeds.append(_Seed(ref=ref, kind=kind, reason=reason, key=_key_of(ref)))

    for follow in store.follow.list_active():
        add(follow.media_ref, follow.kind, "similar_to_followed")
    for ref, kind in library_titles():
        add(ref, kind, "similar_to_owned")
    return seeds


def _native_id(provider: Recommender, ref: MediaRef) -> str | None:
    """Return the id a provider is asked a seed by.

    Args:
        provider: The recommending provider.
        ref: The seed's provider ids.

    Returns:
        The id in the provider's numbering; ``None`` when the seed holds none.
    """
    value = getattr(ref, _NATIVE_ID.get(provider.provider_name, "imdb_id"))
    return None if value is None else str(value)


def refresh_suggestions(
    store: AcquireStore,
    library_titles: Callable[[], Iterable[HeldTitle]],
    providers: Sequence[Recommender],
    *,
    now: int,
    max_seeds: int,
    min_interval_s: int = DEFAULT_MIN_INTERVAL_S,
    force: bool = False,
) -> SuggestionsRefreshReport:
    """Rebuild the suggestions deck from the providers' recommendations, politely.

    Args:
        store: The acquire store (the follows read, the deck written).
        library_titles: Reads the titles the library holds (through the indexer), most recently added first.
        providers: The recommending providers, in priority order; none means nothing is asked.
        now: Current unix time (stamped as ``refreshed_at``).
        max_seeds: The most seeds asked in this run; the least recently asked go first.
        min_interval_s: A deck refreshed less than this long ago is left alone.
        force: Ask even when the deck is fresh.

    Returns:
        The run's report.
    """
    last = store.suggestions.refreshed_at()
    if not force and last is not None and now - last < min_interval_s:
        return SuggestionsRefreshReport(fresh=True)
    if not providers:
        log.info("acquire.suggestions_refresh.no_provider")
        return SuggestionsRefreshReport()

    deck: dict[tuple[str, str, str], SuggestionRow] = {}
    asked = failed = remaining = seeds_asked = 0
    asked_seeds: dict[str, int] = {}
    last_asked = store.suggestions.seeds_asked_at()
    # Least recently asked first; the sort is stable, so seeds never asked keep the follows-first order.
    for seed in sorted(_seeds(store, library_titles), key=lambda s: last_asked.get(s.key, -1)):
        usable = [(p, media_id) for p in providers if (media_id := _native_id(p, seed.ref)) is not None]
        if not usable:
            continue  # no provider can be asked by this seed's ids: no call, no slot
        if seeds_asked >= max_seeds:
            remaining += 1
            continue
        seeds_asked += 1
        answered, unanswered = _ask_seed(usable, seed, now, deck)
        asked += answered
        failed += unanswered
        if answered:
            asked_seeds[seed.key] = now

    if asked == 0:
        return SuggestionsRefreshReport(failed=failed, remaining=remaining)
    store.suggestions.replace_deck(list(deck.values()), asked_seeds=asked_seeds)
    return SuggestionsRefreshReport(asked=asked, failed=failed, stored=len(deck), remaining=remaining)


def _ask_seed(
    usable: list[tuple[Recommender, str]], seed: _Seed, now: int, deck: dict[tuple[str, str, str], SuggestionRow]
) -> tuple[int, int]:
    """Ask every provider that can be asked about one seed and add what they recommend to the deck.

    A title already in the deck stays for the seed that recommended it first.

    Args:
        usable: Each provider with the seed's id in its numbering.
        seed: The seed.
        now: The refresh's unix time.
        deck: The deck being built, by ``(provider, provider_id, kind)``.

    Returns:
        ``(answered, failed)`` provider calls.
    """
    media_type = MediaType.MOVIE if seed.kind == "movie" else MediaType.TV
    answered = failed = 0
    for provider, media_id in usable:
        recommendations = _ask(provider, media_id, media_type, seed)
        if recommendations is None:
            failed += 1
            continue
        answered += 1
        for rec in recommendations:
            row = _row_of(rec, seed, now)
            if row is not None:
                deck.setdefault((row.provider, row.provider_id, row.kind), row)
    return answered, failed


def _ask(provider: Recommender, media_id: str, media_type: MediaType, seed: _Seed) -> list[Recommendation] | None:
    """Ask one provider for a seed's recommendations, fail-soft.

    Args:
        provider: The recommending provider.
        media_id: The seed's id in the provider's numbering.
        media_type: The seed's media type.
        seed: The seed (named in the log).

    Returns:
        The recommendations (possibly none); ``None`` when the provider failed.
    """
    try:
        return provider.get_recommendations(media_id, media_type)
    except Exception as exc:  # noqa: BLE001 — fail-soft: one bad seed must not stop the run
        log.warning(
            "acquire.suggestions_refresh.ask_failed",
            provider=provider.provider_name,
            seed=seed.key,
            error=str(exc),
        )
        return None


def _row_of(rec: Recommendation, seed: _Seed, now: int) -> SuggestionRow | None:
    """Map a provider's recommendation to a deck row.

    Args:
        rec: The recommendation.
        seed: The seed it answers.
        now: The refresh's unix time.

    Returns:
        The row; ``None`` for a recommendation with no id or no title.
    """
    if not rec.provider_id.strip() or not rec.title.strip():
        return None
    return SuggestionRow(
        provider=rec.provider,
        provider_id=rec.provider_id,
        kind="movie" if rec.media_type == MediaType.MOVIE else "show",
        title=rec.title,
        year=rec.year,
        rating=None,
        poster=None,
        reason=seed.reason,
        seed_key=seed.key,
        refreshed_at=now,
    )
