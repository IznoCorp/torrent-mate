"""``scoped`` and ``scoped_hashes`` keep the torrents of the instance's own category."""

from personalscraper.api.torrent._base import scoped, scoped_hashes
from tests.fixtures.torrent_scope import OTHER_CATEGORY_HASH, PREPROD_HASH, PROD_HASH, SCOPE, shared_client, torrent


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
