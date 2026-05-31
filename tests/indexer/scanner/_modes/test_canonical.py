import pytest

from personalscraper.indexer.scanner._modes._canonical import derive_canonical_provider


@pytest.mark.parametrize(
    "kind,tvdb_id,tmdb_id,nfo_default,expected",
    [
        # show with tvdb_id → tvdb wins regardless of NFO default
        ("show", "12345", "67890", "tmdb", "tvdb"),
        ("show", "12345", None, None, "tvdb"),
        # show without tvdb_id → tmdb if available
        ("show", None, "67890", "tmdb", "tmdb"),
        # movie with tmdb_id → tmdb wins
        ("movie", None, "99", "tvdb", "tmdb"),
        ("movie", None, "99", None, "tmdb"),
        # no IDs → None
        ("movie", None, None, None, None),
        ("show", None, None, "tvdb", None),
    ],
)
def test_derive_canonical_provider(
    kind: str,
    tvdb_id: str | None,
    tmdb_id: str | None,
    nfo_default: str | None,
    expected: str | None,
) -> None:
    """Kind-deterministic canonical provider derivation for all ID combinations."""
    result = derive_canonical_provider(kind, tvdb_id, tmdb_id, nfo_default)
    assert result == expected


def test_kind_beats_nfo_xml_order() -> None:
    """kind-deterministic rule beats NFO-declared default — the critical invariant."""
    # show: tvdb_id present → tvdb, even if NFO says tmdb is default
    assert derive_canonical_provider("show", tvdb_id="111", tmdb_id="222", nfo_default="tmdb") == "tvdb"
    # movie: tmdb_id present → tmdb, even if NFO says tvdb is default
    assert derive_canonical_provider("movie", tvdb_id=None, tmdb_id="333", nfo_default="tvdb") == "tmdb"
