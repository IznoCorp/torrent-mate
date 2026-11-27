"""``Suggestions.read(after_title=…)``: the interface continues the deck from the last card's title.

A card of the contract's ``Suggestion`` carries no cursor, and the interface sends the last card's
``title`` as ``after`` (its typed client: « the last card's `title` is where the next page starts »).
The service therefore continues the deck from the card that title names. The numeric cursor the
service itself gives (``after``) is pinned in ``test_suggestions.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.app.errors import AppBadRequest
from personalscraper.conf.models.acquire import AcquireConfig
from tests.unit.app.acquisition.test_suggestions import _actor, _Library, _row, _service


@pytest.fixture
def store(tmp_path: Path) -> ConcreteAcquireStore:
    """A real acquire store the test seeds the deck in.

    Args:
        tmp_path: Pytest temp directory.

    Returns:
        The store, closed by the test through its own garbage collection of the connection.
    """
    return build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))


def _deck(store: ConcreteAcquireStore, count: int) -> None:
    """Fill the deck with ``count`` shows titled ``Title 1`` … ``Title <count>``.

    Args:
        store: The store.
        count: How many rows.
    """
    store.suggestions.replace_deck([_row("tmdb", str(n)) for n in range(1, count + 1)])


def test_the_page_after_a_title_continues_the_deck_past_that_card(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """The cards come after the one the title names, in deck order."""
    _deck(store, 6)
    service, _ = _service(tmp_path)

    page = service.read(_actor(), None, limit=2, after_title="Title 2")

    assert [item.title for item in page.items] == ["Title 3", "Title 4"]


def test_a_title_the_deck_does_not_hold_starts_at_the_head(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """A deck replaced since the page was read has no such card: the new deck starts over."""
    _deck(store, 3)
    service, _ = _service(tmp_path)

    page = service.read(_actor(), None, limit=2, after_title="Title of a deck that is gone")

    assert [item.title for item in page.items] == ["Title 1", "Title 2"]


def test_a_title_past_the_first_batch_is_found(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """The deck is scanned past its first read batch to find the title."""
    _deck(store, 130)
    service, _ = _service(tmp_path)

    page = service.read(_actor(), None, limit=2, after_title="Title 120")

    assert [item.title for item in page.items] == ["Title 121", "Title 122"]


def test_the_last_card_of_the_deck_leaves_nothing_after_it(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """Continuing from the last card is an empty page that ends the deck."""
    _deck(store, 3)
    service, _ = _service(tmp_path)

    page = service.read(_actor(), None, limit=2, after_title="Title 3")

    assert (page.items, page.after) == ((), None)


def test_a_title_that_is_digits_is_a_title_not_a_cursor(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """« 1917 » names a film, never the deck key 1917."""
    store.suggestions.replace_deck([_row("tmdb", "1", title="1917"), _row("tmdb", "2", title="Next")])
    service, _ = _service(tmp_path)

    assert [item.title for item in service.read(_actor(), None, limit=5, after_title="1917").items] == ["Next"]


def test_a_cursor_and_a_title_are_not_asked_together(store: ConcreteAcquireStore, tmp_path: Path) -> None:
    """One way to continue per read."""
    _deck(store, 3)
    service, _ = _service(tmp_path, library=_Library())

    with pytest.raises(AppBadRequest):
        service.read(_actor(), "1", after_title="Title 1")
