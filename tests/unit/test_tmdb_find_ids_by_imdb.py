"""``TMDBClient.find_ids_by_imdb``: the TMDB ids an IMDb id numbers, one per kind."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata.tmdb import TMDBClient


@pytest.fixture
def transport() -> MagicMock:
    """A MagicMock standing in for the HTTP transport.

    Returns:
        The mock.
    """
    return MagicMock()


@pytest.fixture
def client(transport: MagicMock) -> TMDBClient:
    """A client bound to the mocked transport (no real HTTP).

    Args:
        transport: The mocked transport.

    Returns:
        The client.
    """
    return TMDBClient(transport=transport, language="fr-FR")


def test_a_film_resolves_to_its_movie_id(client: TMDBClient, transport: MagicMock) -> None:
    """A movie hit is the ``movie`` entry, and the find endpoint is asked by external source."""
    transport.get.return_value = {"movie_results": [{"id": 550}, {"id": 551}], "tv_results": []}

    assert client.find_ids_by_imdb("tt0137523") == {"movie": 550}
    transport.get.assert_called_once_with("/find/tt0137523", params={"external_source": "imdb_id"})


def test_a_show_resolves_to_its_tv_id(client: TMDBClient, transport: MagicMock) -> None:
    """A TV hit is the ``tv`` entry."""
    transport.get.return_value = {"movie_results": [], "tv_results": [{"id": 1396}]}

    assert client.find_ids_by_imdb("tt0903747") == {"tv": 1396}


def test_an_id_naming_both_kinds_resolves_to_both(client: TMDBClient, transport: MagicMock) -> None:
    """The two result lists are both read: the id names one title, which TMDB may file twice."""
    transport.get.return_value = {"movie_results": [{"id": 1}], "tv_results": [{"id": 2}]}

    assert client.find_ids_by_imdb("tt1") == {"movie": 1, "tv": 2}


def test_an_id_matching_neither_resolves_to_nothing(client: TMDBClient, transport: MagicMock) -> None:
    """A person, an episode or nothing is no medium."""
    transport.get.return_value = {"movie_results": [], "person_results": [{"id": 9}]}

    assert client.find_ids_by_imdb("tt0000001") == {}


def test_a_result_with_no_numeric_id_is_left_out(client: TMDBClient, transport: MagicMock) -> None:
    """A malformed hit never becomes an id."""
    transport.get.return_value = {"movie_results": [{"id": "550"}], "tv_results": [{"name": "x"}]}

    assert client.find_ids_by_imdb("tt1") == {}


def test_a_non_object_answer_is_a_type_error(client: TMDBClient, transport: MagicMock) -> None:
    """The transport guard of the other reads holds here."""
    transport.get.return_value = ["not", "an", "object"]

    with pytest.raises(TypeError):
        client.find_ids_by_imdb("tt1")
