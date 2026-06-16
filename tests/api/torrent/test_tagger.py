"""Tests for TorrentTagger capability on QBitClient and TransmissionClient.

Covers DESIGN criteria 1 (SEED_PURE importable), 2 (qBit tagger endpoints +
idempotence), and 3 (Transmission category preservation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient

# ---------------------------------------------------------------------------
# Criterion 1 — SEED_PURE constant
# ---------------------------------------------------------------------------


def test_seed_pure_importable_and_value():
    """SEED_PURE is importable from core.tags and equals 'seed-pure'."""
    from personalscraper.core.tags import SEED_PURE

    assert SEED_PURE == "seed-pure"


def test_seed_pure_in_all():
    """SEED_PURE is in core.tags.__all__."""
    import personalscraper.core.tags as m

    assert "SEED_PURE" in m.__all__


# ---------------------------------------------------------------------------
# Criterion 2 — QBitClient tagger
# ---------------------------------------------------------------------------


def _make_qbit_client() -> "QBitClient":
    """Build a QBitClient with a mocked underlying qbittorrentapi.Client."""
    from personalscraper.api.torrent.qbittorrent import QBitClient

    client = QBitClient.__new__(QBitClient)
    client._client = MagicMock()
    return client


def test_qbit_add_tags_calls_addTags():
    """add_tags calls torrents_addTags with correct hash and comma-joined tags."""
    client = _make_qbit_client()
    client.add_tags("abc123", ["seed-pure", "other"])
    client._client.torrents_addTags.assert_called_once_with(torrent_hashes="abc123", tags="seed-pure,other")


def test_qbit_remove_tags_calls_removeTags():
    """remove_tags calls torrents_removeTags with correct hash and comma-joined tags."""
    client = _make_qbit_client()
    client.remove_tags("abc123", ["seed-pure"])
    client._client.torrents_removeTags.assert_called_once_with(torrent_hashes="abc123", tags="seed-pure")


def test_qbit_add_tags_empty_is_noop():
    """add_tags with empty list makes no API call."""
    client = _make_qbit_client()
    client.add_tags("abc123", [])
    client._client.torrents_addTags.assert_not_called()


def test_qbit_remove_tags_empty_is_noop():
    """remove_tags with empty list makes no API call."""
    client = _make_qbit_client()
    client.remove_tags("abc123", [])
    client._client.torrents_removeTags.assert_not_called()


def test_qbit_tagger_protocol_compliance():
    """QBitClient satisfies the TorrentTagger protocol at runtime."""
    from personalscraper.api.torrent._contracts import TorrentTagger

    client = _make_qbit_client()
    assert isinstance(client, TorrentTagger)


# ---------------------------------------------------------------------------
# Criterion 3 — TransmissionClient tagger (category preservation is the
# load-bearing correctness point)
# ---------------------------------------------------------------------------


def _make_tx_client() -> "TransmissionClient":
    """Build a TransmissionClient with a mocked underlying transmission_rpc.Client."""
    from personalscraper.api.torrent.transmission import TransmissionClient

    client = TransmissionClient.__new__(TransmissionClient)
    client._client = MagicMock()
    return client


def _mock_torrent(labels: list[str]) -> MagicMock:
    """Return a mock Transmission Torrent object with the given labels."""
    t = MagicMock()
    t.labels = labels
    return t


def _mock_full_torrent(labels: list[str]) -> MagicMock:
    """Return a mock Transmission Torrent with every scalar ``_torrent_item`` reads.

    ``_torrent_item`` consumes more than ``labels`` (``download_dir``,
    ``added_date``, ``hash_string``, ``name``, ``total_size``, ``percent_done``,
    ``status``, ``ratio``). A bare ``MagicMock`` would raise on
    ``float(percent_done)`` / ``len(get_files())`` etc., so this helper sets
    benign scalars and varies only ``labels``.
    """
    t = MagicMock()
    t.labels = labels
    t.download_dir = ""  # falsy → skip content_path resolution
    t.added_date = None  # falsy → added_on stays None
    t.hash_string = "h"
    t.name = "n"
    t.total_size = 0
    t.percent_done = 1.0
    t.status = "seeding"
    t.ratio = 0.0
    return t


def test_tx_add_tags_preserves_category():
    """add_tags keeps labels[0] (category) and appends the new tag.

    Golden: category='movies', existing_tags=['tag1'],
    add_tags(['seed-pure']) → change_torrent called with
    labels=['movies', 'tag1', 'seed-pure'].
    """
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "tag1"])

    client.add_tags("abc123", ["seed-pure"])

    client._client.get_torrent.assert_called_once_with("abc123", arguments=["labels"])
    client._client.change_torrent.assert_called_once_with(ids="abc123", labels=["movies", "tag1", "seed-pure"])


def test_tx_add_tags_idempotent_already_present():
    """add_tags does not duplicate a tag already in the list."""
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "seed-pure"])

    client.add_tags("abc123", ["seed-pure"])

    # labels must stay exactly ['movies', 'seed-pure'] — no duplicate
    client._client.change_torrent.assert_called_once_with(ids="abc123", labels=["movies", "seed-pure"])


def test_tx_remove_tags_preserves_category():
    """remove_tags keeps labels[0] and removes only the requested tag."""
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "seed-pure", "other"])

    client.remove_tags("abc123", ["seed-pure"])

    client._client.change_torrent.assert_called_once_with(ids="abc123", labels=["movies", "other"])


def test_tx_remove_tags_idempotent_absent():
    """remove_tags on an absent tag is a no-op (no error, category preserved)."""
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies", "other"])

    client.remove_tags("abc123", ["seed-pure"])

    client._client.change_torrent.assert_called_once_with(ids="abc123", labels=["movies", "other"])


def test_tx_add_tags_no_category_roundtrips_as_tag():
    """No-category torrent keeps the tag readable as a tag (F-A regression).

    Load-bearing for the whole feature: Transmission stores
    ``labels=[category, *tags]`` flat. For a category-less torrent
    (``labels=[]``), the empty-string sentinel must be used so the tag is
    written at ``labels[1:]`` (``labels=["", "seed-pure"]``) rather than
    promoted to the category slot. ``_torrent_item`` must then read it back as
    a TAG (``category is None`` AND ``SEED_PURE in tags``) — the exact property
    the ingest skip (``SEED_PURE in tags``) depends on.

    Mutation-proof: the pre-fix code writes ``labels=["seed-pure"]`` and reads
    it back as the category, so ``SEED_PURE not in tags`` and this test fails.
    """
    from personalscraper.api.torrent.transmission import _split_labels
    from personalscraper.core.tags import SEED_PURE

    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent([])

    client.add_tags("h", [SEED_PURE])

    # Write side: tag must land at labels[1:] behind the no-category sentinel.
    client._client.change_torrent.assert_called_once_with(ids="h", labels=["", SEED_PURE])

    # Read side: the written labels round-trip to category=None, tag present.
    category, tags = _split_labels(["", SEED_PURE])
    assert category is None
    assert SEED_PURE in tags


def test_tx_torrent_item_no_category_sentinel_reads_as_tag():
    """The PRODUCTION reader _torrent_item reads the sentinel as a tag (F-A / F-G1).

    The regression test above asserts the read side via ``_split_labels`` in
    isolation; this drives the actual production reader ``_torrent_item`` so a
    future re-inline of the sentinel logic (desyncing it from ``_split_labels``)
    cannot ship green. For ``labels=["", "seed-pure"]`` the reader must yield
    ``category is None`` and ``tags == ["seed-pure"]`` — the exact property the
    ingest skip (``SEED_PURE in tags``) depends on.

    Mutation-proof: re-inlining ``category = labels[0]`` makes ``category == ""``
    (not None) and this test fails.
    """
    from personalscraper.api.torrent.transmission import _torrent_item
    from personalscraper.core.tags import SEED_PURE

    item = _torrent_item(_mock_full_torrent(["", SEED_PURE]))

    assert item.category is None
    assert item.tags == [SEED_PURE]


def test_tx_remove_tags_no_category():
    """remove_tags on a no-category torrent collapses back to empty labels."""
    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["", "seed-pure"])

    client.remove_tags("abc123", ["seed-pure"])

    client._client.change_torrent.assert_called_once_with(ids="abc123", labels=[])


def test_tx_add_tags_empty_is_noop():
    """add_tags with empty list makes no API call."""
    client = _make_tx_client()
    client.add_tags("abc123", [])
    client._client.get_torrent.assert_not_called()
    client._client.change_torrent.assert_not_called()


def test_tx_remove_tags_empty_is_noop():
    """remove_tags with empty list makes no API call."""
    client = _make_tx_client()
    client.remove_tags("abc123", [])
    client._client.get_torrent.assert_not_called()
    client._client.change_torrent.assert_not_called()


def test_tx_tagger_protocol_compliance():
    """TransmissionClient satisfies the TorrentTagger protocol at runtime."""
    from personalscraper.api.torrent._contracts import TorrentTagger

    client = _make_tx_client()
    assert isinstance(client, TorrentTagger)


# ---------------------------------------------------------------------------
# Criterion 4 — Regression: library exceptions must be translated to ApiError
# (test-per-bug: raw library exceptions currently escape the client boundary)
# ---------------------------------------------------------------------------


def test_tx_add_tags_translates_transmission_error_to_api_error():
    """TransmissionClient.add_tags translates TransmissionError to ApiError.

    Regression test — before the fix, _client.get_torrent raising
    TransmissionError escaped the client boundary unchanged, defeating the
    orchestrator's ``except ApiError`` swallow (DESIGN §4.2/§5/§6/§8).
    """
    import transmission_rpc

    from personalscraper.api._contracts import ApiError

    client = _make_tx_client()
    client._client.get_torrent.side_effect = transmission_rpc.TransmissionError("boom")

    with pytest.raises(ApiError):
        client.add_tags("h", ["seed-pure"])


def test_tx_remove_tags_translates_transmission_error_to_api_error():
    """TransmissionClient.remove_tags translates TransmissionError to ApiError.

    Regression test — before the fix, _client.get_torrent raising
    TransmissionError escaped the client boundary (same root cause as
    add_tags above).
    """
    import transmission_rpc

    from personalscraper.api._contracts import ApiError

    client = _make_tx_client()
    client._client.get_torrent.side_effect = transmission_rpc.TransmissionError("boom")

    with pytest.raises(ApiError):
        client.remove_tags("h", ["seed-pure"])


def test_tx_add_tags_change_torrent_error_translated():
    """TransmissionClient.add_tags translates change_torrent TransmissionError.

    Covers the second raw call site: _client.change_torrent can also raise
    TransmissionError (e.g. hash no longer tracked after get_torrent succeeded).
    """
    import transmission_rpc

    from personalscraper.api._contracts import ApiError

    client = _make_tx_client()
    client._client.get_torrent.return_value = _mock_torrent(["movies"])
    client._client.change_torrent.side_effect = transmission_rpc.TransmissionError("write failed")

    with pytest.raises(ApiError):
        client.add_tags("h", ["seed-pure"])


def test_qbit_add_tags_translates_api_error():
    """QBitClient.add_tags translates qbittorrentapi.APIError to ApiError.

    Regression test — before the fix, _client.torrents_addTags raising the
    library APIError escaped the client boundary unchanged.
    """
    import qbittorrentapi.exceptions

    from personalscraper.api._contracts import ApiError

    client = _make_qbit_client()
    client._client.torrents_addTags.side_effect = qbittorrentapi.exceptions.APIError("boom")

    with pytest.raises(ApiError):
        client.add_tags("h", ["seed-pure"])


def test_qbit_remove_tags_translates_api_error():
    """QBitClient.remove_tags translates qbittorrentapi.APIError to ApiError.

    Regression test — before the fix, _client.torrents_removeTags raising the
    library APIError escaped the client boundary unchanged.
    """
    import qbittorrentapi.exceptions

    from personalscraper.api._contracts import ApiError

    client = _make_qbit_client()
    client._client.torrents_removeTags.side_effect = qbittorrentapi.exceptions.APIError("boom")

    with pytest.raises(ApiError):
        client.remove_tags("h", ["seed-pure"])
