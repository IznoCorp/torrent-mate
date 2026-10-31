"""The media routes: a medium's sheet, its seasons and its rescrape, by provider identity.

Each route parses the identity and makes ONE library service call; these tests hold
the wire: the bodies' shapes (the film sheet without its show-only block), the statuses
and ``Problem`` codes the contract declares, the rights each operation asks, and the
read-only clone refusing the rescrape. The facts themselves are proved in
``tests/unit/app/library``; here the service answers fixed facts, save one poster read
served end to end by the real service over a fixture index.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import WRITE_RIGHTS, Right
from personalscraper.app.errors import AppUnavailable, RefusalCode
from personalscraper.app.library.facts import (
    CastFact,
    EpisodeFact,
    GenreId,
    MediaSheetFacts,
    MediaStatus,
    SeasonSummaryFact,
    refuse_not_found,
)
from personalscraper.app.library.identity import Provider
from personalscraper.app.library.reads import LibraryReads, SeasonFacts, SeasonsFacts
from personalscraper.app.library.rescrape import LibraryRescrape, RescrapeAccepted
from personalscraper.app.library.sheets import LocalPoster, MediaSheets
from personalscraper.conf.models.config import Config
from personalscraper.core.identity import MediaRef
from tests.http_v1.test_deprecations import _client as v0_client
from tests.unit.app.library.world import FixtureIndex

_FILM = MediaSheetFacts(
    title="Heat",
    kind="movie",
    year=1995,
    rating=7.9,
    genres=(GenreId.CRIME, GenreId.THRILLER),
    runtime=170,
    overview="A thief and a detective.",
    director="Michael Mann",
    creator=None,
    cast=(CastFact(name="Al Pacino", role="Vincent Hanna"),),
    cast_portraits={"Al Pacino": "https://image.tmdb.org/t/p/w185/pacino.jpg"},
    trailer_key="abc123XYZ",
    trailer_name="Heat — bande-annonce",  # french-ok: a trailer title, provider data
    trailer_language="fr",
    ids={"tmdb": 949, "imdb": "tt0113277"},
    status=MediaStatus.RELEASED,
    owned=True,
    episodes=None,
    seasons=None,
    tmdb_television_id=None,
    poster_url="https://image.tmdb.org/t/p/w342/heat.jpg",
    local_poster=False,
    poster_high_definition_url="https://image.tmdb.org/t/p/original/heat.jpg",
    hero_url="https://image.tmdb.org/t/p/original/heat-wide.jpg",
    metadata_refreshed_at=date(2026, 10, 1),
)

_SHOW = MediaSheetFacts(
    title="Friends",
    kind="show",
    year=1994,
    rating=None,
    genres=(),
    runtime=None,
    overview=None,
    director=None,
    creator="David Crane",
    cast=(),
    cast_portraits={},
    trailer_key=None,
    trailer_name=None,
    trailer_language=None,
    ids={"tvdb": 79168, "tmdb": 1668},
    status=MediaStatus.ENDED,
    owned=False,
    episodes={1: (EpisodeFact(1, "The Pilot", date(1994, 9, 22)), EpisodeFact(2, None, None))},
    seasons=(SeasonSummaryFact(number=1, episodes=24, air_date=date(1994, 9, 22)),),
    tmdb_television_id="1668",
    poster_url=None,
    local_poster=False,
    poster_high_definition_url=None,
    hero_url=None,
    metadata_refreshed_at=None,
)

_SEASONS = SeasonsFacts(
    seasons=(
        SeasonFacts(number=1, episodes=24, air_date=date(1994, 9, 22), off_catalogue=()),
        SeasonFacts(number=2, episodes=None, air_date=None, off_catalogue=(25,)),
    ),
    owned={1: (1, 2), 2: (25,)},
    aired={1: 24, 2: None},
)

_READ = frozenset({Right.LIBRARY_READ})
_RESCRAPE = frozenset({Right.LIBRARY_RESCRAPE})


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts on a production instance: no ceiling from the environment.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "prod")


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, MediaRef]]:
    """Answer the service's three calls with fixed facts, recording each call.

    ``tmdb/404`` is an id no provider knows, ``tmdb/503`` one whose provider does not answer.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.

    Returns:
        The ``(method, ref)`` of every call, in order.
    """
    calls: list[tuple[str, MediaRef]] = []

    def refuse(ref: MediaRef) -> None:
        """Raise the refusal the id stands for."""
        if ref.tmdb_id == 404:
            raise refuse_not_found("tmdb")
        if ref.tmdb_id == 503:
            raise AppUnavailable(
                "A metadata provider did not answer.",
                code=RefusalCode.PROVIDER_UNAVAILABLE,
                params={"provider": "tmdb"},
            )

    def read_sheet(self: MediaSheets, actor: object, ref: MediaRef) -> MediaSheetFacts:
        """The film for a TMDB id, the show for a TVDB id."""
        calls.append(("read_sheet", ref))
        refuse(ref)
        return _SHOW if ref.tvdb_id is not None else _FILM

    def read_seasons(self: LibraryReads, actor: object, ref: MediaRef) -> SeasonsFacts:
        """The show's seasons."""
        calls.append(("read_seasons", ref))
        refuse(ref)
        return _SEASONS

    def request_rescrape(self: LibraryRescrape, actor: object, ref: MediaRef) -> RescrapeAccepted:
        """An accepted rescrape, queued."""
        calls.append(("request_rescrape", ref))
        refuse(ref)
        return RescrapeAccepted(provider=Provider.TMDB, provider_id="949", queued=True, run_uid="run-1")

    monkeypatch.setattr(MediaSheets, "read_sheet", read_sheet)
    monkeypatch.setattr(LibraryReads, "read_seasons", read_seasons)
    monkeypatch.setattr(LibraryRescrape, "request_rescrape", request_rescrape)
    return calls


class TestReadMediaSheet:
    """``GET /media/{provider}/{providerId}``."""

    def test_a_film_sheet_carries_no_show_block(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """A film's sheet: every required property, no episodes, seasons or TMDB television id."""
        response = v1_client(rights=_READ).get("/media/tmdb/949")

        assert response.status_code == 200
        assert response.json() == {
            "title": "Heat",
            "kind": "movie",
            "year": 1995,
            "rating": 7.9,
            "genres": ["crime", "thriller"],
            "runtime": 170,
            "overview": "A thief and a detective.",
            "director": "Michael Mann",
            "creator": None,
            "cast": [{"name": "Al Pacino", "role": "Vincent Hanna"}],
            "castPortraits": {"Al Pacino": "https://image.tmdb.org/t/p/w185/pacino.jpg"},
            "trailer": "Heat — bande-annonce",  # french-ok: a trailer title, provider data
            "trailerVideo": {
                "key": "abc123XYZ",
                "name": "Heat — bande-annonce",  # french-ok: a trailer title, provider data
                "language": "fr",
            },
            "ids": {"tmdb": 949, "imdb": "tt0113277"},
            "status": "released",
            "owned": True,
            "poster": "https://image.tmdb.org/t/p/w342/heat.jpg",
            "posterHighDefinition": "https://image.tmdb.org/t/p/original/heat.jpg",
            "hero": "https://image.tmdb.org/t/p/original/heat-wide.jpg",
            "metadataRefreshedAt": "2026-10-01",
        }
        assert asked == [("read_sheet", MediaRef(tmdb_id=949))]

    def test_a_show_sheet_carries_its_episodes_and_seasons(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """A show's sheet: episodes keyed by season, the provider's seasons, its TMDB television id."""
        response = v1_client(rights=_READ).get("/media/tvdb/79168")

        assert response.status_code == 200
        body = response.json()
        assert body["episodes"] == {
            "1": [
                {"number": 1, "title": "The Pilot", "airDate": "1994-09-22"},
                {"number": 2, "title": None, "airDate": None},
            ]
        }
        assert body["seasons"] == [{"number": 1, "episodes": 24, "airDate": "1994-09-22"}]
        assert body["tmdbTelevisionId"] == "1668"
        assert body["creator"] == "David Crane"
        assert body["trailer"] is None
        assert body["trailerVideo"] is None
        assert body["castPortraits"] == {}
        assert body["metadataRefreshedAt"] is None
        assert asked == [("read_sheet", MediaRef(tvdb_id=79168))]

    def test_a_trailer_without_its_language_is_no_trailer_object(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A key and a name without a language cannot fill the contract's ``Trailer``: null, the title stays."""
        unlanguaged = dataclasses.replace(_FILM, trailer_language=None)
        monkeypatch.setattr(MediaSheets, "read_sheet", lambda self, actor, ref: unlanguaged)

        body = v1_client(rights=_READ).get("/media/tmdb/949").json()

        assert body["trailerVideo"] is None
        assert body["trailer"] == "Heat — bande-annonce"  # french-ok: a trailer title, provider data

    def test_an_unknown_id_is_not_found(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """The provider does not know the id: 404 ``media.not_found``."""
        response = v1_client(rights=_READ).get("/media/tmdb/404")

        assert response.status_code == 404
        assert response.json()["code"] == "media.not_found"

    def test_a_silent_provider_is_unavailable(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """The provider does not answer: 503 ``provider.unavailable``."""
        response = v1_client(rights=_READ).get("/media/tmdb/503")

        assert response.status_code == 503
        assert response.json()["code"] == "provider.unavailable"

    def test_a_malformed_id_is_a_bad_request(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """A TMDB id that is not a positive integer: 400 ``request.invalid``, the service never asked."""
        response = v1_client(rights=_READ).get("/media/tmdb/abc")

        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert asked == []

    def test_an_unknown_provider_is_a_bad_request(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """A provider outside the contract's enum: 400 ``request.invalid``, the service never asked."""
        response = v1_client(rights=_READ).get("/media/plex/949")

        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert asked == []

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """No session: 401."""
        assert v1_client(role=None).get("/media/tmdb/949").status_code == 401
        assert asked == []

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing`` naming it, the service never asked."""
        response = v1_client(rights=_RESCRAPE).get("/media/tmdb/949")

        assert response.status_code == 403
        assert (response.json()["code"], response.json()["params"]) == ("right.missing", {"rights": ["library.read"]})
        assert asked == []

    def test_a_folder_poster_is_served_by_the_poster_route(
        self, v1_client: Callable[..., TestClient], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No provider poster, one in the library folder: ``poster`` is the v1 poster route of that identity."""
        local = dataclasses.replace(_SHOW, owned=True, local_poster=True)
        monkeypatch.setattr(MediaSheets, "read_sheet", lambda self, actor, ref: local)

        body = v1_client(rights=_READ).get("/media/tvdb/79168").json()

        assert body["poster"] == "/api/v1/media/tvdb/79168/poster"
        assert body["posterHighDefinition"] is None

    def test_no_poster_anywhere_is_null(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """No provider poster and none in the folder: ``poster`` stays null."""
        assert v1_client(rights=_READ).get("/media/tvdb/79168").json()["poster"] is None


class TestReadMediaPoster:
    """``GET /media/{provider}/{providerId}/poster``."""

    @pytest.fixture
    def posters(self, monkeypatch: pytest.MonkeyPatch) -> list[MediaRef]:
        """Answer the service's poster read: a PNG for ``tvdb/79168``, ``media.not_found`` otherwise.

        Args:
            monkeypatch: Pytest's monkeypatch fixture.

        Returns:
            The ref of every call, in order.
        """
        calls: list[MediaRef] = []

        def read_local_poster(self: MediaSheets, actor: object, ref: MediaRef) -> LocalPoster:
            """The folder's PNG for the held show, a refusal for anything else."""
            calls.append(ref)
            if ref.tvdb_id != 79168:
                raise refuse_not_found("tvdb")
            return LocalPoster(content=b"\x89PNG\r\n\x1a\nposter", media_type="image/png")

        monkeypatch.setattr(MediaSheets, "read_local_poster", read_local_poster)
        return calls

    def test_the_folder_poster_is_answered_with_its_media_type(
        self, v1_client: Callable[..., TestClient], posters: list[MediaRef]
    ) -> None:
        """200: the file's bytes, under its media type."""
        response = v1_client(rights=_READ).get("/media/tvdb/79168/poster")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == b"\x89PNG\r\n\x1a\nposter"
        assert posters == [MediaRef(tvdb_id=79168)]

    def test_the_library_folder_poster_is_served_end_to_end(
        self, v1_client: Callable[..., TestClient], test_config: Config, tmp_path: Path
    ) -> None:
        """The real service over a fixture index: the folder's ``poster.png``, its bytes under ``image/png``."""
        library_db = Path(test_config.indexer.db_path)
        library_db.parent.mkdir(parents=True, exist_ok=True)
        index = FixtureIndex(library_db)
        index.mount(1, tmp_path / "disk1")
        movie = index.item("Heat", tmdb="949", poster_url=None, poster_file=True)
        index.movie_file(movie, "films/Heat (1995)")
        folder = tmp_path / "disk1" / "films" / "Heat (1995)"
        folder.mkdir(parents=True)
        (folder / "poster.png").write_bytes(b"\x89PNG\r\n\x1a\nposter")
        index.conn.close()

        response = v1_client(rights=_READ).get("/media/tmdb/949/poster")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == b"\x89PNG\r\n\x1a\nposter"

    def test_no_poster_is_not_found(self, v1_client: Callable[..., TestClient], posters: list[MediaRef]) -> None:
        """No medium, no mounted folder or no poster in it: 404 ``media.not_found``."""
        response = v1_client(rights=_READ).get("/media/tvdb/1/poster")

        assert response.status_code == 404
        assert response.json()["code"] == "media.not_found"

    def test_a_malformed_id_is_a_bad_request(
        self, v1_client: Callable[..., TestClient], posters: list[MediaRef]
    ) -> None:
        """A TVDB id that is not a positive integer: 400 ``request.invalid``, no disk read."""
        response = v1_client(rights=_READ).get("/media/tvdb/abc/poster")

        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert posters == []

    def test_no_session_is_unauthenticated(self, v1_client: Callable[..., TestClient], posters: list[MediaRef]) -> None:
        """No session: the perimeter's 401, no disk read."""
        response = v1_client(role=None).get("/media/tvdb/79168/poster")

        assert response.status_code == 401
        assert response.json()["code"] == "auth.required"
        assert posters == []

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], posters: list[MediaRef]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing`` naming it, no disk read."""
        response = v1_client(rights=_RESCRAPE).get("/media/tvdb/79168/poster")

        assert response.status_code == 403
        assert (response.json()["code"], response.json()["params"]) == ("right.missing", {"rights": ["library.read"]})
        assert posters == []


class TestReadMediaSeasons:
    """``GET /media/{provider}/{providerId}/seasons``."""

    def test_the_seasons_and_the_holdings(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """Each season with its count, first air date and off-catalogue episodes; owned and aired by season."""
        response = v1_client(rights=_READ).get("/media/tvdb/79168/seasons")

        assert response.status_code == 200
        assert response.json() == {
            "seasons": [
                {"number": 1, "episodes": 24, "airDate": "1994-09-22", "offCatalogue": []},
                {"number": 2, "episodes": None, "airDate": None, "offCatalogue": [25]},
            ],
            "owned": {"1": [1, 2], "2": [25]},
            "aired": {"1": 24, "2": None},
        }
        assert asked == [("read_seasons", MediaRef(tvdb_id=79168))]

    def test_an_unknown_id_is_not_found(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """The provider does not know the id: 404 ``media.not_found``."""
        response = v1_client(rights=_READ).get("/media/tmdb/404/seasons")

        assert response.status_code == 404
        assert response.json()["code"] == "media.not_found"

    def test_a_silent_provider_is_unavailable(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """The provider does not answer: 503 ``provider.unavailable``."""
        response = v1_client(rights=_READ).get("/media/tmdb/503/seasons")

        assert response.status_code == 503
        assert response.json()["code"] == "provider.unavailable"

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """No session: 401."""
        assert v1_client(role=None).get("/media/tvdb/79168/seasons").status_code == 401

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing`` naming it, the service never asked."""
        response = v1_client(rights=_RESCRAPE).get("/media/tvdb/79168/seasons")

        assert response.status_code == 403
        assert (response.json()["code"], response.json()["params"]) == ("right.missing", {"rights": ["library.read"]})
        assert asked == []


class TestRescrapeMedia:
    """``POST /media/{provider}/{providerId}/rescrape``."""

    def test_an_accepted_rescrape_is_202(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """The ask is accepted: 202 with the medium echoed, its queue state and its run."""
        response = v1_client(rights=_RESCRAPE).post("/media/tmdb/949/rescrape")

        assert response.status_code == 202
        assert response.json() == {"provider": "tmdb", "providerId": "949", "queued": True, "runUid": "run-1"}
        assert asked == [("request_rescrape", MediaRef(tmdb_id=949))]

    def test_an_id_no_row_holds_is_not_found(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """No library row holds the id: 404 ``media.not_found``."""
        response = v1_client(rights=_RESCRAPE).post("/media/tmdb/404/rescrape")

        assert response.status_code == 404
        assert response.json()["code"] == "media.not_found"

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """No session: 401."""
        assert v1_client(role=None).post("/media/tmdb/949/rescrape").status_code == 401
        assert asked == []

    def test_without_library_rescrape_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """A role with ``library.read`` alone: 403 ``right.missing`` naming ``library.rescrape``, nothing launched."""
        response = v1_client(rights=_READ).post("/media/tmdb/949/rescrape")

        assert response.status_code == 403
        assert (response.json()["code"], response.json()["params"]) == (
            "right.missing",
            {"rights": ["library.rescrape"]},
        )
        assert asked == []

    def test_the_read_only_clone_refuses_it_even_to_an_admin(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, MediaRef]]
    ) -> None:
        """Under the read-only ceiling every write is refused, the Admin's too: 403 ``instance.forbidden_write``."""
        ceiling = InstanceCeiling(forbidden=WRITE_RIGHTS, read_only=True)

        response = v1_client(role="admin", ceiling=ceiling).post("/media/tmdb/949/rescrape")

        assert response.status_code == 403
        assert response.json()["code"] == "instance.forbidden_write"
        assert response.json()["params"]["right"] == "library.rescrape"
        assert asked == []


class TestLibraryUnavailable:
    """Every media operation over a ``library.db`` that cannot be opened: 503 ``library.unavailable``.

    Operator bugs B-697, B-698, B-699 (the Kyma and Silo sheets): the dev server's index was absent and each
    read crashed into a 500 the sheet printed in English. The composed service reads the
    configured index; absent or corrupt, each operation answers the typed refusal the
    interface words.
    """

    @pytest.fixture(params=["absent", "corrupt"])
    def unreadable_index(self, request: pytest.FixtureRequest, test_config: Config) -> Path:
        """The configured ``library.db``: absent, or a file of corrupt bytes.

        Args:
            request: Pytest's request, naming the case.
            test_config: The synthetic config.

        Returns:
            The index's path.
        """
        library_db = Path(test_config.indexer.db_path)
        if request.param == "corrupt":
            library_db.parent.mkdir(parents=True, exist_ok=True)
            library_db.write_bytes(b"not a database, corrupt bytes" * 64)
        else:
            assert not library_db.exists()
        return library_db

    @pytest.mark.parametrize(
        ("method", "path", "rights"),
        [
            ("GET", "/media/tvdb/403245", _READ),
            ("GET", "/media/tmdb/1365362", _READ),
            ("GET", "/media/tvdb/403245/seasons", _READ),
            ("GET", "/media/tvdb/403245/poster", _READ),
            ("POST", "/media/tvdb/403245/rescrape", _RESCRAPE),
        ],
    )
    def test_the_operation_is_refused_unavailable(
        self,
        v1_client: Callable[..., TestClient],
        unreadable_index: Path,
        method: str,
        path: str,
        rights: frozenset[Right],
    ) -> None:
        """503 ``library.unavailable``, never the 500 ``internal``, no word of the failure on the wire."""
        response = v1_client(rights=rights).request(method, path)

        assert response.status_code == 503
        assert response.json()["code"] == "library.unavailable"
        assert response.json()["status"] == 503
        assert "sqlite" not in response.text.lower()
        assert str(unreadable_index) not in response.text


def _silent_provider() -> MagicMock:
    """A v0 provider client that never answers: the v0 sheet degrades, no network is reached.

    Returns:
        The fake client.
    """
    client = MagicMock()
    client.get_movie.side_effect = RuntimeError("no provider")
    client.get_tv.side_effect = RuntimeError("no provider")
    return client


def test_the_v0_sheet_names_its_concrete_v1_successor(test_config: Config) -> None:
    """v1 mounted: the v0 sheet says it is deprecated and links the v1 sheet of the SAME medium."""
    with (
        patch("personalscraper.web.routes.media._build_tmdb_client", return_value=_silent_provider()),
        patch("personalscraper.web.routes.media._build_ownership_block", return_value=None),
    ):
        response = v0_client(test_config, v1_enabled=True).get("/api/media/tmdb/603")

    assert "deprecation" in response.headers
    assert response.headers["link"] == '</api/v1/media/tmdb/603>; rel="successor-version"'
