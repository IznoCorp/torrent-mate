"""A medium's wire identity parsed into a ``MediaRef``."""

from __future__ import annotations

import pytest

from personalscraper.app.errors import AppBadRequest, RefusalCode
from personalscraper.app.library.identity import Provider, parse_media_ref, ref_key
from personalscraper.core.identity import MediaRef


@pytest.mark.parametrize(
    ("provider", "provider_id", "expected"),
    [
        ("tvdb", "391101", MediaRef(tvdb_id=391101)),
        ("tmdb", "949", MediaRef(tmdb_id=949)),
        ("imdb", "tt0113277", MediaRef(imdb_id="tt0113277")),
    ],
)
def test_a_valid_pair(provider: str, provider_id: str, expected: MediaRef) -> None:
    """Each provider's id lands in its own field."""
    assert parse_media_ref(provider, provider_id) == expected


@pytest.mark.parametrize(
    ("provider", "provider_id", "field"),
    [
        ("trakt", "1", "provider"),
        ("tvdb", "abc", "providerId"),
        ("tmdb", "0", "providerId"),
        ("tmdb", "-3", "providerId"),
        ("imdb", "0113277", "providerId"),
    ],
)
def test_a_bad_pair_names_its_field(provider: str, provider_id: str, field: str) -> None:
    """An unknown provider or an id it cannot hold is ``request.invalid`` naming the field."""
    with pytest.raises(AppBadRequest) as refused:
        parse_media_ref(provider, provider_id)

    assert refused.value.code is RefusalCode.REQUEST_INVALID
    assert refused.value.params == {"fields": [field]}


def test_ref_key_reads_tvdb_first() -> None:
    """A reference is read at TVDB, then TMDB, then IMDb."""
    assert ref_key(MediaRef(tvdb_id=1, tmdb_id=2)) == (Provider.TVDB, "1")
    assert ref_key(MediaRef(tmdb_id=2, imdb_id="tt1")) == (Provider.TMDB, "2")
    assert ref_key(MediaRef(imdb_id="tt1")) == (Provider.IMDB, "tt1")
