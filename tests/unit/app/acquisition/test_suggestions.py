"""``Suggestions.read``: the deck a refresh stored, minus what the reader already holds (K3 P11c).

The deck is built over a real acquire store on ``tmp_path``; the library is a fake ownership
reader (no ``library.db`` is opened). Owned and followed are told by provider id, never by
title. The per-account rejection store has its own tests (``test_suggestion_rejections``): what is
tested here is how a read leaves out what the seam tells it, with a fake filter standing for it.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from contextlib import nullcontext
from pathlib import Path
from typing import Literal

import pytest

from personalscraper.acquire.domain import FollowedSeries, SuggestionRow
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import Right
from personalscraper.app.acquisition.suggestions import SuggestionKey, Suggestions
from personalscraper.app.errors import AppBadRequest, AppForbidden, RefusalCode
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

_CEILING = InstanceCeiling(forbidden=frozenset(), read_only=False)


def _actor(
    account: str = "account-requester", rights: frozenset[Right] = frozenset({Right.ACQUISITION_REQUEST})
) -> Actor:
    """An actor of an account holding ``rights``."""
    return Actor(
        account_id=account,
        name=account,
        role_id="requester",
        role_kind=RoleKind.ORDINARY,
        role_rights=rights,
        ceiling=_CEILING,
    )


class _Library:
    """A fake ownership reader: the library holds the ids it is built with, live files only."""

    def __init__(
        self,
        *,
        movie_tmdb: Collection[int] = (),
        show_tmdb: Collection[int] = (),
        imdb: Collection[str] = (),
    ) -> None:
        self.movie_tmdb = set(movie_tmdb)
        self.show_tmdb = set(show_tmdb)
        self.imdb = set(imdb)
        self.closed = False

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Whether a film is held."""
        return media_ref.tmdb_id in self.movie_tmdb or media_ref.imdb_id in self.imdb

    def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
        """One episode pair when the show is held."""
        return {(1, 1)} if media_ref.tmdb_id in self.show_tmdb or media_ref.imdb_id in self.imdb else set()

    def close(self) -> None:
        """Record the release."""
        self.closed = True


class _NoTitles:
    """A fake index reader that holds no row, so a reason names no title."""

    def holders(self, provider: str, provider_id: str) -> list[object]:
        """No row bears any id."""
        return []


class _Rejections:
    """A fake rejection filter, per account: what an account rejected, by key."""

    def __init__(self, by_account: dict[str, set[SuggestionKey]]) -> None:
        self.by_account = by_account
        self.asked_by: list[str] = []

    def rejected(self, actor: Actor, keys: Sequence[SuggestionKey]) -> Collection[SuggestionKey]:
        """The keys among ``keys`` the actor's own account rejected."""
        self.asked_by.append(actor.account_id)
        return {k for k in keys if k in self.by_account.get(actor.account_id, set())}


def _row(provider: str, provider_id: str, kind: Literal["movie", "show"] = "show", **extra: object) -> SuggestionRow:
    """A deck row."""
    fields: dict[str, object] = {
        "provider": provider,
        "provider_id": provider_id,
        "kind": kind,
        "title": f"Title {provider_id}",
        "year": 2021,
        "rating": 8.1,
        "poster": "https://img/p.jpg",
        "reason": "similar_to_owned",
        "seed_key": "tmdb:603",
        "refreshed_at": 1_800_000_000,
    }
    fields.update(extra)
    return SuggestionRow(**fields)  # type: ignore[arg-type]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """A real acquire store the test seeds the deck and the follows in."""
    opened = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield opened
    finally:
        opened.close()


def _service(
    tmp_path: Path, library: _Library | None = None, rejections: _Rejections | None = None, key: bytes = b"k" * 32
) -> tuple[Suggestions, _Library]:
    """The service over the test's acquire store path and a fake library."""
    held = library if library is not None else _Library()
    service = Suggestions(
        open_store=lambda: build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db")),
        open_ownership=lambda: held,
        open_index=lambda: nullcontext(_NoTitles()),
        cursor_key=lambda: key,
        rejections=rejections if rejections is not None else _Rejections({}),
    )
    return service, held


def _titles(page_items: Sequence[object]) -> list[str]:
    """The provider ids of a page, in order."""
    return [item.provider_id for item in page_items]  # type: ignore[attr-defined]


class TestRead:
    """What the deck shows its reader."""

    def test_an_empty_deck_is_an_empty_page(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """No refresh ever ran: nothing to show, nothing after."""
        service, _ = _service(tmp_path)
        page = service.read(_actor(), None)
        assert page.items == () and page.after is None

    def test_a_card_carries_the_rows_columns(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """The reader sees the stored title, year, rating, poster, reason code and seed."""
        store.suggestions.replace_deck(
            [_row("tmdb", "42", "movie", reason="similar_to_followed", seed_key="tvdb:81189")]
        )
        service, _ = _service(tmp_path)

        (card,) = service.read(_actor(), None).items

        assert (card.provider, card.provider_id, card.kind, card.title, card.year) == (
            "tmdb",
            "42",
            "movie",
            "Title 42",
            2021,
        )
        assert (card.rating, card.poster, card.reason, card.seed_key) == (
            8.1,
            "https://img/p.jpg",
            "similar_to_followed",
            "tvdb:81189",
        )

    def test_the_library_is_released_after_a_read(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """The ownership reader is opened for the call and closed with it."""
        store.suggestions.replace_deck([_row("tmdb", "1")])
        service, library = _service(tmp_path)
        service.read(_actor(), None)
        assert library.closed

    def test_an_owned_film_and_an_owned_show_are_excluded(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """By provider id: a film a live file holds, a show with any live episode file."""
        store.suggestions.replace_deck(
            [_row("tmdb", "603", "movie"), _row("tmdb", "1399"), _row("tmdb", "9999"), _row("tmdb", "9998", "movie")]
        )
        service, _ = _service(tmp_path, _Library(movie_tmdb={603}, show_tmdb={1399}))

        assert _titles(service.read(_actor(), None).items) == ["9999", "9998"]

    def test_an_imdb_id_from_a_slug_provider_is_matched_to_the_library(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """Trakt answers an IMDb id (``tt…``) when it has no slug: it is the library's by that id."""
        store.suggestions.replace_deck([_row("trakt", "tt0903747"), _row("trakt", "tt0000001")])
        service, _ = _service(tmp_path, _Library(imdb={"tt0903747"}))

        assert _titles(service.read(_actor(), None).items) == ["tt0000001"]

    def test_an_id_the_library_cannot_be_asked_by_is_never_excluded(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """A Trakt slug or Trakt numeric id names no TVDB, TMDB or IMDb id: no title guess, it stays."""
        store.suggestions.replace_deck([_row("trakt", "breaking-bad"), _row("trakt", "1388")])
        service, _ = _service(tmp_path, _Library(movie_tmdb={1388}, show_tmdb={1388}, imdb={"breaking-bad"}))

        assert _titles(service.read(_actor(), None).items) == ["breaking-bad", "1388"]

    def test_a_trakt_card_is_excluded_by_the_ids_beside_its_slug(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """Trakt's ``provider_id`` is a slug: the owned film and the followed show leave by their other ids."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=81189), title="Breaking Bad", added_at=1))
        store.suggestions.replace_deck(
            [
                _row("trakt", "inception-2010", "movie", external_ids={"imdb": "tt1375666", "tmdb": "27205"}),
                _row("trakt", "breaking-bad", external_ids={"imdb": "tt0903747", "tvdb": "81189"}),
                _row("trakt", "the-wire", external_ids={"imdb": "tt0306414", "tvdb": "79126"}),
                _row("trakt", "no-ids"),
            ]
        )
        service, _ = _service(tmp_path, _Library(movie_tmdb={27205}))

        assert _titles(service.read(_actor(), None).items) == ["the-wire", "no-ids"]

    def test_a_followed_show_and_a_followed_film_are_excluded(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """A standing follow holds the id: by TVDB for a show, by TMDB for a film."""
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=81189), title="Breaking Bad", added_at=1))
        store.follow.add(FollowedSeries(media_ref=MediaRef(tmdb_id=27205), title="Inception", added_at=1, kind="movie"))
        store.suggestions.replace_deck(
            [_row("tvdb", "81189"), _row("tmdb", "27205", "movie"), _row("tmdb", "27205"), _row("tvdb", "5")]
        )
        service, _ = _service(tmp_path)

        # The show row of TMDB 27205 is another medium than the followed film of that number.
        assert _titles(service.read(_actor(), None).items) == ["27205", "5"]

    def test_a_removed_follow_and_a_request_row_do_not_exclude(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """Only a standing follow does: a removed one and a one-off request leave the title suggested."""
        removed = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=1), title="Removed", added_at=1))
        request = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=2), title="Request", added_at=1))
        store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=3), title="Paused", added_at=1))
        conn = store._ensure_open()
        conn.execute("UPDATE followed_series SET removed_at = 777 WHERE id = ?", (removed,))
        conn.execute("UPDATE followed_series SET scope = 'request' WHERE id = ?", (request,))
        store.follow.set_active(3, False)
        store.suggestions.replace_deck([_row("tvdb", "1"), _row("tvdb", "2"), _row("tvdb", "3")])
        service, _ = _service(tmp_path)

        assert _titles(service.read(_actor(), None).items) == ["1", "2"]


class TestRejectionSeam:
    """The seam the rejection store plugs into once O-9 is ruled."""

    def test_without_a_filter_nothing_is_rejected(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """No rejection store wired: owned and followed are the only exclusions."""
        store.suggestions.replace_deck([_row("tmdb", "1"), _row("tmdb", "2")])
        service, _ = _service(tmp_path)
        assert _titles(service.read(_actor(), None).items) == ["1", "2"]

    def test_what_the_filter_names_is_excluded_for_its_reader_only(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """The filter is asked with the reader's actor: another account's rejection leaves the title in."""
        store.suggestions.replace_deck([_row("tmdb", "1"), _row("tmdb", "2", "movie"), _row("tmdb", "3")])
        rejections = _Rejections(
            {
                "account-requester": {("tmdb", "1", "show")},
                "account-other": {("tmdb", "3", "show"), ("tmdb", "2", "movie")},
            }
        )
        service, _ = _service(tmp_path, rejections=rejections)

        assert _titles(service.read(_actor("account-requester"), None).items) == ["2", "3"]
        assert _titles(service.read(_actor("account-other"), None).items) == ["1"]
        assert rejections.asked_by == ["account-requester", "account-other"]

    def test_a_rejected_title_does_not_cost_the_page_a_row(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """The page is filled from the rows that survive, not cut from the deck then thinned."""
        store.suggestions.replace_deck([_row("tmdb", str(i)) for i in range(6)])
        rejections = _Rejections({"account-requester": {("tmdb", "0", "show"), ("tmdb", "1", "show")}})
        service, _ = _service(tmp_path, rejections=rejections)

        assert _titles(service.read(_actor(), None, limit=3).items) == ["2", "3", "4"]


class TestPaging:
    """The deck is read a page at a time, continued by ``after``."""

    def test_after_continues_the_deck_without_overlap_to_its_end(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """Pages of 2 over 5 titles: 2, 2, 1, and the last page names no continuation."""
        store.suggestions.replace_deck([_row("tmdb", str(i)) for i in range(5)])
        service, _ = _service(tmp_path)

        first = service.read(_actor(), None, limit=2)
        second = service.read(_actor(), first.after, limit=2)
        third = service.read(_actor(), second.after, limit=2)

        assert (_titles(first.items), _titles(second.items), _titles(third.items)) == (["0", "1"], ["2", "3"], ["4"])
        assert first.after is not None and second.after is not None
        assert third.after is None

    def test_a_page_skips_owned_titles_and_still_fills(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """Owned rows between two kept ones do not shorten the page nor break the cursor."""
        store.suggestions.replace_deck([_row("tmdb", str(i)) for i in range(6)])
        service, _ = _service(tmp_path, _Library(show_tmdb={1, 2}))

        first = service.read(_actor(), None, limit=2)
        second = service.read(_actor(), first.after, limit=2)

        assert (_titles(first.items), _titles(second.items)) == (["0", "3"], ["4", "5"])

    def test_a_card_names_the_cursor_that_continues_after_it(self, store: ConcreteAcquireStore, tmp_path: Path) -> None:
        """``after`` is the cursor of the page's last card, so a client may continue from any card."""
        store.suggestions.replace_deck([_row("tmdb", str(i)) for i in range(3)])
        service, _ = _service(tmp_path)

        page = service.read(_actor(), None, limit=2)
        from_the_first_card = service.read(_actor(), page.items[0].cursor, limit=5)

        assert page.after == page.items[-1].cursor
        assert _titles(from_the_first_card.items) == ["1", "2"]

    def test_a_cursor_from_an_older_deck_restarts_the_new_one(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """A refresh between two pages never makes the reader skip a title of the new deck."""
        store.suggestions.replace_deck([_row("tmdb", "old1"), _row("tmdb", "old2")])
        service, _ = _service(tmp_path)
        stale = service.read(_actor(), None, limit=1).after
        store.suggestions.replace_deck([_row("tmdb", "new1"), _row("tmdb", "new2")])

        assert _titles(service.read(_actor(), stale).items) == ["new1", "new2"]

    def test_a_cursor_is_read_under_the_key_it_was_issued_under_and_no_other(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """Another service holding the same key (a restart) continues the deck; one holding another refuses."""
        store.suggestions.replace_deck([_row("tmdb", str(i)) for i in range(3)])
        cursor = _service(tmp_path)[0].read(_actor(), None, limit=1).after

        assert _titles(_service(tmp_path)[0].read(_actor(), cursor).items) == ["1", "2"]
        with pytest.raises(AppBadRequest):
            _service(tmp_path, key=b"o" * 32)[0].read(_actor(), cursor)

    @pytest.mark.parametrize("after", ["", "abc", "-1", "1.5"])
    def test_a_cursor_that_is_not_one_is_a_bad_request(
        self, store: ConcreteAcquireStore, tmp_path: Path, after: str
    ) -> None:
        """The deck's cursors are what ``read`` gave: anything else is refused, not guessed."""
        service, _ = _service(tmp_path)
        with pytest.raises(AppBadRequest) as refusal:
            service.read(_actor(), after)
        assert refusal.value.code == RefusalCode.REQUEST_INVALID


class TestAuthorisation:
    """``readSuggestions`` asks the right to request."""

    def test_an_actor_without_the_right_is_refused_before_anything_is_read(
        self, store: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """No acquisition right, no deck."""
        store.suggestions.replace_deck([_row("tmdb", "1")])
        service, library = _service(tmp_path)

        with pytest.raises(AppForbidden):
            service.read(_actor(rights=frozenset()), None)
        assert not library.closed
