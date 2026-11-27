"""K3-G7's rejection store in ``app.db`` (O-9 A), and the titles a card's reason names.

The store is the environment's real ``app`` store on ``tmp_path`` (its migrations run); the deck is a
real acquire store; the library's index is a fake reader (no ``library.db`` is opened).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import pytest

from personalscraper.acquire.domain import FollowedSeries, SuggestionReason, SuggestionRow
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.accounts.actor import Actor, RoleKind
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.model import Account
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.acquisition.rejection_repository import AccountRejections
from personalscraper.app.acquisition.suggestions import Suggestions
from personalscraper.app.errors import AppForbidden, RefusalCode
from personalscraper.app.store.store import AppStore
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.library_view import IndexUnavailable

_KEY = ("tmdb", "1", "show")
_OTHER_KEY = ("tmdb", "1", "movie")
_MINE = "account-mine"
_THEIRS = "account-theirs"


def _actor(account: str = _MINE, *, read_only: bool = False) -> Actor:
    """An actor of an account holding ``acquisition.request``."""
    return Actor(
        account_id=account,
        name=account,
        role_id="household",
        role_kind=RoleKind.ORDINARY,
        role_rights=frozenset({Right.ACQUISITION_REQUEST}),
        ceiling=InstanceCeiling(forbidden=WRITE_RIGHTS if read_only else frozenset(), read_only=read_only),
    )


@pytest.fixture
def app_store(tmp_path: Path) -> Iterator[AppStore]:
    """A real ``app.db`` holding two accounts.

    Args:
        tmp_path: Pytest's temporary directory.

    Yields:
        The store.
    """
    store = AppStore(tmp_path / "app.db")
    for account in (_MINE, _THEIRS):
        store.accounts.insert_account(
            Account(
                id=account,
                name=account,
                email=f"{account}@example.org",
                avatar="",
                role_id="household",
                password_hash=None,
                created_at=1.0,
                updated_at=1.0,
            )
        )
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def acquire(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """A real ``acquire.db`` to seed the deck and the follows in.

    Args:
        tmp_path: Pytest's temporary directory.

    Yields:
        The store.
    """
    store = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield store
    finally:
        store.close()


class _Item:
    """An index row, as far as a title is read off it."""

    def __init__(self, title: str, kind: str) -> None:
        self.title = title
        self.kind = kind


class _Index:
    """A fake library reader: the titles it holds, by ``(provider, provider_id)``, as films."""

    def __init__(self, titles: Mapping[tuple[str, str], str]) -> None:
        self.titles = dict(titles)
        self.asked: list[tuple[str, str]] = []

    def holders(self, provider: str, provider_id: str) -> list[_Item]:
        """The rows bearing one provider id."""
        self.asked.append((provider, provider_id))
        title = self.titles.get((provider, provider_id))
        return [] if title is None else [_Item(title, "movie")]


class _Library:
    """A fake ownership reader of a library that owns none of the deck's titles."""

    def owns(self, media_ref: MediaRef, **_: object) -> bool:
        """No film is held."""
        return False

    def owned_pairs(self, media_ref: MediaRef) -> set[tuple[int, int]]:
        """No episode is held."""
        return set()

    def close(self) -> None:
        """Nothing to release."""


def _unreadable() -> AbstractContextManager[_Index]:
    """An index that cannot be read."""
    raise IndexUnavailable("no index")


def _service(tmp_path: Path, app_store: AppStore, index: _Index | None = None, *, readable: bool = True) -> Suggestions:
    """The service over the test's two stores and a fake library."""
    held = index if index is not None else _Index({})
    return Suggestions(
        open_store=lambda: build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db")),
        open_ownership=_Library,  # type: ignore[arg-type]
        open_index=(lambda: nullcontext(held)) if readable else _unreadable,  # type: ignore[arg-type,return-value]
        cursor_key=lambda: b"k" * 32,
        rejections=AccountRejections(app_store),
    )


def _row(provider_id: str, reason: SuggestionReason, seed_key: str, kind: str = "show") -> SuggestionRow:
    """A deck row."""
    return SuggestionRow(
        provider="tmdb",
        provider_id=provider_id,
        kind=kind,  # type: ignore[arg-type]
        title=f"Title {provider_id}",
        year=2021,
        rating=8.1,
        poster=None,
        reason=reason,
        seed_key=seed_key,
        refreshed_at=1_800_000_000,
    )


class TestTheStore:
    """``suggestion_rejection``: one row per account and title."""

    def test_a_rejection_is_the_accounts_own(self, app_store: AppStore) -> None:
        """Another account's rejection never counts."""
        app_store.suggestion_rejections.add(_MINE, _KEY, now=1.0)

        assert app_store.suggestion_rejections.rejected(_MINE, [_KEY, _OTHER_KEY]) == {_KEY}
        assert app_store.suggestion_rejections.rejected(_THEIRS, [_KEY]) == set()

    def test_adding_twice_holds_one_row_and_removing_says_whether_it_held_one(self, app_store: AppStore) -> None:
        """A rejection is a state; the removal tells whether there was one."""
        app_store.suggestion_rejections.add(_MINE, _KEY, now=1.0)
        app_store.suggestion_rejections.add(_MINE, _KEY, now=2.0)

        assert app_store.suggestion_rejections.remove(_MINE, _KEY) is True
        assert app_store.suggestion_rejections.remove(_MINE, _KEY) is False
        assert app_store.suggestion_rejections.rejected(_MINE, [_KEY]) == set()

    def test_no_key_asked_is_no_key_answered(self, app_store: AppStore) -> None:
        """An empty page asks nothing of the table."""
        assert app_store.suggestion_rejections.rejected(_MINE, []) == set()

    def test_a_deleted_account_takes_its_rejections_with_it(self, app_store: AppStore, tmp_path: Path) -> None:
        """``ON DELETE CASCADE``: no row outlives its account."""
        app_store.suggestion_rejections.add(_MINE, _KEY, now=1.0)
        connection = app_store._ensure_open()

        connection.execute("DELETE FROM account WHERE id = ?", (_MINE,))

        assert connection.execute("SELECT COUNT(*) FROM suggestion_rejection").fetchone()[0] == 0


class TestTheDoorInProcess:
    """An in-process caller is refused what an HTTP one is."""

    @pytest.mark.parametrize("act", ["reject", "undo_rejection"])
    def test_a_read_only_instance_refuses_the_write(self, app_store: AppStore, tmp_path: Path, act: str) -> None:
        """403 before any store is opened."""
        with pytest.raises(AppForbidden) as refused:
            getattr(_service(tmp_path, app_store), act)(_actor(read_only=True), "show:tmdb:1")

        assert refused.value.code is RefusalCode.INSTANCE_FORBIDDEN_WRITE


class TestTheReasonsTitles:
    """The reason names the seed by its title, read where the seed lives."""

    def test_a_followed_seed_is_named_by_its_follows_title(
        self, app_store: AppStore, acquire: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """``similar_to_followed``: the follow's own title."""
        acquire.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=81189), title="Silo", added_at=1, kind="show"))
        acquire.suggestions.replace_deck([_row("1", "similar_to_followed", "tvdb:81189")])

        (card,) = _service(tmp_path, app_store).read(_actor(), None).items

        assert card.reason_titles == ("Silo",)

    def test_an_owned_seed_is_named_by_the_librarys_title_read_once(
        self, app_store: AppStore, acquire: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """``similar_to_owned``: the library's title, through the index, once per seed of a page."""
        index = _Index({("tmdb", "603"): "The Matrix"})
        acquire.suggestions.replace_deck([_row(n, "similar_to_owned", "tmdb:603", "movie") for n in ("1", "2")])

        cards = _service(tmp_path, app_store, index).read(_actor(), None).items

        assert [card.reason_titles for card in cards] == [("The Matrix",), ("The Matrix",)]
        assert index.asked == [("tmdb", "603")]

    def test_a_row_of_the_other_kind_under_the_same_number_names_nothing(
        self, app_store: AppStore, acquire: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """TMDB numbers films and shows apart: a show's seed is never named by a film's title."""
        acquire.suggestions.replace_deck([_row("1", "similar_to_owned", "tmdb:603", "show")])

        (card,) = _service(tmp_path, app_store, _Index({("tmdb", "603"): "The Matrix"})).read(_actor(), None).items

        assert card.reason_titles == ()

    def test_a_seed_nobody_holds_any_more_names_no_title(
        self, app_store: AppStore, acquire: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """A follow gone, a medium deleted: no title is guessed."""
        acquire.suggestions.replace_deck(
            [_row("1", "similar_to_followed", "tvdb:1"), _row("2", "similar_to_owned", "imdb:tt0000001")]
        )

        cards = _service(tmp_path, app_store).read(_actor(), None).items

        assert [card.reason_titles for card in cards] == [(), ()]

    def test_an_unreadable_index_names_no_title_and_serves_the_deck(
        self, app_store: AppStore, acquire: ConcreteAcquireStore, tmp_path: Path
    ) -> None:
        """The words lose their title, never the reader their cards."""
        acquire.suggestions.replace_deck([_row("1", "similar_to_owned", "tmdb:603")])

        (card,) = _service(tmp_path, app_store, readable=False).read(_actor(), None).items

        assert card.reason_titles == ()
