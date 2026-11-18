"""Rescrape by medium: one medium, named by a provider id, asked through the run queue."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from personalscraper.app.errors import AppNotFound, AppPreconditionRequired, RefusalCode
from personalscraper.app.library.identity import Provider
from personalscraper.app.library.rescrape import RescrapeAccepted
from personalscraper.app.maintenance import service as maintenance_service
from personalscraper.app.maintenance.registry import REGISTRY, canonical_options_json
from personalscraper.app.supervisor.model import RequestState, RunKind
from personalscraper.core.identity import MediaRef
from tests.unit.app.library.world import World

_RUNNER_PID = 4242


@pytest.fixture(autouse=True)
def no_process(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, ...]]:
    """Forbid every process spawn: a rescrape is asked, never started by the asker.

    Args:
        monkeypatch: Pytest's monkeypatch.

    Returns:
        The spawns attempted (the tests assert it stays empty).
    """
    calls: list[tuple[object, ...]] = []

    def refuse(*args: object, **kwargs: object) -> None:
        """Record the attempt and fail it."""
        calls.append(args)
        raise AssertionError("a rescrape request must not spawn a process")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    return calls


def _asked(world: World) -> list[tuple[int, RequestState, str]]:
    """Read the queue: every rescrape request, oldest first.

    Args:
        world: The test world.

    Returns:
        ``(item_id, state, uid)`` per request.
    """
    view = world.runs.queue_view()
    requests = [*([view.running] if view.running else []), *view.queued]
    return [(r.options.item_id, r.state, r.uid) for r in requests if r.kind is RunKind.RESCRAPE]


def _runs(index_path: Path) -> list[tuple[str, str]]:
    """Read the maintenance runs reserved in ``library.db``.

    Args:
        index_path: ``library.db``.

    Returns:
        ``(run_uid, command)`` per row.
    """
    with sqlite3.connect(index_path) as conn:
        return conn.execute("SELECT run_uid, command FROM pipeline_run WHERE kind='maintenance'").fetchall()


def test_a_held_movie_is_queued_for_rescrape(world: World, no_process: list[tuple[object, ...]]) -> None:
    """One request is queued for the holding row; nothing is spawned nor reserved in ``library.db``."""
    movie = world.index.item("Heat", tmdb="949", imdb="tt0113277")
    world.index.movie_file(movie, "films/Heat")

    accepted = world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=949))

    assert (accepted.provider, accepted.provider_id, accepted.queued) == (Provider.TMDB, "949", True)
    assert _asked(world) == [(movie, RequestState.QUEUED, accepted.run_uid)]
    assert no_process == []
    assert _runs(world.index.path) == []


def test_a_show_is_rescraped_by_its_tvdb_id(world: World) -> None:
    """A show is addressed by its TVDB id and answered under it."""
    show = world.index.item("Holes", kind="show", tvdb="81189", tmdb="1396")
    world.index.episodes(show, 1, [1, 2])

    accepted = world.rescrape.request_rescrape(world.actor, MediaRef(tvdb_id=81189))

    assert (accepted.provider, accepted.provider_id) == (Provider.TVDB, "81189")
    assert [item for item, _state, _uid in _asked(world)] == [show]


def test_an_unknown_id_is_not_found_and_nothing_is_queued(world: World) -> None:
    """No row holds the id: 404 ``media.not_found``, no request."""
    with pytest.raises(AppNotFound) as refused:
        world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=1))

    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND
    assert _asked(world) == []


def test_holders_without_live_files_are_not_found(world: World) -> None:
    """Rows hold the id but none has a live file (a tombstone, a 0-file phantom): 404, no request."""
    gone = world.index.item("Gone", tmdb="7")
    world.index.movie_file(gone, "films/Gone", deleted=True)
    world.index.item("Gone", tmdb="7", year=2021)

    with pytest.raises(AppNotFound) as refused:
        world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=7))

    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND
    assert _asked(world) == []


def test_of_two_rows_only_the_one_with_live_files_is_rescraped(world: World) -> None:
    """A duplicate whose second row is a 0-file phantom rescrapes the row holding the files."""
    world.index.item("Friends", kind="show", tvdb="79168", year=1994)
    held = world.index.item("Friends [UNCUT]", kind="show", tvdb="79168", year=1994)
    world.index.episodes(held, 1, [1])

    accepted = world.rescrape.request_rescrape(world.actor, MediaRef(tvdb_id=79168))

    assert _asked(world) == [(held, RequestState.QUEUED, accepted.run_uid)]


def test_two_rows_with_live_files_are_both_queued(world: World) -> None:
    """Both rows hold files: one request each; the answer names the lowest row's request."""
    first = world.index.item("Friends", kind="show", tvdb="79168", year=1994)
    world.index.episodes(first, 1, [1], folder="series/Friends/Saison 01")
    second = world.index.item("Friends [UNCUT]", kind="show", tvdb="79168", year=1994)
    world.index.episodes(second, 1, [1], folder="series/Friends UNCUT/Saison 01")

    accepted = world.rescrape.request_rescrape(world.actor, MediaRef(tvdb_id=79168))

    asked = _asked(world)
    assert sorted(item for item, _state, _uid in asked) == sorted([first, second])
    assert accepted.run_uid == next(uid for item, _state, uid in asked if item == min(first, second))


def test_a_tmdb_id_held_by_a_film_and_a_show_rescrapes_the_film(world: World) -> None:
    """TMDB's movie and TV id spaces are distinct: a TMDB id names its movie holders first."""
    film = world.index.item("Film", tmdb="500")
    world.index.movie_file(film, "films/Film")
    show = world.index.item("Show", kind="show", tmdb="500")
    world.index.episodes(show, 1, [1])

    world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=500))

    assert [item for item, _state, _uid in _asked(world)] == [film]


def test_a_second_ask_joins_the_waiting_request(world: World) -> None:
    """The same medium asked twice: the second is answered by the first's request, nothing more is queued."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")

    first = world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=949))
    second = world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=949))

    assert second == first
    assert len(_asked(world)) == 1


def test_a_rescrape_already_running_is_joined_and_not_queued(world: World) -> None:
    """The row's rescrape already runs: the ask is accepted on that request, ``queued`` is false."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")
    waiting = world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=949))
    request = world.runs.request(waiting.run_uid)
    assert request is not None
    request.admit(_RUNNER_PID, 1_001.0)
    assert world.app_store.runs.save(request)

    accepted = world.rescrape.request_rescrape(world.actor, MediaRef(tmdb_id=949))

    assert accepted == RescrapeAccepted(
        provider=Provider.TMDB, provider_id="949", queued=False, run_uid=waiting.run_uid
    )
    assert len(_asked(world)) == 1


def test_the_per_medium_action_is_a_write_without_dry_run() -> None:
    """The action the service launches: a live write, one required integer item id."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]

    assert (action.risk, action.dry_run, action.category) == ("write", "unsupported", "analyze")
    assert [(o.name, o.type, o.required) for o in action.options] == [("item_id", "int", True)]


def test_the_per_medium_action_is_reserved_without_a_dry_run(world: World) -> None:
    """The reservation takes no 428 path for the per-medium action."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape-item"]

    maintenance_service._reserve_run_row(
        world.index.path,
        run_uid="a" * 32,
        action=action,
        command=action.id,
        options_json=canonical_options_json({"item_id": 1}),
        dry_run=False,
    )

    assert [run[1] for run in _runs(world.index.path)] == ["library-rescrape-item"]


def test_the_library_wide_rescrape_still_demands_a_dry_run(world: World) -> None:
    """The old ``library-rescrape`` is destructive: its live apply still needs a fresh dry-run (428)."""
    (action,) = [a for a in REGISTRY if a.id == "library-rescrape"]

    with pytest.raises(AppPreconditionRequired):
        maintenance_service._reserve_run_row(
            world.index.path,
            run_uid="b" * 32,
            action=action,
            command=action.id,
            options_json=canonical_options_json({"item-id": 1}),
            dry_run=False,
        )

    assert _runs(world.index.path) == []
