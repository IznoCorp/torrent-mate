"""``MediaSheets``: a medium's sheet and poster, the provider's facts crossed with the library's.

Reads over the index (``library.db``), the aired catalogue (``acquire.db``) and the
metadata providers. Every read is ``library.read``: each method is authorised by
``@requires`` before it opens anything.
"""

from __future__ import annotations

import mimetypes
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Final, Literal

from personalscraper.acquire.catalogue import CatalogueEpisode, ProviderLookup
from personalscraper.api.metadata._base import MediaDetails
from personalscraper.app.accounts.actor import Actor
from personalscraper.app.accounts.authorise import requires
from personalscraper.app.library.catalogue import catalogue_key
from personalscraper.app.library.completeness import CatalogueView
from personalscraper.app.library.facts import (
    EpisodeFact,
    MediaSheetFacts,
    ProviderSheet,
    ProviderSheetCache,
    SeasonSummaryFact,
    SheetClient,
    cast_of,
    cast_portraits_of,
    fetch_details,
    genres_of,
    hero_of,
    poster_of,
    refuse_not_found,
    status_of,
    trailer_key_of,
)
from personalscraper.app.library.identity import Provider, ref_key
from personalscraper.app.library.listing import held_of, open_reader, resolve_media_folder
from personalscraper.core.artwork_naming import artwork_inventory
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import IndexItem, LibraryIndex
from personalscraper.logger import get_logger

log = get_logger("app.library.sheets")

__all__ = ["POSTER_MAX_BYTES", "LocalPoster", "MediaSheets"]

#: The largest poster file served, in bytes: a request reads it whole into memory, so a
#: file above this (no real poster is) is refused before it is read.
POSTER_MAX_BYTES: Final[int] = 20 * 1024 * 1024


@dataclass(frozen=True)
class LocalPoster:
    """The poster file a medium's library folder holds, read at request time.

    Attributes:
        content: The file's bytes.
        media_type: Its media type, from its extension (``image/jpeg``, ``image/png``).
    """

    content: bytes
    media_type: str


def _folder_poster(mount_path: str, folder: str) -> LocalPoster | None:
    """Read the item-level poster of one media folder, never anything outside it.

    The folder is resolved inside its disk (:func:`resolve_media_folder`), and the poster
    file (the name the artwork inventory recognises) must resolve directly inside the
    folder: a symlink or a ``..`` leading elsewhere is refused, whatever it reaches.

    Args:
        mount_path: The disk's mount point, as the index names it.
        folder: The media folder below it, as the index names it.

    Returns:
        The poster, or ``None`` when the disk, the folder or the poster is not there, when
        a path escapes, when a symlink loops, or when the poster exceeds
        ``POSTER_MAX_BYTES``.
    """
    resolved = resolve_media_folder(mount_path, folder)
    if resolved is None:
        return None
    _, directory = resolved
    try:
        name = artwork_inventory(directory)["poster"]
        if name is None:
            return None
        poster = (directory / name).resolve(strict=True)
        if poster.parent != directory or not poster.is_file():
            return None
        if poster.stat().st_size > POSTER_MAX_BYTES:
            return None
        content = poster.read_bytes()
    except (OSError, RuntimeError):
        # Python 3.12's strict resolve raises RuntimeError, not OSError, on a symlink loop.
        return None
    media_type, _ = mimetypes.guess_type(poster.name)
    return LocalPoster(content=content, media_type=media_type or "application/octet-stream")


def _sheet_ids(
    held: IndexItem | None, answered: Mapping[str, str], provider: str, provider_id: str
) -> dict[str, int | str]:
    """Merge the ids the library's row holds with those the provider answered.

    The row's ids win; the provider's fill the gaps. Placeholders (``""``, ``"0"``) name nothing.

    Args:
        held: The live row holding the medium, or ``None``.
        answered: The provider's ``external_ids`` (text values).
        provider: The provider asked.
        provider_id: The id it was asked at.

    Returns:
        ``{"tvdb": int, "tmdb": int, "imdb": str}`` in that order, the absent ones left out.
    """
    known = {**answered, provider: provider_id}
    ids: dict[str, int | str] = {}
    for name in ("tvdb", "tmdb", "imdb"):
        if held is not None and name in held.ids:
            ids[name] = held.ids[name]
            continue
        raw = str(known.get(name) or "").strip()
        if name == "imdb" and raw:
            ids[name] = raw
        elif raw.isdigit() and raw != "0":
            ids[name] = int(raw)
    return ids


def _crossed_trailer_and_rating(details: MediaDetails, crossed: MediaDetails) -> MediaDetails:
    """Fill a TVDB answer's missing trailer and rating from the TMDB answer for the same show.

    The trailer travels whole (URL, name, language) so its parts never mix two providers.

    Args:
        details: TVDB's answer.
        crossed: TMDB's answer for the same show.

    Returns:
        TVDB's answer with TMDB's trailer when TVDB has none, and TMDB's rating when TVDB
        has none.
    """
    trailer = details if details.trailer_url else crossed
    return replace(
        details,
        trailer_url=trailer.trailer_url,
        trailer_name=trailer.trailer_name,
        trailer_language=trailer.trailer_language,
        rating=details.rating if details.rating is not None else crossed.rating,
    )


class MediaSheets:
    """A medium's sheet and its local poster.

    The provider's answers are cached for five minutes; the catalogue view is shared with
    the reads.
    """

    def __init__(
        self,
        *,
        index: LibraryIndex,
        view: CatalogueView,
        providers: ProviderLookup,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Hold the index, the catalogue view and the providers; nothing is opened yet.

        Args:
            index: ``library.db``, read-only.
            view: The aired catalogue and the ownership checker (shared: closed by its owner).
            providers: Where the metadata provider clients are found; ``None`` for an unavailable one.
            clock: Epoch seconds; the provider cache's clock.
        """
        self._index = index
        self._view = view
        self._providers = providers
        self._sheets = ProviderSheetCache(clock)

    @requires("readMediaSheet")
    def read_sheet(self, actor: Actor, ref: MediaRef) -> MediaSheetFacts:
        """Read a medium's sheet: the provider's facts crossed with the library's.

        A medium the library does not hold is still answered (owned ``False``).

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).
            ref: The medium.

        Returns:
            The sheet's facts.

        Raises:
            AppNotFound: ``media.not_found`` when the provider does not know the id, or for
                an IMDb id the library does not hold (no client reads a sheet by IMDb id).
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read;
                ``provider.unavailable`` when the provider is not configured or
                does not answer.
        """
        with open_reader(self._index) as reader:
            holders, folders = held_of(reader, ref)
        live = [row for row in holders if row.item_id in folders]
        held = live[0] if live else None
        provider, provider_id = self._provider_for(ref, held)
        answer = self.provider_sheet(provider, provider_id, held.kind if held is not None else None)
        details = answer.details
        ids = _sheet_ids(held, details.external_ids, provider, provider_id)
        is_show = answer.kind == "show"
        episodes: list[CatalogueEpisode] | None = None
        if is_show:
            key = catalogue_key(held.ids, held.canonical_provider) if held is not None else catalogue_key(ids, provider)
            if key is not None:
                episodes = self._view.episodes_at(key)
        provider_poster = poster_of(details)
        poster_url = provider_poster or (held.poster_url if held is not None else None)
        refreshed = held.date_provider_read if held is not None else None
        tmdb_tv = ids.get("tmdb") if is_show else None
        return MediaSheetFacts(
            title=held.title if held is not None else details.title,
            kind=answer.kind,
            year=details.year if details.year is not None else (held.year if held is not None else None),
            rating=details.rating,
            genres=genres_of(details),
            runtime=details.runtime_minutes,
            overview=(held.overview if held is not None and held.overview else None) or details.overview or None,
            director=details.director,
            creator=answer.creator,
            cast=cast_of(details),
            cast_portraits=cast_portraits_of(details),
            trailer_key=trailer_key_of(details),
            trailer_name=details.trailer_name,
            trailer_language=details.trailer_language,
            ids=ids,
            status=status_of(details),
            owned=held is not None,
            episodes=self._episode_facts(episodes) if is_show else None,
            seasons=self._season_summaries(details, episodes) if is_show else None,
            tmdb_television_id=str(tmdb_tv) if tmdb_tv is not None else None,
            poster_url=poster_url,
            local_poster=poster_url is None and held is not None and held.has_local_poster,
            poster_high_definition_url=provider_poster,
            hero_url=hero_of(details),
            metadata_refreshed_at=datetime.fromtimestamp(refreshed).date() if refreshed is not None else None,
        )

    @requires("readMediaPoster")
    def read_local_poster(self, actor: Actor, ref: MediaRef) -> LocalPoster:
        """Read the poster file of the library folder holding a medium.

        The folder is the index's (the row the sheet reads: the lowest holding row with
        live files), on a disk the index says is mounted; the file is resolved now, never
        named by the request.

        Args:
            actor: Who reads; authorised by ``@requires`` (``library.read``).
            ref: The medium.

        Returns:
            The poster's bytes and media type.

        Raises:
            AppNotFound: ``media.not_found`` when no row holding the id has a live file, or
                when none of its folders holds a poster that can be read inside it.
            AppUnavailable: ``library.unavailable`` when ``library.db`` cannot be read.
        """
        provider, _ = ref_key(ref)
        with open_reader(self._index) as reader:
            holders, folders = held_of(reader, ref)
            live = [row for row in holders if row.item_id in folders]
            mounted = reader.mounted_media_folders(live[0].item_id) if live else []
        for mount_path, folder in mounted:
            poster = _folder_poster(mount_path, folder)
            if poster is not None:
                return poster
        raise refuse_not_found(provider.value)

    # ------------------------------------------------------------------ the sheet's parts

    def _provider_for(self, ref: MediaRef, held: IndexItem | None) -> tuple[str, str]:
        """Choose the provider and id a sheet is read at.

        TVDB and TMDB ids are read where the wire names them. An IMDb id is read at the held
        row's TVDB id for a show or TMDB id for a movie (then the other one).

        Args:
            ref: The medium.
            held: The live row holding it, or ``None``.

        Returns:
            ``(provider, id as text)``.

        Raises:
            AppNotFound: ``media.not_found`` for an IMDb id no live row resolves.
        """
        provider, provider_id = ref_key(ref)
        if provider is not Provider.IMDB:
            return provider.value, provider_id
        if held is not None:
            order = ("tvdb", "tmdb") if held.kind == "show" else ("tmdb", "tvdb")
            for name in order:
                if name in held.ids:
                    return name, str(held.ids[name])
        raise refuse_not_found(Provider.IMDB.value)

    def provider_sheet(self, provider: str, provider_id: str, kind: Literal["movie", "show"] | None) -> ProviderSheet:
        """Read a provider's answer, through the five-minute cache.

        A TVDB show is crossed with TMDB through its TMDB id for what TVDB does not give:
        the creator when it names none (operator ruling 2026-08-04), the trailer and the
        rating (TVDB has neither, and the interface opens a show at TVDB first). Fail-soft:
        a failed cross leaves those facts unknown and the sheet answers from TVDB alone.

        Args:
            provider: ``"tvdb"`` or ``"tmdb"``.
            provider_id: The id at that provider.
            kind: The medium's kind when the library knows it.

        Returns:
            The answer.
        """
        cached = self._sheets.get((provider, provider_id))
        if cached is not None and (kind is None or cached.kind == kind):
            return cached
        details, answered = fetch_details(self._providers.get(provider), provider, provider_id, kind)
        creator = details.creator
        tmdb_id = details.external_ids.get("tmdb", "").strip()
        tmdb = self._providers.get("tmdb")
        lacking = not creator or not details.trailer_url or details.rating is None
        if answered == "show" and lacking and provider == "tvdb" and tmdb_id not in ("", "0"):
            if isinstance(tmdb, SheetClient):
                try:
                    crossed = tmdb.get_tv(tmdb_id)
                except Exception as exc:  # noqa: BLE001 — fail-soft: the crossed facts stay unknown
                    log.debug("app.library.creator_cross_failed", tmdb_id=tmdb_id, error=str(exc))
                else:
                    creator = creator or crossed.creator
                    details = _crossed_trailer_and_rating(details, crossed)
        answer = ProviderSheet(details=details, kind=answered, creator=creator)
        self._sheets.put((provider, provider_id), answer)
        return answer

    @staticmethod
    def _episode_facts(episodes: Sequence[CatalogueEpisode] | None) -> dict[int, tuple[EpisodeFact, ...]] | None:
        """Group the catalogue's episodes by season for the sheet.

        Args:
            episodes: The show's catalogue, or ``None`` when never fetched.

        Returns:
            ``{season: episodes}``, or ``None`` when the catalogue is unknown.
        """
        if episodes is None:
            return None
        grouped: dict[int, list[EpisodeFact]] = {}
        for ep in episodes:
            grouped.setdefault(ep.season, []).append(EpisodeFact(ep.episode, ep.title, ep.air_date))
        return {season: tuple(grouped[season]) for season in sorted(grouped)}

    @staticmethod
    def _season_summaries(
        details: MediaDetails, episodes: Sequence[CatalogueEpisode] | None
    ) -> tuple[SeasonSummaryFact, ...]:
        """List a show's seasons as the provider knows them.

        Args:
            details: The provider's details (its ``seasons``).
            episodes: The show's catalogue, for each season's first air date, or ``None``.

        Returns:
            One summary per provider season; a count of 0 reads « not said ».
        """
        first: dict[int, date] = {}
        for ep in episodes or []:
            if ep.air_date is not None and (ep.season not in first or ep.air_date < first[ep.season]):
                first[ep.season] = ep.air_date
        return tuple(
            SeasonSummaryFact(
                number=season.season_number,
                episodes=season.episode_count or None,
                air_date=first.get(season.season_number),
            )
            for season in sorted(details.seasons, key=lambda s: s.season_number)
        )
