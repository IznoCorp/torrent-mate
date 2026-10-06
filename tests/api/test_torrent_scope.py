"""``scoped`` and ``scoped_hashes`` keep the torrents of the instance's own category."""

from personalscraper.api.torrent._base import scoped, scoped_hashes
from tests.fixtures.torrent_scope import (
    OTHER_CATEGORY_HASH,
    PREPROD_HASH,
    PROD_HASH,
    SCOPE,
    HashOnlyClient,
    shared_client,
    torrent,
)


def test_scoped_none_returns_every_item_unchanged() -> None:
    """No scope: the list is the input, in order (today's behaviour)."""
    items = [torrent(PROD_HASH, None), torrent(PREPROD_HASH, "tm-preprod")]
    assert scoped(items, None) == items


def test_scoped_keeps_only_the_scope_category() -> None:
    """A scope keeps the items of its category, and drops uncategorised and foreign ones."""
    mine = torrent(PREPROD_HASH, "tm-preprod")
    items = [torrent(PROD_HASH, None), torrent("c" * 40, "tm-other"), mine]
    assert scoped(items, SCOPE) == [mine]


def test_scoped_accepts_a_generator() -> None:
    """The input may be any iterable."""
    mine = torrent(PREPROD_HASH, "tm-preprod")
    assert scoped((i for i in [mine]), None) == [mine]


def test_scoped_hashes_none_is_the_clients_hash_set() -> None:
    """No scope: exactly ``get_all_hashes()``, no per-torrent lookup."""
    client = shared_client()
    assert scoped_hashes(client, None) == {PROD_HASH, OTHER_CATEGORY_HASH, PREPROD_HASH}
    client.get_by_hashes.assert_not_called()


def test_scoped_hashes_under_scope_is_the_own_category_only() -> None:
    """A scope keeps the hashes of the torrents in its category."""
    assert scoped_hashes(shared_client(), SCOPE) == {PREPROD_HASH}


def test_scoped_hashes_under_scope_asks_the_client_by_category() -> None:
    """A scope asks the client for its category and never sends it the whole hash list."""
    client = shared_client()
    assert scoped_hashes(client, SCOPE) == {PREPROD_HASH}
    client.get_by_category.assert_called_once_with(SCOPE.category)
    client.get_by_hashes.assert_not_called()


def test_scoped_hashes_none_does_not_ask_by_category() -> None:
    """No scope: neither a category listing nor a per-torrent lookup."""
    client = shared_client()
    scoped_hashes(client, None)
    client.get_by_category.assert_not_called()
    client.get_by_hashes.assert_not_called()


def test_scoped_hashes_drops_a_foreign_category_a_client_filter_lets_through() -> None:
    """A client whose category filter also returns sub-categories still yields the exact category only."""
    client = shared_client()
    client.get_by_category.side_effect = lambda category: [
        torrent(PREPROD_HASH, "tm-preprod"),
        torrent(OTHER_CATEGORY_HASH, "tm-preprod/child"),
    ]
    assert scoped_hashes(client, SCOPE) == {PREPROD_HASH}


def test_scoped_hashes_client_without_categories_keeps_the_hash_lookup() -> None:
    """A client that cannot filter by category answers the same set through the hash lookup."""
    client = HashOnlyClient()
    assert scoped_hashes(client, SCOPE) == {PREPROD_HASH}
    assert client.by_hashes_calls == [{PROD_HASH, OTHER_CATEGORY_HASH, PREPROD_HASH}]
