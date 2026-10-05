"""The library routes: the listing, its categories, the recents, the incomplete shows, a membership and a deletion.

Each route makes ONE ``LibraryService`` call; these tests hold the wire: the bodies'
shapes, the query parameters' spelling, the statuses and ``Problem`` codes the contract
declares, the rights each operation asks, and the preprod ceiling refusing the deletion.
The facts themselves are proved in ``tests/unit/app/library``; here the service answers
fixed facts, save the deletion served end to end by the composed service over a fixture
index, its deletion authority reading the configured ``acquire.db``.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.store import build_acquire_store
from personalscraper.app.accounts.ceiling import InstanceCeiling
from personalscraper.app.accounts.rights import Right
from personalscraper.app.errors import AppConflict, AppNotFound, RefusalCode
from personalscraper.app.library.deletion import DeletionReport, MediaDeletion, PlexOutcome
from personalscraper.app.library.listing import LibrarySort
from personalscraper.app.library.service import (
    CategoryCount,
    IncompleteEntry,
    LibraryEntry,
    LibraryPage,
    LibraryService,
    Membership,
)
from personalscraper.conf.models.config import Config
from personalscraper.core.identity import MediaRef
from tests.unit.app.library.world import FixtureIndex

_FILM = LibraryEntry(
    title="Heat",
    year=1995,
    kind="movie",
    category_id="movies",
    overview="A thief and a detective.",
    ids={"tmdb": 949, "imdb": "tt0113277"},
    poster_url="https://image.tmdb.org/t/p/w342/heat.jpg",
)

_SHOW = LibraryEntry(
    title="Outer Range",
    year=None,
    kind="show",
    category_id="tv_shows",
    overview=None,
    ids={"tvdb": 404040},
    poster_url=None,
    local_poster=True,
)

_BARE = LibraryEntry(
    title="Friends",
    year=1994,
    kind="show",
    category_id="tv_shows",
    overview=None,
    ids={"tvdb": 79168},
    poster_url=None,
)

_READ = frozenset({Right.LIBRARY_READ})
_DELETE = frozenset({Right.LIBRARY_DELETE})


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts on a production instance: no ceiling from the environment.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.
    """
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Answer the service's six calls with fixed facts, recording each call.

    ``tmdb/404`` is an id no row holds, ``tmdb/409`` one two rows hold, ``tmdb/423`` one
    asked while the pipeline holds the library.

    Args:
        monkeypatch: Pytest's monkeypatch fixture.

    Returns:
        The ``(method, arguments)`` of every call, in order.
    """
    calls: list[tuple[str, Any]] = []

    def read_items(
        self: LibraryService,
        actor: object,
        *,
        category: Sequence[str] | None,
        sort: LibrarySort,
        reversed_: bool,
        query: str | None,
        page: int,
    ) -> LibraryPage:
        """One page holding the film and the show, the service's own refusal on a negative page."""
        calls.append(
            ("read_items", {"category": category, "sort": sort, "reversed": reversed_, "query": query, "page": page})
        )
        return LibraryPage(total=40, matching=2, loaded=38, items=(_FILM, _SHOW))

    def read_categories(self: LibraryService, actor: object) -> list[CategoryCount]:
        """Two leaves."""
        calls.append(("read_categories", None))
        return [CategoryCount("movies", 12), CategoryCount("tv_shows_animation", 3)]

    def read_recent(self: LibraryService, actor: object) -> list[LibraryEntry]:
        """The show, then the film."""
        calls.append(("read_recent", None))
        return [_SHOW, _FILM]

    def read_incomplete(self: LibraryService, actor: object) -> list[IncompleteEntry]:
        """One show missing two episodes."""
        calls.append(("read_incomplete", None))
        return [IncompleteEntry(entry=_BARE, owned=22, aired=24)]

    def read_membership(self: LibraryService, actor: object, ref: MediaRef) -> Membership:
        """The film held twice for TMDB 949, nothing for any other id."""
        calls.append(("read_membership", ref))
        if ref.tmdb_id == 949:
            return Membership(in_library=True, rows=2, incomplete=False, ids=_FILM.ids, kind="movie")
        return Membership(in_library=False, rows=0, incomplete=False, ids=None, kind=None)

    def delete_media(self: LibraryService, actor: object, refs: Sequence[MediaRef]) -> DeletionReport:
        """Every medium deleted, but the three refused ids."""
        calls.append(("delete_media", list(refs)))
        for ref in refs:
            params = {"provider": "tmdb", "providerId": str(ref.tmdb_id)}
            if ref.tmdb_id == 404:
                raise AppNotFound("No row holds the id.", code=RefusalCode.MEDIA_NOT_FOUND, params=params)
            if ref.tmdb_id == 409:
                raise AppConflict("Two rows hold the id.", code=RefusalCode.MEDIA_AMBIGUOUS, params=params)
            if ref.tmdb_id == 423:
                raise AppConflict("The pipeline holds the library.", code=RefusalCode.LIBRARY_LOCKED)
        done = tuple(
            MediaDeletion(
                ref=ref,
                folders_deleted=1,
                folders_vetoed=0,
                folders_failed=0,
                folders_unreachable=0,
                parents_removed=0,
                rows_removed=1,
                plex=PlexOutcome.NOT_CONFIGURED,
            )
            for ref in refs
        )
        return DeletionReport(deleted=len(done), media=done)

    for name, fake in (
        ("read_items", read_items),
        ("read_categories", read_categories),
        ("read_recent", read_recent),
        ("read_incomplete", read_incomplete),
        ("read_membership", read_membership),
        ("delete_media", delete_media),
    ):
        monkeypatch.setattr(LibraryService, name, fake)
    return calls


_FILM_ITEM = {
    "title": "Heat",
    "category": "movies",
    "overview": "A thief and a detective.",
    "ids": {"tmdb": 949, "imdb": "tt0113277"},
    "poster": "https://image.tmdb.org/t/p/w342/heat.jpg",
    "year": 1995,
    "kind": "movie",
}

_SHOW_ITEM = {
    "title": "Outer Range",
    "category": "tv_shows",
    "overview": None,
    "ids": {"tvdb": 404040},
    "poster": "/api/v1/media/tvdb/404040/poster",
    "year": None,
    "kind": "show",
}


class TestReadLibraryItems:
    """``GET /library/items``."""

    def test_one_page_with_its_three_counts(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """No parameter: the most recent first, page 0; the items and the three counts."""
        response = v1_client(rights=_READ).get("/library/items")

        assert response.status_code == 200
        assert response.json() == {"total": 40, "matching": 2, "loaded": 38, "items": [_FILM_ITEM, _SHOW_ITEM]}
        assert asked == [
            ("read_items", {"category": None, "sort": LibrarySort.RECENT, "reversed": False, "query": None, "page": 0})
        ]

    def test_the_query_parameters_reach_the_service(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """Repeated ``category``, ``sort``, ``reversed=1``, ``query`` and ``page``, spelled as in the contract."""
        response = v1_client(rights=_READ).get(
            "/library/items?category=movies_animation&category=tv_shows_animation&sort=missing&reversed=1"
            "&query=heat&page=2"
        )

        assert response.status_code == 200
        assert asked == [
            (
                "read_items",
                {
                    "category": ["movies_animation", "tv_shows_animation"],
                    "sort": LibrarySort.MISSING,
                    "reversed": True,
                    "query": "heat",
                    "page": 2,
                },
            )
        ]

    @pytest.mark.parametrize("query", ["page=abc", "sort=recent", "reversed=true"])
    def test_a_bad_parameter_is_a_bad_request(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]], query: str
    ) -> None:
        """A page that is no integer, a sort or a ``reversed`` outside the enum: 400 ``request.invalid``, no read."""
        response = v1_client(rights=_READ).get(f"/library/items?{query}")

        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert asked == []

    def test_a_negative_page_is_a_bad_request(self, v1_client: Callable[..., TestClient], test_config: Config) -> None:
        """The real service refuses a negative page: 400 ``request.invalid`` naming ``page``."""
        response = v1_client(rights=_READ).get("/library/items?page=-1")

        assert response.status_code == 400
        assert (response.json()["code"], response.json()["params"]) == ("request.invalid", {"fields": ["page"]})

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """No session: 401, no read."""
        assert v1_client(role=None).get("/library/items").status_code == 401
        assert asked == []

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing`` naming it, no read."""
        response = v1_client(rights=_DELETE).get("/library/items")

        assert response.status_code == 403
        assert (response.json()["code"], response.json()["params"]) == ("right.missing", {"rights": ["library.read"]})
        assert asked == []


class TestReadLibraryCategories:
    """``GET /library/categories``."""

    def test_the_leaves_and_their_counts(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """Each engine leaf with its count."""
        response = v1_client(rights=_READ).get("/library/categories")

        assert response.status_code == 200
        assert response.json() == [{"id": "movies", "count": 12}, {"id": "tv_shows_animation", "count": 3}]
        assert asked == [("read_categories", None)]

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """No session: 401."""
        assert v1_client(role=None).get("/library/categories").status_code == 401
        assert asked == []

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing``."""
        response = v1_client(rights=_DELETE).get("/library/categories")

        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"
        assert asked == []


class TestReadLibraryRecent:
    """``GET /library/recent``."""

    def test_the_recent_rows_carry_no_category_nor_overview(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """Each row: title, ids, poster, year and kind — a folder poster through the poster route."""
        response = v1_client(rights=_READ).get("/library/recent")

        assert response.status_code == 200
        assert response.json() == [
            {
                "title": "Outer Range",
                "ids": {"tvdb": 404040},
                "poster": "/api/v1/media/tvdb/404040/poster",
                "year": None,
                "kind": "show",
            },
            {
                "title": "Heat",
                "ids": {"tmdb": 949, "imdb": "tt0113277"},
                "poster": "https://image.tmdb.org/t/p/w342/heat.jpg",
                "year": 1995,
                "kind": "movie",
            },
        ]
        assert asked == [("read_recent", None)]

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """No session: 401."""
        assert v1_client(role=None).get("/library/recent").status_code == 401
        assert asked == []

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing``."""
        response = v1_client(rights=_DELETE).get("/library/recent")

        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"
        assert asked == []


class TestReadLibraryIncomplete:
    """``GET /library/incomplete``."""

    def test_each_show_with_its_held_and_aired_counts(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """A show: title, counts, year, ids, poster, its leaf category and ``kind`` show."""
        response = v1_client(rights=_READ).get("/library/incomplete")

        assert response.status_code == 200
        assert response.json() == [
            {
                "title": "Friends",
                "owned": 22,
                "aired": 24,
                "year": 1994,
                "ids": {"tvdb": 79168},
                "poster": None,
                "category": "tv_shows",
                "kind": "show",
            }
        ]
        assert asked == [("read_incomplete", None)]

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """No session: 401."""
        assert v1_client(role=None).get("/library/incomplete").status_code == 401
        assert asked == []

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing``."""
        response = v1_client(rights=_DELETE).get("/library/incomplete")

        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"
        assert asked == []


class TestReadLibraryMembership:
    """``GET /library/membership``."""

    def test_a_held_medium(self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]) -> None:
        """Held by two rows: in the library, a duplicate, its ids and kind."""
        response = v1_client(rights=_READ).get("/library/membership?provider=tmdb&providerId=949")

        assert response.status_code == 200
        assert response.json() == {
            "inLibrary": True,
            "rows": 2,
            "incomplete": False,
            "ids": {"tmdb": 949, "imdb": "tt0113277"},
            "kind": "movie",
        }
        assert asked == [("read_membership", MediaRef(tmdb_id=949))]

    def test_a_medium_not_held(self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]) -> None:
        """Not held: no rows, null ids and kind."""
        response = v1_client(rights=_READ).get("/library/membership?provider=tvdb&providerId=1")

        assert response.status_code == 200
        assert response.json() == {"inLibrary": False, "rows": 0, "incomplete": False, "ids": None, "kind": None}
        assert asked == [("read_membership", MediaRef(tvdb_id=1))]

    @pytest.mark.parametrize(
        "query", ["provider=tmdb&providerId=abc", "provider=plex&providerId=1", "provider=tmdb", "providerId=1"]
    )
    def test_a_bad_identity_is_a_bad_request(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]], query: str
    ) -> None:
        """A malformed id, a provider outside the enum, or either half missing: 400 ``request.invalid``, no read."""
        response = v1_client(rights=_READ).get(f"/library/membership?{query}")

        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert asked == []

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """No session: 401."""
        assert v1_client(role=None).get("/library/membership?provider=tmdb&providerId=949").status_code == 401
        assert asked == []

    def test_without_library_read_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """A role without ``library.read``: 403 ``right.missing``."""
        response = v1_client(rights=_DELETE).get("/library/membership?provider=tmdb&providerId=949")

        assert response.status_code == 403
        assert response.json()["code"] == "right.missing"
        assert asked == []


def _delete(client: TestClient, media: list[dict[str, str]]) -> Any:
    """Send ``deleteLibraryItems`` with a body (``TestClient.delete`` takes none).

    Args:
        client: The client.
        media: The body's ``media``.

    Returns:
        The response.
    """
    return client.request("DELETE", "/library/items", json={"media": media})


class TestDeleteLibraryItems:
    """``DELETE /library/items``."""

    def test_the_deleted_count(self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]) -> None:
        """Two media named by their ids: both parsed, one service call, the count of what went."""
        response = _delete(
            v1_client(rights=_DELETE),
            [{"provider": "tmdb", "providerId": "949"}, {"provider": "tvdb", "providerId": "79168"}],
        )

        assert response.status_code == 200
        assert response.json() == {"deleted": 2}
        assert asked == [("delete_media", [MediaRef(tmdb_id=949), MediaRef(tvdb_id=79168)])]

    @pytest.mark.parametrize(
        ("provider_id", "status", "code"),
        [("404", 404, "media.not_found"), ("409", 409, "media.ambiguous"), ("423", 409, "library.locked")],
    )
    def test_a_refusal_is_answered_as_a_problem(
        self,
        v1_client: Callable[..., TestClient],
        asked: list[tuple[str, Any]],
        provider_id: str,
        status: int,
        code: str,
    ) -> None:
        """An id no row holds, an id two rows hold, the pipeline's lock: the contract's status and code."""
        response = _delete(v1_client(rights=_DELETE), [{"provider": "tmdb", "providerId": provider_id}])

        assert response.status_code == status
        assert response.json()["code"] == code
        assert response.json()["status"] == status

    @pytest.mark.parametrize(
        "body",
        [
            {"media": []},
            {},
            {"media": [{"provider": "tmdb", "providerId": "abc"}]},
            {"media": [{"provider": "plex", "providerId": "1"}]},
            {"titles": ["Heat"]},
        ],
    )
    def test_a_bad_body_is_a_bad_request(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]], body: dict[str, Any]
    ) -> None:
        """No medium, a malformed id, a provider outside the enum, an unknown field: 400, nothing deleted."""
        response = v1_client(rights=_DELETE).request("DELETE", "/library/items", json=body)

        assert response.status_code == 400
        assert response.json()["code"] == "request.invalid"
        assert asked == []

    def test_no_session_is_unauthenticated(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """No session: 401, nothing deleted."""
        assert _delete(v1_client(role=None), [{"provider": "tmdb", "providerId": "949"}]).status_code == 401
        assert asked == []

    def test_without_library_delete_it_is_forbidden(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """A role with ``library.read`` alone: 403 ``right.missing`` naming ``library.delete``, nothing deleted."""
        response = _delete(v1_client(rights=_READ), [{"provider": "tmdb", "providerId": "949"}])

        assert response.status_code == 403
        assert (response.json()["code"], response.json()["params"]) == ("right.missing", {"rights": ["library.delete"]})
        assert asked == []

    def test_the_preprod_ceiling_refuses_it_even_to_an_admin(
        self, v1_client: Callable[..., TestClient], asked: list[tuple[str, Any]]
    ) -> None:
        """Preprod forbids ``library.delete``: 403, the Admin's ask too, nothing deleted."""
        ceiling = InstanceCeiling(forbidden=frozenset({Right.LIBRARY_DELETE}), read_only=False)

        response = _delete(v1_client(role="admin", ceiling=ceiling), [{"provider": "tmdb", "providerId": "949"}])

        assert response.status_code == 403
        assert response.json()["code"] == "instance.forbidden_write"
        assert asked == []


class TestDeleteLibraryItemsEndToEnd:
    """``DELETE /library/items`` through the composed service: its deletion authority reads ``acquire.db``."""

    @pytest.fixture
    def folder(self, test_config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """One film held in the fixture index, its folder on a faked mounted disk.

        Args:
            test_config: The synthetic config; its ``library.db`` is the fixture index.
            tmp_path: Pytest's temporary directory.
            monkeypatch: Pytest's patcher, faking the mount points.

        Returns:
            The film's folder.
        """
        root = tmp_path / "Disk1" / "medias"
        mounts = {root.parent.resolve(), Path("/")}
        monkeypatch.setattr(os.path, "ismount", lambda path: Path(path) in mounts)
        library_db = Path(test_config.indexer.db_path)
        library_db.parent.mkdir(parents=True, exist_ok=True)
        index = FixtureIndex(library_db)
        index.mount(1, root)
        movie = index.item("Heat", tmdb="949")
        index.movie_file(movie, "films/Heat (1995)")
        index.conn.close()
        folder = root / "films" / "Heat (1995)"
        folder.mkdir(parents=True)
        (folder / "movie.mkv").write_bytes(b"x")
        return folder

    def test_a_medium_no_tracker_is_owed_goes(self, v1_client: Callable[..., TestClient], folder: Path) -> None:
        """No seed obligation: the folder goes, one medium deleted."""
        response = _delete(v1_client(role="admin"), [{"provider": "tmdb", "providerId": "949"}])

        assert response.status_code == 200
        assert response.json() == {"deleted": 1}
        assert not folder.exists()

    def test_a_medium_still_owed_to_a_tracker_is_kept(
        self, v1_client: Callable[..., TestClient], test_config: Config, folder: Path
    ) -> None:
        """An unmet seed obligation on the folder: the deletion authority keeps it, nothing deleted."""
        store = build_acquire_store(test_config.acquire)
        try:
            store.seed.add(
                SeedObligation(
                    info_hash="obligation-one",
                    source_tracker="tracker-one",
                    min_seed_time_s=86_400,
                    min_ratio=1.0,
                    added_at=int(time.time()),
                    dispatched_path=str(folder / "movie.mkv"),
                )
            )
        finally:
            store.close()

        response = _delete(v1_client(role="admin"), [{"provider": "tmdb", "providerId": "949"}])

        assert response.status_code == 200
        assert response.json() == {"deleted": 0}
        assert (folder / "movie.mkv").is_file()
